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
    autodetect_credentials,
    is_league_client_running,
    get_latest_log_file,
    extract_params_from_log,
    detect_file_encoding
)

# HTTP 客户端
from .client import make_request

# 游戏流程
from .game_flow import (
    get_gameflow_phase,
    accept_ready_check,
    get_champ_select_session,
    get_champ_select_enemies
)

# 召唤师信息
from .summoner import (
    get_current_summoner,
    get_puuid,
    get_summoner_by_id,
    get_summoner_by_puuid,
    get_summoner_by_name,
    get_ranked_stats
)

# 战绩查询
from .match_history import (
    get_match_history,
    get_tft_match_history,
    get_match_by_id
)

# 游戏内实时数据（live_game 模块已删除）

# 数据增强
from .enrichment import enrich_game_with_summoner_info, enrich_tft_game_with_summoner_info

__all__ = [
    # 凭证检测
    'autodetect_credentials',
    'is_league_client_running',
    'get_latest_log_file',
    'extract_params_from_log',
    'detect_file_encoding',
    
    # HTTP 客户端
    'make_request',
    
    # 游戏流程
    'get_gameflow_phase',
    'accept_ready_check',
    'get_champ_select_session',
    'get_champ_select_enemies',
    
    # 召唤师信息
    'get_current_summoner',
    'get_puuid',
    'get_summoner_by_id',
    'get_summoner_by_puuid',
    'get_summoner_by_name',
    'get_ranked_stats',
    
    # 战绩查询
    'get_match_history',
    'get_tft_match_history',
    'get_match_by_id',
    
    # 游戏内实时数据（已删除）
    
    # 数据增强
    'enrich_game_with_summoner_info',
    'enrich_tft_game_with_summoner_info',
]
