import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app


class DeveloperProgressApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.todo_path = root / "功能开发待办.md"
        self.app = create_app(
            data_root=root / "data",
            environment="test",
            locked_environment="test",
            development_todo_path=self.todo_path,
        )
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()
        self._tmp.cleanup()

    def test_progress_is_calculated_from_markdown_checklist(self) -> None:
        self.todo_path.write_text(
            "\n".join(
                [
                    "# 功能开发待办",
                    "",
                    "- [x] 已完成功能：详细说明",
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
        self.assertEqual(payload["total"], 3)
        self.assertEqual(payload["completed"], 2)
        self.assertEqual(payload["pending"], 1)
        self.assertEqual(payload["progress_percent"], 66.7)
        self.assertEqual(payload["items"][0]["title"], "已完成功能")
        self.assertEqual(payload["items"][0]["description"], "详细说明")
        self.assertEqual(payload["items"][1]["status"], "pending")
        self.assertEqual(payload["items"][2]["description"], "English separator")

    def test_empty_checklist_returns_zero_progress(self) -> None:
        self.todo_path.write_text("# 功能开发待办\n\n暂无条目\n", encoding="utf-8")

        response = self.client.get("/api/developer/progress")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 0)
        self.assertEqual(payload["completed"], 0)
        self.assertEqual(payload["pending"], 0)
        self.assertEqual(payload["progress_percent"], 0.0)
        self.assertEqual(payload["items"], [])

    def test_missing_checklist_returns_service_unavailable(self) -> None:
        response = self.client.get("/api/developer/progress")

        self.assertEqual(response.status_code, 503)
        self.assertIn("待办文档不存在", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
