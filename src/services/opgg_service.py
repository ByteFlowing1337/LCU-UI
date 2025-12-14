"""External champion stats + Data Dragon metadata integration service.

This module currently returns placeholder champion performance statistics
while enriching them with official champion metadata fetched from Riot's
public Data Dragon (versions + champion.json). This avoids brittle scraping
solutions (e.g. parsing OP.GG HTML) while still providing useful context.

Key exported function:
    fetch_champion_stats(champion_key: str, region: str = 'global') -> dict | None

Returned dict (example):
{
    'champion': 'Aatrox',          # normalized key requested
    'region': 'global',            # passthrough region label
    'win_rate': 51.23,             # placeholder performance stats
    'pick_rate': 6.54,
    'ban_rate': 8.11,
    'tier': 'A',
    'source': 'placeholder',       # performance stats source
    'cached': False,               # full entry served from performance cache?
    'age_seconds': 0,              # performance cache age
    'dd_source': 'DataDragon',     # metadata source identifier
    'dd_version': '15.1.1',        # latest version used (example)
    'name': 'Aatrox',              # localized English name from champion.json
    'title': 'the Darkin Blade',   # champion title
    'tags': ['Fighter', 'Tank'],   # gameplay tags
    'partype': 'Blood Well'        # resource type
}

If Data Dragon fetch fails, metadata fields are omitted (graceful degradation).
"""
from __future__ import annotations
import time
import threading
from typing import Dict, Tuple, Optional
import requests

# --------------------------
# Cache structures
# --------------------------

# Simple in-memory TTL cache
_CACHE: Dict[Tuple[str, str], dict] = {}
_CACHE_TIMESTAMPS: Dict[Tuple[str, str], float] = {}
_CACHE_LOCK = threading.Lock()

# Champion metadata cache (ddragon) – keyed by champion key
_META_CACHE: Dict[str, dict] = {}
_META_VERSION: Optional[str] = None
_META_LOCK = threading.Lock()

# Default TTL (seconds)
TTL_SECONDS = 1800  # 30 minutes

# Placeholder base stats (could be expanded)
_PLACEHOLDER_BASE = {
    'win_rate': 50.0,
    'pick_rate': 5.0,
    'ban_rate': 5.0,
    'tier': 'B',
    'source': 'placeholder'
}

# Data Dragon endpoints
_DDRAGON_VERSIONS_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
_DDRAGON_CHAMPION_JSON_TMPL = "https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"

# Network config
_HTTP_TIMEOUT = 4  # seconds
_RETRY_COUNT = 1


def _normalize_key(champion_key: str) -> str:
    if not champion_key:
        return ''
    return champion_key.strip().replace(' ', '').replace("'", '').replace('.', '').capitalize()


def _http_get(url: str) -> Optional[requests.Response]:
    """Lightweight wrapper with timeout + single retry.

    Returns None on failure.
    """
    for attempt in range(_RETRY_COUNT + 1):
        try:
            resp = requests.get(url, timeout=_HTTP_TIMEOUT)
            if resp.status_code == 200:
                return resp
        except Exception:
            pass
        # brief backoff (no sleep for simplicity – keeps request fast)
    return None


def _get_latest_version() -> Optional[str]:
    """Fetch or reuse cached latest Data Dragon version string."""
    global _META_VERSION
    with _META_LOCK:
        if _META_VERSION:
            return _META_VERSION
    resp = _http_get(_DDRAGON_VERSIONS_URL)
    if not resp:
        return None
    try:
        versions = resp.json()
        if isinstance(versions, list) and versions:
            latest = versions[0]
            with _META_LOCK:
                _META_VERSION = latest
            return latest
    except Exception:
        return None
    return None


def _load_champion_metadata(version: str) -> Optional[dict]:
    url = _DDRAGON_CHAMPION_JSON_TMPL.format(version=version)
    resp = _http_get(url)
    if not resp:
        return None
    try:
        data = resp.json()
        if isinstance(data, dict):
            return data.get('data') or {}
    except Exception:
        return None
    return None


