import asyncio

import pytest

from sdci.exceptions import SDCIServerException
from sdci.server_runner import FileUploader
from sdci.settings import Settings


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(Settings, "UPLOADS_DIR", str(tmp_path))
    return tmp_path


class FakeUploadFile:
    """Minimal stub mimicking FastAPI's UploadFile streaming interface."""

    def __init__(self, data: bytes):
        self._buffer = data

    async def read(self, size: int) -> bytes:
        chunk, self._buffer = self._buffer[:size], self._buffer[size:]
        return chunk


class BrokenUploadFile:
    """Delivers one chunk, then fails - a dropped or cancelled transfer."""

    def __init__(self, first_chunk: bytes, error: BaseException):
        self._first_chunk = first_chunk
        self._error = error
        self._reads = 0

    async def read(self, size: int) -> bytes:
        self._reads += 1

        if self._reads == 1:
            return self._first_chunk

        raise self._error


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


def test_save_removes_partial_file_when_the_transfer_breaks(upload_dir):
    uploader = FileUploader("releases", "app.zip")
    upload_file = BrokenUploadFile(b"partial-data", OSError("connection reset"))

    with pytest.raises(OSError):
        asyncio.run(uploader.save(upload_file))

    assert not (upload_dir / "releases" / "app.zip").exists()


def test_save_removes_partial_file_when_cancelled(upload_dir):
    uploader = FileUploader("releases", "app.zip")
    upload_file = BrokenUploadFile(b"partial-data", asyncio.CancelledError())

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(uploader.save(upload_file))

    assert not (upload_dir / "releases" / "app.zip").exists()


def test_save_raises_when_destination_exists(upload_dir):
    target_dir = upload_dir / "releases"
    target_dir.mkdir()
    (target_dir / "app.zip").write_bytes(b"existing")

    uploader = FileUploader("releases", "app.zip")
    with pytest.raises(SDCIServerException):
        asyncio.run(uploader.save(FakeUploadFile(b"new-data")))


def test_save_keeps_an_existing_destination_intact(upload_dir):
    """The partial-file cleanup must never touch a file it did not create."""
    target_dir = upload_dir / "releases"
    target_dir.mkdir()
    (target_dir / "app.zip").write_bytes(b"existing")

    uploader = FileUploader("releases", "app.zip")
    with pytest.raises(SDCIServerException):
        asyncio.run(uploader.save(FakeUploadFile(b"new-data")))

    assert (target_dir / "app.zip").read_bytes() == b"existing"
