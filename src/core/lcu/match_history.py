"""
战绩查询 API（面向对象）
"""
import time
import requests
from urllib.parse import quote_plus
from utils.logger import logger


CACHE_TTL = 300
MAX_CACHE_SIZE = 100


class MatchHistoryAPI:
    def __init__(self, client):
        self.client = client
        self._cache = {}

    def _clean_cache(self):
        current_time = time.time()
        expired_keys = [k for k, (t, _) in self._cache.items() if current_time - t > CACHE_TTL]
        for k in expired_keys:
            self._cache.pop(k, None)

        if len(self._cache) > MAX_CACHE_SIZE:
            sorted_items = sorted(self._cache.items(), key=lambda x: x[1][0])
            for k, _ in sorted_items[:len(self._cache) - MAX_CACHE_SIZE]:
                self._cache.pop(k, None)

    def get_match_history(self, puuid, count=20, begin_index=0):
        self._clean_cache()

        full_cache_key = f"{puuid}_full"
        sliced_cache_key = f"{puuid}_{begin_index}_{count}"

        if sliced_cache_key in self._cache:
            cached_time, cached_data = self._cache[sliced_cache_key]
            if time.time() - cached_time < CACHE_TTL:
                logger.debug(f"✅ 使用切片缓存 (begin={begin_index}, count={count})")
                return cached_data

        all_games = None
        if full_cache_key in self._cache:
            cached_time, cached_games = self._cache[full_cache_key]
            if time.time() - cached_time < CACHE_TTL:
                logger.debug(f"✅ 使用完整数据缓存 (共 {len(cached_games)} 场)")
                all_games = cached_games

        if all_games is None:
            endpoint = f"/lol-match-history/v1/products/lol/{quote_plus(puuid)}/matches"
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

            for idx, profile in enumerate(attempt_profiles):
                params = {'begIndex': 0, 'endIndex': profile['endIndex']}
                timeout = profile['timeout']
                logger.debug(f"📊 请求 {profile['endIndex']} 场历史记录 (profile={profile['desc']}, timeout={timeout}s)...")

                result = self.client.request(
                    "GET",
                    endpoint,
                    params=params,
                    timeout=timeout
                )

                if not result:
                    direct_timeout = min(timeout + 6, 28)
                    url = f"{self.client.base_url}{endpoint}"
                    try:
                        logger.warning(f"⏳ 统一请求无响应，尝试直接请求 (timeout={direct_timeout}s)...")
                        resp = self.client.session.get(
                            url,
                            params=params,
                            timeout=direct_timeout,
                            verify=False
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

                    self._cache[full_cache_key] = (time.time(), all_games)
                    break

            if all_games is None:
                return None

        sliced_games = all_games[begin_index:begin_index + count]

        logger.debug(f"📊 从 {len(all_games)} 场中切片，取第 {begin_index+1}-{begin_index+len(sliced_games)} 场")
        if sliced_games:
            logger.debug(f"   第一场: gameId={sliced_games[0].get('gameId', 'N/A')}")
            if len(sliced_games) > 1:
                logger.debug(f"   最后一场: gameId={sliced_games[-1].get('gameId', 'N/A')}")

        sliced_result = {
            'games': {
                'games': sliced_games
            }
        }

        self._cache[sliced_cache_key] = (time.time(), sliced_result)
        logger.debug(f"✅ 返回 {len(sliced_games)} 场比赛")

        return sliced_result

    def get_tft_match_history(self, puuid, count=20):
        self._clean_cache()
        cache_key = f"tft_{puuid}_{count}"
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if time.time() - cached_time < CACHE_TTL:
                logger.debug(f"✅ 使用缓存数据 (TFT PUUID={puuid[:8]}..., count={count})")
                return cached_data

        timeout = min(8 + (count // 20) * 2, 25)
        logger.debug(f"📊 查询 TFT {count} 场战绩，预计timeout={timeout}秒")

        url = f"{self.client.base_url}/lol-match-history/v1/products/tft/{quote_plus(puuid)}/matches?begin=0&count={count}"

        max_retries = 2
        for attempt in range(max_retries):
            try:
                resp = self.client.session.get(url, verify=False, timeout=timeout)
                logger.debug(f"📡 TFT 请求响应: {resp.status_code}")

                if resp.status_code == 200:
                    data = resp.json()
                    normalized = self._normalize_tft_response(data)
                    self._cache[cache_key] = (time.time(), normalized)

                    games_count = self._get_games_count(normalized)
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

    @staticmethod
    def _normalize_tft_response(data):
        if isinstance(data, list):
            return {'games': {'games': data}}
        elif isinstance(data, dict):
            if 'games' in data and isinstance(data['games'], list):
                return {'games': {'games': data['games']}}
            elif 'games' in data and isinstance(data['games'], dict) and 'games' in data['games']:
                return data
        return {'games': {'games': []}}

    @staticmethod
    def _get_games_count(normalized):
        try:
            g = normalized.get('games', {})
            if isinstance(g, dict):
                return len(g.get('games', []))
        except Exception:
            pass
        return 0

    def get_match_by_id(self, match_id):
        candidates = [
            f"/lol-match-history/v1/games/{match_id}",
        ]

        for ep in candidates:
            try:
                res = self.client.request("GET", ep, timeout=3)
                if res:
                    logger.debug(f"✅ 获取对局成功 (match_id={match_id})")
                    return res
            except Exception:
                continue

        logger.warning(f"❌ 无法通过任何已知 LCU 端点获取 match_id={match_id}")
        return None
