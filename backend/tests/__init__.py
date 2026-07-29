"""Atelier backend tests.

测试隔离保护约定：
- 所有测试必须使用临时数据目录，绝不写入生产数据库。
- 所有测试必须锁定到 test 环境，防止误操作生产库。
- 禁止导入 ``backend.app.main``，因为它会初始化生产数据库。
- 新增测试应继承 ``IsolatedTestCase``，自动获得隔离保护。
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app


class IsolatedTestCase(unittest.TestCase):
    """测试隔离基类。

    自动创建临时数据目录并锁定到 test 环境。
    子类通过 ``self.app``、``self.client``、``self.manager`` 访问应用实例。
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.app = create_app(
            data_root=Path(self._tmp.name),
            environment="test",
            locked_environment="test",
        )
        self.client = TestClient(self.app)
        self.manager = self.app.state.database_manager


