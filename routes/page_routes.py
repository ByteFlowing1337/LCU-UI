"""
页面渲染路由模块
负责返回 HTML 页面
"""
from flask import Blueprint, render_template, request
from config import app_state
import constants
from core import lcu
import urllib.parse

page_bp = Blueprint('pages', __name__)


@page_bp.route('/')
def index():
    """渲染主页面"""
    lcu_connected = app_state.is_lcu_connected()
    recent_games = []
    current_summoner = None
    
    if lcu_connected:
        try:
            token = app_state.lcu_credentials["auth_token"]
            port = app_state.lcu_credentials["app_port"]
            
            # 获取当前登录的召唤师信息
            current_summoner_data = lcu.get_current_summoner(token, port)
            if current_summoner_data:
                current_summoner = {
                    'displayName': current_summoner_data.get('gameName', '') + '#' + current_summoner_data.get('tagLine', ''),
                    'profileIconId': current_summoner_data.get('profileIconId', 29),
                    'summonerLevel': current_summoner_data.get('summonerLevel', 0),
                    'puuid': current_summoner_data.get('puuid', '')
                }
                
                # 获取最近5场战绩
                if current_summoner['puuid']:
                    history = lcu.get_match_history(token, port, current_summoner['puuid'], count=5, begin_index=0)
                    if history:
                        games_data = history.get('games', {}).get('games', [])
                        for game in games_data[:5]:
                            participants = game.get('participants', [])
                            player_stats = None
                            for p in participants:
                                if p.get('puuid') == current_summoner['puuid']:
                                    player_stats = p
                                    break
                            
                            if not player_stats and participants:
                                player_stats = participants[0]
                            
                            win = False
                            if player_stats:
                                stats = player_stats.get('stats', {})
                                win = stats.get('win', False)
                            
                            queue_id = game.get('queueId', 0)
                            queue_name = _get_queue_name(queue_id)
                            
                            game_creation = game.get('gameCreation', 0)
                            time_ago = _format_time_ago(game_creation)
                            
                            recent_games.append({
                                'win': win,
                                'queue_name': queue_name,
                                'time_ago': time_ago,
                                'champion_id': player_stats.get('championId', 0) if player_stats else 0
                            })
        except Exception as e:
            print(f"Error fetching recent games: {e}")
    
    return render_template('index.html', 
                          lcu_connected=lcu_connected,
                          current_summoner=current_summoner,
                          recent_games=recent_games)


def _get_queue_name(queue_id):
    """根据队列ID返回队列名称"""
    queue_names = {
        420: 'Ranked Solo/Duo',
        440: 'Ranked Flex',
        400: 'Normal Draft',
        430: 'Normal Blind',
        450: 'ARAM',
        900: 'URF',
        1700: 'Arena',
        1900: 'URF',
        0: 'Custom'
    }
    return queue_names.get(queue_id, f'Queue {queue_id}')


def _format_time_ago(timestamp_ms):
    """将时间戳转换为相对时间字符串"""
    import time
    if not timestamp_ms:
        return 'Unknown'
    
    now = time.time() * 1000
    diff_ms = now - timestamp_ms
    diff_seconds = diff_ms / 1000
    diff_minutes = diff_seconds / 60
    diff_hours = diff_minutes / 60
    diff_days = diff_hours / 24
    
    if diff_days >= 1:
        return f'{int(diff_days)} day{"s" if diff_days >= 2 else ""} ago'
    elif diff_hours >= 1:
        return f'{int(diff_hours)} hour{"s" if diff_hours >= 2 else ""} ago'
    elif diff_minutes >= 1:
        return f'{int(diff_minutes)} min{"s" if diff_minutes >= 2 else ""} ago'
    else:
        return 'Just now'


