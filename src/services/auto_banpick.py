"""
自动 Ban/Pick 服务
在英雄选择阶段自动执行 ban 和 pick 操作
"""
import time
from config import app_state
from core import lcu


def _get_banned_and_picked_ids(session):
    """获取已被禁用和已被选取的英雄ID集合"""
    banned_ids = set()
    picked_ids = set()

    for team in session.get('teams', []):
        for ban in team.get('bans', []):
            cid = ban.get('championId')
            if cid:
                banned_ids.add(cid)

    actions = session.get('actions', [])
    for action_group in actions:
        if not isinstance(action_group, list):
            continue
        for a in action_group:
            cid = a.get('championId')
            if cid and a.get('completed'):
                picked_ids.add(cid)
    
    return banned_ids, picked_ids


def _get_candidates(ban_champion_id, pick_champion_id):
    """获取 Ban 和 Pick 的候选英雄列表"""
    ban_candidates = []
    pick_candidates = []
    
    if ban_champion_id:
        ban_candidates.append(ban_champion_id)
    ban_candidates.extend(getattr(app_state, 'ban_candidate_ids', []) or [])

    if pick_champion_id:
        pick_candidates.append(pick_champion_id)
    pick_candidates.extend(getattr(app_state, 'pick_candidate_ids', []) or [])
    
    return ban_candidates, pick_candidates


def _try_ban_champion(socketio, token, port, action_id, candidates, unavailable_ids):
    """尝试自动禁用英雄"""
    for cid in candidates:
        if not cid or cid in unavailable_ids:
            continue
        try:
            success = complete_action(token, port, action_id, cid, action_type='ban')
            if success:
                app_state.ban_champion_id = cid
                socketio.emit('status_update', {
                    'type': 'success',
                    'message': f'✅ 已自动禁用英雄 (ID: {cid})'
                })
                print(f"✅ 自动禁用英雄成功: {cid}")
                return True
        except Exception as e:
            print(f"⚠️ 自动禁用英雄失败: {e}")
            socketio.emit('status_update', {
                'type': 'warning',
                'message': f'⚠️ 自动禁用失败: {e}'
            })
    return False


def _try_pick_champion(socketio, token, port, action_id, candidates, unavailable_ids):
    """尝试自动选择英雄"""
    for cid in candidates:
        if not cid or cid in unavailable_ids:
            continue
        try:
            success = complete_action(token, port, action_id, cid, action_type='pick')
            if success:
                app_state.pick_champion_id = cid
                socketio.emit('status_update', {
                    'type': 'success',
                    'message': f'✅ 已自动选择英雄 (ID: {cid})'
                })
                print(f"✅ 自动选择英雄成功: {cid}")
                return True
        except Exception as e:
            print(f"⚠️ 自动选择英雄失败: {e}")
            socketio.emit('status_update', {
                'type': 'warning',
                'message': f'⚠️ 自动选择失败: {e}'
            })
    return False


