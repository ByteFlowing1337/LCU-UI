"""
敌我分析服务
"""
import time
from config import app_state
from core import lcu
from utils.logger import logger



def _get_player_rank_info(token, port, puuid):
    """
    获取玩家的段位信息
    
    Args:
        token: LCU认证令牌
        port: LCU端口
        puuid: 玩家PUUID
    
    Returns:
        dict: 包含段位信息的字典
    """
    try:
        ranked_stats = lcu.get_ranked_stats(token, port, puuid=puuid)
        if not ranked_stats or not isinstance(ranked_stats, dict):
            return {'tier': 'UNRANKED', 'division': '', 'lp': 0}
        
        queues = ranked_stats.get('queues', [])
        if not queues:
            return {'tier': 'UNRANKED', 'division': '', 'lp': 0}
        
        # 查找单双排段位
        solo_queue = None
        for queue in queues:
            queue_type = str(queue.get('queueType') or queue.get('queue') or queue.get('type') or '').upper()
            if queue_type in ['RANKED_SOLO_5X5', 'RANKED_SOLO', 'SOLO']:
                solo_queue = queue
                break
        
        if solo_queue:
            tier = solo_queue.get('tier', 'UNRANKED')
            division = solo_queue.get('division', '')
            lp = solo_queue.get('leaguePoints', 0)
            
            # 处理特殊段位（大师、宗师、王者没有division）
            if tier in ['MASTER', 'GRANDMASTER', 'CHALLENGER']:
                division = ''
            
            return {
                'tier': tier,
                'division': division,
                'lp': lp
            }
        
        return {'tier': 'UNRANKED', 'division': '', 'lp': 0}
    except Exception as e:
        logger.warning(f"⚠️ 获取段位信息失败: {str(e)}")
        return {'tier': 'UNRANKED', 'division': '', 'lp': 0}


def auto_analyze_task(socketio):
    """
    敌我分析的后台任务
    
    Args:
        socketio: Flask-SocketIO实例，用于发送消息到前端
    """
    enemy_retry_count = 0
    MAX_ENEMY_RETRIES = 10
    last_phase = None

    try:
        while app_state.auto_analyze_enabled:
            if not app_state.is_lcu_connected():
                time.sleep(2)
                continue

            phase = None

            try:
                token = app_state.lcu_credentials["auth_token"]
                port = app_state.lcu_credentials["app_port"]

                phase = lcu.get_gameflow_phase(token, port)

                # 检测到新的游戏流程开始，重置状态
                if last_phase in ["Lobby", "None", None] and phase not in ["Lobby", "None"]:
                    app_state.reset_analysis_state()
                    enemy_retry_count = 0
                    logger.info(f"🔄 检测到新游戏流程开始 ({last_phase} -> {phase})，重置分析状态")

                # ChampSelect 阶段：分析队友战绩
                elif phase == "ChampSelect" and not app_state.teammate_analysis_done:
                    _analyze_teammates(token, port, socketio)

                # InProgress/GameStart 阶段：分析敌人战绩
                elif phase in ["InProgress", "GameStart"] and not app_state.enemy_analysis_done:
                    if enemy_retry_count < MAX_ENEMY_RETRIES:
                        enemy_retry_count += 1
                        success = _analyze_enemies(token, port, socketio, enemy_retry_count, MAX_ENEMY_RETRIES)
                        if not success:
                            time.sleep(3)  # 失败后等待3秒重试
                    else:
                        # 达到最大重试次数
                        socketio.emit('status_update', {'type': 'biz', 'message': '❌ 无法获取敌方信息，已停止重试'})
                        app_state.enemy_analysis_done = True
                        logger.error(f"❌ 达到最大重试次数 ({MAX_ENEMY_RETRIES})，停止尝试")

                # EndOfGame 阶段：显示提示
                elif phase == "EndOfGame":
                    # 只在刚进入 EndOfGame 时提示一次
                    if last_phase != "EndOfGame":
                        if app_state.teammate_analysis_done or app_state.enemy_analysis_done:
                            socketio.emit('status_update', {'type': 'biz', 'message': '🏁 比赛结束，等待下一局...'})
                            logger.info("🏁 游戏结束")

                # 更新上一次的阶段
                last_phase = phase

            except Exception as e:
                error_msg = f'敌我分析任务出错: {str(e)}'
                socketio.emit('status_update', {'type': 'biz', 'message': f'❌ {error_msg}'})
                logger.error(f"❌ 异常: {error_msg}")
                time.sleep(5)
                continue

            if not app_state.auto_analyze_enabled:
                break

            # 循环等待时间
            if phase in ["InProgress", "GameStart"] and not app_state.enemy_analysis_done:
                time.sleep(1)
            else:
                time.sleep(2)
    finally:
        app_state.auto_analyze_thread = None
        app_state.auto_analyze_enabled = False
        logger.info("🛑 敌我分析任务已退出")


