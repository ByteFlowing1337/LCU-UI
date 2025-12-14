"""
LCU HTTP 客户端模块
提供统一的 LCU API 请求封装
"""
import json
import requests
from requests.auth import HTTPBasicAuth
import urllib3

from utils.logger import logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def make_request(method, endpoint, token, port, **kwargs):
    """
    统一的 LCU API 请求封装，处理认证和 SSL 验证。
    
    Args:
        method: HTTP方法 ('GET', 'POST', 'PUT', 'DELETE' 等)
        endpoint: API端点路径（如 '/lol-summoner/v1/current-summoner'）
        token: 认证令牌
        port: LCU端口
        **kwargs: 其他请求参数（可包含自定义timeout、params、json等）
    
    Returns:
        dict: 响应JSON数据，失败返回None
    
    Examples:
        >>> make_request('GET', '/lol-gameflow/v1/gameflow-phase', token, port)
        >>> make_request('POST', '/lol-matchmaking/v1/ready-check/accept', token, port)
        >>> make_request('GET', '/lol-summoner/v1/summoners', token, port, params={'name': 'Faker'})
    """
    url = f"https://127.0.0.1:{port}{endpoint}"
    # LCU 认证要求使用 HTTPBasicAuth，用户名是 'riot'
    auth = HTTPBasicAuth('riot', token) 
    
    # 🔇 减少日志噪音：仅在详细模式下打印（通过环境变量控制）
    # logger.debug(f"--- LCU Request: {method} {endpoint} ---")
    
    # 处理 JSON 数据：将 json 参数转换为 data + Content-Type
    if 'json' in kwargs:
        kwargs['data'] = json.dumps(kwargs.pop('json'))
        kwargs['headers'] = kwargs.get('headers', {})
        kwargs['headers']['Content-Type'] = 'application/json'

    # 动态timeout：如果没有指定，则使用默认值5秒
    # 大数据量查询（如战绩）会在调用时传入更大的timeout
    if 'timeout' not in kwargs:
        kwargs['timeout'] = 5

    try:
        response = requests.request(
            method,
            url,
            auth=auth,
            verify=False,  # 忽略SSL证书错误
            **kwargs
        )
        
        # 抛出 HTTPError 异常，处理 4xx/5xx 状态码
        response.raise_for_status() 

        if response.status_code == 204:  # No Content
            return None
        
        return response.json()
        
    except requests.exceptions.HTTPError as e:
        # 🔇 静默处理404错误（端点尝试时很常见），只记录其他错误
        if e.response.status_code != 404:
            # Print full URL to help diagnose path/encoding issues
            logger.warning(f"⚠️ LCU API 错误 ({method} {endpoint}) -> URL: {url} : {e.response.status_code} {e.response.reason}")
            
            # 打印 403 错误的详细信息
            if e.response.status_code == 403:
                logger.warning("!!! 权限拒绝 (403 Forbidden) !!! 可能原因: LCU 客户端限制或当前游戏状态不允许查询。")
        
        return None
        
    except requests.exceptions.RequestException as e:
        # 🔇 忽略连接拒绝错误（通常是因为客户端未启动或正在重启），避免刷屏
        error_str = str(e)
        if "WinError 10061" in error_str or "Connection refused" in error_str:
            return None

        # 处理其他请求异常（如连接超时、DNS 错误）
        logger.warning(f"⚠️ LCU API 请求异常 ({method} {endpoint}) -> URL: {url} : {e}")
        return None