def auto_banpick_task(socketio, ban_champion_id=None, pick_champion_id=None):
    """
    自动 Ban/Pick 的后台任务
    
    Args:
        socketio: Flask-SocketIO实例，用于发送消息到前端
        ban_champion_id: 要禁用的英雄ID（可选）
        pick_champion_id: 要选择的英雄ID（可选）
    """
    try:
        last_phase = None
        ban_done = False
        pick_done = False
        
        while app_state.auto_banpick_enabled:
            if not app_state.is_lcu_connected():
                time.sleep(0.5)
                continue

            try:
                token = app_state.lcu_credentials["auth_token"]
                port = app_state.lcu_credentials["app_port"]

                phase = lcu.get_gameflow_phase(token, port)

                # ChampSelect 阶段：自动 ban/pick
                if phase == "ChampSelect":
                    if phase != last_phase:
                        print("🎮 进入英雄选择阶段")
                        socketio.emit('status_update', {
                            'type': 'biz', 
                            'message': '🎮 进入英雄选择阶段，准备自动 Ban/Pick'
                        })
                        last_phase = phase
                        ban_done = False
                        pick_done = False
                    
                    # 获取选人会话数据
                    session = lcu.get_champ_select_session(token, port)
                    if not session:
                        time.sleep(0.5)
                        continue
                    
                    # 获取本地玩家的 cellId
                    local_player_cell_id = session.get('localPlayerCellId')
                    if local_player_cell_id is None:
                        time.sleep(0.5)
                        continue
                    
                    # 收集当前已被禁用/已被选中的英雄ID
                    banned_ids, picked_ids = _get_banned_and_picked_ids(session)

                    # 构建 Ban/Pick 候选列表
                    ban_candidates, pick_candidates = _get_candidates(
                        app_state.ban_champion_id, 
                        app_state.pick_champion_id
                    )
                    
                    # 处理 actions
                    actions = session.get('actions', [])
                    # 收集当前已被禁用/已被选中的英雄ID，用于跳过不可用的候选
                    banned_ids = set()
                    picked_ids = set()

                    for team in session.get('teams', []):
                        for ban in team.get('bans', []):
                            cid = ban.get('championId')
                            if cid:
                                banned_ids.add(cid)

                    for action_group in actions:
                        if not isinstance(action_group, list):
                            continue
                        for a in action_group:
                            cid = a.get('championId')
                            if cid and a.get('completed'):
                                picked_ids.add(cid)

                    # 构建 Ban/Pick 候选列表（主目标优先，其次备选队列）
                    ban_candidates = []
                    pick_candidates = []
                    if ban_champion_id:
                        ban_candidates.append(ban_champion_id)
                    ban_candidates.extend(getattr(app_state, 'ban_candidate_ids', []) or [])

                    if pick_champion_id:
                        pick_candidates.append(pick_champion_id)
                    pick_candidates.extend(getattr(app_state, 'pick_candidate_ids', []) or [])
                    for action_group in actions:
                        if not isinstance(action_group, list):
                            continue
                        
                        for action in action_group:
                            if action.get('actorCellId') != local_player_cell_id:
                                continue
                            
                            action_id = action.get('id')
                            action_type = action.get('type', '').lower()
                            is_in_progress = action.get('isInProgress', False)
                            completed = action.get('completed', False)
                            
                            # 跳过已完成或未开始的动作
                            if completed or not is_in_progress:
                                continue
                            
                            # 自动 Ban：按候选顺序寻找第一个可用英雄
                            if action_type == 'ban' and not ban_done and ban_candidates:
                                for cid in ban_candidates:
                                    if not cid:
                                        continue
                                    if cid in banned_ids or cid in picked_ids:
                                        continue
                                    try:
                                        success = complete_action(
                                            token, port, action_id, cid,
                                            action_type='ban'
                                        )
                                        if success:
                                            ban_done = True
                                            app_state.ban_champion_id = cid
                                            socketio.emit('status_update', {
                                                'type': 'success',
                                                'message': f'✅ 已自动禁用英雄 (ID: {cid})'
                                            })
                                            print(f"✅ 自动禁用英雄成功: {cid}")
                                            break
                                    except Exception as e:
                                        print(f"⚠️ 自动禁用英雄失败: {e}")
                                        socketio.emit('status_update', {
                                            'type': 'warning',
                                            'message': f'⚠️ 自动禁用失败: {e}'
                                        })
                            
                            # 自动 Pick：按候选顺序寻找第一个可用英雄
                            elif action_type == 'pick' and not pick_done and pick_candidates:
                                for cid in pick_candidates:
                                    if not cid:
                                        continue
                                    if cid in banned_ids or cid in picked_ids:
                                        continue
                                    try:
                                        success = complete_action(
                                            token, port, action_id, cid,
                                            action_type='pick'
                                        )
                                        if success:
                                            pick_done = True
                                            app_state.pick_champion_id = cid
                                            socketio.emit('status_update', {
                                                'type': 'success',
                                                'message': f'✅ 已自动选择英雄 (ID: {cid})'
                                            })
                                            print(f"✅ 自动选择英雄成功: {cid}")
                                            break
                                    except Exception as e:
                                        print(f"⚠️ 自动选择英雄失败: {e}")
                                        socketio.emit('status_update', {
                                            'type': 'warning',
                                            'message': f'⚠️ 自动选择失败: {e}'
                                        })
                
                elif phase != "ChampSelect" and last_phase == "ChampSelect":
                    print("🏁 离开英雄选择阶段")
                    last_phase = phase
                    ban_done = False
                    pick_done = False
                    socketio.emit("status_update", {
                        "type": "auto_banpick_stopped",
                        "message": "自动 Ban/Pick 已结束（离开英雄选择阶段）",
})

            except Exception as e:
                print(f"❌ 自动 Ban/Pick 任务异常: {e}")

            time.sleep(0.5)  # 更快的轮询以确保及时响应
            
    finally:
        app_state.auto_banpick_thread = None
        app_state.auto_banpick_enabled = False
        print("🛑 自动 Ban/Pick 任务已退出")


def complete_action(token, port, action_id, champion_id, action_type='pick'):
    """
    完成一个选人/禁用动作
    
    Args:
        token: LCU认证令牌
        port: LCU端口
        action_id: 动作ID
        champion_id: 英雄ID
        action_type: 动作类型 ('ban' 或 'pick')
    
    Returns:
        bool: 是否成功
    """
    endpoint = f"/lol-champ-select/v1/session/actions/{action_id}"

    # LCU 要求完整的 TeamBuilderDirect-ChampSelectAction 结构，这里在原 action
    # 的基础上只覆盖 championId / completed / type，避免缺字段导致 500。
    action = lcu.get_champ_select_session(token, port)
    if not action:
        return False

    # 从当前 session 中找到对应 action 的完整数据
    actions = action.get("actions", [])
    found = None
    for group in actions:
        if not isinstance(group, list):
            continue
        for a in group:
            if a.get("id") == action_id:
                found = a
                break
        if found:
            break

    if not found:
        return False

    payload = {
        **found,
        "championId": champion_id,
        "completed": True,
        "type": action_type,
    }

    # core.lcu.client.make_request expects "json" keyword for JSON body
    response = lcu.make_request("PATCH", endpoint, token, port, json=payload)
    
    # 如果响应不为空且没有错误，认为成功
    return response is not None


def hover_champion(token, port, action_id, champion_id):
    """
    悬停（预选）一个英雄
    
    Args:
        token: LCU认证令牌
        port: LCU端口
        action_id: 动作ID
        champion_id: 英雄ID
    
    Returns:
        dict: 响应数据
    """
    endpoint = f"/lol-champ-select/v1/session/actions/{action_id}"

    payload = {
        "championId": champion_id,
        "completed": False,
    }

    return lcu.make_request("PATCH", endpoint, token, port, json=payload)