def _analyze_teammates(token, port, socketio):
    """
    分析队友战绩（ChampSelect阶段）
    
    Args:
        token: LCU认证令牌
        port: LCU端口
        socketio: SocketIO实例
    """
    session = lcu.get_champ_select_session(token, port)
    if session:
        teammates = []
        for team_member in session.get('myTeam', []):
            puuid = team_member.get('puuid')
            if puuid:
                app_state.current_teammates.add(puuid)  # 记录队友PUUID
                
                # 获取段位信息
                rank_info = _get_player_rank_info(token, port, puuid)
                
                teammates.append({
                    'gameName': team_member.get('gameName', '未知'),
                    'tagLine': team_member.get('tagLine', ''),
                    'puuid': puuid,
                    'rank': rank_info
                })
        
        if teammates:
            socketio.emit('teammates_found', {'teammates': teammates})
            socketio.emit('status_update', {'type': 'biz', 'message': f'👥 发现 {len(teammates)} 名队友，开始分析战绩...'})
            app_state.teammate_analysis_done = True
            logger.info(f"✅ 队友分析完成，共 {len(teammates)} 人")
            logger.info(f"📝 记录队友PUUID集合: {len(app_state.current_teammates)} 人")


def _ensure_teammates_from_live_game(token, port, socketio, players_data):
    """在游戏已开始但未进行队友分析时，从实时对局数据填充队友信息。"""
    if app_state.teammate_analysis_done:
        return

    teammate_entries = (players_data or {}).get('teammates') or []
    if not teammate_entries:
        return

    teammates = []
    for entry in teammate_entries:
        puuid = entry.get('puuid')
        if not puuid:
            continue

        app_state.current_teammates.add(puuid)
        rank_info = _get_player_rank_info(token, port, puuid)
        teammates.append({
            'gameName': entry.get('gameName') or entry.get('summonerName', '未知'),
            'tagLine': entry.get('tagLine', ''),
            'puuid': puuid,
            'rank': rank_info
        })

    if teammates:
        socketio.emit('teammates_found', {'teammates': teammates})
        socketio.emit('status_update', {'type': 'biz', 'message': f'👥 发现 {len(teammates)} 名队友，开始分析战绩...'})
        app_state.teammate_analysis_done = True
        logger.info(f"✅ (实时) 队友分析完成，共 {len(teammates)} 人")
        logger.info(f"📝 记录队友PUUID集合: {len(app_state.current_teammates)} 人")


def _analyze_enemies(token, port, socketio, retry_count, max_retries):
    """
    分析敌人战绩（InProgress阶段）
    
    Args:
        token: LCU认证令牌
        port: LCU端口
        socketio: SocketIO实例
        retry_count: 当前重试次数
        max_retries: 最大重试次数
    
    Returns:
        bool: 是否成功
    """
    socketio.emit('status_update', {'type': 'biz', 'message': f'🔍 正在获取敌方信息... (尝试 {retry_count}/{max_retries})'})
    logger.info(f"开始第 {retry_count} 次尝试获取敌方信息")
    
    # 调用API获取所有玩家（通过team字段区分敌我：ORDER vs CHAOS）
    players_data = lcu.get_all_players_from_game(token, port)
    
    if players_data:
        # 如果之前未能在 ChampSelect 阶段获取队友，此处补发
        _ensure_teammates_from_live_game(token, port, socketio, players_data)

        enemies = players_data.get('enemies', [])
        
        # 双重过滤：排除队友PUUID
        if app_state.current_teammates:
            filtered_enemies = []
            for enemy in enemies:
                if enemy.get('puuid') and enemy['puuid'] not in app_state.current_teammates:
                    filtered_enemies.append(enemy)
                elif enemy.get('puuid') in app_state.current_teammates:
                    logger.info(f"🚫 过滤队友: {enemy.get('summonerName', '未知')}")
            enemies = filtered_enemies
        
        # 为每个敌人添加段位信息
        for enemy in enemies:
            puuid = enemy.get('puuid')
            if puuid:
                rank_info = _get_player_rank_info(token, port, puuid)
                enemy['rank'] = rank_info
        
        if len(enemies) > 0:
            socketio.emit('enemies_found', {'enemies': enemies})
            socketio.emit('status_update', {'type': 'biz', 'message': f'💥 发现 {len(enemies)} 名敌人，开始分析战绩...'})
            app_state.enemy_analysis_done = True
            logger.info(f"✅ 敌人分析完成，共 {len(enemies)} 人")
            return True
        else:
            logger.warning(f"⚠️ 第 {retry_count} 次尝试：过滤后无敌人数据")
            return False
    else:
        logger.warning(f"⚠️ 第 {retry_count} 次尝试：未获取到游戏数据")
        return False
