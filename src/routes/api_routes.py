"""
[DEPRECATED] API 路由模块
此模块已废弃，所有路由已迁移至 data_routes.py 和 page_routes.py。
保留此文件是为了防止潜在的导入错误。
"""
from .data_routes import data_bp as api_bp
from .data_routes import data_bp as api

# Re-export for compatibility
__all__ = ["api_bp", "api"]
