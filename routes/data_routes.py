"""
数据 API 路由模块
处理所有数据获取的 API 端点
"""
from flask import Blueprint, request, jsonify
import requests

from config import app_state
from core import lcu
from utils.game_data_formatter import format_game_data
from services.match_service import process_lol_match_history, process_single_tft_game, get_match_detail
from services.opgg_service import fetch_champion_stats

# 创建数据 API 蓝图
data_bp = Blueprint('data', __name__)


@data_bp.route('/get_history', methods=['GET'])
def get_history():
    """
    获取指定召唤师的战绩
    
    查询参数:
        name: 召唤师名称 (格式: 名称#TAG)
        puuid: 或直接使用 puuid
        count: 每页数量 (默认20，最大200)
        page: 页码 (默认1，表示第1-20场；page=2表示第21-40场)
    
    Returns:
        JSON: 包含战绩数据的响应
    """
    # support either name OR puuid to speed up lookups from client
    summoner_name = request.args.get('name')
    puuid = request.args.get('puuid')

    if not summoner_name and not puuid:
        return jsonify({
            "success": False,
            "message": "请求缺少召唤师名称 (name) 或 puuid 查询参数"
        })

    if not app_state.is_lcu_connected():
        return jsonify({
            "success": False,
            "message": "未连接到客户端"
        })

    # 获取PUUID（若客户端未直接提供）
    token = app_state.lcu_credentials["auth_token"]
    port = app_state.lcu_credentials["app_port"]
    if not puuid:
        puuid = lcu.get_puuid(token, port, summoner_name)
        if not puuid:
            return jsonify({
                "success": False,
                "message": f"找不到召唤师 '{summoner_name}' 或 LCU API 失败"
            })

    # 🚀 优化：默认只查询 20 场，支持分页查询
    count = request.args.get('count', 20, type=int)  # 每页数量
    count = min(max(count, 1), 200)  # 限制在1-200之间
    
    page = request.args.get('page', 1, type=int)  # 页码，从1开始
    page = max(page, 1)  # 确保页码至少为1
    
    # 计算beginIndex: page=1 -> beginIndex=0; page=2 -> beginIndex=20
    begin_index = (page - 1) * count
    
    # 获取战绩
    history = lcu.get_match_history(token, port, puuid, count=count, begin_index=begin_index)
    if not history:
        return jsonify({
            "success": False,
            "message": "获取战绩失败"
        })
    
    # 处理数据
    processed_games = process_lol_match_history(history, puuid)
    
    # OP.GG integration removed: processed_games contains core match info only.
    
    return jsonify({
        "success": True, 
        "games": processed_games,
        "page": page,
        "count": count
    })


@data_bp.route('/get_tft_history', methods=['GET'])
def get_tft_history():
    """
    获取指定召唤师的 TFT 战绩（调用 LCU 的 TFT 产品端点）

    查询参数:
        name: 召唤师名称 (格式: 名称#TAG) 或
        puuid: 直接使用 puuid
        count: 可选，查询数量（默认20）
    """
    summoner_name = request.args.get('name')
    puuid = request.args.get('puuid')

    if not summoner_name and not puuid:
        return jsonify({
            "success": False,
            "message": "请求缺少召唤师名称 (name) 或 puuid 查询参数"
        })

    if not app_state.is_lcu_connected():
        return jsonify({
            "success": False,
            "message": "未连接到客户端"
        })

    token = app_state.lcu_credentials["auth_token"]
    port = app_state.lcu_credentials["app_port"]
    if not puuid:
        puuid = lcu.get_puuid(token, port, summoner_name)
        if not puuid:
            return jsonify({
                "success": False,
                "message": f"找不到召唤师 '{summoner_name}' 或 LCU API 失败"
            })

    count = request.args.get('count', 20, type=int)
    count = min(max(count, 1), 200)

    history = lcu.get_tft_match_history(token, port, puuid, count=count)
    if not history:
        return jsonify({
            "success": False,
            "message": "获取 TFT 战绩失败"
        })

    # 只返回摘要字段供前端快速显示，不返回完整游戏数据
    games = history.get('games', {}).get('games', [])[:20]
    
    # 为每场比赛提取摘要字段
    summary_games = []
    for idx, game in enumerate(games):
        # 只添加摘要字段（快速显示在卡片上）
        summary = process_single_tft_game(game, puuid)
        summary['match_index'] = idx
        
        summary_games.append(summary)

    return jsonify({
        "success": True,
        "games": summary_games
    })


@data_bp.route('/get_summoner_rank', methods=['GET'])
def get_summoner_rank():
    """
    返回召唤师的头像、等级与段位信息（用于客户端在页面加载后异步获取）。

    查询参数：
        name: 召唤师名称（可选）
        puuid: PUUID（可选，优先）

    返回：
        { success: bool, profile_icon_id, summoner_level, ranked: { queues: [...] } }
    """
    summoner_name = request.args.get('name')
    puuid = request.args.get('puuid')

    if not summoner_name and not puuid:
        return jsonify({"success": False, "message": "缺少 name 或 puuid 参数"}), 400

    if not app_state.is_lcu_connected():
        return jsonify({"success": False, "message": "未连接到客户端"}), 400

    token = app_state.lcu_credentials["auth_token"]
    port = app_state.lcu_credentials["app_port"]

    # 获取基础召唤师信息
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


