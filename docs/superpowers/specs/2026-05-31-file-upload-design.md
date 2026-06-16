# SDCI File Upload — Design Spec

**Date:** 2026-05-31
**Status:** Approved (design), pending implementation plan

## Context

SDCI currently lets a client trigger remote shell-script tasks on a server. Many
deployment workflows also need to push an **asset** (a build artifact, a config
file, an archive) to the server before or instead of running a task. Today there
is no way to do this — the operator has to copy files out of band (scp, rsync,
etc.).

This feature adds a first-class, authenticated, single-file upload path:

- A server endpoint that receives one file into a configurable upload directory.
- A client `upload-asset` subcommand that streams the file and shows a progress bar.

Uploading more than one file at a time is **out of scope** — if the user needs to
send many files they zip them first and upload the archive. The server already
enforces "do one thing at a time" via a global lock; uploads join that model so a
task run and an upload can never clobber each other.

## Goals

- Upload exactly one file per request.
- Configurable server-side upload directory (flag + env var).
- Place the file inside a caller-specified relative directory, created recursively.
- Block path traversal — uploads can never escape the upload directory.
- Fail (do not overwrite) if the destination file already exists.
- Client shows an upload progress bar and fails clearly on timeout / error.

## Non-Goals

- Multi-file / batch upload.
- Server-side unzip or post-processing.
- Renaming the file on upload (the destination keeps the original filename).
- Resumable / chunked-resume uploads.

## Design Decisions (confirmed)

| Decision | Choice |
|----------|--------|
| Concurrency | Uploads **share the existing global task lock** — the server runs either one task OR one upload at a time. |
| Destination exists | **Fail** with an error (no silent overwrite). |
| Progress bar | `click.progressbar` — **no new dependency**. |
| `REMOTE_PATH` meaning | A relative **directory** (possibly nested, e.g. `dir1/dir2/dir3`) inside the upload dir. The file is saved there under its **original filename**. Path traversal is rejected. |

## Server

### Configuration (`src/sdci/settings.py`)

Add a new config value following the existing `TASKS_DIR` pattern — both a
module-level constant and a `Settings` class attribute:

```python
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "./uploads")

class Settings:
    ...
    UPLOAD_DIR = UPLOAD_DIR
```

`run_server` (in `src/sdci/server.py`) gains a `--upload-dir` Click option that
overrides `Settings.UPLOAD_DIR` when provided (mirrors `--tasks-dir`). At startup
the directory is created if it does not exist (`os.makedirs(..., exist_ok=True)`).

### Upload logic (`src/sdci/server_runner.py`)

A new `FileUploader` class, styled after `CommandRunner` (chainable `.for_lock()`),
keeps path resolution and validation isolated and unit-testable:

- `__init__(self, remote_dir: str, filename: str)` — stores the requested relative
  directory and the uploaded file's basename.
- `resolved_path` — computes `UPLOAD_DIR / remote_dir / filename`, resolved to an
  absolute real path. **Validation:** the resolved path must be inside the resolved
  `UPLOAD_DIR`; otherwise raise `SDCIServerException` (→ HTTP 400). Use
  `os.path.realpath` + `os.path.commonpath`, and also reject the filename if it
  contains a path separator.
- `save(self, upload_file)` — creates the target directory recursively, raises
  `SDCIServerException` if the destination file already exists (→ HTTP 409), then
  streams the upload to disk in chunks (e.g. 1 MiB) and returns the byte count.

### Endpoint (`src/sdci/server.py`)

`POST /upload_file/`, protected by the existing `verify_token` dependency,
accepts `multipart/form-data`:

- `file: UploadFile` — the file payload.
- `path: str` (form field) — the relative destination directory (`REMOTE_PATH`).

Flow:

1. If `lock.locked()` → **429** `"Server is busy running a task or upload"`.
2. `await lock.acquire()`; wrap the rest in `try/finally` to guarantee release.
3. Build `FileUploader(path, file.filename).for_lock(lock)`.
4. Resolve + validate the path → **400** on traversal / invalid filename.
5. Save → **409** if the destination already exists.
6. On success return JSON:
   ```json
   { "path": "<remote_dir>/<filename>", "size": 1234, "status": "UPLOADED" }
   ```

A new `UploadOutputSchema` (Pydantic, in `src/sdci/schemas.py`) types the response.

### Status code summary

| Status | Meaning |
|--------|---------|
| 200 | Upload succeeded |
| 400 | Path traversal / invalid destination |
| 401 | Bad/missing token |
| 409 | Destination file already exists |
| 429 | Server busy (task or upload in progress) |

## Client

### New subcommand (`src/sdci/cli.py`)

```
sdci-cli upload-asset [--token TOKEN] SERVER LOCAL_FILE REMOTE_PATH
```

- `LOCAL_FILE` — path to the file on the host machine (validated to exist).
- `REMOTE_PATH` — relative destination directory on the server.
- Token resolution identical to `run`: `--token` → `SDCI_TOKEN` env → keyring
  (`keyring.get_password("SDCI_token", server)`).
- Exits non-zero on any failure; prints a clear message.

### Client service (`src/sdci/client_service.py`)

Add `SDCIClient.upload(self, local_file: str, remote_path: str)`:

- Opens `LOCAL_FILE` and wraps it in a small progress file-object whose `read(n)`
  reads from the underlying file and advances a `click.progressbar` (length = file
  size) by the bytes returned.
- Sends a `requests` POST to `{endpoint}/upload_file/` with:
  - `files={"file": (basename, progress_wrapper)}`
  - `data={"path": remote_path}`
  - `Authorization: Bearer <token>` header
  - `timeout=CLIENT_REQUEST_TIMEOUT_SECONDS`
- Maps responses to `SDCIException`:
  - 401 → unauthorized, 400 → invalid path, 409 → file exists, 429 → server busy.
  - `requests` `ConnectionError` / `Timeout` / `HTTPError` → wrapped `SDCIException`.
- Returns the parsed `UploadOutputSchema` on success.

The existing `requests` exception handling in `trigger` is the model to follow;
the timeout error must be caught explicitly so a stalled upload fails cleanly.

## Error Handling

- **Server busy:** 429, client prints "SERVER HAS A WORKING TASK OR UPLOAD — PLEASE WAIT".
- **Traversal / invalid path:** 400, client aborts with the server detail message.
- **Already exists:** 409, client aborts — operator must remove the file first.
- **Timeout / connection:** client wraps in `SDCIException`, non-zero exit.
- Server always releases the lock in `finally`, even on validation failure.

## Testing

pytest unit tests (framework already installed) under `tests/`:

- `FileUploader` rejects path traversal (`../escape`, absolute paths, filename
  containing a separator).
- `FileUploader` creates nested directories recursively and writes file contents.
- `FileUploader` raises on an existing destination file.
- Client status-code → `SDCIException` mapping (401 / 400 / 409 / 429), using a
  stubbed/mocked `requests` response.

Manual end-to-end: start `sdci-server --upload-dir ./uploads`, run
`sdci-cli upload-asset http://localhost:8842 ./some.zip releases/v1`, confirm the
file lands at `./uploads/releases/v1/some.zip`, the progress bar renders, and a
second upload of the same file fails with 409.

## Documentation & Release

- Update `README.md` and `CLAUDE.md` architecture notes with the new endpoint,
  the `--upload-dir` flag / `UPLOAD_DIR` env var, and the `upload-asset` command.
- Bump `version` in `pyproject.toml` (repo convention: bump before opening a PR).
