"""
服务模块初始化
"""
from .auto_accept import auto_accept_task
from .auto_analyze import auto_analyze_task
from .auto_banpick import auto_banpick_task

__all__ = ['auto_accept_task', 'auto_analyze_task', 'auto_banpick_task']
