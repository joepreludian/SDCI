import asyncio

import pytest

from sdci.exceptions import SDCIServerException
from sdci.server_runner import FileUploader
from sdci.settings import Settings


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(Settings, "UPLOAD_DIR", str(tmp_path))
    return tmp_path


class FakeUploadFile:
    """Minimal stub mimicking FastAPI's UploadFile streaming interface."""

    def __init__(self, data: bytes):
        self._buffer = data

    async def read(self, size: int) -> bytes:
        chunk, self._buffer = self._buffer[:size], self._buffer[size:]
        return chunk


def test_resolved_path_inside_upload_dir(upload_dir):
    uploader = FileUploader("releases/v1", "app.zip")
    expected = str((upload_dir / "releases" / "v1" / "app.zip").resolve())
    assert uploader.resolved_path == expected


def test_resolved_path_rejects_parent_traversal(upload_dir):
    uploader = FileUploader("../escape", "app.zip")
    with pytest.raises(SDCIServerException):
        uploader.resolved_path


def test_resolved_path_rejects_absolute_remote_dir(upload_dir):
    uploader = FileUploader("/etc", "passwd")
    with pytest.raises(SDCIServerException):
        uploader.resolved_path


def test_resolved_path_rejects_filename_with_separator(upload_dir):
    uploader = FileUploader("releases", "../../app.zip")
    with pytest.raises(SDCIServerException):
        uploader.resolved_path


def test_save_creates_nested_dirs_and_writes_contents(upload_dir):
    uploader = FileUploader("releases/v1", "app.zip").for_lock(asyncio.Lock())
    payload = b"hello-world-payload" * 1000

    written = asyncio.run(uploader.save(FakeUploadFile(payload)))

    target = upload_dir / "releases" / "v1" / "app.zip"
    assert target.exists()
    assert target.read_bytes() == payload
    assert written == len(payload)


def test_save_raises_when_destination_exists(upload_dir):
    target_dir = upload_dir / "releases"
    target_dir.mkdir()
    (target_dir / "app.zip").write_bytes(b"existing")

    uploader = FileUploader("releases", "app.zip")
    with pytest.raises(SDCIServerException):
        asyncio.run(uploader.save(FakeUploadFile(b"new-data")))
