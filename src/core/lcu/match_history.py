"""
战绩查询 API
处理比赛历史记录和对局详情查询
"""
from .client import make_request
import time
import base64
import requests
from requests.auth import HTTPBasicAuth
from urllib.parse import quote_plus
from utils.logger import logger

# 简单的内存缓存：{puuid: (timestamp, data)}
_match_history_cache = {}
CACHE_TTL = 300  # 缓存5分钟
MAX_CACHE_SIZE = 100  # 最大缓存100个玩家


def _clean_cache():
    """清理过期缓存和超出容量的缓存"""
    global _match_history_cache
    current_time = time.time()
    
    # 删除过期缓存
    expired_keys = [k for k, (t, _) in _match_history_cache.items() if current_time - t > CACHE_TTL]
    for k in expired_keys:
        del _match_history_cache[k]
    
    # 如果缓存过大，删除最旧的条目
    if len(_match_history_cache) > MAX_CACHE_SIZE:
        sorted_items = sorted(_match_history_cache.items(), key=lambda x: x[1][0])
        for k, _ in sorted_items[:len(_match_history_cache) - MAX_CACHE_SIZE]:
            del _match_history_cache[k]


def get_match_history(token, port, puuid, count=20, begin_index=0):
    """
    通过 PUUID 获取比赛历史记录。
    
    Args:
        token: LCU认证令牌
        port: LCU端口
        puuid: 玩家PUUID
        count: 查询数量 (默认20场)
        begin_index: 起始索引 (默认0，用于分页)
    
    Returns:
        dict: 战绩数据，包含 games 列表（已切片）
    
    Notes:
        - LCU API 不支持真正的分页参数，我们会一次性请求大量数据并缓存
        - 首次请求会获取最多200场，缓存10分钟
        - 后续分页请求会从缓存中切片
    """
    # 定期清理缓存
    _clean_cache()
    
    # 检查是否有完整数据的缓存
    full_cache_key = f"{puuid}_full"
    sliced_cache_key = f"{puuid}_{begin_index}_{count}"
    
    # 先检查切片后的缓存
    if sliced_cache_key in _match_history_cache:
        cached_time, cached_data = _match_history_cache[sliced_cache_key]
        if time.time() - cached_time < CACHE_TTL:
            logger.debug(f"✅ 使用切片缓存 (begin={begin_index}, count={count})")
            return cached_data
    
    # 检查完整数据缓存
    all_games = None
    if full_cache_key in _match_history_cache:
        cached_time, cached_games = _match_history_cache[full_cache_key]
        if time.time() - cached_time < CACHE_TTL:
            logger.debug(f"✅ 使用完整数据缓存 (共 {len(cached_games)} 场)")
            all_games = cached_games
    
    # 如果没有缓存，请求完整数据
    if all_games is None:
        endpoint = f"/lol-match-history/v1/products/lol/{quote_plus(puuid)}/matches"

        # 分阶段尝试，先请求较小范围数据，必要时逐步扩大
        attempt_profiles = [
            {
                'endIndex': min(max(count, 20), 30),
                'timeout': 12,
                'desc': 'baseline'
            },
            {
                'endIndex': min(max(count + 10, 30), 50),
                'timeout': 18,
                'desc': 'expanded'
            }
        ]

        auth = HTTPBasicAuth('riot', token)

        for idx, profile in enumerate(attempt_profiles):
            params = {'begIndex': 0, 'endIndex': profile['endIndex']}
            timeout = profile['timeout']
            logger.debug(f"📊 请求 {profile['endIndex']} 场历史记录 (profile={profile['desc']}, timeout={timeout}s)...")

            # 先尝试通过统一的 make_request（可复用连接池与日志）
            result = make_request(
                "GET",
                endpoint,
                token,
                port,
                params=params,
                timeout=timeout
            )

            # 如果 make_request 超时或返回 None，尝试直接使用 requests (支持更长 timeout)
            if not result:
                direct_timeout = min(timeout + 6, 28)
                url = f"https://127.0.0.1:{port}{endpoint}"
                try:
                    logger.warning(f"⏳ make_request 无响应，尝试直接请求 (timeout={direct_timeout}s)...")
                    resp = requests.get(
                        url,
                        params=params,
                        auth=auth,
                        verify=False,
                        timeout=direct_timeout
                    )
                    resp.raise_for_status()
                    result = resp.json()
                except requests.RequestException as exc:
                    logger.warning(f"⚠️ 直接请求失败: {exc}")
                    if idx == len(attempt_profiles) - 1:
                        logger.error(f"❌ 查询最终失败 (PUUID={puuid[:8]}...)")
                        return None
                    logger.debug("⏱️ 等待 1 秒后尝试下一套配置...")
                    time.sleep(1)
                    continue

            if result:
                games_data = result.get('games', {})
                if isinstance(games_data, dict):
                    all_games = games_data.get('games', [])
                else:
                    all_games = games_data if isinstance(games_data, list) else []

                logger.debug(f"✅ API返回 {len(all_games)} 场历史记录 (profile={profile['desc']})")

                _match_history_cache[full_cache_key] = (time.time(), all_games)
                break

        if all_games is None:
            return None
    
    # 如果还是没有数据，返回None
    if all_games is None:
        return None
    
    # 从完整数据中切片
    sliced_games = all_games[begin_index:begin_index + count]
    
    logger.debug(f"📊 从 {len(all_games)} 场中切片，取第 {begin_index+1}-{begin_index+len(sliced_games)} 场")
    if sliced_games:
        logger.debug(f"   第一场: gameId={sliced_games[0].get('gameId', 'N/A')}")
        if len(sliced_games) > 1:
            logger.debug(f"   最后一场: gameId={sliced_games[-1].get('gameId', 'N/A')}")
    
    # 构造返回结果，保持原有结构
    sliced_result = {
        'games': {
            'games': sliced_games
        }
    }
    
    # 缓存切片后的结果
    _match_history_cache[sliced_cache_key] = (time.time(), sliced_result)
    logger.debug(f"✅ 返回 {len(sliced_games)} 场比赛")
    
    return sliced_result


