"""
LCU 凭证检测和提取模块
负责从进程命令行中获取 LCU 认证信息（remoting-auth-token 与 app-port）。
"""
import psutil


def is_league_client_running(status_bar):
    """
    检测 LeagueClient.exe 进程是否正在运行。
    
    Args:
        status_bar: 状态栏对象（用于显示消息）
    
    Returns:
        bool: 进程是否运行
    """
    client_process_name = "LeagueClientUx.exe" 
    
    # 遍历所有正在运行的进程
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] == client_process_name:
            status_bar.showMessage(f"✅ 检测到进程: {client_process_name} 正在运行。")
            return True
            
    status_bar.showMessage(f"❌ 未检测到进程: {client_process_name}。请先启动客户端。")
    return False





def extract_params_from_process(status_bar):
    """从 LeagueClientUx.exe 进程的命令行参数中提取 token 和 port。"""
    target_name = "LeagueClientUx.exe"
    try:
        for proc in psutil.process_iter(['name', 'cmdline']):
            if proc.info.get('name') != target_name:
                continue

            cmdline = proc.info.get('cmdline') or []
            token = None
            port = None

            for arg in cmdline:
                if arg.startswith("--remoting-auth-token="):
                    token = arg.split("=", 1)[1]
                elif arg.startswith("--app-port="):
                    try:
                        port = int(arg.split("=", 1)[1])
                    except ValueError:
                        port = None

            if token and port:
                status_bar.showMessage(f"✅ 从进程参数获取凭证成功 (port={port})")
                return token, port

            status_bar.showMessage(f"⚠️ 找到 {target_name} 进程，但未解析到 remoting-auth-token 或 app-port。")
            return None, None

        status_bar.showMessage(f"⚠️ 未找到进程: {target_name}")
        return None, None
    except Exception as exc:
        status_bar.showMessage(f"从进程读取参数失败: {exc}")
        return None, None


def autodetect_credentials(status_bar):
    """仅通过进程参数自动检测 LCU 凭证。"""
    status_bar.showMessage("正在通过进程参数自动检测 LCU 凭证...")

    token, port = extract_params_from_process(status_bar)
    if token and port:
        return token, port

    status_bar.showMessage("⚠️ 未能从进程参数解析到 LCU 凭证。请确认客户端已启动。")
    return None, None












