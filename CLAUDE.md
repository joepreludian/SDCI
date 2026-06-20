# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SDCI (Sidecar Micro CD) is a lightweight continuous deployment system with a server-client architecture. The server runs shell script tasks on demand, streaming output in real-time. The client triggers tasks via HTTP with token-based auth.

Tasks are `.sh` files in `TASKS_DIR`; the task name is the filename without `.sh`. The server invokes them as `bash {task}.sh {args...}`. Note: `pyproject.toml` requires Python `>=3.10` (the dev venv is 3.10), though the README states 3.13.

## Build & Run Commands

```bash
# Install dependencies (uses uv as package manager/build backend)
uv pip install .

# Build package
make build          # cleans dist/ then runs uv build

# Publish to PyPI
make publish        # builds then runs uv publish

# Docker
make docker-build   # builds package then docker compose build sdci-base
make docker-testing # builds, runs sdci-client smoke test, then docker compose down

# Run server locally
sdci-server serve --host 127.0.0.1 --port 8842 --server-token YOUR_TOKEN --tasks-dir ./tasks

# Run client
sdci-cli run --token YOUR_TOKEN http://localhost:8842 TASK_NAME [ARGS...]
```

Hooks: ruff (lint + format), isort (black profile), trailing-whitespace, end-of-file-fixer, check-yaml, check-added-large-files, debug-statements.

## Testing

No unit test framework yet. Smoke tests run via Docker Compose (`make docker-testing`), which starts the server, runs a client task, and tears down.

## Architecture

**Server** (`src/sdci/server.py`): FastAPI app on port 8842. Endpoints:
- `GET /health` — unauthenticated liveness check (used by the Docker healthcheck)
- `POST /tasks/{task_name}/` — executes `{TASKS_DIR}/{task_name}.sh` as async subprocess, returns streaming response (auth required)
- `POST /tasks/{task_name}/status/` — returns task state (pid, exit_code, status) (auth required)
- `POST /upload_file/` — multipart upload of a single file (`file: UploadFile`, `path: str` form field). Saves to `{UPLOADS_DIR}/{path}/{filename}` (dirs created recursively, original filename kept). Returns `UploadOutputSchema` (`path`, `size`, `status="UPLOADED"`). 400 on path traversal / invalid filename, 409 if destination exists, 429 if busy (auth required).

Auth is Bearer token via `HTTPBearer`, compared against `Settings.SERVER_TOKEN`.

A global `asyncio.Lock` enforces single-task execution — the server rejects requests with 429 while a task OR upload is running. Task state is tracked in a global `task_info_store` dict, keyed by task name. The upload endpoint acquires the same lock and releases it in a `finally`.

**Client** (`src/sdci/cli.py`): Click CLI (`sdci-cli`) with subcommands:
- `run` — triggers a task, streams output, then polls `/status/` and exits with the task's exit code. Token resolution order: `--token` flag → `SDCI_TOKEN` env var → system keyring (`keyring.get_password("SDCI_token", server)`).
- `upload-asset [--token] SERVER LOCAL_FILE REMOTE_PATH` — uploads a single file to `/upload_file/`, streaming it with a `click.progressbar`. Same token resolution as `run`. Maps 401/400/409/429 to `SDCIException`, exits non-zero on failure.
- `store-token SERVER TOKEN` / `delete-token SERVER` — manage the keyring entry for a server.

**Task Runner** (`src/sdci/server_runner.py`): `CommandRunner` runs `.sh` scripts from `TASKS_DIR` via `asyncio.create_subprocess_exec`, streaming stdout line-by-line. Kills the process on timeout (default 120s). `AvailableCommandsDescriber` lists available tasks by scanning for `.sh` files. `FileUploader` (chainable `.for_lock()`) validates the upload destination (`resolved_path` rejects path traversal / filenames with separators via `os.path.realpath` + `os.path.commonpath`) and streams an `UploadFile` to disk in 1 MiB chunks, refusing to overwrite an existing file.

**Settings** (`src/sdci/settings.py`): Exposes config **twice** — as module-level constants AND as a `Settings` class. The server reads `Settings.*` (so its `--server-token`/`--tasks-dir`/`--uploads-dir` flags, which mutate the class, take effect); the client reads the module-level `CLIENT_REQUEST_TIMEOUT_SECONDS` constant directly (frozen at import). When changing config behavior, update the right form. Key env vars: `SDCI_SERVER_TOKEN`, `TASK_RUN_TIMEOUT`, `CLIENT_REQUEST_TIMEOUT`, `TASKS_DIR`, `UPLOADS_DIR` (legacy `UPLOAD_DIR` still honored as a fallback).

**Entry points** (defined in `pyproject.toml`):
- `sdci-server` → `sdci.__main__:run_server`
- `sdci-cli` → `sdci.cli:entrypoint`

## Docker

The Dockerfile installs Docker CLI inside the image (for tasks that need to run Docker commands via mounted socket). The docker-compose.yaml defines three services: `sdci-base` (build-only), `sdci-server` (with healthcheck), and `sdci-client` (for smoke tests). The server mounts `/var/run/docker.sock` and the tasks directory.

## Development guidelines
- DO NOT USE "Co-Authored by Claude" into the commits.
- Commits must follow the conventional commit format.
- Before pushing any code, use `pre-commit`.
- Bump version in `pyproject.toml` before pushing a new PR.
- In case of a complex logic, encapsulate it in a service layer.
- Use Strict TDD for new features.
- For `superpowers` skill: store specs into `docs/specs`.
- After a new feature, write a documentation page in `docs/manual/`.
  - Use concise texting. Use mermaid JS classes for diagrams if needed for a better explanation.
