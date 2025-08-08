import logging
from typing import Literal, Optional

import requests
from requests.exceptions import ChunkedEncodingError, ConnectionError, HTTPError

from sdci.exceptions import SDCIException
from sdci.schemas import TaskOutputSchema
from sdci.settings import CLIENT_REQUEST_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


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
