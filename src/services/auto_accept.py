"""
自动接受对局服务
"""
import time
from config import app_state
from core import lcu

from utils.logger import logger


def auto_accept_task(socketio):
    """
    自动接受对局的后台任务
    
    Args:
        socketio: Flask-SocketIO实例，用于发送消息到前端
    """
    last_phase = None
    accepted_this_phase = False

    try:
        while app_state.auto_accept_enabled:
            if not app_state.is_lcu_connected():
                time.sleep(0.5)
                continue

            try:
                token = app_state.lcu_credentials["auth_token"]
                port = app_state.lcu_credentials["app_port"]

                phase = lcu.get_gameflow_phase(token, port)

                # 状态重置逻辑：当阶段发生变化时
                if phase != last_phase:
                    last_phase = phase
                    # 如果离开了 ReadyCheck 阶段，重置接受标志
                    if phase != "ReadyCheck":
                        accepted_this_phase = False

                # ReadyCheck 阶段：自动接受对局
                if phase == "ReadyCheck" and not accepted_this_phase:
                    try:
                        lcu.accept_ready_check(token, port)
                        socketio.emit('status_update', {'type': 'biz', 'message': '✅ 已自动接受对局!'})
                        logger.info("✅ 自动接受对局成功")
                        accepted_this_phase = True
                    except Exception as accept_error:
                        # 如果接受失败，可能还需要重试，所以不设置 accepted_this_phase = True
                        # 但为了避免刷屏，可以控制错误日志的频率（这里暂不处理，假设失败是少数情况）
                        logger.warning(f"⚠️ 自动接受对局失败: {accept_error}")
                        socketio.emit('status_update', {'type': 'biz', 'message': f'⚠️ 自动接受失败: {accept_error}'})
                        time.sleep(1) # 失败后稍作等待

            except Exception as e:
                logger.error(f"❌ 自动接受任务异常: {e}")

            time.sleep(1)
    finally:
        app_state.auto_accept_thread = None
        app_state.auto_accept_enabled = False
        logger.info("🛑 自动接受任务已退出")
