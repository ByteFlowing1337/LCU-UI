"""
自动 Ban/Pick 服务
在英雄选择阶段自动执行 ban 和 pick 操作。
"""
import time
from config import app_state
from core import lcu


def _get_banned_and_picked_ids(session):
    """提取已被禁用和已被选取的英雄ID集合。"""
    banned_ids = set()
    picked_ids = set()

    for team in session.get('teams', []):
        for ban in team.get('bans', []):
            cid = ban.get('championId')
            if cid:
                banned_ids.add(cid)

    for action_group in session.get('actions', []):
        if not isinstance(action_group, list):
            continue
        for action in action_group:
            cid = action.get('championId')
            if cid and action.get('completed'):
                picked_ids.add(cid)

    return banned_ids, picked_ids


def _get_candidates(ban_champion_id, pick_champion_id):
    """构造 Ban/Pick 的候选列表（主目标优先，其次全局候选）。"""
    ban_candidates = []
    pick_candidates = []

    if ban_champion_id:
        ban_candidates.append(ban_champion_id)
    ban_candidates.extend(getattr(app_state, 'ban_candidate_ids', []) or [])

    if pick_champion_id:
        pick_candidates.append(pick_champion_id)
    pick_candidates.extend(getattr(app_state, 'pick_candidate_ids', []) or [])

    return ban_candidates, pick_candidates


def complete_action(client, action_id, champion_id, action_type='pick'):
    """完成一个选人/禁用动作。"""
    endpoint = f"/lol-champ-select/v1/session/actions/{action_id}"

    session = client.get_champ_select_session()
    if not session:
        return False

    actions = session.get("actions", [])
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

    response = client.client.request("PATCH", endpoint, json=payload)
    return response is not None


def hover_champion(client, action_id, champion_id):
    """仅预选英雄（不提交）。"""
    endpoint = f"/lol-champ-select/v1/session/actions/{action_id}"
    payload = {
        "championId": champion_id,
        "completed": False,
    }
    return client.client.request("PATCH", endpoint, json=payload)


def auto_banpick_task(socketio, ban_champion_id=None, pick_champion_id=None):
    """后台任务：在 ChampSelect 阶段自动 Ban/Pick。"""
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
                client = lcu.get_client()

                phase = client.get_gameflow_phase()

                if phase == "ChampSelect":
                    if phase != last_phase:
                        socketio.emit('status_update', {
                            'type': 'biz',
                            'message': '🎮 进入英雄选择阶段，准备自动 Ban/Pick'
                        })
                        last_phase = phase
                        ban_done = False
                        pick_done = False

                    session = client.get_champ_select_session()
                    if not session:
                        time.sleep(0.5)
                        continue

                    local_player_cell_id = session.get('localPlayerCellId')
                    if local_player_cell_id is None:
                        time.sleep(0.5)
                        continue

                    banned_ids, picked_ids = _get_banned_and_picked_ids(session)
                    ban_candidates, pick_candidates = _get_candidates(app_state.ban_champion_id, app_state.pick_champion_id)

                    actions = session.get('actions', [])
                    for action_group in actions:
                        if not isinstance(action_group, list):
                            continue
                        for action in action_group:
                            if action.get('actorCellId') != local_player_cell_id:
                                continue

                            action_id = action.get('id')
                            action_type = (action.get('type') or '').lower()
                            is_in_progress = action.get('isInProgress', False)
                            completed = action.get('completed', False)

                            if completed or not is_in_progress:
                                continue

                            if action_type == 'ban' and not ban_done and ban_candidates:
                                for cid in ban_candidates:
                                    if not cid or cid in banned_ids or cid in picked_ids:
                                        continue
                                    if complete_action(client, action_id, cid, action_type='ban'):
                                        ban_done = True
                                        app_state.ban_champion_id = cid
                                        socketio.emit('status_update', {
                                            'type': 'success',
                                            'message': f'✅ 已自动禁用英雄 (ID: {cid})'
                                        })
                                        break

                            elif action_type == 'pick' and not pick_done and pick_candidates:
                                for cid in pick_candidates:
                                    if not cid or cid in banned_ids or cid in picked_ids:
                                        continue
                                    if complete_action(client, action_id, cid, action_type='pick'):
                                        pick_done = True
                                        app_state.pick_champion_id = cid
                                        socketio.emit('status_update', {
                                            'type': 'success',
                                            'message': f'✅ 已自动选择英雄 (ID: {cid})'
                                        })
                                        break

                elif phase != "ChampSelect" and last_phase == "ChampSelect":
                    last_phase = phase
                    ban_done = False
                    pick_done = False
                    socketio.emit("status_update", {
                        "type": "auto_banpick_stopped",
                        "message": "自动 Ban/Pick 已结束（离开英雄选择阶段）",
                    })

            except Exception as e:
                print(f"❌ 自动 Ban/Pick 任务异常: {e}")

            time.sleep(0.5)

    finally:
        app_state.auto_banpick_thread = None
        app_state.auto_banpick_enabled = False
        print("🛑 自动 Ban/Pick 任务已退出")
