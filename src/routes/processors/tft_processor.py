"""
TFT 游戏数据处理器模块
"""
from .lol_processor import format_game_mode, calculate_time_ago


def process_single_tft_game(game, puuid=None):
    """
    从单个 TFT 游戏对象中提取摘要字段（用于卡片快速显示）
    不修改原始游戏数据，只添加快速显示需要的摘要字段
    
    Args:
        game: 单个游戏对象
        puuid: 召唤师 PUUID（用于匹配玩家数据）
    
    Returns:
        dict: 包含摘要字段的字典，这些字段会合并到原始游戏对象中
    """
    if not isinstance(game, dict):
        return {}
    
    # TFT 数据在 json 字段中
    game_json = game.get('json')
    if not isinstance(game_json, dict):
        game_json = game
    
    metadata = game.get('metadata', {})
    
    # 定位玩家数据（用户的数据）
    participant = None
    participants_data = game_json.get('participants') if isinstance(game_json, dict) else None
    participants_list = participants_data if isinstance(participants_data, list) else []
    
    # 从 participants 中找到用户的数据
    if isinstance(participants_list, list) and len(participants_list) > 0:
        if puuid:
            for p in participants_list:
                if not isinstance(p, dict):
                    continue
                if p.get('puuid') == puuid:
                    participant = p
                    break
        
        # 如果没找到则用第一个（通常是查询用户）
        if participant is None:
            participant = participants_list[0] if len(participants_list) > 0 else None
    
    # 提取摘要字段
    summary = {}
    
    # 胜负标志（placement == 1 为赢）
    win_flag = False
    if isinstance(participant, dict):
        placement = participant.get('placement')
        if placement is not None:
            try:
                win_flag = int(placement) == 1
            except Exception:
                pass
    summary['win'] = win_flag
    
    # 排名
    placement = 8  # 默认值
    if isinstance(participant, dict):
        p = participant.get('placement')
        if p is not None:
            try:
                placement = int(p)
            except Exception:
                pass
    summary['placement'] = placement
    
    # 最后一轮
    last_round = 0
    if isinstance(participant, dict):
        lr = participant.get('last_round')
        if lr is not None:
            try:
                last_round = int(lr)
            except Exception:
                pass
    summary['last_round'] = last_round
    
    # 玩家等级
    level = 0
    if isinstance(participant, dict):
        lv = participant.get('level')
        if lv is not None:
            try:
                level = int(lv)
            except Exception:
                pass
    summary['level'] = level
    
    # 总伤害
    total_damage = 0
    if isinstance(participant, dict):
        dmg = participant.get('total_damage_to_players')
        if dmg is not None:
            try:
                total_damage = int(dmg)
            except Exception:
                pass
    summary['total_damage'] = total_damage
    
    # 剩余金币
    gold_left = 0
    if isinstance(participant, dict):
        gold = participant.get('gold_left')
        if gold is not None:
            try:
                gold_left = int(gold)
            except Exception:
                pass
    summary['gold_left'] = gold_left
    
    # 提取最高 Style 的 Traits（Style >= 2）
    top_traits = []
    if isinstance(participant, dict):
        traits = participant.get('traits', [])
        if isinstance(traits, list):
            # 过滤 style >= 2 的 traits
            high_style_traits = [t for t in traits if isinstance(t, dict) and t.get('style', 0) >= 2]
            # 按 style 降序排序
            high_style_traits.sort(key=lambda t: t.get('style', 0), reverse=True)
            # 取前 3 个
            for trait in high_style_traits[:3]:
                if isinstance(trait, dict):
                    name = trait.get('name', 'Unknown')
                    num_units = trait.get('num_units', 0)
                    style = trait.get('style', 0)
                    top_traits.append({
                        'name': name,
                        'num_units': num_units,
                        'style': style
                    })
    summary['top_traits'] = top_traits
    
    # 游戏模式
    game_mode = (game_json.get('gameMode') or game_json.get('tft_game_type') or 'UNKNOWN') if isinstance(game_json, dict) else 'UNKNOWN'
    summary['gameMode'] = game_mode
    summary['mode'] = format_game_mode(game_mode)
    
    # 时间差（使用 gameCreation）
    game_creation = (game_json.get('gameCreation', 0) if isinstance(game_json, dict) else 0)
    summary['time_ago'] = calculate_time_ago(game_creation)
    summary['game_creation'] = game_creation
    
    # 对局时长
    game_length = (game_json.get('game_length', 0) if isinstance(game_json, dict) else 0)
    summary['duration'] = int(game_length) if game_length else 0
    
    # Match ID
    match_id = metadata.get('match_id') if isinstance(metadata, dict) else None
    summary['match_id'] = match_id
    
    return summary
