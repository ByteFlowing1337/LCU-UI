"""
LCU HTTP 客户端模块 
提供统一的 LCU API 请求封装，支持 Session 复用
"""
import json
import requests
from requests.auth import HTTPBasicAuth
import urllib3

from utils.logger import logger

# 禁用警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class LCUClient:
    """轻量 LCU HTTP 客户端，基于 Session 复用连接。"""

    def __init__(self, token, port):
        self.token = token
        self.port = port
        self.base_url = f"https://127.0.0.1:{port}"

        # Session 维持 TCP 连接，适合高频轮询
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth('riot', token)
        self.session.verify = False
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

    def request(self, method, endpoint, **kwargs):
        """发送请求，自动处理 JSON 与超时。"""
        url = f"{self.base_url}{endpoint}"

        if 'json' in kwargs:
            kwargs['data'] = json.dumps(kwargs.pop('json'))

        kwargs.setdefault('timeout', 5)

        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()

            if response.status_code == 204:
                return None

            return response.json()

        except requests.exceptions.HTTPError as e:
            if e.response.status_code != 404:
                logger.warning(f"⚠️ LCU API Error ({method} {endpoint}) -> {e.response.status_code} {e.response.reason}")
                if e.response.status_code == 403:
                    logger.warning("!!! 403 Forbidden - Client state restriction.")
            return None

        except requests.exceptions.RequestException as e:
            error_str = str(e)
            if "WinError 10061" in error_str or "Connection refused" in error_str:
                return None
            logger.warning(f"⚠️ LCU Network Error: {e}")
            return None

    def get_raw_session(self):
        """暴露底层 Session，便于少数需要自定义超时的场景。"""
        return self.session

