"""
游戏数据处理器模块
"""
from datetime import datetime
import constants


def process_lol_match_history(history, puuid=None):
    """
    处理 LOL 战绩数据，提取关键信息
    
    Args:
        history: LCU API返回的原始战绩数据
        puuid: 召唤师 PUUID
    
    Returns:
        list: 处理后的战绩列表
    """
    processed_games = []
    # 不再限制为前20场，因为分页已经在API层面处理
    games = history.get('games', {}).get('games', [])

    for idx, game in enumerate(games):
        summary = process_single_lol_game(game, puuid)
        summary['match_index'] = idx
        processed_games.append(summary)
    
    return processed_games


def process_single_lol_game(game, puuid=None):
    """
    从单个 LOL 游戏对象中提取摘要字段（用于卡片快速显示）
    
    Args:
        game: 单个游戏对象
        puuid: 召唤师 PUUID（用于匹配玩家数据）
    
    Returns:
        dict: 包含摘要字段的字典
    """
    if not isinstance(game, dict):
        return {}
    
    summary = {}
    
    # 获取参与者列表
    participants = game.get('participants', [])
    if not isinstance(participants, list):
        participants = []
    
    # 查找用户的参与者数据
    participant = None
    for p in participants:
        if not isinstance(p, dict):
            continue
        if puuid and p.get('puuid') == puuid:
            participant = p
            break
    
    # 如果没找到则用第一个（通常是查询用户）
    if participant is None and len(participants) > 0:
        participant = participants[0]
    
    # 提取胜负：从队伍信息中获取
    win = False
    if isinstance(participant, dict):
        # 先尝试从参与者直接获取
        participant_win = participant.get('win')
        if participant_win is not None:
            win = bool(participant_win)
        else:
            # 如果参与者没有 win 字段，从队伍信息中获取
            team_id = participant.get('teamId', 0)
            teams = game.get('teams', [])
            for team in teams:
                if team.get('teamId') == team_id:
                    team_win = team.get('win', 'Fail')
                    if isinstance(team_win, str):
                        win = team_win == 'Win'
                    else:
                        win = bool(team_win)
                    break
    summary['win'] = win
    
    # 提取英雄名称
    champion_id = 0
    champion_en = "Unknown"
    if isinstance(participant, dict):
        champion_id = participant.get('championId', 0)
        champion_en = constants._get_champion_map().get(champion_id, f"Champion{champion_id}")
    summary['champion_id'] = champion_id
    summary['champion_en'] = champion_en
    
    # 提取 KDA
    kda = "0/0/0"
    if isinstance(participant, dict):
        stats = participant.get('stats', {})
        if isinstance(stats, dict):
            kills = stats.get('kills', 0)
            deaths = stats.get('deaths', 0)
            assists = stats.get('assists', 0)
            kda = f"{kills}/{deaths}/{assists}"
    summary['kda'] = kda
    
    # 提取金币
    gold = 0
    if isinstance(participant, dict):
        stats = participant.get('stats', {})
        if isinstance(stats, dict):
            gold_earned = stats.get('goldEarned', 0)
            try:
                gold = int(gold_earned / 1000)  # 转换为 k 格式（千）
            except Exception:
                gold = 0
    summary['gold'] = gold
    
    # 提取 CS
    cs = 0
    if isinstance(participant, dict):
        stats = participant.get('stats', {})
        if isinstance(stats, dict):
            minions = stats.get('totalMinionsKilled', 0)
            neutral = stats.get('neutralMinionsKilled', 0)
            try:
                cs = int(minions) + int(neutral)
            except Exception:
                cs = 0
    summary['cs'] = cs
    
    # 提取英雄等级
    champion_level = 0
    if isinstance(participant, dict):
        stats = participant.get('stats', {})
        if isinstance(stats, dict):
            champion_level = stats.get('champLevel', 0)
    summary['champion_level'] = champion_level
    
    # 游戏模式
    game_mode = game.get('gameMode', 'CLASSIC')
    summary['gameMode'] = game_mode
    summary['mode'] = format_game_mode(game_mode)
    
    # CHERRY 模式的排名信息
    if game_mode == 'CHERRY' and isinstance(participant, dict):
        stats = participant.get('stats', {})
        if isinstance(stats, dict):
            # 尝试多个可能的字段名
            placement = (
                stats.get('subteamPlacement') or 
                stats.get('placement') or 
                participant.get('subteamPlacement') or 
                participant.get('placement') or 
                0
            )
            if placement:
                summary['placement'] = int(placement)
                summary['subteamPlacement'] = int(placement)
    
    # 时间差（使用 gameCreation）
    game_creation = game.get('gameCreation', 0)
    summary['time_ago'] = calculate_time_ago(game_creation)
    summary['game_creation'] = game_creation
    
    # 对局时长（秒）
    game_length = game.get('gameDuration', 0)
    summary['duration'] = int(game_length) if game_length else 0
    
    # Match ID
    match_id = game.get('matchId', '')
    summary['match_id'] = match_id
    
    return summary


def format_game_mode(mode):
    """格式化游戏模式名称"""
    mode_map = {
        'CLASSIC': '经典模式',
        'ARAM': '极地大乱斗',
        'KIWI': '海克斯大乱斗',
        'CHERRY': '斗魂竞技场',
        'URF': '无限火力',
        'ONEFORALL': '克隆模式',
        'NEXUSBLITZ': '激斗峡谷',
        'TUTORIAL': '教程',
        'PRACTICETOOL': '训练模式'
    }
    return mode_map.get(mode, mode)


def calculate_time_ago(timestamp_ms):
    """计算时间差"""
    if not timestamp_ms:
        return '未知时间'
    
    game_time = datetime.fromtimestamp(timestamp_ms / 1000)
    now = datetime.now()
    diff = now - game_time
    
    if diff.days > 0:
        return f"{diff.days}天前"
    elif diff.seconds >= 3600:
        hours = diff.seconds // 3600
        return f"{hours}小时前"
    elif diff.seconds >= 60:
        minutes = diff.seconds // 60
        return f"{minutes}分钟前"
    else:
        return "刚刚"
