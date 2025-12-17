"""
LCU API 模块
League of Legends Client Update API 客户端封装

提供与英雄联盟客户端交互的完整功能:
- 凭证自动检测
- 游戏流程控制
- 召唤师信息查询
- 战绩历史记录
- 游戏内实时数据
- 数据增强功能

使用示例:
    from core.lcu import autodetect_credentials, get_current_summoner
    
    # 自动检测LCU凭证
    token, port = autodetect_credentials(status_bar)
    
    # 获取当前召唤师信息
    summoner = get_current_summoner(token, port)
"""

# 凭证检测
from .credentials import (
    extract_params_from_process,
    autodetect_credentials,
    is_league_client_running,

)

from .client import LCUClient
from .summoner import SummonerAPI
from .game_flow import GameFlowAPI
from .match_history import MatchHistoryAPI
from .live_client import LiveClientAPI
from .enrichment import EnrichmentService, enrich_game_with_augments


class LCU:
    """聚合型 LCU 入口，内部复用单一 LCUClient。"""

    def __init__(self, token, port):
        self.client = LCUClient(token, port)
        self.summoner = SummonerAPI(self.client)
        self.game_flow = GameFlowAPI(self.client)
        self.match_history = MatchHistoryAPI(self.client)
        self.enrichment = EnrichmentService(self.summoner)
        self.live_client = LiveClientAPI(self.summoner)

    # 召唤师信息
    def get_current_summoner(self):
        return self.summoner.get_current_summoner()

    def get_puuid(self, summoner_name):
        return self.summoner.get_puuid(summoner_name)

    def get_summoner_by_id(self, summoner_id):
        return self.summoner.get_summoner_by_id(summoner_id)

    def get_summoner_by_puuid(self, puuid):
        return self.summoner.get_summoner_by_puuid(puuid)

    def get_summoner_by_name(self, name):
        return self.summoner.get_summoner_by_name(name)

    def get_ranked_stats(self, summoner_id=None, puuid=None):
        return self.summoner.get_ranked_stats(summoner_id=summoner_id, puuid=puuid)

    # 游戏流程
    def get_gameflow_phase(self):
        return self.game_flow.get_gameflow_phase()

    def accept_ready_check(self):
        return self.game_flow.accept_ready_check()

    def get_champ_select_session(self):
        return self.game_flow.get_champ_select_session()

    def get_champ_select_enemies(self):
        return self.game_flow.get_champ_select_enemies()

    # 战绩查询
    def get_match_history(self, puuid, count=20, begin_index=0):
        return self.match_history.get_match_history(puuid, count=count, begin_index=begin_index)

    def get_tft_match_history(self, puuid, count=20):
        return self.match_history.get_tft_match_history(puuid, count=count)

    def get_match_by_id(self, match_id):
        return self.match_history.get_match_by_id(match_id)

    # 实时对局
    def get_all_players_from_game(self):
        return self.live_client.get_all_players_from_game()

    # 数据增强
    def enrich_game_with_summoner_info(self, game):
        return self.enrichment.enrich_game_with_summoner_info(game)

    def enrich_tft_game_with_summoner_info(self, game):
        return self.enrichment.enrich_tft_game_with_summoner_info(game)


_active_client = None


def get_client(token, port):
    """获取全局唯一 LCU 实例；token/port 变化时自动重建。"""
    global _active_client
    if _active_client is None or _active_client.client.token != token or _active_client.client.port != port:
        _active_client = LCU(token, port)
    return _active_client


__all__ = [
    'LCU',
    'get_client',
    # 凭证检测
    'autodetect_credentials',
    'extract_params_from_process',
    'is_league_client_running',
    # 共享服务
    'enrich_game_with_augments',
]
