"""
召唤师信息 API
查询召唤师资料、PUUID 等信息
"""
import re
import time
from .client import make_request
from utils.logger import logger

# PUUID缓存：{summoner_name: (timestamp, puuid)}
_puuid_cache = {}
PUUID_CACHE_TTL = 600  # 缓存10分钟
MAX_PUUID_CACHE_SIZE = 200  # 最大缓存200个召唤师


def _clean_puuid_cache():
    """清理过期的PUUID缓存"""
    global _puuid_cache
    current_time = time.time()
    
    # 删除过期缓存
    expired_keys = [k for k, (t, _) in _puuid_cache.items() if current_time - t > PUUID_CACHE_TTL]
    for k in expired_keys:
        del _puuid_cache[k]
    
    # 如果缓存过大，删除最旧的条目
    if len(_puuid_cache) > MAX_PUUID_CACHE_SIZE:
        sorted_items = sorted(_puuid_cache.items(), key=lambda x: x[1][0])
        for k, _ in sorted_items[:len(_puuid_cache) - MAX_PUUID_CACHE_SIZE]:
            del _puuid_cache[k]


def get_current_summoner(token, port):
    """
    获取当前登录召唤师的完整信息。
    
    返回数据包含:
    - summonerId: 召唤师ID
    - displayName: 显示名称
    - puuid: PUUID
    - profileIconId: 头像ID
    - summonerLevel: 等级
    
    Args:
        token: LCU认证令牌
        port: LCU端口
    
    Returns:
        dict: 召唤师信息
    """
    return make_request("GET", "/lol-summoner/v1/current-summoner", token, port)


def get_puuid(token, port, summoner_name):
    """
    通过召唤师名字获取PUUID。
    
    使用 LCU API /lol-summoner/v1/summoners?name={summoner_name} 查询。
    会自动清理名称中的 Unicode 控制字符（如 Bidi 字符）。
    结果会缓存10分钟，避免重复查询。
    
    Args:
        token: LCU认证令牌
        port: LCU端口
        summoner_name: 召唤师名称（支持 GameName#TAG 格式）
    
    Returns:
        str: PUUID，失败返回None
    """
    # 定期清理缓存
    _clean_puuid_cache()
    
    # 检查缓存
    if summoner_name in _puuid_cache:
        cached_time, cached_puuid = _puuid_cache[summoner_name]
        if time.time() - cached_time < PUUID_CACHE_TTL:
            logger.debug(f"✅ 使用PUUID缓存 ({summoner_name})")
            return cached_puuid
    
    endpoint = "/lol-summoner/v1/summoners"
    
    # 移除不可见的 Unicode 控制字符 (如 U+206E, U+2069 等 Bidi 字符)
    # 同时保留 # 号用于 Riot ID 格式
    CLEANR = re.compile(r'[\u200e-\u200f\u202a-\u202e\u2066-\u2069]')
    cleaned_name = re.sub(CLEANR, '', summoner_name).strip() 

    # 使用 make_request 发送请求
    data = make_request(
        "GET",
        endpoint,
        token,
        port,
        params={'name': cleaned_name}  # 使用查询参数传递清洗后的名称
    )
    
    if data:
        # Riot ID 查询返回的是一个包含 puuid 的字典
        puuid = data.get('puuid')
        if puuid:
            # 缓存结果
            _puuid_cache[summoner_name] = (time.time(), puuid)
            logger.debug(f"✅ 查询PUUID成功 ({summoner_name})")
        return puuid
    return None


def get_summoner_by_id(token, port, summoner_id):
    """
    通过 summonerId 获取召唤师信息。
    
    Args:
        token: LCU认证令牌
        port: LCU端口
        summoner_id: 召唤师ID
    
    Returns:
        dict: 召唤师信息
    """
    endpoint = f"/lol-summoner/v1/summoners/{summoner_id}"
    return make_request("GET", endpoint, token, port)


def get_summoner_by_puuid(token, port, puuid):
    """
    通过 puuid 获取召唤师信息。
    
    Args:
        token: LCU认证令牌
        port: LCU端口
        puuid: 玩家PUUID
    
    Returns:
        dict: 召唤师信息
    """
    endpoint = f"/lol-summoner/v1/summoners/by-puuid/{puuid}"
    return make_request("GET", endpoint, token, port)


def get_summoner_by_name(token, port, name):
    """
    通过召唤师名字查询完整信息。
    
    使用 ?name= 查询参数，LCU 返回字典格式。
    
    Args:
        token: LCU认证令牌
        port: LCU端口
        name: 召唤师名称
    
    Returns:
        dict: 召唤师信息
    """
    endpoint = "/lol-summoner/v1/summoners"
    return make_request("GET", endpoint, token, port, params={'name': name})


def _normalize_ranked_payload(payload, endpoint_tag):
    """将不同端点返回的数据统一为包含 queues 列表的字典。"""
    if not payload:
        return None

    # 直接返回带有 queues 的字典
    if isinstance(payload, dict) and isinstance(payload.get('queues'), list) and payload['queues']:
        normalized = dict(payload)
        normalized['dataSource'] = endpoint_tag
        return normalized

    queues = []
    normalized_payload = None

    if isinstance(payload, dict):
        normalized_payload = dict(payload)

        queue_map = normalized_payload.get('queueMap')
        if isinstance(queue_map, dict):
            queues.extend([v for v in queue_map.values() if isinstance(v, dict)])

        queue_summaries = normalized_payload.get('queueSummaries')
        if isinstance(queue_summaries, list):
            queues.extend([q for q in queue_summaries if isinstance(q, dict)])

        entries = normalized_payload.get('entries')
        if isinstance(entries, list):
            queues.extend([q for q in entries if isinstance(q, dict)])

        if queues:
            normalized_payload['queues'] = queues
            normalized_payload['dataSource'] = endpoint_tag
            return normalized_payload

    elif isinstance(payload, list):
        queues = [q for q in payload if isinstance(q, dict)]
        if queues:
            return {
                'queues': queues,
                'dataSource': endpoint_tag,
                'raw': payload
            }

    return None


def get_ranked_stats(token, port, summoner_id=None, puuid=None):
    """获取召唤师排位信息（支持按 PUUID 或 summonerId 查询）。"""
    endpoints = []

    if puuid:
        endpoints.append((f"/lol-ranked/v1/ranked-stats/{puuid}", "lol-ranked/v1/ranked-stats/puuid"))
        endpoints.append((f"/lol-ranked/v1/ranked-stats/by-puuid/{puuid}", "lol-ranked/v1/ranked-stats/by-puuid-legacy"))

    if summoner_id:
        endpoints.extend([
            (f"/lol-ranked/v1/ranked-stats/{summoner_id}", "lol-ranked/v1/ranked-stats/by-id"),
            (f"/lol-ranked/v2/summoner/{summoner_id}", "lol-ranked/v2/summoner"),
            (f"/lol-league/v1/entries/by-summoner/{summoner_id}", "lol-league/v1/entries/by-summoner"),
            (f"/lol-league/v1/positions/by-summoner/{summoner_id}", "lol-league/v1/positions/by-summoner"),
        ])

    if not endpoints:
        return {}

    for endpoint, tag in endpoints:
        payload = make_request("GET", endpoint, token, port)
        normalized = _normalize_ranked_payload(payload, tag)
        if normalized:
            if 'raw' not in normalized:
                normalized['raw'] = payload
            return normalized

    return {}

