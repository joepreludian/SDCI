# SDCI systemd Setup — Design Spec

**Date:** 2026-06-14
**Status:** Approved (design), pending implementation plan

## Context

SDCI ships a server (`sdci-server`) that, today, is launched directly with flags:

```bash
sdci-server --host 127.0.0.1 --port 8842 --server-token TOKEN --tasks-dir ./tasks
```

Running it as a long-lived service on a Linux host currently means hand-writing a
systemd unit, dropping the token somewhere, and wiring up `daemon-reload` /
`enable` / `restart` by hand. This feature adds a first-class installer so an
operator can stand the server up as a managed systemd service in one command:

```bash
sdci-server setup --ip <IP> --token <TOKEN>
```

`setup` renders a **simple** `sdci.service` unit (plus a root-only environment
file for the token), installs them under `/etc/systemd/system`, and reloads +
enables + restarts the service. It runs as the invoking user and escalates to
`sudo` only for the privileged steps.

## Goals

- One command turns a host into a running, boot-enabled SDCI server.
- Keep the secret token **out of** the unit file, `systemctl cat`, and the process list.
- Run the service as the **invoking user**, not root.
- Be safe and explicit about directories: create the tool's own default dirs,
  but never silently create operator-specified ones.
- All rendering / path / sequencing logic is unit-testable without a real systemd
  (so the suite runs on the macOS dev box and in CI).

## Non-Goals

- User-level units (`~/.config/systemd/user/`). This installs a **system** unit.
- Managing multiple SDCI instances beyond a `--service-name` override.
- Creating a dedicated `sdci` system user, or chowning operator-specified dirs.
- Uninstall / teardown command (may come later; out of scope here).
- Non-systemd init systems (SysV, OpenRC, launchd).

## Design Decisions (confirmed)

| Decision | Choice |
|----------|--------|
| Command wiring | `sdci-server` becomes a Click **group**. The current behavior moves to a `serve` subcommand; `setup` is the new subcommand. **Breaking change** — `sdci-server --host ...` becomes `sdci-server serve --host ...`. |
| Token storage | Written to `/etc/sdci/sdci.env` (`root:root`, mode `0600`), referenced by the unit via `EnvironmentFile=`. Never placed in `ExecStart`. |
| Service user | The **invoking user** (`getpass.getuser()`), overridable with `--user`. |
| Privilege | `setup` runs as the user and shells out to `sudo` for each privileged step (first call prompts for the password). |
| Code structure | A `SystemdInstaller` **service class** (Approach A), styled after `FileUploader`/`CommandRunner`. Pure stdlib; no new dependencies. |
| Default dirs | `~/.sdci/tasks` and `~/.sdci/uploads` are **created** if missing. |
| Operator-specified dirs | If `--tasks-dir`/`--upload-dir` is passed explicitly, the dir **must already exist** — setup validates and errors out, it does **not** create it. |
| Existing unit | Abort with a confirm prompt unless `--force` is given. |

## Command Interface

`sdci-server` is restructured into a group with two subcommands.

### `sdci-server serve` (existing behavior, renamed)

Identical flags and behavior to today's `run_server`:

```bash
sdci-server serve [--host ...] [--port ...] [--server-token ...] [--tasks-dir ...] [--upload-dir ...]
```

### `sdci-server setup` (new)

```bash
sdci-server setup --ip <IP> --token <TOKEN> \
  [--port 8842] [--tasks-dir DIR] [--upload-dir DIR] \
  [--user LOGIN] [--service-name sdci] [--force]
```

| Flag | Required | Default | Purpose |
|------|----------|---------|---------|
| `--ip` | yes | — | becomes `serve --host <ip>` in the unit |
| `--token` | yes | — | written to the env file as `SDCI_SERVER_TOKEN` |
| `--port` | no | `8842` | `serve --port` |
| `--tasks-dir` | no | `~/.sdci/tasks` | absolute tasks dir (see dir rules below) |
| `--upload-dir` | no | `~/.sdci/uploads` | absolute upload dir (see dir rules below) |
| `--user` | no | invoking user | systemd `User=` |
| `--service-name` | no | `sdci` | unit filename (`<name>.service`) |
| `--force` | no | off | overwrite an existing unit without prompting |

