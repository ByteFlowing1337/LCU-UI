"""
Live client data helpers.
Fetches active player info and splits player list into teammates/enemies
using the local live client data API (port 2999).
"""
import requests
import urllib3

from utils.logger import logger
from .summoner import get_puuid

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _fetch_liveclient_json(path, timeout=2.5):
    """Call the live client data endpoint and return JSON or None on error."""
    url = f"https://127.0.0.1:2999{path}"
    try:
        response = requests.get(url, timeout=timeout, verify=False)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        # Keep logs quiet during normal polling; failures usually mean no active game.
        return None


def _resolve_puuid(token, port, player):
    """Best-effort PUUID lookup using available names from liveclient payload."""
    candidates = []
    riot_id = player.get("riotId")
    game_name = player.get("riotIdGameName") or player.get("gameName")
    tag_line = player.get("riotIdTagLine") or ""
    summoner_name = player.get("summonerName")

    if riot_id:
        candidates.append(riot_id)
    if game_name and tag_line:
        candidates.append(f"{game_name}#{tag_line}")
    if summoner_name:
        candidates.append(summoner_name)

    for name in candidates:
        try:
            puuid = get_puuid(token, port, name)
            if puuid:
                return puuid
        except Exception as exc:  # Defensive: avoid breaking loop
            logger.debug(f"get_puuid failed for {name}: {exc}")
            continue
    return None


def get_all_players_from_game(token, port):
    """
    Return teammates and enemies from the live client data API.

    Uses /liveclientdata/activeplayer and /liveclientdata/playerlist on port 2999
    to identify the current team (ORDER/CHAOS) and split players accordingly.
    Each player entry includes basic identity fields plus a best-effort PUUID
    so downstream ranking lookups can proceed.
    """
    active_player = _fetch_liveclient_json("/liveclientdata/activeplayer")
    player_list = _fetch_liveclient_json("/liveclientdata/playerlist")

    if not player_list:
        return None

    active_team = (active_player or {}).get("team")
    active_name = (active_player or {}).get("summonerName")

    entries = []
    for player in player_list:
        if not isinstance(player, dict):
            continue

        team = player.get("team")
        game_name = player.get("riotIdGameName") or player.get("gameName") or player.get("riotId")
        tag_line = player.get("riotIdTagLine") or ""
        display_name = player.get("summonerName") or game_name or "Unknown"

        puuid = _resolve_puuid(token, port, player)

        entry = {
            "summonerName": display_name,
            "gameName": game_name or display_name,
            "tagLine": tag_line,
            "team": team,
            "puuid": puuid,
            "champion": player.get("championName") or player.get("rawChampionName"),
        }
        entries.append(entry)

        # Infer active team if not provided but names match.
        if not active_team and active_name:
            if display_name == active_name or player.get("summonerName") == active_name:
                active_team = team

    if active_team:
        teammates = [p for p in entries if p.get("team") == active_team]
        enemies = [p for p in entries if p.get("team") not in (None, active_team)]
    else:
        teammates = [p for p in entries if p.get("team") == "ORDER"]
        enemies = [p for p in entries if p.get("team") == "CHAOS"]
        if not teammates and not enemies:
            return None

    return {
        "teammates": teammates,
        "enemies": enemies,
        "activeTeam": active_team,
        "activePlayer": active_player,
        "rawPlayers": entries,
    }
