"""Atelier ASGI 入口模块。

仅持有全局 ``app`` 实例，供 ``uvicorn backend.app.main:app`` 部署使用。
工厂函数、常量与请求模型位于 :mod:`backend.app.app_factory`，
测试应从工厂模块导入，不得导入本模块，以避免触发真实数据库初始化。
"""
from __future__ import annotations

from .app_factory import (
    DEFAULT_DATA_ROOT,
    FRONTEND_ROOT,
    PROJECT_ROOT,
    ActivateDatabaseRequest,
    CreateChapterRequest,
    CreateProjectRequest,
    create_app,
)

app = create_app()