**Directory rules:**

- The unit's `WorkingDirectory` (`~/.sdci`) is **tool-managed** and always created
  if missing — independent of the tasks/upload dir rules below — so the service
  never fails on a missing `WorkingDirectory`.
- When a dir is left at its **default** (`~/.sdci/...`), setup creates it
  (`os.makedirs(..., exist_ok=True)`), owned by the invoking user.
- When a dir is **explicitly provided**, setup requires it to already exist;
  otherwise it raises `SDCIServerException` and aborts **without** creating it.

`~` is expanded against the **target user's** home (`--user`, default the invoking
user). Paths written into the unit are always absolute.

## Rendered Artifacts

### Unit — `/etc/systemd/system/<service-name>.service` (`root:root`, `0644`)

```ini
[Unit]
Description=SDCI - Sidecar Micro CD server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=<user>
WorkingDirectory=<home-of-user>/.sdci
EnvironmentFile=/etc/sdci/sdci.env
ExecStart=<abs path to sdci-server> serve --host <ip> --port <port> --tasks-dir <tasks_dir> --upload-dir <upload_dir>
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

- The token is **not** present here.
- `<abs path to sdci-server>` is resolved at setup time via
  `shutil.which("sdci-server")` (captures the venv path; systemd has a minimal
  `PATH`). If it cannot be resolved, setup raises `SDCIServerException`.
- `WorkingDirectory` is the target user's `~/.sdci`.

### Env file — `/etc/sdci/sdci.env` (`root:root`, `0600`)

```
SDCI_SERVER_TOKEN=<token>
```

`serve` reads `SDCI_SERVER_TOKEN` when `--server-token` is not given (existing
behavior in `settings.py` / `server.py`), so it picks the token up from the
`EnvironmentFile`.

## Components (Approach A)

### `src/sdci/server_setup.py` (new)

A `SystemdInstaller` service class keeps rendering, path logic, validation, and
the privileged-command sequence isolated and unit-testable. Unit/env bodies are
module-level `string.Template` constants.

```python
class SystemdInstaller:
    def __init__(self, *, ip, token, port=8842, tasks_dir=None, upload_dir=None,
                 user=None, service_name="sdci", force=False): ...

    # paths
    @property
    def unit_path(self) -> str: ...        # /etc/systemd/system/<name>.service
    @property
    def env_path(self) -> str: ...         # /etc/sdci/sdci.env

    # rendering (pure, no I/O)
    def render_unit(self) -> str: ...      # token MUST NOT appear here
    def render_env(self) -> str: ...       # SDCI_SERVER_TOKEN=<token>

    # checks
    def check_platform(self) -> None: ...  # Linux + systemctl on PATH, else raise
    def resolve_binary(self) -> str: ...   # shutil.which("sdci-server"), else raise
    def prepare_dirs(self) -> None: ...    # create defaults / validate explicit dirs

    # privileged helpers + orchestration
    def _run_privileged(self, args: list[str], input: str | None = None) -> None: ...
    def install(self) -> None: ...         # full sequence (section below)