@data_bp.route('/get_match', methods=['GET'])
def get_match():
    """
    返回指定召唤师历史列表中某一场的完整对局信息（包含所有参赛者）
    
    支持 LOL 和 TFT 两种游戏类型

    查询参数:
        name: 召唤师名称 (格式: 名称#TAG)
        index: 在 /get_history 返回的 games 列表中的索引 (整数，0 表示最近一场)
        match_id: 对局 ID（可选，直接通过对局ID查询）
        is_tft: 是否为 TFT 对局（true/false）
    """
    summoner_name = request.args.get('name')
    index = request.args.get('index', type=int)
    match_id = request.args.get('match_id')
    is_tft = request.args.get('is_tft', 'false').lower() == 'true'

    if not app_state.is_lcu_connected():
        return jsonify({"success": False, "message": "未连接到客户端"}), 400

    token = app_state.lcu_credentials["auth_token"]
    port = app_state.lcu_credentials["app_port"]

    try:
        game = get_match_detail(token, port, summoner_name, index, match_id, is_tft)
        return jsonify({"success": True, "game": game})
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"success": False, "message": str(e)}), 500
    except Exception as e:
        print(f"Error getting match detail: {e}")
        return jsonify({"success": False, "message": "获取对局详情失败"}), 500


@data_bp.route('/get_live_game_data', methods=['GET'])
def get_live_game_data():
    """
    获取实时游戏数据（从游戏API 2999端口）
    
    Returns:
        JSON: 格式化后的游戏数据（队友、敌人、游戏信息等）
    """
    try:
        # 尝试连接游戏客户端API（端口2999，减少timeout）
        response = requests.get('https://127.0.0.1:2999/liveclientdata/allgamedata', 
                               verify=False, timeout=2)
        
        if response.status_code == 200:
            all_game_data = response.json()
            formatted_data = format_game_data(all_game_data)
            
            # OP.GG integration removed: returning formatted game data without external stats.
            
            return jsonify({
                "success": True,
                "inGame": True,
                "data": formatted_data
            })
        else:
            return jsonify({
                "success": False,
                "inGame": False,
                "message": "无法连接到游戏客户端"
            })
            
    except requests.exceptions.RequestException:
        return jsonify({
            "success": False,
            "inGame": False,
            "message": "未在游戏中或游戏API不可用"
        })


@data_bp.route('/external/champion_stats', methods=['GET'])
def external_champion_stats():
    """Return external champion stats (placeholder-backed).

    Query params:
      champion: champion English key (e.g., Aatrox)
      region: optional region label (default 'global')
    """
    champion = (request.args.get('champion') or '').strip()
    region = (request.args.get('region') or 'global').strip()
    if not champion:
        return jsonify({
            'success': False,
            'message': 'missing champion param'
        }), 400

    try:
        data = fetch_champion_stats(champion, region=region)
        if not data:
            return jsonify({'success': False, 'message': 'no data'}), 404
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@data_bp.route('/api/champions', methods=['GET'])
def get_champions():
    """
    获取英雄ID到名称的映射
    
    Returns:
        JSON: 英雄ID -> 名称的映射字典
    """
    import constants
    champion_map = constants._get_champion_map()
    return jsonify(champion_map)


@data_bp.route('/api/summoner_stats/<path:game_name>/<path:tag_line>', methods=['GET'])
def get_summoner_stats(game_name, tag_line):
    """
    获取召唤师的简要统计信息
    
    Args:
        game_name: 游戏名
        tag_line: Tag
    
    Returns:
        JSON: 包含胜率等统计的响应
    """
    import urllib.parse
    game_name = urllib.parse.unquote(game_name)
    tag_line = urllib.parse.unquote(tag_line)
    
    if not app_state.is_lcu_connected():
        return jsonify({'error': 'LCU not connected'}), 400
    
    token = app_state.lcu_credentials["auth_token"]
    port = app_state.lcu_credentials["app_port"]
    
    # 获取召唤师信息
    full_name = f"{game_name}#{tag_line}"
    summoner_data = lcu.get_summoner_by_name(token, port, full_name)
    
    if not summoner_data:
        return jsonify({'error': 'Summoner not found'}), 404
    
    puuid = summoner_data.get('puuid')
    if not puuid:
        return jsonify({'error': 'PUUID not found'}), 404
    
    # 获取最近20场战绩计算胜率
    try:
        history = lcu.get_match_history(token, port, puuid, count=20, begin_index=0)
        if not history:
            return jsonify({'wins': 0, 'losses': 0, 'winrate': 0})
        
        games = history.get('games', {}).get('games', [])
        wins = 0
        losses = 0
        
        for game in games:
            participants = game.get('participants', [])
            for p in participants:
                if p.get('puuid') == puuid:
                    stats = p.get('stats', {})
                    if stats.get('win', False):
                        wins += 1
                    else:
                        losses += 1
                    break
        
        total = wins + losses
        winrate = round((wins / total * 100), 1) if total > 0 else 0
        
        return jsonify({
            'wins': wins,
            'losses': losses,
            'winrate': winrate
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
