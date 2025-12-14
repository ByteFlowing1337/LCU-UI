"""
游戏数据格式化工具
处理游戏API返回的数据，提取玩家详细信息
"""


def _extract_subteam_id(player_data):
    """尝试从 liveclient 玩家数据中提取斗魂竞技场的小队编号。"""
    if not isinstance(player_data, dict):
        return None

    candidate_keys = [
        "playerSubteamId",
        "subteamId",
        "subTeamId",
        "subteamID",
        "arenaTeamId",
        "teamId",
    ]

    def _coerce(value):
        if value in (None, "", -1):
            return None
        if isinstance(value, dict):
            for inner_key in ("id", "teamId", "subteamId"):
                inner_val = value.get(inner_key)
                if inner_val not in (None, "", -1):
                    try:
                        return int(inner_val)
                    except (TypeError, ValueError):
                        return None
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    for key in candidate_keys:
        subteam_val = player_data.get(key)
        coerced = _coerce(subteam_val)
        if coerced is not None:
            return coerced

    # 某些模式会把 subteam 信息塞进嵌套字段
    nested_sources = [
        player_data.get("scores"),
        player_data.get("team"),
        player_data.get("championStats"),
    ]

    for candidate in nested_sources:
        if not isinstance(candidate, dict):
            continue
        for key in candidate_keys:
            coerced = _coerce(candidate.get(key))
            if coerced is not None:
                return coerced

    raw_team = player_data.get("team")
    if isinstance(raw_team, str):
        digits = "".join(ch for ch in raw_team if ch.isdigit())
        if digits:
            try:
                return int(digits)
            except ValueError:
                return None

    return None

def format_player_info(player_data, active_player_name):
    """
    格式化单个玩家的详细信息
    
    Args:
        player_data: allPlayers中的单个玩家数据
        active_player_name: 当前玩家名称（用于标识）
    
    Returns:
        dict: 格式化后的玩家信息
    """
    summoner_name = player_data.get('summonerName', 'Unknown')
    riot_id = player_data.get('riotId', summoner_name)
    game_name = player_data.get('riotIdGameName', '')
    tag_line = player_data.get('riotIdTagLine', '')
    
    # 提取KDA（防御性编程：处理 None 情况）
    scores = player_data.get('scores')
    if scores is None or not isinstance(scores, dict):
        scores = {}
    
    kills = scores.get('kills', 0)
    deaths = scores.get('deaths', 0)
    assists = scores.get('assists', 0)
    cs = scores.get('creepScore', 0)
    
    # 提取英雄信息
    champion_name = player_data.get('championName', 'Unknown')
    champion_raw = player_data.get('rawChampionName', '')
    level = player_data.get('level', 0)
    is_dead = player_data.get('isDead', False)
    respawn_timer = player_data.get('respawnTimer', 0)
    
    # 提取装备信息（防御性编程：处理 None 情况）
    items = player_data.get('items')
    if items is None or not isinstance(items, list):
        items = []
    
    item_list = []
    for item in items:
        if item and item.get('itemID') not in [0, 3340, 3363, 3364]:  # 排除空格和饰品
            item_list.append({
                'id': item.get('itemID'),
                'name': item.get('displayName', ''),
                'count': item.get('count', 1),
                'canUse': item.get('canUse', False)
            })
    
    # 提取符文信息（防御性编程：处理 None 情况）
    runes = player_data.get('runes')
    if runes is None or not isinstance(runes, dict):
        runes = {}
    
    keystone = runes.get('keystone', {})
    if keystone is None or not isinstance(keystone, dict):
        keystone = {}
    
    primary_tree = runes.get('primaryRuneTree', {})
    if primary_tree is None or not isinstance(primary_tree, dict):
        primary_tree = {}
    
    secondary_tree = runes.get('secondaryRuneTree', {})
    if secondary_tree is None or not isinstance(secondary_tree, dict):
        secondary_tree = {}
    
    # 提取召唤师技能（防御性编程：处理 None 情况）
    summoner_spells = player_data.get('summonerSpells')
    if summoner_spells is None or not isinstance(summoner_spells, dict):
        summoner_spells = {}
    
    spell_one = summoner_spells.get('summonerSpellOne', {})
    if spell_one is None or not isinstance(spell_one, dict):
        spell_one = {}
    
    spell_two = summoner_spells.get('summonerSpellTwo', {})
    if spell_two is None or not isinstance(spell_two, dict):
        spell_two = {}
    
    # 提取增强（Augments）- KIWI模式特有
    # 检查召唤师技能中是否包含增强技能（rawDescription包含"Augment"）
    augments = []
    if spell_one and 'Augment' in spell_one.get('rawDescription', ''):
        augments.append({
            'name': spell_one.get('displayName', ''),
            'raw': spell_one.get('rawDisplayName', ''),
            'description': spell_one.get('rawDescription', '')
        })
    if spell_two and 'Augment' in spell_two.get('rawDescription', ''):
        augments.append({
            'name': spell_two.get('displayName', ''),
            'raw': spell_two.get('rawDisplayName', ''),
            'description': spell_two.get('rawDescription', '')
        })
    
    # 提取队伍信息
    raw_team = player_data.get('team', 'UNKNOWN')
    team = raw_team
    if isinstance(raw_team, dict):
        team = raw_team.get('name') or raw_team.get('displayName') or 'UNKNOWN'
    elif not team:
        team = 'UNKNOWN'
    position = player_data.get('position', 'NONE')
    subteam_id = _extract_subteam_id(player_data)
    
    # 判断是否为当前玩家
    is_current_player = (summoner_name == active_player_name)
    
    return {
        'summonerName': summoner_name,
        'riotId': riot_id,
        'gameName': game_name,
        'tagLine': tag_line,
        'champion': champion_name,
        'championRaw': champion_raw,
        'level': level,
        'isDead': is_dead,
        'respawnTimer': round(respawn_timer, 1) if respawn_timer > 0 else 0,
        'kills': kills,
        'deaths': deaths,
        'assists': assists,
        'cs': cs,
        'kda': f"{kills}/{deaths}/{assists}",
        'items': item_list,
        'keystone': keystone.get('displayName', ''),
        'keystoneId': keystone.get('id', 0),
        'primaryRune': primary_tree.get('displayName', ''),
        'secondaryRune': secondary_tree.get('displayName', ''),
        'spell1': spell_one.get('displayName', ''),
        'spell2': spell_two.get('displayName', ''),
        'augments': augments,  # KIWI模式增强列表
        'team': team,
        'teamRaw': raw_team,
        'position': position,
        'subteamId': subteam_id,
        'isCurrentPlayer': is_current_player
    }


