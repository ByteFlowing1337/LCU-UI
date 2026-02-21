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
    accepted_this_phase = False
    client = lcu.get_client()
    phase = client.get_gameflow_phase()

    # 循环监测游戏流程阶段
    while app_state.auto_accept_enabled:
        # 如果离开了 ReadyCheck 阶段，重置接受标志
        if phase != "ReadyCheck":
            accepted_this_phase = False

        # ReadyCheck 阶段：自动接受对局
        if phase == "ReadyCheck" and not accepted_this_phase:
                client.accept_ready_check()
                socketio.emit('status_update', {'type': 'biz', 'message': '✅ 已自动接受对局!'})
                logger.info("✅ 自动接受对局成功")
                accepted_this_phase = True
        time.sleep(1)
        phase = client.get_gameflow_phase()