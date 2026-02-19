"""
召唤师信息 API（面向对象）
依赖共享的 LCUClient，内部维护独立缓存。
"""
import re
import time
from utils.logger import logger


PUUID_CACHE_TTL = 600
MAX_PUUID_CACHE_SIZE = 200
BIDI_CONTROL_PATTERN = re.compile(r'[\u200e\u200f\u202a-\u202e\u2066-\u2069]')


class SummonerAPI:
    def __init__(self, client):
        self.client = client
        self._puuid_cache = {}

    @staticmethod
    def _sanitize_summoner_name(name):
        if not isinstance(name, str):
            return name
        cleaned = re.sub(BIDI_CONTROL_PATTERN, '', name)
        return cleaned.strip()

    def _clean_puuid_cache(self):
        """清理过期和过量缓存。"""
        current_time = time.time()
        expired_keys = [k for k, (t, _) in self._puuid_cache.items() if current_time - t > PUUID_CACHE_TTL]
        for k in expired_keys:
            self._puuid_cache.pop(k, None)

        if len(self._puuid_cache) > MAX_PUUID_CACHE_SIZE:
            sorted_items = sorted(self._puuid_cache.items(), key=lambda x: x[1][0])
            for k, _ in sorted_items[:len(self._puuid_cache) - MAX_PUUID_CACHE_SIZE]:
                self._puuid_cache.pop(k, None)

    def get_current_summoner(self):
        return self.client.request("GET", "/lol-summoner/v1/current-summoner")

    def get_puuid(self, summoner_name):
        """通过召唤师名字获取 PUUID，带缓存。"""
        self._clean_puuid_cache()

        cleaned_name = self._sanitize_summoner_name(summoner_name)
        if not cleaned_name:
            return None

        if cleaned_name in self._puuid_cache:
            cached_time, cached_puuid = self._puuid_cache[cleaned_name]
            if time.time() - cached_time < PUUID_CACHE_TTL:
                logger.debug(f"✅ 使用PUUID缓存 ({cleaned_name})")
                return cached_puuid

        endpoint = "/lol-summoner/v1/summoners"

        data = self.client.request(
            "GET",
            endpoint,
            params={'name': cleaned_name}
        )

        if data:
            puuid = data.get('puuid')
            if puuid:
                self._puuid_cache[cleaned_name] = (time.time(), puuid)
                logger.debug(f"✅ 查询PUUID成功 ({cleaned_name})")
            return puuid
        return None

    def get_summoner_by_id(self, summoner_id):
        endpoint = f"/lol-summoner/v1/summoners/{summoner_id}"
        return self.client.request("GET", endpoint)

    def get_summoner_by_puuid(self, puuid):
        endpoint = f"/lol-summoner/v1/summoners/by-puuid/{puuid}"
        return self.client.request("GET", endpoint)

    def get_summoner_by_name(self, name):
        endpoint = "/lol-summoner/v1/summoners"
        cleaned_name = self._sanitize_summoner_name(name)
        if not cleaned_name:
            return None
        return self.client.request("GET", endpoint, params={'name': cleaned_name})

    @staticmethod
    def _normalize_ranked_payload(payload, endpoint_tag):
        if not payload:
            return None

        if isinstance(payload, dict) and isinstance(payload.get('queues'), list) and payload['queues']:
            normalized = dict(payload)
            normalized['dataSource'] = endpoint_tag
            return normalized

        queues = []
        normalized_payload = None

        if isinstance(payload, dict):
            normalized_payload = dict(payload)

            queue_map = normalized_payload.get('queueMap')
            if isinstance(queue_map, dict):
                queues.extend([v for v in queue_map.values() if isinstance(v, dict)])

            queue_summaries = normalized_payload.get('queueSummaries')
            if isinstance(queue_summaries, list):
                queues.extend([q for q in queue_summaries if isinstance(q, dict)])

            entries = normalized_payload.get('entries')
            if isinstance(entries, list):
                queues.extend([q for q in entries if isinstance(q, dict)])

            if queues:
                normalized_payload['queues'] = queues
                normalized_payload['dataSource'] = endpoint_tag
                return normalized_payload

        elif isinstance(payload, list):
            queues = [q for q in payload if isinstance(q, dict)]
            if queues:
                return {
                    'queues': queues,
                    'dataSource': endpoint_tag,
                    'raw': payload
                }

        return None

    def get_ranked_stats(self, summoner_id=None, puuid=None):
        """获取召唤师排位信息（支持按 PUUID 或 summonerId 查询）。"""
        endpoints = []

        if puuid:
            endpoints.append((f"/lol-ranked/v1/ranked-stats/{puuid}", "lol-ranked/v1/ranked-stats/puuid"))
            endpoints.append((f"/lol-ranked/v1/ranked-stats/by-puuid/{puuid}", "lol-ranked/v1/ranked-stats/by-puuid-legacy"))

        if summoner_id:
            endpoints.extend([
                (f"/lol-ranked/v1/ranked-stats/{summoner_id}", "lol-ranked/v1/ranked-stats/by-id"),
                (f"/lol-ranked/v2/summoner/{summoner_id}", "lol-ranked/v2/summoner"),
                (f"/lol-league/v1/entries/by-summoner/{summoner_id}", "lol-league/v1/entries/by-summoner"),
                (f"/lol-league/v1/positions/by-summoner/{summoner_id}", "lol-league/v1/positions/by-summoner"),
            ])

        if not endpoints:
            return {}

        for endpoint, tag in endpoints:
            payload = self.client.request("GET", endpoint)
            normalized = self._normalize_ranked_payload(payload, tag)
            if normalized:
                if 'raw' not in normalized:
                    normalized['raw'] = payload
                return normalized

        return {}