def _ensure_metadata_loaded() -> Optional[str]:
    """Ensure champion metadata for latest version is in cache; return version."""
    global _META_VERSION
    # Quick check without lock for performance
    if _META_CACHE and _META_VERSION:
        return _META_VERSION
    version = _get_latest_version()
    if not version:
        return None
    with _META_LOCK:
        if _META_CACHE and _META_VERSION == version:
            return version
        meta = _load_champion_metadata(version)
        if not meta:
            return None
        _META_CACHE.clear()
        for k, v in meta.items():
            if isinstance(v, dict):
                _META_CACHE[k] = v
        _META_VERSION = version
    return version


def _get_champion_meta(champion_key: str) -> Optional[dict]:
    """Return metadata dict for champion key (case-normalized) or None."""
    version = _ensure_metadata_loaded()
    if not version:
        return None
    ck = _normalize_key(champion_key)
    # Data Dragon keys sometimes vary in case; attempt direct + case-insensitive match
    meta = _META_CACHE.get(ck)
    if meta:
        return {**meta, 'version': version}
    # fallback: iterate (small cost, executed rarely)
    lowered = ck.lower()
    for k, v in _META_CACHE.items():
        if k.lower() == lowered:
            return {**v, 'version': version}
    return None


def fetch_champion_stats(champion_key: str, region: str = 'global') -> dict | None:
    """Return champion performance stats (placeholder) + Data Dragon metadata.

    Performance portion is cached with TTL. Metadata is cached separately and
    reused until Data Dragon publishes a new version (auto-detected lazily).
    """
    ck = _normalize_key(champion_key)
    if not ck:
        return None

    cache_key = (ck, region)
    now = time.time()

    # Try performance cache first
    with _CACHE_LOCK:
        ts = _CACHE_TIMESTAMPS.get(cache_key)
        if ts and (now - ts) < TTL_SECONDS:
            cached_entry = _CACHE.get(cache_key)
            if cached_entry:
                entry = dict(cached_entry)
                entry['cached'] = True
                entry['age_seconds'] = int(now - ts)
                # enrich with metadata (non-cached inside this structure)
                meta = _get_champion_meta(ck)
                if meta:
                    entry.update({
                        'dd_source': 'DataDragon',
                        'dd_version': meta.get('version'),
                        'name': meta.get('name'),
                        'title': meta.get('title'),
                        'tags': meta.get('tags'),
                        'partype': meta.get('partype'),
                    })
                return entry

    # Build new placeholder performance entry
    h = abs(hash(ck)) % 1000
    variation = (h / 1000.0)  # 0..0.999
    win_rate = round(48.5 + variation * 4.0, 2)  # ~48.5 - 52.5
    pick_rate = round(3.0 + variation * 7.0, 2)  # ~3.0 - 10.0
    ban_rate = round(2.0 + variation * 10.0, 2)  # ~2.0 - 12.0
    tier_index = int(variation * 5)  # 0..4
    tier_map = ['B', 'B+', 'A', 'A+', 'S']
    tier = tier_map[tier_index]

    entry = {
        'champion': ck,
        'region': region,
        'win_rate': win_rate,
        'pick_rate': pick_rate,
        'ban_rate': ban_rate,
        'tier': tier,
        'source': 'placeholder',
        'cached': False,
        'age_seconds': 0,
    }

    # Persist performance portion in cache
    with _CACHE_LOCK:
        _CACHE[cache_key] = dict(entry)  # store base without metadata
        _CACHE_TIMESTAMPS[cache_key] = now

    # Enrich with metadata (no lock needed beyond internal metadata functions)
    meta = _get_champion_meta(ck)
    if meta:
        entry.update({
            'dd_source': 'DataDragon',
            'dd_version': meta.get('version'),
            'name': meta.get('name'),
            'title': meta.get('title'),
            'tags': meta.get('tags'),
            'partype': meta.get('partype'),
        })
    return entry


def purge_cache():
    """Manually clear performance + metadata caches (for tests/admin)."""
    with _CACHE_LOCK:
        _CACHE.clear()
        _CACHE_TIMESTAMPS.clear()
    with _META_LOCK:
        _META_CACHE.clear()
        # Keep _META_VERSION so we don't refetch versions list unless needed

__all__ = [
    'fetch_champion_stats',
    'purge_cache',
    'TTL_SECONDS'
]
