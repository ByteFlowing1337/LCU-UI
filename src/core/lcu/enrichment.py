"""
数据增强模块
为游戏数据填充缺失的召唤师信息
"""
from .summoner import get_summoner_by_puuid, get_summoner_by_id, get_summoner_by_name
from constants import get_augment_icon_url, get_augment_info


def enrich_game_with_summoner_info(token, port, game):
    """
    为 game['participants'] 中的每个参与者填充缺失的召唤师信息。
    
    尝试通过以下方式获取信息:
    1. 通过 puuid 查询
    2. 通过 summonerId 查询
    3. 通过 summonerName 查询
    4. 从 participantIdentities 中提取（备用）
    
    Args:
        token: LCU认证令牌
        port: LCU端口
        game: 游戏数据对象（dict）
    
    Returns:
        dict: 增强后的游戏数据（就地修改并返回）
    
    Notes:
        - 此函数会就地修改传入的 game 对象
        - 填充字段: summonerName, profileIcon, puuid
        - 如果所有方法都失败，会尝试从 participantIdentities 中提取
    """
    if not game or not isinstance(game, dict):
        return game

    participants = game.get('participants') or []
    
    # 构建 participantIdentities 映射，作为备用数据源
    idents = {}
    for ident in (game.get('participantIdentities') or []):
        pid = ident.get('participantId')
        player = ident.get('player') or {}
        if pid is not None:
            idents[pid] = player
    
    # 遍历每个参与者，填充缺失信息
    for p in participants:
        try:
            # 如果已有可读的 summonerName，跳过
            # Ensure summonerName exists if riotId fields are present
            if not p.get('summonerName'):
                # prefer Riot game name + tagline if available
                game_name = p.get('riotIdGameName') or p.get('riotId') or None
                tag_line = p.get('riotIdTagline') or p.get('riotTagLine') or ''
                if game_name:
                    p['summonerName'] = f"{game_name}#{tag_line}" if tag_line else game_name

            if p.get('summonerName'):
                # already have a readable name — but we may still try to fill profileIcon below
                pass

            info = None
            
            # 方法1: 尝试通过 puuid 查询
            puuid = p.get('puuid') or (p.get('player') or {}).get('puuid')
            if puuid:
                info = get_summoner_by_puuid(token, port, puuid)

            # 方法2: 尝试通过 summonerId 查询
            if not info:
                sid = p.get('summonerId') or (p.get('player') or {}).get('summonerId')
                if sid:
                    info = get_summoner_by_id(token, port, sid)

            # 方法3: 尝试通过 name 查询
            if not info:
                name = p.get('summonerName') or (p.get('player') or {}).get('summonerName')
                if name:
                    info = get_summoner_by_name(token, port, name)

            # 如果查询成功，填充数据
            if info and isinstance(info, dict):
                # 标准化可能的字段名
                p['summonerName'] = (
                    info.get('displayName') or 
                    info.get('summonerName') or 
                    info.get('gameName') or 
                    p.get('summonerName')
                )
                
                # 填充头像ID
                if 'profileIconId' in info:
                    p['profileIcon'] = info.get('profileIconId')
                elif 'profileIcon' in info:
                    p['profileIcon'] = info.get('profileIcon')
                
                # 填充PUUID
                if 'puuid' in info:
                    p['puuid'] = info.get('puuid')
            
            # 备用方案: 使用 participantIdentities 映射
            if (not p.get('summonerName')) and p.get('participantId') and idents.get(p.get('participantId')):
                player = idents.get(p.get('participantId')) or {}
                game_name = (player.get('gameName') or player.get('summonerName')) or ''
                tag = player.get('tagLine')
                
                if game_name:
                    p['summonerName'] = f"{game_name}{('#'+tag) if tag else ''}"
                
                if player.get('profileIcon') is not None and not p.get('profileIcon'):
                    p['profileIcon'] = player.get('profileIcon')
                
                if player.get('puuid') and not p.get('puuid'):
                    p['puuid'] = player.get('puuid')
                    
        except Exception as e:
            print(f"enrich参与者信息失败: {e}")
            continue

    return game


