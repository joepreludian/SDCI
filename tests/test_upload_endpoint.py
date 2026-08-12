"""End-to-end tests for POST /upload_file/ with the monitoring middleware in place."""

import pytest
from fastapi.testclient import TestClient

from sdci.server import app
from sdci.server_middleware import UploadMonitorMiddleware
from sdci.settings import Settings


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(Settings, "SERVER_TOKEN", "tok")
    monkeypatch.setattr(Settings, "UPLOADS_DIR", str(tmp_path))
    return TestClient(app)


def test_upload_monitor_middleware_is_registered():
    assert any(
        middleware.cls is UploadMonitorMiddleware for middleware in app.user_middleware
    )


def test_upload_still_succeeds_through_the_middleware(client, tmp_path):
    response = client.post(
        "/upload_file/",
        headers={"Authorization": "Bearer tok"},
        files={"file": ("app.zip", b"payload-data")},
        data={"path": "releases/v1"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "path": "releases/v1/app.zip",
        "size": 12,
        "status": "UPLOADED",
    }
    assert (tmp_path / "releases" / "v1" / "app.zip").read_bytes() == b"payload-data"


def test_upload_rejects_a_bad_token(client):
    response = client.post(
        "/upload_file/",
        headers={"Authorization": "Bearer wrong"},
        files={"file": ("app.zip", b"payload-data")},
        data={"path": "releases/v1"},
    )

    assert response.status_code == 401
