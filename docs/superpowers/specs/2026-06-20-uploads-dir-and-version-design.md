# Design: `--uploads-dir` configuration + `--version` flag

**Date:** 2026-06-20
**Status:** Implemented

## Summary

Three related CLI improvements:

1. **`setup --uploads-dir`** — the systemd `setup` command can now configure the
   uploads directory, which is baked into the generated unit's `ExecStart`.
2. **Rename `serve --upload-dir` → `serve --uploads-dir`** — for naming
   consistency with `--tasks-dir` and the new `setup` flag. Hard rename (the old
   spelling is removed).
3. **`--version`** — both `sdci-server` and `sdci-cli` print the installed package
   version and exit.

## Decisions

- **Hard rename** of the serve flag (no `--upload-dir` alias). The project is
  alpha; a clean name is preferred over carrying a deprecated spelling.
- **`--version` on both binaries** (server and client), implemented with Click's
  eager `version_option` so `sdci-cli --version` exits before its startup banner.
- **Env var renamed to `UPLOADS_DIR`** with the legacy `UPLOAD_DIR` kept as a
  read fallback, so existing deployments keep working:
  `UPLOADS_DIR = os.environ.get("UPLOADS_DIR", os.environ.get("UPLOAD_DIR", "./uploads"))`.
  The internal `Settings.UPLOADS_DIR` attribute is renamed to match.
- **`setup --uploads-dir` mirrors `--tasks-dir`**: default `~/.sdci/uploads`
  (auto-created); an explicit value is made absolute and **must already exist**
  (raises `SDCIServerException` otherwise, never created). This keeps the two
  directory options in the installer behaving identically and predictably, even
  though `serve` itself would create the directory at startup.

## Changes by file

| File | Change |
|---|---|
| `src/sdci/settings.py` | `UPLOAD_DIR` → `UPLOADS_DIR` (constant + `Settings` attr) with `UPLOAD_DIR` env fallback |
| `src/sdci/server_runner.py` | `FileUploader.resolved_path` reads `Settings.UPLOADS_DIR` |
| `src/sdci/server.py` | `serve` flag rename + `Settings.UPLOADS_DIR`; `setup` gains `--uploads-dir`; `@click.version_option` on the group |
| `src/sdci/cli.py` | `@click.version_option` on the `entrypoint` group |
| `src/sdci/server_setup.py` | `SystemdInstaller` accepts `uploads_dir`, renders `--uploads-dir` into `ExecStart`, prepares the dir |
| `docs/manual/{file-upload,systemd-setup,version}.md`, `README.md`, `CLAUDE.md` | Documentation |
| `pyproject.toml` | Version bump 1.1.0 → 1.2.0 |

## Testing (strict TDD)

- `tests/test_server_cli.py` — serve param rename, `setup --uploads-dir`
  forwarding, `sdci-server --version`.
- `tests/test_client_cli.py` (new) — `sdci-cli --version` prints version, exits 0,
  skips the banner.
- `tests/test_server_setup.py` — default/explicit `uploads_dir` rendering, default
  path property, and `prepare_dirs` behavior (create default, reject explicit
  missing, accept explicit existing).
- `tests/test_file_uploader.py` — `Settings.UPLOADS_DIR`.

`--version` tests assert against `importlib.metadata.version("sdci")` dynamically,
so they are independent of the version bump.