def enrich_tft_game_with_summoner_info(token, port, game):
    """
    为 TFT 游戏数据填充召唤师信息
    
    TFT 数据结构: game['json']['participants']
    
    Args:
        token: LCU认证令牌
        port: LCU端口
        game: TFT 游戏数据对象（dict）
    
    Returns:
        dict: 增强后的游戏数据（就地修改并返回）
    """
    if not game or not isinstance(game, dict):
        return game
    
    # TFT 参与者在 json.participants 中
    game_json = game.get('json', game)
    if not isinstance(game_json, dict):
        return game
    
    participants = game_json.get('participants') or []
    
    # 遍历每个参与者，填充缺失信息
    for p in participants:
        try:
            # 如果没有 summonerName，先尝试从 riotId 字段构造一个可读名称
            if not p.get('summonerName'):
                rn = p.get('riotIdGameName') or p.get('riotId') or None
                rt = p.get('riotIdTagline') or p.get('riotTagLine') or ''
                if rn:
                    p['summonerName'] = f"{rn}#{rt}" if rt else rn

            info = None

            # 方法1: 尝试通过 puuid 查询以获取更完整的召唤师信息（头像等）
            puuid = p.get('puuid') or (p.get('player') or {}).get('puuid')
            if puuid:
                info = get_summoner_by_puuid(token, port, puuid)

            # 如果查询成功，填充数据（包括头像）
            if info and isinstance(info, dict):
                # 标准化可能的字段名
                game_name = info.get('gameName') or info.get('displayName') or info.get('summonerName') or ''
                tag_line = info.get('tagLine') or info.get('tagline') or ''

                if game_name:
                    p['summonerName'] = f"{game_name}#{tag_line}" if tag_line else game_name
                    p['riotIdGameName'] = game_name
                    p['riotIdTagline'] = tag_line

                # 填充头像ID（优先 profileIconId）
                if 'profileIconId' in info and info.get('profileIconId') is not None:
                    p['profileIcon'] = info.get('profileIconId')
                elif 'profileIcon' in info and info.get('profileIcon') is not None:
                    p['profileIcon'] = info.get('profileIcon')

                # 确保 puuid 存在
                if 'puuid' in info and info.get('puuid'):
                    p['puuid'] = info.get('puuid')
                    
        except Exception as e:
            print(f"[TFT] enrich参与者信息失败: {e}")
            continue

    return game


def enrich_game_with_augments(game):
    """
    为 KIWI 和 CHERRY 模式游戏数据添加 augment 图标 URL 和中文信息
    
    遍历 participants，为每个玩家的 playerAugment1-6 生成对应的图标 URL 和中文名称/描述
    
    Args:
        game: 游戏数据对象（dict）
    
    Returns:
        dict: 增强后的游戏数据（就地修改并返回）
    
    Notes:
        - 处理 KIWI 和 CHERRY 模式游戏
        - KIWI模式: augment ID 已经包含+1000偏移
        - CHERRY模式: augment ID 是原始ID，需要+1000才能映射
        - 为每个 playerAugment 字段添加对应的 augmentIcon、augmentName、augmentDesc 字段
    """
    if not game or not isinstance(game, dict):
        return game
    
    game_mode = game.get('gameMode')
    
    # 只处理 KIWI 和 CHERRY 模式
    if game_mode not in ['KIWI', 'CHERRY']:
        return game
    
    participants = game.get('participants') or []
    
    for p in participants:
        try:
            stats = p.get('stats') or {}
            
            # 处理 6 个 augment 插槽
            for i in range(1, 7):
                augment_key = f'playerAugment{i}'
                icon_key = f'augmentIcon{i}'
                name_key = f'augmentName{i}'
                desc_key = f'augmentDesc{i}'
                
                augment_id = stats.get(augment_key)
                
                # 如果 augment ID 有效（非0），生成 URL 和中文信息
                if augment_id and augment_id > 0:
                    # CHERRY模式的ID需要+1000才能映射到我们的常量表
                    # KIWI模式的ID已经包含+1000偏移
                    mapped_id = augment_id + 1000 if game_mode == 'CHERRY' else augment_id
                    
                    # 图标URL
                    icon_url = get_augment_icon_url(mapped_id)
                    stats[icon_key] = icon_url
                    
                    # 中文名称和描述：从全表中根据 mapped_id 查找具体 augment 的信息
                    aug_info_map = get_augment_info()
                    # 可能的返回值是以 id 为键的字典，尝试用 int 或 str key 获取具体项
                    aug = {}
                    if isinstance(aug_info_map, dict):
                        # 安全地根据 mapped_id 查找项，兼容 int 或 str 类型的字典键
                        for k, v in aug_info_map.items():
                            try:
                                if k == mapped_id or str(k) == str(mapped_id):
                                    aug = v or {}
                                    break
                            except Exception:
                                continue

                    if aug and isinstance(aug, dict):
                        stats[name_key] = aug.get('name', '') or aug.get('title', '')
                        stats[desc_key] = aug.get('desc', '') or aug.get('description', '')
                    else:
                        stats[name_key] = None
                        stats[desc_key] = None
                else:
                    stats[icon_key] = None
                    stats[name_key] = None
                    stats[desc_key] = None
                    
        except Exception as e:
            print(f"enrich augment信息失败: {e}")
            continue
    
    return game
