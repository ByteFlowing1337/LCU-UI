"""
WebSocket事件处理模块
"""
import threading
from flask_socketio import emit
from config import app_state
from services import auto_accept_task, auto_analyze_task, auto_banpick_task
from core import lcu


class SocketIOMessageProxy:
    """用 Socket.IO 消息模拟 status_bar 的 showMessage 方法"""
    
    def __init__(self, socketio):
        self.socketio = socketio
    
    def showMessage(self, message):
        """发送状态消息到前端"""
        # Emit structured status: type 'lcu' for connection-related messages
        self.socketio.emit('status_update', {'type': 'lcu', 'message': message})
        print(f"[LCU连接] {message}")


def register_socket_events(socketio):
    """
    注册所有WebSocket事件处理器
    
    Args:
        socketio: Flask-SocketIO实例
    """
    thread_lock = threading.Lock()
    
    @socketio.on('connect')
    def handle_connect():
        """客户端连接事件"""
        print('浏览器客户端已连接，触发自动检测...')
        status_proxy = SocketIOMessageProxy(socketio)
        status_proxy.showMessage('已连接到本地服务器，开始自动检测LCU...')
        
        socketio.start_background_task(_detect_and_connect_lcu, socketio, status_proxy)
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """客户端断开连接事件"""
        print('浏览器客户端已断开连接')
        # 当检测到任一客户端断开时，通知其他已连接的客户端关闭页面。
        # 这会触发前端的 `server_shutdown` 处理器（尝试关闭窗口或显示提示）。
        try:
            socketio.emit('server_shutdown', {'reason': 'client_disconnect'})
            print('已向所有已连接客户端广播 server_shutdown')
        except Exception as e:
            print(f'广播 server_shutdown 失败: {e}')
        # 不重置功能开关，但清理线程状态标记
        # 这样如果用户刷新页面，重新连接后可以重新启动功能
    
    @socketio.on('start_auto_accept')
    def handle_start_auto_accept():
        """启动自动接受对局"""
        with thread_lock:
            # Require LCU connection before starting auto-accept
            if not app_state.is_lcu_connected():
                emit('status_update', {'type': 'biz', 'message': '无法启动自动接受：未连接到LCU'})
                print("❌ 尝试启动自动接受失败：LCU 未连接")
                return

            thread = app_state.auto_accept_thread
            if thread and not thread.is_alive():
                app_state.auto_accept_thread = None
                thread = None

            if thread and thread.is_alive():
                if app_state.auto_accept_enabled:
                    emit('status_update', {'type': 'biz', 'message': '自动接受功能已在运行中'})
                else:
                    app_state.auto_accept_enabled = True
                    emit('status_update', {'type': 'biz', 'message': '自动接受对局功能已重新开启'})
                    print("🎮 自动接受对局功能已重新激活现有线程")
            else:
                app_state.auto_accept_enabled = True
                app_state.auto_accept_thread = threading.Thread(
                    target=auto_accept_task,
                    args=(socketio,),
                    daemon=True
                )
                app_state.auto_accept_thread.start()
                emit('status_update', {'type': 'biz', 'message': '自动接受对局功能已开启'})
                print("🎮 自动接受对局功能已启动")

    
    @socketio.on('start_auto_analyze')
    def handle_start_auto_analyze():
        """启动敌我分析"""
        with thread_lock:
            # Require LCU connection before starting auto-analyze
            if not app_state.is_lcu_connected():
                emit('status_update', {'type': 'biz', 'message': '无法启动敌我分析：未连接到LCU'})
                print("❌ 尝试启动敌我分析失败：LCU 未连接")
                return

            thread = app_state.auto_analyze_thread
            if thread and not thread.is_alive():
                app_state.auto_analyze_thread = None
                thread = None

            if thread and thread.is_alive():
                if app_state.auto_analyze_enabled:
                    emit('status_update', {'type': 'biz', 'message': ' 敌我分析功能已在运行中'})
                else:
                    app_state.reset_analysis_state()
                    app_state.auto_analyze_enabled = True
                    emit('status_update', {'type': 'biz', 'message': ' 敌我分析功能已重新开启'})
                    print("🔍 敌我分析功能已重新激活现有线程")
            else:
                # 重置分析状态，允许重新分析
                app_state.reset_analysis_state()
                app_state.auto_analyze_enabled = True
                app_state.auto_analyze_thread = threading.Thread(
                    target=auto_analyze_task,
                    args=(socketio,),
                    daemon=True
                )
                app_state.auto_analyze_thread.start()
                emit('status_update', {'type': 'biz', 'message': ' 敌我分析功能已开启'})
                print("🔍 敌我分析功能已启动")
    
    @socketio.on('stop_auto_accept')
    def handle_stop_auto_accept():
        """停止自动接受对局"""
        with thread_lock:
            app_state.auto_accept_enabled = False
            emit('status_update', {'type': 'biz', 'message': ' 自动接受对局功能已停止'})
            print("🛑 自动接受对局功能已停止")
    
    @socketio.on('stop_auto_analyze')
    def handle_stop_auto_analyze():
        """停止敌我分析"""
        with thread_lock:
            app_state.auto_analyze_enabled = False
            app_state.reset_analysis_state()
            emit('status_update', {'type': 'biz', 'message': ' 敌我分析功能已停止'})
            print("🛑 敌我分析功能已停止")
    
    @socketio.on('start_auto_banpick')
    def handle_start_auto_banpick(data=None):
        """启动自动Ban/Pick"""
        with thread_lock:
            # Require LCU connection before starting auto-banpick
            if not app_state.is_lcu_connected():
                emit('status_update', {'type': 'biz', 'message': '❌ 无法启动自动Ban/Pick：未连接到LCU'})
                print("❌ 尝试启动自动Ban/Pick失败：LCU 未连接")
                return
            
            # Update champion IDs and candidate lists if provided
            if data:
                if 'ban_champion_id' in data:
                    app_state.ban_champion_id = data['ban_champion_id']
                if 'pick_champion_id' in data:
                    app_state.pick_champion_id = data['pick_champion_id']
                # 可选备选列表：按优先级顺序
                ban_candidates = data.get('ban_candidates')
                pick_candidates = data.get('pick_candidates')
                if isinstance(ban_candidates, list):
                    app_state.ban_candidate_ids = [cid for cid in ban_candidates if cid]
                if isinstance(pick_candidates, list):
                    app_state.pick_candidate_ids = [cid for cid in pick_candidates if cid]
            
            thread = app_state.auto_banpick_thread
            if thread and not thread.is_alive():
                app_state.auto_banpick_thread = None
                thread = None
            
            if thread and thread.is_alive():
                if app_state.auto_banpick_enabled:
                    emit('status_update', {'type': 'biz', 'message': ' 自动Ban/Pick功能已在运行中'})
                else:
                    app_state.auto_banpick_enabled = True
                    emit('status_update', {'type': 'biz', 'message': ' 自动Ban/Pick功能已重新开启'})
                    print("🎯 自动Ban/Pick功能已重新激活现有线程")
            else:
                app_state.auto_banpick_enabled = True
                app_state.auto_banpick_thread = threading.Thread(
                    target=auto_banpick_task,
                    args=(socketio,),
                    daemon=True
                )
                app_state.auto_banpick_thread.start()
                ban_msg = f"Ban: {app_state.ban_champion_id}" if app_state.ban_champion_id else "未设置"
                pick_msg = f"Pick: {app_state.pick_champion_id}" if app_state.pick_champion_id else "未设置"
                emit('status_update', {'type': 'biz', 'message': f' 自动Ban/Pick功能已开启 ({ban_msg}, {pick_msg})'})
                print(f"🎯 自动Ban/Pick功能已启动 - Ban: {app_state.ban_champion_id}, Pick: {app_state.pick_champion_id}")
    
    @socketio.on('stop_auto_banpick')
    def handle_stop_auto_banpick():
        """停止自动Ban/Pick"""
        with thread_lock:
            app_state.auto_banpick_enabled = False
            emit('status_update', {'type': 'biz', 'message': ' 自动Ban/Pick功能已停止'})
            print("🛑 自动Ban/Pick功能已停止")
    
    @socketio.on('configure_banpick')
    def handle_configure_banpick(data):
        """配置自动Ban/Pick的英雄ID"""
        ban_id = data.get('ban_champion_id')
        pick_id = data.get('pick_champion_id')
        ban_candidates = data.get('ban_candidates')
        pick_candidates = data.get('pick_candidates')
        
        if ban_id is not None:
            app_state.ban_champion_id = ban_id
        if pick_id is not None:
            app_state.pick_champion_id = pick_id
        if isinstance(ban_candidates, list):
            app_state.ban_candidate_ids = [cid for cid in ban_candidates if cid]
        if isinstance(pick_candidates, list):
            app_state.pick_candidate_ids = [cid for cid in pick_candidates if cid]
        
        ban_msg = f"Ban: {app_state.ban_champion_id}" if app_state.ban_champion_id else "未设置"
        pick_msg = f"Pick: {app_state.pick_champion_id}" if app_state.pick_champion_id else "未设置"
        emit('status_update', {'type': 'biz', 'message': f'自动Ban/Pick配置已更新 ({ban_msg}, {pick_msg})'})
        print(f"⚙️ 自动Ban/Pick配置更新 - Ban: {app_state.ban_champion_id}, Pick: {app_state.pick_champion_id}")
 
    



def _detect_and_connect_lcu(socketio, status_proxy):
    """
    后台任务：持续监控并尝试获取 LCU 凭证
    
    Args:
        socketio: SocketIO实例
        status_proxy: 消息代理对象
    """
    import time
    
    while True:
        status_proxy.showMessage("正在自动检测英雄联盟客户端 (进程和凭证)...")
        
        token, port = lcu.autodetect_credentials(status_proxy)

        if token and port:
            app_state.lcu_credentials["auth_token"] = token
            app_state.lcu_credentials["app_port"] = port
            status_proxy.showMessage(f"✅ LCU 连接成功！端口: {port}。")
            # 连接成功后，每30秒检查一次连接状态
            time.sleep(30)
        else:
            app_state.lcu_credentials["auth_token"] = None
            app_state.lcu_credentials["app_port"] = None
            status_proxy.showMessage("❌ 连接 LCU 失败。请检查客户端是否运行，10秒后重试...")
            # 连接失败后，每10秒重试一次
            time.sleep(10)