```

`--tasks-dir`/`--upload-dir` are tracked as "explicit vs default" (e.g. the
constructor receives `None` for an unset dir and substitutes the default,
remembering which were defaulted) so `prepare_dirs()` can apply the create-vs-validate rule.

### `src/sdci/server.py` (refactor)

- Add a `@click.group()` (e.g. `main`).
- Move the current `run_server` body into a `serve` subcommand (logging config,
  settings override, startup checks, `uvicorn.run` — unchanged).
- Add a thin `setup` subcommand that constructs `SystemdInstaller(**opts)` and
  calls `.install()`, translating `SDCIServerException` into a clear message +
  `exit(1)`.

### Entry point

`pyproject.toml` `sdci-server` is repointed from `sdci.__main__:run_server` to the
new group (e.g. `sdci.server:main`); `__main__.py` is updated to invoke the group.

## Install Flow & Privilege

`setup` runs as the invoking user and shells out to `sudo` for each privileged
step (the first `sudo` call prompts for the password; the credential is then
cached for the rest):

1. **Platform guard** — require `sys.platform == "linux"` and
   `shutil.which("systemctl")`. Otherwise raise `SDCIServerException` (clean
   failure on the macOS dev box).
2. **Resolve binary** — `shutil.which("sdci-server")`; error if missing.
3. **Prepare dirs** — always create the tool-managed `WorkingDirectory`
   (`~/.sdci`); create default tasks/upload dirs; validate that explicit dirs
   exist (raise if not). No creation of operator-specified dirs.
4. **Existing-unit check** — if `unit_path` exists and `--force` is not set,
   prompt for confirmation; abort on "no".
5. **Privileged steps** (each via `sudo`):
   - `sudo install -d -m 0755 /etc/sdci`
   - write env file: pipe `render_env()` to `sudo tee <env_path>` via **stdin**,
     then `sudo chmod 600 <env_path>` (token never appears on argv / `ps`)
   - write unit: pipe `render_unit()` to `sudo tee <unit_path>` via stdin, then
     `sudo chmod 644 <unit_path>`
   - `sudo systemctl daemon-reload`
   - `sudo systemctl enable <service-name>`
   - `sudo systemctl restart <service-name>`
6. Print success and a hint: `systemctl status <service-name>`.

## Error Handling

`SDCIServerException` is raised for:

- non-systemd platform (not Linux, or `systemctl` absent),
- `sdci-server` binary not resolvable,
- an explicit `--tasks-dir`/`--upload-dir` that does not exist,
- a failing `sudo`/`systemctl` step (surface the command's stderr),
- user-declined overwrite of an existing unit.

The `setup` Click command catches it, prints a clear message, and `exit(1)`.

## Testing (TDD) — `tests/test_server_setup.py`

All dependencies (`subprocess`, `shutil.which`, `sys.platform`, filesystem) are
mocked/monkeypatched, so the suite runs without a real systemd:

- `render_unit()` produces the correct `ExecStart` (absolute binary path, host,
  port, tasks/upload dirs) and includes `User=`, `EnvironmentFile=`,
  `Restart=on-failure`.
- `render_unit()` **does not** contain the token.
- `render_env()` contains `SDCI_SERVER_TOKEN=<token>`.
- `unit_path` and `env_path` resolve to the expected locations (with a custom
  `--service-name` too).
- `check_platform()` raises when `shutil.which("systemctl")` is `None` or the
  platform is not Linux.
- `resolve_binary()` raises when `shutil.which("sdci-server")` is `None`.
- `prepare_dirs()` always creates the `WorkingDirectory` (`~/.sdci`), creates
  default tasks/upload dirs when missing, and raises for an explicit dir that does
  not exist (and does **not** create it).
- `install()` issues the expected privileged sequence (mock `subprocess.run` /
  `_run_privileged`): asserts `daemon-reload`, `enable`, `restart` are invoked and
  the token is passed via **stdin**, not argv.
- existing unit without `--force` aborts (mock `os.path.exists` + confirmation).

Manual end-to-end (on a Linux host with systemd):
`sdci-server setup --ip 0.0.0.0 --token TEST`, then confirm
`systemctl status sdci` shows it active, `systemctl cat sdci` does **not** reveal
the token, and `/etc/sdci/sdci.env` is `0600` root-owned.

## Breaking Change, Documentation & Release

- **Breaking:** `sdci-server --host ...` → `sdci-server serve --host ...`. Update:
  - `Dockerfile:28` → `CMD ["sdci-server", "serve", "--host", "0.0.0.0"]`
    (verify `docker-compose.yaml`, whose server inherits the Dockerfile `CMD`).
  - `README.md` run example(s).
  - `CLAUDE.md` architecture / run-command notes (document `serve` + `setup`).
- New manual page `docs/manual/systemd-setup.md` (concise; a small Mermaid
  diagram of the install sequence).
- Bump `pyproject.toml` `version` `0.7.0 → 0.8.0` (breaking CLI change).
- Conventional commits; **no** "Co-Authored-By"; run `pre-commit` before pushing.
