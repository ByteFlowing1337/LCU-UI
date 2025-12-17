"""
数据增强模块（面向对象）
"""
from constants import get_augment_icon_url, get_augment_info


class EnrichmentService:
    def __init__(self, summoner_api):
        self.summoner_api = summoner_api

    def enrich_game_with_summoner_info(self, game):
        if not game or not isinstance(game, dict):
            return game

        participants = game.get('participants') or []

        idents = {}
        for ident in (game.get('participantIdentities') or []):
            pid = ident.get('participantId')
            player = ident.get('player') or {}
            if pid is not None:
                idents[pid] = player

        for p in participants:
            try:
                if not p.get('summonerName'):
                    game_name = p.get('riotIdGameName') or p.get('riotId') or None
                    tag_line = p.get('riotIdTagline') or p.get('riotTagLine') or ''
                    if game_name:
                        p['summonerName'] = f"{game_name}#{tag_line}" if tag_line else game_name

                info = None

                puuid = p.get('puuid') or (p.get('player') or {}).get('puuid')
                if puuid:
                    info = self.summoner_api.get_summoner_by_puuid(puuid)

                if not info:
                    sid = p.get('summonerId') or (p.get('player') or {}).get('summonerId')
                    if sid:
                        info = self.summoner_api.get_summoner_by_id(sid)

                if not info:
                    name = p.get('summonerName') or (p.get('player') or {}).get('summonerName')
                    if name:
                        info = self.summoner_api.get_summoner_by_name(name)

                if info and isinstance(info, dict):
                    p['summonerName'] = (
                        info.get('displayName') or
                        info.get('summonerName') or
                        info.get('gameName') or
                        p.get('summonerName')
                    )

                    if 'profileIconId' in info:
                        p['profileIcon'] = info.get('profileIconId')
                    elif 'profileIcon' in info:
                        p['profileIcon'] = info.get('profileIcon')

                    if 'puuid' in info:
                        p['puuid'] = info.get('puuid')

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

    def enrich_tft_game_with_summoner_info(self, game):
        if not game or not isinstance(game, dict):
            return game

        game_json = game.get('json', game)
        if not isinstance(game_json, dict):
            return game

        participants = game_json.get('participants') or []

        for p in participants:
            try:
                if not p.get('summonerName'):
                    rn = p.get('riotIdGameName') or p.get('riotId') or None
                    rt = p.get('riotIdTagline') or p.get('riotTagLine') or ''
                    if rn:
                        p['summonerName'] = f"{rn}#{rt}" if rt else rn

                info = None

                puuid = p.get('puuid') or (p.get('player') or {}).get('puuid')
                if puuid:
                    info = self.summoner_api.get_summoner_by_puuid(puuid)

                if info and isinstance(info, dict):
                    game_name = info.get('gameName') or info.get('displayName') or info.get('summonerName') or ''
                    tag_line = info.get('tagLine') or info.get('tagline') or ''

                    if game_name:
                        p['summonerName'] = f"{game_name}#{tag_line}" if tag_line else game_name
                        p['riotIdGameName'] = game_name
                        p['riotIdTagline'] = tag_line

                    if 'profileIconId' in info and info.get('profileIconId') is not None:
                        p['profileIcon'] = info.get('profileIconId')
                    elif 'profileIcon' in info and info.get('profileIcon') is not None:
                        p['profileIcon'] = info.get('profileIcon')

                    if 'puuid' in info and info.get('puuid'):
                        p['puuid'] = info.get('puuid')

            except Exception as e:
                print(f"[TFT] enrich参与者信息失败: {e}")
                continue

        return game


def enrich_game_with_augments(game):
    if not game or not isinstance(game, dict):
        return game

    game_mode = game.get('gameMode')
    if game_mode not in ['KIWI', 'CHERRY']:
        return game

    participants = game.get('participants') or []

    for p in participants:
        try:
            stats = p.get('stats') or {}

            for i in range(1, 7):
                augment_key = f'playerAugment{i}'
                icon_key = f'augmentIcon{i}'
                name_key = f'augmentName{i}'
                desc_key = f'augmentDesc{i}'

                augment_id = stats.get(augment_key)

                if augment_id and augment_id > 0:
                    mapped_id = augment_id + 1000 if game_mode == 'CHERRY' else augment_id

                    icon_url = get_augment_icon_url(mapped_id)
                    stats[icon_key] = icon_url

                    aug_info_map = get_augment_info()
                    aug = {}
                    if isinstance(aug_info_map, dict):
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
