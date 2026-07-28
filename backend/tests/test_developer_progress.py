import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app


class DeveloperProgressApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.todo_path = root / "系统功能清单.md"
        self.app = create_app(
            data_root=root / "data",
            environment="test",
            locked_environment="test",
            system_features_path=self.todo_path,
        )
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()
        self._tmp.cleanup()

    def test_progress_is_calculated_from_markdown_checklist(self) -> None:
        self.todo_path.write_text(
            "\n".join(
                [
                    "# Atelier 系统功能清单",
                    "",
                    "## 基础模块",
                    "- [x] 已完成功能：详细说明",
                    "- [~] 开发中功能",
                    "## 生产模块",
                    "- [ ] 待开发功能",
                    "- [X] 大写勾选: English separator",
                    "普通段落不会进入汇总",
                ]
            ),
            encoding="utf-8",
        )

        response = self.client.get("/api/developer/progress")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 4)
        self.assertEqual(payload["completed"], 2)
        self.assertEqual(payload["in_progress"], 1)
        self.assertEqual(payload["pending"], 1)
        self.assertEqual(payload["progress_percent"], 50.0)
        self.assertEqual(payload["items"][0]["title"], "已完成功能")
        self.assertEqual(payload["items"][0]["description"], "详细说明")
        self.assertEqual(payload["items"][0]["module"], "基础模块")
        self.assertEqual(payload["items"][1]["status"], "in_progress")
        self.assertEqual(payload["items"][2]["status"], "pending")
        self.assertEqual(payload["items"][3]["description"], "English separator")
        self.assertEqual(len(payload["modules"]), 2)
        self.assertEqual(payload["modules"][0]["name"], "基础模块")
        self.assertEqual(payload["modules"][0]["progress_percent"], 50.0)

    def test_empty_checklist_returns_zero_progress(self) -> None:
        self.todo_path.write_text("# 系统功能清单\n\n暂无条目\n", encoding="utf-8")

        response = self.client.get("/api/developer/progress")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 0)
        self.assertEqual(payload["completed"], 0)
        self.assertEqual(payload["in_progress"], 0)
        self.assertEqual(payload["pending"], 0)
        self.assertEqual(payload["progress_percent"], 0.0)
        self.assertEqual(payload["items"], [])

    def test_missing_checklist_returns_service_unavailable(self) -> None:
        response = self.client.get("/api/developer/progress")

        self.assertEqual(response.status_code, 503)
        self.assertIn("系统功能清单不存在", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
