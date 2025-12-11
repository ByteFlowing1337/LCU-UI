"""
游戏流程相关 API
处理游戏阶段、准备检查、选人等功能
"""
from utils.logger import logger
from .client import make_request


def get_gameflow_phase(token, port):
    """
    获取当前游戏流程阶段。
    
    可能的阶段值:
    - 'None': 无
    - 'Lobby': 房间中
    - 'Matchmaking': 匹配中
    - 'ReadyCheck': 准备检查
    - 'ChampSelect': 选人阶段
    - 'InProgress': 游戏中
    - 'EndOfGame': 游戏结束
    
    Args:
        token: LCU认证令牌
        port: LCU端口
    
    Returns:
        str: 游戏阶段字符串
    """
    return make_request("GET", "/lol-gameflow/v1/gameflow-phase", token, port)


def accept_ready_check(token, port):
    """
    接受排队准备检查。
    
    Args:
        token: LCU认证令牌
        port: LCU端口
    
    Returns:
        dict: 响应数据
    """
    return make_request("POST", "/lol-matchmaking/v1/ready-check/accept", token, port)


def get_champ_select_session(token, port):
    """
    获取选人会话数据。
    
    返回的数据包含:
    - myTeam: 己方队伍信息
    - theirTeam: 敌方队伍信息（如果可见）
    - timer: 选人计时器
    - actions: 选人/禁用动作列表
    
    Args:
        token: LCU认证令牌
        port: LCU端口
    
    Returns:
        dict: 选人会话数据，失败返回None
    """
    return make_request("GET", "/lol-champ-select/v1/session", token, port)


def get_champ_select_enemies(token, port):
    """
    【备用方案】从选人会话中获取敌方玩家信息。
    仅在选人阶段可用，游戏开始后此API无法使用。
    
    Args:
        token: LCU认证令牌
        port: LCU端口
    
    Returns:
        list: 敌方玩家列表
    """
    session = get_champ_select_session(token, port)
    if not session:
        logger.warning("❌ 无法获取选人会话（可能不在选人阶段）")
        return []
    
    try:
        # 获取己方队伍ID
        my_team = session.get('myTeam', [])
        if not my_team:
            return []
        
        my_team_ids = {player['summonerId'] for player in my_team}
        
        # 获取所有队伍成员
        all_players = session.get('myTeam', []) + session.get('theirTeam', [])
        
        # 筛选出敌方玩家
        enemy_players = [
            player for player in all_players 
            if player.get('summonerId') not in my_team_ids
        ]
        
        logger.info(f"选人阶段找到 {len(enemy_players)} 名敌方玩家")
        return enemy_players
        
    except Exception as e:
        logger.error(f"解析选人会话失败: {e}")
        return []
