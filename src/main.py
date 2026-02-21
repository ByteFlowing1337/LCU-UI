"""
The entrance of the application.

"""
from flask import Flask
from flask_socketio import SocketIO
import threading
import webbrowser
import signal
import time
import os
import sys

from config import HOST, PORT, PUBLIC_HOST
from routes import page_bp, data_bp
from websocket import register_socket_events
from websocket.socket_events import ensure_lcu_detection_thread, LoggingStatusProxy
from utils import get_local_ip
from utils.logger import logger


def create_app():
    """
    创建并配置Flask应用
    
    Returns:
        tuple: (app, socketio)
    """
    import sys

    # 兼容 PyInstaller 打包环境
    if getattr(sys, 'frozen', False):
        # 打包后，资源在 sys._MEIPASS 目录
        base_path: str = getattr(sys, '_MEIPASS', os.path.dirname(__file__))
        template_folder = os.path.join(base_path, 'templates')
        static_folder = os.path.join(base_path, 'static')
        app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
    else:
        # 正常开发环境：模板位于 src/templates，静态资源在仓库根的 static/
        base_path = os.path.dirname(__file__)
        template_folder = os.path.join(base_path, 'templates')
        static_folder = os.path.abspath(os.path.join(base_path, '..', 'static'))
        app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
    
    # 注册蓝图
    app.register_blueprint(page_bp)  # 页面渲染路由
    # 数据 API 统一挂在 /api 前缀，匹配前端请求
    app.register_blueprint(data_bp, url_prefix='/api')
    
 
    
    # 初始化SocketIO
    # 打包环境使用 threading 模式，并排除 eventlet/gevent
    socketio = SocketIO(
        app, 
        cors_allowed_origins="*",
        async_mode='threading',
        logger=False,
        engineio_logger=False
    )
    
    # 注册WebSocket事件
    register_socket_events(socketio)
    
    return app, socketio


def _wait_and_open_browser(url, host, port, timeout, interval):
    """等待服务器就绪并打开浏览器"""
    import socket
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, int(port)), timeout=1):
                logger.info(f"检测到服务器 {host}:{port} 可连接，准备打开浏览器: {url}")
                webbrowser.open(url)
                return
        except Exception:
            time.sleep(interval)
    # 超时了，仍然尝试打开一次（避免完全不打开的情况）
    logger.warning(f"等待 {host}:{port} 超时 ({timeout}s)，将尝试直接打开浏览器: {url}")
    webbrowser.open(url)


def open_browser_when_ready(url, host='127.0.0.1', port=5000, timeout=10, interval=0.2):
    """
    在服务器端口可连接后打开浏览器（在单独线程中运行）。

    这比固定延时更稳健：它会轮询目标端口直到可连接或超时，避免浏览器在服务器尚未就绪时打开导致需要手动刷新。

    Args:
        url: 要打开的URL
        host: 主机名或IP（用于端口检测）
        port: 端口号
        timeout: 最长等待秒数
        interval: 重试间隔秒数
    """
    t = threading.Thread(
        target=_wait_and_open_browser, 
        args=(url, host, port, timeout, interval), 
        daemon=True
    )
    t.start()


def main():
    """主函数"""
    # 创建应用
    app, socketio = create_app()
    
    # 获取本地IP（优先使用配置中的 PUBLIC_HOST）
    detected_ip = get_local_ip()
    display_host = PUBLIC_HOST or (detected_ip if detected_ip else '127.0.0.1')
    server_address = f'http://{display_host}:{PORT}'

    # 在服务器可用后打开浏览器（更稳健，避免需要手动刷新）
    # 如果你希望强制使用回环或局域网地址，可在 config.py 中设置 PUBLIC_HOST
    # Check for --no-browser argument (used by Tauri sidecar)
    if "--no-browser" not in sys.argv:
        open_browser_when_ready(server_address, host=display_host, port=PORT, timeout=10)




    # 输出启动信息
    logger.info("Lcu UI 已启动！")
    logger.info(f"本机访问地址: http://127.0.0.1:{PORT}")
    logger.info(f"局域网访问地址: {server_address}")

    # 提前启动一次 LCU 探测（即便前端尚未连接），方便诊断
    try:
        ensure_lcu_detection_thread(socketio, LoggingStatusProxy(socketio))
    except Exception as exc:
        logger.warning(f"预热 LCU 探测线程失败: {exc}")
    
    # 启动服务器：默认关闭调试热重载，避免双进程与重复打开浏览器
    socketio.run(
        app,
        host=HOST,
        port=PORT,
        debug=False,
        use_reloader=False,
        allow_unsafe_werkzeug=True
    )


if __name__ == '__main__':
    main()
