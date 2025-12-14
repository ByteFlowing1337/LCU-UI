"""
LCU 凭证检测和提取模块
负责从日志文件和进程中获取 LCU 认证信息
"""
import os
import re
import chardet
import psutil
from constants import LOG_DIR


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


def detect_file_encoding(file_path, status_bar):
    """
    检测文件编码。
    
    Args:
        file_path: 文件路径
        status_bar: 状态栏对象
    
    Returns:
        str: 检测到的编码，默认'gbk'
    """
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read(4096)
            result = chardet.detect(raw_data)
            return result['encoding'] or 'gbk'
    except Exception as e:
        status_bar.showMessage(f"检测文件编码失败: {e}, 默认使用GBK")
        return 'gbk'


def get_latest_log_file(status_bar):
    """
    获取最新的日志文件（按文件修改时间）。
    
    Args:
        status_bar: 状态栏对象
    
    Returns:
        str: 日志文件路径，失败返回None
    """
    try:
        if not os.path.exists(LOG_DIR):
            status_bar.showMessage(f"错误：日志目录未找到: {LOG_DIR}。请检查 LOG_DIR 变量。")
            return None
            
        full_log_files = []
        for f in os.listdir(LOG_DIR):
            if f.endswith("_LeagueClientUx.log") and "T" in f:
                full_log_files.append(os.path.join(LOG_DIR, f))
        
        if not full_log_files:
            status_bar.showMessage(f"未在目录 {LOG_DIR} 中找到符合条件的日志文件。")
            return None
        
        latest_file = max(full_log_files, key=os.path.getmtime)
        
        if os.path.getsize(latest_file) < 500:
            status_bar.showMessage(f"警告：最新日志文件 ({os.path.basename(latest_file)}) 太小，可能为空或正在写入。")
            return None 
            
        return latest_file
    
    except FileNotFoundError:
        status_bar.showMessage(f"错误：日志目录未找到: {LOG_DIR}")
        return None
    except Exception as e:
        status_bar.showMessage(f"获取日志文件时出错: {e}")
        return None


def extract_params_from_log(log_file, status_bar):
    """
    从日志文件中提取认证令牌和端口号。
    
    Args:
        log_file: 日志文件路径
        status_bar: 状态栏对象
    
    Returns:
        tuple: (token, port) 或 (None, None)
    """
    try:
        encoding = detect_file_encoding(log_file, status_bar)
        status_bar.showMessage(f"检测到文件编码: {encoding}")
        
        with open(log_file, "r", encoding=encoding, errors='replace') as f:
            content = f.read()
            
            token_match = re.search(r"--remoting-auth-token=([\w-]+)", content)
            port_match = re.search(r"--app-port=(\d+)", content)
            
            if token_match and port_match:
                token = token_match.group(1)
                port = int(port_match.group(1))
                status_bar.showMessage(f"成功提取参数：Token={token[:8]}..., Port={port}")
                return token, port
            else:
                status_bar.showMessage("在日志文件中未找到所需的 --remoting-auth-token 或 --app-port 参数。")
                return None, None
                
    except FileNotFoundError:
        status_bar.showMessage(f"错误：日志文件未找到: {log_file}")
        return None, None
    except Exception as e:
        status_bar.showMessage(f"读取日志文件时出错: {e}")
        return None, None


def autodetect_credentials(status_bar):
    """
    自动检测LCU凭证的入口函数。
    
    流程:
    1. 检查 LeagueClientUx.exe 进程是否运行
    2. 如果进程运行，则尝试从最新日志中提取凭证
    
    Args:
        status_bar: 状态栏对象
    
    Returns:
        tuple: (auth_token, app_port) 或 (None, None)
    """
    status_bar.showMessage("正在尝试自动检测 LCU 凭证 (进程+日志)...")
    
    # 步骤 1: 检查进程
    if not is_league_client_running(status_bar):
        status_bar.showMessage("⚠️ 进程检测失败。无法连接 LCU。")
        return None, None
        
    # 进程运行，继续读取日志
    log_file = get_latest_log_file(status_bar)
    
    if log_file:
        status_bar.showMessage(f"找到日志文件: {os.path.basename(log_file)}")
        auth_token, app_port = extract_params_from_log(log_file, status_bar)
        
        if auth_token and app_port:
            status_bar.showMessage("✅ LCU 进程和参数均自动获取成功!")
        else:
            status_bar.showMessage("⚠️ 进程运行中，但日志中未找到 LCU 凭证。")
            
        return auth_token, app_port
    else:
        status_bar.showMessage("⚠️ 进程运行中，但未找到有效的日志文件。")
        return None, None
