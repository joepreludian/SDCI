from unittest import mock

import pytest

from sdci.client_service import SDCIClient
from sdci.exceptions import SDCIException
from sdci.schemas import UploadOutputSchema


def _make_response(status_code, json_data=None):
    response = mock.Mock()
    response.status_code = status_code
    response.json.return_value = json_data or {}
    return response


@pytest.fixture
def local_file(tmp_path):
    target = tmp_path / "asset.zip"
    target.write_bytes(b"payload-data" * 100)
    return str(target)


def _client_with_response(response):
    client = SDCIClient("http://server", "tok")
    client._client = mock.Mock()
    client._client.post.return_value = response
    return client


def test_upload_success_returns_schema(local_file):
    response = _make_response(
        200, {"path": "releases/v1/asset.zip", "size": 1200, "status": "UPLOADED"}
    )
    client = _client_with_response(response)

    result = client.upload(local_file, "releases/v1")

    assert isinstance(result, UploadOutputSchema)
    assert result.path == "releases/v1/asset.zip"
    assert result.size == 1200
    assert result.status == "UPLOADED"


@pytest.mark.parametrize("status_code", [401, 400, 409, 429])
def test_upload_error_status_raises(local_file, status_code):
    response = _make_response(status_code, {"detail": "boom"})
    client = _client_with_response(response)

    with pytest.raises(SDCIException):
        client.upload(local_file, "releases/v1")


def test_upload_connection_error_wrapped(local_file):
    from requests.exceptions import ConnectionError

    client = SDCIClient("http://server", "tok")
    client._client = mock.Mock()
    client._client.post.side_effect = ConnectionError("down")

    with pytest.raises(SDCIException):
        client.upload(local_file, "releases/v1")


def test_upload_timeout_wrapped(local_file):
    from requests.exceptions import Timeout

    client = SDCIClient("http://server", "tok")
    client._client = mock.Mock()
    client._client.post.side_effect = Timeout("slow")

    with pytest.raises(SDCIException):
        client.upload(local_file, "releases/v1")
