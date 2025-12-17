"""
Live client data helpers（面向对象）。
"""
import requests
import urllib3

from utils.logger import logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class LiveClientAPI:
    def __init__(self, summoner_api):
        self.summoner_api = summoner_api

    @staticmethod
    def _fetch_liveclient_json(path, timeout=2.5):
        url = f"https://127.0.0.1:2999{path}"
        try:
            response = requests.get(url, timeout=timeout, verify=False)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException:
            return None

    def _resolve_puuid(self, player):
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
                puuid = self.summoner_api.get_puuid(name)
                if puuid:
                    return puuid
            except Exception as exc:
                logger.debug(f"get_puuid failed for {name}: {exc}")
                continue
        return None

    def get_all_players_from_game(self):
        active_player = self._fetch_liveclient_json("/liveclientdata/activeplayer")
        player_list = self._fetch_liveclient_json("/liveclientdata/playerlist")

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

            puuid = self._resolve_puuid(player)

            entry = {
                "summonerName": display_name,
                "gameName": game_name or display_name,
                "tagLine": tag_line,
                "team": team,
                "puuid": puuid,
                "champion": player.get("championName") or player.get("rawChampionName"),
            }
            entries.append(entry)

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
