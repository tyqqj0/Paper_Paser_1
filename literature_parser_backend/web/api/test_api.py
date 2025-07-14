"""API 端点测试"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from literature_parser_backend.web.application import get_app


@pytest.fixture
def client():
    """创建测试客户端"""
    app = get_app()
    return TestClient(app)


@pytest.fixture
def literature_data():
    """测试用文献数据"""
    return {
        "doi": "10.1038/nature12373",
        "arxiv_id": None,
        "pdf_url": "https://example.com/paper.pdf",
        "title": "Test Paper",
        "authors": ["Author One", "Author Two"],
    }


class TestLiteratureAPI:
    """文献API测试"""

    @patch("literature_parser_backend.web.api.literature.LiteratureDAO")
    @patch("literature_parser_backend.web.api.literature.process_literature_task")
    def test_create_literature_new(
        self, mock_task, mock_dao_class, client, literature_data,
    ):
        """测试提交新文献"""
        # 模拟DAO
        mock_dao = AsyncMock()
        mock_dao_class.return_value = mock_dao
        mock_dao.find_by_doi.return_value = None  # 未找到现有文献

        # 模拟Celery任务
        mock_task_result = MagicMock()
        mock_task_result.id = "test-task-id"
        mock_task.delay.return_value = mock_task_result

        response = client.post("/api/literature", json=literature_data)

        assert response.status_code == 202
        data = response.json()
        assert data["taskId"] == "test-task-id"
        assert data["status"] == "processing"

        # 验证调用
        mock_dao.find_by_doi.assert_called_once_with("10.1038/nature12373")
        mock_task.delay.assert_called_once()

    @patch("literature_parser_backend.web.api.literature.LiteratureDAO")
    def test_create_literature_exists(self, mock_dao_class, client, literature_data):
        """测试提交已存在文献"""
        # 模拟DAO返回现有文献
        mock_dao = AsyncMock()
        mock_dao_class.return_value = mock_dao

        existing_lit = MagicMock()
        existing_lit.id = "existing-lit-id"
        mock_dao.find_by_doi.return_value = existing_lit

        response = client.post("/api/literature", json=literature_data)

        assert response.status_code == 200
        data = response.json()
        assert data["literatureId"] == "existing-lit-id"
        assert data["status"] == "exists"

    @patch("literature_parser_backend.web.api.literature.LiteratureDAO")
    def test_get_literature_summary(self, mock_dao_class, client):
        """测试获取文献摘要"""
        # 模拟DAO
        mock_dao = AsyncMock()
        mock_dao_class.return_value = mock_dao

        # 模拟文献对象
        mock_literature = MagicMock()
        mock_literature.id = "test-lit-id"
        mock_literature.identifiers = {"doi": "10.1038/nature12373"}
        mock_literature.metadata = {"title": "Test Paper"}
        mock_literature.task_info = {"status": "completed"}
        mock_literature.created_at = "2024-01-01T00:00:00Z"
        mock_literature.updated_at = "2024-01-01T00:00:00Z"

        mock_dao.get_by_id.return_value = mock_literature

        response = client.get("/api/literature/test-lit-id")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test-lit-id"
        assert data["identifiers"]["doi"] == "10.1038/nature12373"

    @patch("literature_parser_backend.web.api.literature.LiteratureDAO")
    def test_get_literature_not_found(self, mock_dao_class, client):
        """测试获取不存在的文献"""
        mock_dao = AsyncMock()
        mock_dao_class.return_value = mock_dao
        mock_dao.get_by_id.return_value = None

        response = client.get("/api/literature/nonexistent-id")

        assert response.status_code == 404
        assert "文献不存在" in response.json()["detail"]


class TestTaskAPI:
    """任务API测试"""

    @patch("literature_parser_backend.web.api.task.AsyncResult")
    def test_get_task_status_success(self, mock_async_result, client):
        """测试获取成功任务状态"""
        # 模拟成功的任务结果
        mock_result = MagicMock()
        mock_result.status = "SUCCESS"
        mock_result.result = {"literature_id": "test-lit-id", "message": "处理成功"}
        mock_async_result.return_value = mock_result

        response = client.get("/api/task/test-task-id")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["literature_id"] == "test-lit-id"
        assert data["progress"]["current"] == 100

    @patch("literature_parser_backend.web.api.task.AsyncResult")
    def test_get_task_status_pending(self, mock_async_result, client):
        """测试获取等待中任务状态"""
        mock_result = MagicMock()
        mock_result.status = "PENDING"
        mock_async_result.return_value = mock_result

        response = client.get("/api/task/test-task-id")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        assert data["progress"]["current"] == 0

    @patch("literature_parser_backend.web.api.task.AsyncResult")
    def test_get_task_status_failure(self, mock_async_result, client):
        """测试获取失败任务状态"""
        mock_result = MagicMock()
        mock_result.status = "FAILURE"
        mock_result.info = "处理出错"
        mock_async_result.return_value = mock_result

        response = client.get("/api/task/test-task-id")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failure"
        assert data["error"] == "处理出错"

    @patch("literature_parser_backend.web.api.task.celery_app")
    def test_cancel_task(self, mock_celery_app, client):
        """测试取消任务"""
        # 模拟控制接口
        mock_celery_app.control.revoke = MagicMock()

        response = client.delete("/api/task/test-task-id")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"
        assert data["task_id"] == "test-task-id"

        # 验证revoke被调用
        mock_celery_app.control.revoke.assert_called_once_with(
            "test-task-id", terminate=True,
        )


class TestAPIIntegration:
    """API集成测试"""

    def test_api_routes_registered(self, client):
        """测试API路由是否正确注册"""
        # 测试文献路由
        response = client.post("/api/literature", json={})
        # 应该返回422（验证错误）而不是404（路由不存在）
        assert response.status_code == 422

        # 测试任务路由
        response = client.get("/api/task/some-id")
        # 应该能访问到路由（可能返回500因为没有真实的Celery）
        assert response.status_code != 404

    def test_openapi_schema(self, client):
        """测试OpenAPI文档生成"""
        response = client.get("/docs")
        assert response.status_code == 200

        # 检查API文档中是否包含我们的端点
        response = client.get("/openapi.json")
        assert response.status_code == 200
        openapi_data = response.json()

        paths = openapi_data.get("paths", {})
        assert "/api/literature" in paths
        assert "/api/task/{task_id}" in paths


if __name__ == "__main__":
    # 简单的快速测试
    print("API测试模块已创建")
    print("运行命令: pytest literature_parser_backend/web/api/test_api.py -v")
