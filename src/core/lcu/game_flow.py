"""
游戏流程相关 API（面向对象）
"""
from utils.logger import logger


class GameFlowAPI:
    def __init__(self, client):
        self.client = client

    def get_gameflow_phase(self):
        return self.client.request("GET", "/lol-gameflow/v1/gameflow-phase")

    def accept_ready_check(self):
        return self.client.request("POST", "/lol-matchmaking/v1/ready-check/accept")

    def get_champ_select_session(self):
        return self.client.request("GET", "/lol-champ-select/v1/session")

    def get_champ_select_enemies(self):
        session = self.get_champ_select_session()
        if not session:
            logger.warning("❌ 无法获取选人会话（可能不在选人阶段）")
            return []

        try:
            my_team = session.get('myTeam', [])
            if not my_team:
                return []

            my_team_ids = {player['summonerId'] for player in my_team}
            all_players = session.get('myTeam', []) + session.get('theirTeam', [])

            enemy_players = [
                player for player in all_players
                if player.get('summonerId') not in my_team_ids
            ]

            logger.info(f"选人阶段找到 {len(enemy_players)} 名敌方玩家")
            return enemy_players

        except Exception as e:
            logger.error(f"解析选人会话失败: {e}")
            return []
