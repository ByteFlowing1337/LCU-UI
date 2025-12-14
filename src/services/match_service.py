"""Match processing helpers extracted from routes/api_routes.py

This module contains functions to produce summary objects for LOL/TFT
matches and to process match history. Kept intentionally lightweight so
routes can stay thin and focused on HTTP concerns.
"""
from datetime import datetime
import constants
from core import lcu
from core.lcu.enrichment import enrich_game_with_augments, enrich_tft_game_with_summoner_info



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
    """计算时间差，返回中文友好字符串"""
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


def process_single_tft_game(game, puuid=None):
    """从单个 TFT 游戏对象中提取摘要字段（用于卡片快速显示）

    Returns a dict of summary fields and does not mutate the input.
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

    if isinstance(participants_list, list) and len(participants_list) > 0:
        if puuid:
            for p in participants_list:
                if not isinstance(p, dict):
                    continue
                if p.get('puuid') == puuid:
                    participant = p
                    break

        if participant is None:
            participant = participants_list[0] if len(participants_list) > 0 else None

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
    placement = 8
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
            high_style_traits = [t for t in traits if isinstance(t, dict) and t.get('style', 0) >= 2]
            high_style_traits.sort(key=lambda t: t.get('style', 0), reverse=True)
            for trait in high_style_traits[:3]:
                if isinstance(trait, dict):
                    name = trait.get('name', 'Unknown')
                    num_units = trait.get('num_units', 0)
                    style = trait.get('style', 0)
                    top_traits.append({'name': name, 'num_units': num_units, 'style': style})
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


def process_lol_match_history(history, puuid=None):
    processed_games = []
    games = history.get('games', {}).get('games', [])
    for idx, game in enumerate(games):
        summary = process_single_lol_game(game, puuid)
        summary['match_index'] = idx
        processed_games.append(summary)
    return processed_games


def process_single_lol_game(game, puuid=None):
    if not isinstance(game, dict):
        return {}

    summary = {}
    participants = game.get('participants', [])
    if not isinstance(participants, list):
        participants = []

    participant = None
    for p in participants:
        if not isinstance(p, dict):
            continue
        if puuid and p.get('puuid') == puuid:
            participant = p
            break

    if participant is None and len(participants) > 0:
        participant = participants[0]

    # 提取胜负
    win = False
    if isinstance(participant, dict):
        participant_win = participant.get('win')
        if participant_win is not None:
            win = bool(participant_win)
        else:
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

    # 英雄名称
    champion_id = 0
    champion_en = "Unknown"
    if isinstance(participant, dict):
        champion_id = participant.get('championId', 0)
        champion_en = constants._get_champion_map().get(champion_id, f"Champion{champion_id}")
    summary['champion_id'] = champion_id
    summary['champion_en'] = champion_en

    # KDA
    kda = "0/0/0"
    if isinstance(participant, dict):
        stats = participant.get('stats', {})
        if isinstance(stats, dict):
            kills = stats.get('kills', 0)
            deaths = stats.get('deaths', 0)
            assists = stats.get('assists', 0)
            kda = f"{kills}/{deaths}/{assists}"
    summary['kda'] = kda

    # 金币
    gold = 0
    if isinstance(participant, dict):
        stats = participant.get('stats', {})
        if isinstance(stats, dict):
            gold_earned = stats.get('goldEarned', 0)
            try:
                gold = int(gold_earned / 1000)
            except Exception:
                gold = 0
    summary['gold'] = gold

    # CS
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

    # 英雄等级
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

    # CHERRY 模式排名
    if game_mode == 'CHERRY' and isinstance(participant, dict):
        stats = participant.get('stats', {})
        if isinstance(stats, dict):
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

    # 时间差与时长
    game_creation = game.get('gameCreation', 0)
    summary['time_ago'] = calculate_time_ago(game_creation)
    summary['game_creation'] = game_creation

    game_length = game.get('gameDuration', 0)
    summary['duration'] = int(game_length) if game_length else 0

    match_id = game.get('matchId', '')
    summary['match_id'] = match_id

    return summary


def process_match_history(history, puuid=None):
    processed_games = []
    games = history.get('games', {}).get('games', [])[:20]
    for idx, game in enumerate(games):
        summary = process_single_tft_game(game, puuid)
        summary['match_index'] = idx
        processed_games.append(summary)
    return processed_games


def get_match_detail(token, port, summoner_name, index, match_id=None, is_tft=False):
    """
    获取完整对局详情 (LOL 或 TFT)
    
    Returns:
        dict: 对局数据
    Raises:
        ValueError: 参数错误
        RuntimeError: LCU 连接或查询失败
    """
    # 如果有 match_id，直接通过 match_id 查询（仅支持 LOL）
    if match_id and not is_tft:
        match_obj = lcu.get_match_by_id(token, port, match_id)
        if match_obj:
            game = match_obj.get('game') if (isinstance(match_obj, dict) and 'game' in match_obj) else match_obj
            try:
                lcu.enrich_game_with_summoner_info(token, port, game)
                enrich_game_with_augments(game)
            except Exception as e:
                print(f"召唤师信息补全失败 (match_id path): {e}")
            return game
        else:
            raise RuntimeError("通过 match_id 获取对局失败")

    if not summoner_name or index is None:
        raise ValueError("缺少参数 name 或 index")

    puuid = lcu.get_puuid(token, port, summoner_name)
    if not puuid:
        raise RuntimeError(f"找不到召唤师 '{summoner_name}' 或 LCU API 失败")

    if is_tft:
        # TFT 战绩查询
        fetch_count = min(index + 20, 200)
        history = lcu.get_tft_match_history(token, port, puuid, count=fetch_count)
        if not history:
            raise RuntimeError("获取 TFT 战绩失败")

        games = history.get('games', {}).get('games', [])
        if index < 0 or index >= len(games):
            raise ValueError("索引越界")

        game_summary = games[index]
        
        # TFT 的 match_id 通常在 metadata.match_id 中
        metadata = game_summary.get('metadata', {})
        game_match_id = metadata.get('match_id') if isinstance(metadata, dict) else None
        
        if not game_match_id:
            game_match_id = game_summary.get('matchId') or game_summary.get('gameId') or game_summary.get('match_id')
        
        game = game_summary
        if game_match_id:
            full_game = lcu.get_match_by_id(token, port, game_match_id)
            if full_game:
                game = full_game.get('game') if (isinstance(full_game, dict) and 'game' in full_game) else full_game
        
        try:
            enrich_tft_game_with_summoner_info(token, port, game)
        except Exception as e:
            print(f"TFT 召唤师信息补全失败: {e}")
            
        return game
    else:
        # LOL 战绩查询
        fetch_count = min(index + 20, 200)
        history = lcu.get_match_history(token, port, puuid, count=fetch_count)
        if not history:
            raise RuntimeError("获取战绩失败")

        games = history.get('games', {}).get('games', [])
        if index < 0 or index >= len(games):
            raise ValueError("索引越界")

        game_summary = games[index]
        game_match_id = game_summary.get('matchId') or game_summary.get('gameId') or game_summary.get('match_id')
        
        game = game_summary
        if game_match_id:
            full_game = lcu.get_match_by_id(token, port, game_match_id)
            if full_game:
                game = full_game.get('game') if (isinstance(full_game, dict) and 'game' in full_game) else full_game

        try:
            lcu.enrich_game_with_summoner_info(token, port, game)
            enrich_game_with_augments(game)
        except Exception as e:
            print(f"召唤师信息补全失败: {e}")

        return game
