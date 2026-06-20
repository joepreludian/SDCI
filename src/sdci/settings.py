# SDCI Settings
import os

SERVER_TOKEN = os.environ.get("SDCI_SERVER_TOKEN", None)
TASK_RUN_TIMEOUT_SECONDS = os.environ.get("TASK_RUN_TIMEOUT", 120)
CLIENT_REQUEST_TIMEOUT_SECONDS = os.environ.get("CLIENT_REQUEST_TIMEOUT", 600)
TASKS_DIR = os.environ.get("TASKS_DIR", "./tasks")
# UPLOAD_DIR is the deprecated env var name, kept as a fallback for back-compat.
UPLOADS_DIR = os.environ.get("UPLOADS_DIR", os.environ.get("UPLOAD_DIR", "./uploads"))


class Settings:
    SERVER_TOKEN = SERVER_TOKEN
    TASK_RUN_TIMEOUT_SECONDS = TASK_RUN_TIMEOUT_SECONDS
    CLIENT_REQUEST_TIMEOUT_SECONDS = CLIENT_REQUEST_TIMEOUT_SECONDS
    TASKS_DIR = TASKS_DIR
    UPLOADS_DIR = UPLOADS_DIR
