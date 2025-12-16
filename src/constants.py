import os
import json
from functools import lru_cache

# --- LCU 根路径查找函数 ---

# 日志目录路径
def find_league_client_root_static():
    """
    尝试通过注册表查找英雄联盟客户端的安装根目录 (LeagueClient 文件夹)。
    查找失败时，尝试通用路径作为后备。
    """
    common_paths = [
        r"C:\Riot Games\League of Legends", # Riot Games 默认路径
        r"D:\Riot Games\League of Legends",
        r"C:\WeGameApps\LOL\LeagueClient" # WeGame 默认路径
    ]
    
    for path in common_paths:
        if os.path.isdir(path):
            return path
            
   
    return None

# ----------------------------------------------------
# 2. 定义两个全局常量
# ----------------------------------------------------

# CLIENT_ROOT_PATH: LeagueClient 的根目录 (你想要的结果)
CLIENT_ROOT_PATH = find_league_client_root_static()

if CLIENT_ROOT_PATH:
    # LOG_DIR: LCU 日志文件的精确目录 (lcu_api.py 需要的结果)
    LOG_DIR = os.path.join(CLIENT_ROOT_PATH)
else:
    LOG_DIR = "C:\\WeGameApps\\英雄联盟\\LeagueClient"

# ----------------------------------------------------
# 3. 数据加载优化 - 延迟加载JSON数据
# ----------------------------------------------------

# Cache for loaded JSON data
_data_cache = {}

def _get_data_path():
    """获取data目录的绝对路径（兼容 PyInstaller 打包环境）"""
    import sys
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后，资源在 sys._MEIPASS 临时目录中
        base_path:str = getattr(sys, '_MEIPASS', os.path.dirname(__file__))
    else:
        # 正常运行时，使用脚本所在目录
        base_path = os.path.dirname(__file__)
    return os.path.join(base_path, 'data')

@lru_cache(maxsize=None)
def _load_json_file(filename):
    """延迟加载JSON文件并缓存结果"""
    if filename in _data_cache:
        return _data_cache[filename]
    
    file_path = os.path.join(_get_data_path(), filename)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            _data_cache[filename] = data
            return data
    except FileNotFoundError:
        print(f"Warning: {file_path} not found, using empty dict")
        return {}
    except json.JSONDecodeError:
        print(f"Warning: Invalid JSON in {file_path}, using empty dict")
        return {}

def get_champion_map():
    """获取英雄ID到中文名字的映射"""
    data = _load_json_file('champion_map.json')
    # 转换字符串键为整数键以保持兼容性
    return {int(k): v for k, v in data.items()}

def get_augment_names():
    """获取海克斯天赋ID到图标名称的映射"""
    data = _load_json_file('augment_names.json')
    # 转换字符串键为整数键以保持兼容性
    return {int(k): v for k, v in data.items()}

def get_augment_info():
    """获取海克斯天赋ID到中文信息的映射"""
    data = _load_json_file('augment_info.json')
    # 转换字符串键为整数键以保持兼容性
    return {int(k): v for k, v in data.items()}

# 英雄ID到名称的映射 - 使用延迟加载优化性能
# 数据存储在 data/champion_map.json
CHAMPION_MAP = None  # 将在首次访问时延迟加载

def _get_champion_map():
    """获取英雄ID映射，支持延迟加载"""
    global CHAMPION_MAP
    if CHAMPION_MAP is None:
        CHAMPION_MAP = get_champion_map()
    return CHAMPION_MAP

# 重写CHAMPION_MAP为属性，实现延迟加载

# Note: do not override module attribute with a property object.
# Keep CHAMPION_MAP as a module-level variable (None until loaded)


# 海克斯天赋 (ARAM Augments) 映射 - 使用延迟加载优化性能
# playerAugment ID对应的图标名称，用于构建CDN URL
# 图标URL格式: https://raw.communitydragon.org/15.19/game/assets/ux/cherry/augments/icons/{name}_large.png
# 数据存储在 data/augment_names.json

# ID到图标名称的映射 - 延迟加载
AUGMENT_ID_TO_NAME = None

def _get_augment_names():
    """获取天赋ID到图标名称映射，支持延迟加载"""
    global AUGMENT_ID_TO_NAME
    if AUGMENT_ID_TO_NAME is None:
        AUGMENT_ID_TO_NAME = get_augment_names()
    return AUGMENT_ID_TO_NAME

# ID到中文信息的映射（名称和描述）- 使用延迟加载优化性能  
# 数据存储在 data/augment_info.json
AUGMENT_ID_TO_INFO = None

def _get_augment_info_map():
    """获取天赋ID到中文信息映射，支持延迟加载"""
    global AUGMENT_ID_TO_INFO
    if AUGMENT_ID_TO_INFO is None:
        AUGMENT_ID_TO_INFO = get_augment_info()  # 调用从JSON加载的函数
    return AUGMENT_ID_TO_INFO

# 原来的大字典已移至 data/augment_info.json 以提升性能

def get_augment_icon_url(augment_id, version='15.19'):
    """
    获取海克斯天赋图标的CDN URL
    
    Args:
        augment_id: playerAugment字段的ID值 (如 1084, 1314)
        version: CDN版本号，默认为 '15.19'
    
    Returns:
        图标URL，如果ID未找到则返回None
    """
    names_dict = _get_augment_names()  # 使用延迟加载
    name = names_dict.get(augment_id)
    if name:
        return f'https://raw.communitydragon.org/{version}/game/assets/ux/cherry/augments/icons/{name}_large.png'
    return None

def get_augment_info_by_id(augment_id):
    """
    获取海克斯天赋的中文信息
    
    Args:
        augment_id: playerAugment字段的ID值
    
    Returns:
        dict: {'name': '中文名称', 'desc': '中文描述'} 或 None
    """
    info_dict = _get_augment_info_map()  # 使用延迟加载
    return info_dict.get(augment_id)