@page_bp.route('/summoner/<path:summoner_name>')
def summoner_detail(summoner_name):
    """
    渲染召唤师详细战绩页面
    
    Args:
        summoner_name: 召唤师名称 (格式: 名称#TAG)
    
    Returns:
        HTML: 详细战绩页面
    """
    # URL 解码召唤师名称
    decoded_summoner_name = urllib.parse.unquote(summoner_name)
    
    # allow optional puuid query param to bypass name->puuid lookup in the client
    puuid = request.args.get('puuid')
    
    # 获取召唤师头像 ID、等级和段位信息
    profile_icon_id = 29  # 默认头像
    summoner_level = 0  # 默认等级
    ranked_solo_tier = ""  # 单排段位
    ranked_solo_rank = ""  # 单排小段位
    ranked_solo_lp = 0  # 单排胜点
    ranked_flex_tier = ""  # 灵活组排段位
    ranked_flex_rank = ""  # 灵活组排小段位
    ranked_flex_lp = 0  # 灵活组排胜点
    ranked_solo_summary = None
    ranked_flex_summary = None

    SOLO_QUEUE_TYPES = {
        "RANKED_SOLO_5X5",
        "RANKED_SOLO",
        "SOLO",
    }
    FLEX_QUEUE_TYPES = {
        "RANKED_FLEX_SR",
        "RANKED_FLEX",
        "FLEX",
        "RANKED_FLEX_5X5",
    }

    def _safe_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _summarize_queue(queue: dict | None, label: str):
        if not isinstance(queue, dict):
            return None

        tier_raw = queue.get('tier') or queue.get('tierName') or queue.get('tierNameShort') or ""
        tier = str(tier_raw).strip().upper()
        if tier in {"NA", "NONE", "UNRANKED", "N/A"}:
            tier = ""

        division_raw = queue.get('division') or queue.get('divisionName') or queue.get('rank') or ""
        division = str(division_raw).strip().upper()
        if division in {"NA", "NONE", "UNRANKED", "UNSPECIFIED", "N/A"}:
            division = ""

        lp_candidates = [
            queue.get('leaguePoints'),
            queue.get('leaguePointsEarned'),
            queue.get('lp'),
            queue.get('league_points'),
        ]
        lp_val = next((val for val in lp_candidates if val is not None), 0)
        lp = _safe_int(lp_val)
        if lp is None:
            lp = 0

        wins = _safe_int(queue.get('wins'))
        losses = _safe_int(queue.get('losses'))

        queue_type = queue.get('queueType') or queue.get('queue') or queue.get('type') or ""

        return {
            "label": label,
            "tier": tier,
            "division": division,
            "lp": lp,
            "wins": wins,
            "losses": losses,
            "queueType": str(queue_type).upper(),
            "leagueName": queue.get('leagueName') or queue.get('leagueId') or "",
        }

    if app_state.is_lcu_connected():
        token = app_state.lcu_credentials["auth_token"]
        port = app_state.lcu_credentials["app_port"]

        summoner_data = None
        if puuid:
            summoner_data = lcu.get_summoner_by_puuid(token, port, puuid)
        else:
            summoner_data = lcu.get_summoner_by_name(token, port, decoded_summoner_name)

        if summoner_data:
            profile_icon_id = summoner_data.get('profileIconId', 29)
            summoner_level = summoner_data.get('summonerLevel', 0)
            if not puuid:
                puuid = summoner_data.get('puuid') or puuid

            summoner_id = summoner_data.get('id') or summoner_data.get('summonerId')
            ranked_stats = {}
            if summoner_id or puuid:
                ranked_stats = lcu.get_ranked_stats(
                    token,
                    port,
                    summoner_id=summoner_id,
                    puuid=puuid
                ) or {}

            if isinstance(ranked_stats, dict):
                queues = ranked_stats.get('queues', [])
                if isinstance(queues, list):
                    solo_queue = None
                    flex_queue = None
                    for queue in queues:
                        queue_type = str(queue.get('queueType') or queue.get('queue') or queue.get('type') or "").upper()
                        if not solo_queue and queue_type in SOLO_QUEUE_TYPES:
                            solo_queue = queue
                        elif not flex_queue and queue_type in FLEX_QUEUE_TYPES:
                            flex_queue = queue

                    ranked_solo_summary = _summarize_queue(solo_queue, "单双排 (Solo/Duo)")
                    ranked_flex_summary = _summarize_queue(flex_queue, "灵活排位 (Flex)")

                    if ranked_solo_summary:
                        ranked_solo_tier = ranked_solo_summary.get('tier', '')
                        ranked_solo_rank = ranked_solo_summary.get('division', '')
                        ranked_solo_lp = ranked_solo_summary.get('lp', 0)

                    if ranked_flex_summary:
                        ranked_flex_tier = ranked_flex_summary.get('tier', '')
                        ranked_flex_rank = ranked_flex_summary.get('division', '')
                        ranked_flex_lp = ranked_flex_summary.get('lp', 0)
    
    # pass champion map so templates can resolve championId -> champion key for ddragon
    return render_template(
        'summoner_detail.html', 
        summoner_name=decoded_summoner_name,
        champion_map=constants._get_champion_map(), 
        puuid=puuid,
        profile_icon_id=profile_icon_id,
        summoner_level=summoner_level,
        ranked_solo_tier=ranked_solo_tier,
        ranked_solo_rank=ranked_solo_rank,
        ranked_solo_lp=ranked_solo_lp,
        ranked_flex_tier=ranked_flex_tier,
        ranked_flex_rank=ranked_flex_rank,
        ranked_flex_lp=ranked_flex_lp,
        ranked_solo_summary=ranked_solo_summary,
        ranked_flex_summary=ranked_flex_summary
    )