def format_game_data(all_game_data):
    """
    格式化完整游戏数据
    
    Args:
        all_game_data: 从 /liveclientdata/allgamedata 获取的完整数据
    
    Returns:
        dict: 包含格式化后的玩家列表和游戏信息
    """
    # Defensive programming：确保所有字段都不为 None
    active_player = all_game_data.get('activePlayer')
    if active_player is None or not isinstance(active_player, dict):
        active_player = {}
    
    active_player_name = active_player.get('summonerName', '')
    active_player_team = None
    
    all_players = all_game_data.get('allPlayers')
    if all_players is None or not isinstance(all_players, list):
        all_players = []
    
    game_data = all_game_data.get('gameData')
    if game_data is None or not isinstance(game_data, dict):
        game_data = {}
    
    # 找到当前玩家的队伍
    for player in all_players:
        if player and player.get('summonerName') == active_player_name:
            active_player_team = player.get('team', '')
            break
    
    structured_players = []
    active_player_entry = None

    for player in all_players:
        if not player:  # 跳过空玩家数据
            continue

        try:
            formatted_player = format_player_info(player, active_player_name)
            structured_players.append((player, formatted_player))

            if player.get('summonerName') == active_player_name:
                active_player_entry = formatted_player
                # 覆写一次 team，避免上面没找到
                active_player_team = player.get('team', active_player_team)
        except Exception as e:
            # 记录错误但继续处理其他玩家
            print(f"⚠️ 格式化玩家数据失败 ({player.get('summonerName', 'Unknown')}): {e}")
            continue

    teammates = []
    enemies = []

    game_mode = game_data.get('gameMode', 'CLASSIC') if isinstance(game_data, dict) else 'CLASSIC'
    game_mode_key = str(game_mode).upper()

    active_subteam_id = None
    if active_player_entry:
        active_subteam_id = active_player_entry.get('subteamId')

    use_cherry_subteams = (
        game_mode_key == 'CHERRY'
        and active_subteam_id not in (None, -1)
        and any(
            formatted.get('subteamId') not in (None, active_subteam_id)
            for _, formatted in structured_players
        )
    )

    for raw_player, formatted_player in structured_players:
        if use_cherry_subteams:
            if formatted_player.get('subteamId') == active_subteam_id:
                teammates.append(formatted_player)
            else:
                enemies.append(formatted_player)
            continue

        # 默认逻辑：根据 team 区分
        player_team = raw_player.get('team')
        if active_player_team and player_team == active_player_team:
            teammates.append(formatted_player)
        elif formatted_player.get('isCurrentPlayer'):
            teammates.append(formatted_player)
        else:
            enemies.append(formatted_player)
    
    # 提取游戏信息
    game_info = {
        'mode': game_data.get('gameMode', 'Unknown'),
        'time': round(game_data.get('gameTime', 0), 1),
        'mapName': game_data.get('mapName', ''),
        'mapNumber': game_data.get('mapNumber', 'Unknown')
    }
    
    # 提取事件信息（最近击杀等）
    events_data = all_game_data.get('events')
    if events_data is None or not isinstance(events_data, dict):
        events_data = {}
    
    events = events_data.get('Events', [])
    if events is None or not isinstance(events, list):
        events = []
    
    recent_kills = []
    
    for event in reversed(events):
        if event and event.get('EventName') == 'ChampionKill':
            recent_kills.append({
                'killer': event.get('KillerName', ''),
                'victim': event.get('VictimName', ''),
                'assisters': event.get('Assisters') or [],
                'time': round(event.get('EventTime', 0), 1)
            })
            if len(recent_kills) >= 10:  # 只保留最近10次击杀
                break
    
    return {
        'teammates': teammates,
        'enemies': enemies,
        'gameInfo': game_info,
        'recentKills': recent_kills,
        'activePlayerTeam': active_player_team,
        'activePlayerSubteam': active_subteam_id
    }