def get_tft_match_history(token, port, puuid, count=20):
    """
    通过 PUUID 获取 TFT (TFT product) 的比赛历史记录。

    使用直接 HTTPS 请求 + Basic Auth（与 runs/fetch_tft_history.py 相同的方式），
    避免高级 HTTP 客户端的参数处理差异或兼容性问题。

    Args:
        token: LCU认证令牌
        port: LCU端口
        puuid: 玩家PUUID
        count: 查询数量（默认20）

    Returns:
        dict: 标准化的战绩数据 {'games': {'games': [...]}}，失败返回None
    """
    # reuse cache mechanism but use a distinct cache key
    _clean_cache()
    cache_key = f"tft_{puuid}_{count}"
    if cache_key in _match_history_cache:
        cached_time, cached_data = _match_history_cache[cache_key]
        if time.time() - cached_time < CACHE_TTL:
            logger.debug(f"✅ 使用缓存数据 (TFT PUUID={puuid[:8]}..., count={count})")
            return cached_data

    timeout = 8 + (count // 20) * 2
    timeout = min(timeout, 25)

    logger.debug(f"📊 查询 TFT {count} 场战绩，预计timeout={timeout}秒")

    # 直接使用 HTTPS 请求 + Basic Auth（与 runs/fetch_tft_history.py 相同）
    # 这避免了 make_request 和 HTTPBasicAuth 可能的参数处理差异
    url = f"https://127.0.0.1:{port}/lol-match-history/v1/products/tft/{quote_plus(puuid)}/matches?begin=0&count={count}"
    auth_header = base64.b64encode(f"riot:{token}".encode('ascii')).decode('ascii')
    headers = {'Authorization': f'Basic {auth_header}'}

    logger.debug(f"🔎 TFT 直接请求: {url}")

    max_retries = 2
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=headers, verify=False, timeout=timeout)
            logger.debug(f"📡 TFT 请求响应: {resp.status_code}")

            if resp.status_code == 200:
                data = resp.json()
                # 规范化响应：确保返回 {'games': {'games': [...]}}
                normalized = _normalize_tft_response(data)
                _match_history_cache[cache_key] = (time.time(), normalized)
                
                games_count = _get_games_count(normalized)
                logger.info(f"✅ TFT 查询成功 (PUUID={puuid[:8]}..., {games_count} 场比赛)")
                return normalized
            else:
                logger.warning(f"⚠️ TFT 请求失败: {resp.status_code}")
                if attempt < max_retries - 1:
                    logger.warning(f"⏳ {timeout}秒后重试... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(1)
                else:
                    logger.error("❌ TFT 查询最终失败")
                    return None
        except Exception as e:
            logger.warning(f"⚠️ TFT 请求异常: {e}")
            if attempt < max_retries - 1:
                logger.warning(f"⏳ {timeout}秒后重试... (attempt {attempt + 1}/{max_retries})")
                time.sleep(1)
            else:
                logger.error("❌ TFT 查询异常失败")
                return None

    return None


def _normalize_tft_response(data):
    """
    规范化 TFT 响应为标准格式 {'games': {'games': [...]}}.
    
    Args:
        data: 原始 LCU 响应（可能是 list、{'games': [...]}, 或 {'games': {'games': [...]}})
    
    Returns:
        dict: 标准格式的响应
    """
    if isinstance(data, list):
        return {'games': {'games': data}}
    elif isinstance(data, dict):
        if 'games' in data and isinstance(data['games'], list):
            # {'games': [...]} -> {'games': {'games': [...]}}
            return {'games': {'games': data['games']}}
        elif 'games' in data and isinstance(data['games'], dict) and 'games' in data['games']:
            # already normalized
            return data
    return {'games': {'games': []}}


def _get_games_count(normalized):
    """
    从标准格式的响应中提取游戏数量.
    
    Args:
        normalized: 标准格式的响应 {'games': {'games': [...]}}
    
    Returns:
        int: 游戏数量
    """
    try:
        g = normalized.get('games', {})
        if isinstance(g, dict):
            return len(g.get('games', []))
    except Exception:
        pass
    return 0


def get_match_by_id(token, port, match_id):
    """
    通过 match_id 获取完整对局详情。
    
    尝试多个可能的 LCU 端点，返回第一个成功的响应。
    不同版本的 LCU 或打包服务器可能使用不同的路径。
    
    Args:
        token: LCU认证令牌
        port: LCU端口
        match_id: 对局ID
    
    Returns:
        dict: 对局完整数据，失败返回None
    """
    candidates = [
        f"/lol-match-history/v1/games/{match_id}", 
    ]

    for ep in candidates:
        try:
            # 🔇 仅在失败时打印日志，减少控制台噪音
            res = make_request("GET", ep, token, port, timeout=3)  # 单次请求超时3秒
            if res:
                logger.debug(f"✅ 获取对局成功 (match_id={match_id})")
                return res
        except Exception:
            # 静默失败，继续尝试下一个端点
            continue

    # 如果都失败，打印日志供调试
    logger.warning(f"❌ 无法通过任何已知 LCU 端点获取 match_id={match_id}")
    return None