@page_bp.route('/tft_summoner/<path:summoner_name>')
def tft_summoner_detail(summoner_name):
    """
    渲染 TFT 专用的召唤师战绩页面
    """
    # URL 解码召唤师名称
    decoded_summoner_name = urllib.parse.unquote(summoner_name)
    
    puuid = request.args.get('puuid')
    
    # 获取召唤师头像 ID
    profile_icon_id = 29  # 默认头像
    if app_state.is_lcu_connected():
        token = app_state.lcu_credentials["auth_token"]
        port = app_state.lcu_credentials["app_port"]
        if puuid:
            summoner_data = lcu.get_summoner_by_puuid(token, port, puuid)
            if summoner_data:
                profile_icon_id = summoner_data.get('profileIconId', 29)
        else:
            # 如果没有 puuid，尝试通过名称获取（使用解码后的名称）
            s_data = lcu.get_summoner_by_name(token, port, decoded_summoner_name)
            if s_data:
                profile_icon_id = s_data.get('profileIconId', 29)
                # 同时获取 puuid 用于后续查询
                puuid = s_data.get('puuid')

    return render_template(
        'tft_summoner.html', 
        summoner_name=decoded_summoner_name,  # 传递解码后的名称给模板
        puuid=puuid,
        profile_icon_id=profile_icon_id
    )


@page_bp.route('/match/<path:summoner_name>/<int:game_index>')
def match_detail_page(summoner_name, game_index):
    """
    渲染单场对局详情页面
    
    支持两种访问方式：
    1. /match/召唤师名/索引 - 通过战绩列表索引访问
    2. /match/召唤师名/索引?match_id=xxx - 通过对局ID直接访问（更快）
    """
    # 获取可选的 match_id 参数（如果提供，可以直接查询对局，无需先查战绩）
    match_id = request.args.get('match_id')
    
    # pass champion map so the template can resolve championId -> champion key
    return render_template(
        'match_detail.html', 
        summoner_name=summoner_name, 
        game_index=game_index, 
        match_id=match_id,
        champion_map=constants._get_champion_map()
    )


@page_bp.route('/live_game')
def live_game():
    """
    渲染实时游戏监控页面
    
    Returns:
        HTML: 实时游戏详情页面
    """
    return render_template('live_game.html')



@page_bp.route('/get_summoner_rank', methods=['GET'])
def page_get_summoner_rank():
    """兼容性路由：在页面蓝图下也提供 /get_summoner_rank，以防数据蓝图不可达。

    返回与 data_routes.get_summoner_rank 相同的 JSON 结构。
    """
    from flask import request, jsonify
    if not app_state.is_lcu_connected():
        return jsonify({"success": False, "message": "未连接到客户端"}), 400

    summoner_name = request.args.get('name')
    puuid = request.args.get('puuid')
    token = app_state.lcu_credentials["auth_token"]
    port = app_state.lcu_credentials["app_port"]

    summoner_data = None
    if puuid:
        summoner_data = lcu.get_summoner_by_puuid(token, port, puuid)
    else:
        summoner_data = lcu.get_summoner_by_name(token, port, summoner_name)

    if not summoner_data:
        return jsonify({"success": False, "message": "无法获取召唤师信息"}), 404

    profile_icon_id = summoner_data.get('profileIconId', 29)
    summoner_level = summoner_data.get('summonerLevel', 0)
    summoner_id = summoner_data.get('id')
    puuid = summoner_data.get('puuid') or puuid

    ranked = {}
    if summoner_id or puuid:
        ranked = lcu.get_ranked_stats(token, port, summoner_id=summoner_id, puuid=puuid) or {}

    return jsonify({
        "success": True,
        "profile_icon_id": profile_icon_id,
        "summoner_level": summoner_level,
        "ranked": ranked,
    })
