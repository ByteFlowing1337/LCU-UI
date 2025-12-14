"""
路由模块初始化
"""
from .page_routes import page_bp
from .data_routes import data_bp

# 为了向后兼容，保留 api_bp 作为 data_bp 的别名
api_bp = data_bp

__all__ = ['page_bp', 'data_bp', 'api_bp']
