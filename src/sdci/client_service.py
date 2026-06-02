import logging
import os
from typing import Literal, Optional

import click
import requests
from requests.exceptions import (
    ChunkedEncodingError,
    ConnectionError,
    HTTPError,
    Timeout,
)

from sdci.exceptions import SDCIException
from sdci.schemas import TaskOutputSchema, UploadOutputSchema
from sdci.settings import CLIENT_REQUEST_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


class _ProgressFileReader:
    """Wraps a file object so that read() advances a click progress bar."""

    def __init__(self, file_obj, progress_bar):
        self._file_obj = file_obj
        self._progress_bar = progress_bar

    def read(self, size=-1):
        chunk = self._file_obj.read(size)
        if chunk:
            self._progress_bar.update(len(chunk))
        return chunk


class SDCIClient:
    def __init__(self, endpoint, token) -> None:
        self._client = requests.Session()
        self._endpoint = endpoint
        self._token = token

    def trigger(
        self, task_name, *args, action: Literal["run", "status"] = "run"
    ) -> Optional[TaskOutputSchema]:
        match action:
            case "run":
                action_url = f"{self._endpoint}/tasks/{task_name}/"
            case "status":
                action_url = f"{self._endpoint}/tasks/{task_name}/status/"

        try:
            response = self._client.post(
                action_url,
                headers={
                    "Authorization": f"Bearer {self._token}",
                },
                json={
                    "args": args,
                }
                if action == "run"
                else {},
                stream=action == "run",
                timeout=CLIENT_REQUEST_TIMEOUT_SECONDS,
            )
        except HTTPError as exc:
            raise SDCIException(f"CLIENT HTTPError: {exc}") from exc

        except ChunkedEncodingError as exc:
            raise SDCIException(
                f"CLIENT CHUNKED ENCODING ERROR (POTENTIALLY SERVER ERROR): {exc}"
            ) from exc

        except ConnectionError as exc:
            raise SDCIException(f"SERVER UNAVAILABLE\n\n{exc}") from exc

        if response.status_code == 401:
            raise SDCIException("SERVER UNAUTHORIZED - Please check token")

        if response.status_code == 422:
            raise SDCIException(
                f"SERVER TASK UNAVAILABLE: {response.json().get('detail', 'Unknown Error')}"
            )

        if response.status_code == 429:
            raise SDCIException("SERVER HAS A WORKING TASK - PLEASE WAIT")

        if action == "status":
            return TaskOutputSchema.model_validate(response.json())

        if action == "run":
            with response:
                for line in response.iter_lines():
                    line = line.decode("utf-8")
                    print(line)

    def upload(self, local_file: str, remote_path: str) -> UploadOutputSchema:
        upload_url = f"{self._endpoint}/upload_file/"
        basename = os.path.basename(local_file)
        file_size = os.path.getsize(local_file)

        try:
            with open(local_file, "rb") as file_obj:
                with click.progressbar(
                    length=file_size, label=f"Uploading {basename}"
                ) as progress_bar:
                    wrapper = _ProgressFileReader(file_obj, progress_bar)
                    response = self._client.post(
                        upload_url,
                        headers={
                            "Authorization": f"Bearer {self._token}",
                        },
                        files={"file": (basename, wrapper)},
                        data={"path": remote_path},
                        timeout=CLIENT_REQUEST_TIMEOUT_SECONDS,
                    )
        except Timeout as exc:
            raise SDCIException(f"CLIENT UPLOAD TIMEOUT: {exc}") from exc

        except HTTPError as exc:
            raise SDCIException(f"CLIENT HTTPError: {exc}") from exc

        except ChunkedEncodingError as exc:
            raise SDCIException(
                f"CLIENT CHUNKED ENCODING ERROR (POTENTIALLY SERVER ERROR): {exc}"
            ) from exc

        except ConnectionError as exc:
            raise SDCIException(f"SERVER UNAVAILABLE\n\n{exc}") from exc

        if response.status_code == 401:
            raise SDCIException("SERVER UNAUTHORIZED - Please check token")

        if response.status_code == 400:
            raise SDCIException(response.json().get("detail", "INVALID UPLOAD PATH"))

        if response.status_code == 409:
            raise SDCIException(
                response.json().get("detail", "DESTINATION FILE ALREADY EXISTS")
            )

        if response.status_code == 429:
            raise SDCIException("SERVER HAS A WORKING TASK OR UPLOAD - PLEASE WAIT")

        return UploadOutputSchema.model_validate(response.json())
