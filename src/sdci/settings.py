# SDCI Settings
import os

from sdci.exceptions import SDCIFatalException


def env_int(name: str, default: int) -> int:
    """Read an integer env var. Env vars always arrive as strings."""
    raw_value = os.environ.get(name)

    if raw_value is None:
        return default

    try:
        return int(raw_value)
    except ValueError as exc:
        raise SDCIFatalException(
            f"INVALID ENV VAR {name}={raw_value!r} - expected an integer number of seconds"
        ) from exc


SERVER_TOKEN = os.environ.get("SDCI_SERVER_TOKEN", None)
TASK_RUN_TIMEOUT_SECONDS = env_int("TASK_RUN_TIMEOUT", 600)  # 10 minutes
CLIENT_REQUEST_TIMEOUT_SECONDS = env_int("CLIENT_REQUEST_TIMEOUT", 1800)  # 30 minutes
UPLOAD_TIMEOUT_SECONDS = env_int("UPLOAD_TIMEOUT", 1800)  # 30 minutes
TASKS_DIR = os.environ.get("TASKS_DIR", "./tasks")
# UPLOAD_DIR is the deprecated env var name, kept as a fallback for back-compat.
UPLOADS_DIR = os.environ.get("UPLOADS_DIR", os.environ.get("UPLOAD_DIR", "./uploads"))


class Settings:
    SERVER_TOKEN = SERVER_TOKEN
    TASK_RUN_TIMEOUT_SECONDS = TASK_RUN_TIMEOUT_SECONDS
    CLIENT_REQUEST_TIMEOUT_SECONDS = CLIENT_REQUEST_TIMEOUT_SECONDS
    UPLOAD_TIMEOUT_SECONDS = UPLOAD_TIMEOUT_SECONDS
    TASKS_DIR = TASKS_DIR
    UPLOADS_DIR = UPLOADS_DIR
