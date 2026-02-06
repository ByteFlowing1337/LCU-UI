"""
LCU 凭证检测和提取模块
负责从进程命令行或 lockfile 中获取 LCU 认证信息（remoting-auth-token 与 app-port）。
"""
import os
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


def _candidate_lockfile_paths():
    """返回可能的 lockfile 路径列表，包含常见安装位置和正在运行进程推断的路径。"""
    candidates = []

    target_name = "LeagueClientUx.exe"
    for proc in psutil.process_iter(['name', 'exe']):
        if proc.info.get('name') != target_name:
            continue
        exe_path = proc.info.get('exe')
        if not exe_path:
            continue
        exe_dir = os.path.dirname(exe_path)
        candidates.append(os.path.normpath(os.path.join(exe_dir, '..', 'lockfile')))
        candidates.append(os.path.join(exe_dir, 'lockfile'))

    candidates.extend([
        r"C:\Riot Games\League of Legends\lockfile",
        r"D:\Riot Games\League of Legends\lockfile",
        r"C:\WeGameApps\LOL\LeagueClient\lockfile",
        r"C:\WeGameApps\英雄联盟\LeagueClient\lockfile",
    ])

    seen = set()
    ordered = []
    for path in candidates:
        if path and path not in seen:
            ordered.append(path)
            seen.add(path)
    return ordered


def _read_lockfile(lockfile_path):
    """解析 lockfile，返回 (token, port) 或 (None, None)。"""
    try:
        with open(lockfile_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
    except FileNotFoundError:
        return None, None
    except Exception:
        return None, None

    parts = content.split(':')
    if len(parts) < 4:
        return None, None

    try:
        port = int(parts[2])
    except ValueError:
        return None, None

    token = parts[3]
    return token, port


def read_lockfile_credentials(status_bar):
    """尝试从 lockfile 读取凭证。"""
    for path in _candidate_lockfile_paths():
        token, port = _read_lockfile(path)
        if token and port:
            status_bar.showMessage(f"✅ 通过 lockfile 获取凭证成功 (port={port})")
            return token, port
    status_bar.showMessage("⚠️ 未找到 lockfile，无法从文件获取凭证。")
    return None, None


def autodetect_credentials(status_bar):
    """仅通过进程参数自动检测 LCU 凭证。"""
    status_bar.showMessage("正在通过进程参数自动检测 LCU 凭证...")

    token, port = extract_params_from_process(status_bar)
    if token and port:
        return token, port

    status_bar.showMessage("尝试从 lockfile 读取 LCU 凭证...")
    token, port = read_lockfile_credentials(status_bar)
    if token and port:
        return token, port

    status_bar.showMessage("⚠️ 未能获取到 LCU 凭证。请确认客户端已启动，并检查杀毒或权限设置。")
    return None, None












