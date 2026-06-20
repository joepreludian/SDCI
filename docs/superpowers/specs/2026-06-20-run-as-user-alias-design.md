# SDCI `--run_as_user` Alias — Design Spec

**Date:** 2026-06-20
**Status:** Approved (design)
**Base branch:** `feature/systemd-setup`

## Context

`sdci-server setup` installs SDCI as a systemd service. It already accepts a
`--user` option that sets the unit's `User=` directive (the identity the service
runs as) and, when omitted, defaults to the invoking user via
`getpass.getuser()` inside `SystemdInstaller`. The user requested a
`--run_as_user` flag "to provide a user to be running the server with", keeping
the current value when not provided — which is exactly the existing `--user`
semantics.

## Goal

Add `--run_as_user` as an **alias** of the existing `--user` option so operators
can use either name. Purely additive; no behavior change and no breaking change.

## Non-Goals

- Renaming or removing `--user` (it keeps working).
- Decoupling the service-run user from the home/working/tasks-dir owner — both
  remain driven by the same value, as today.
- Any change to `SystemdInstaller` internals.

## Design Decisions (confirmed)

| Decision | Choice |
|----------|--------|
| Relationship to `--user` | **Alias.** Both `--user` and `--run_as_user` map to the same Click parameter (`user`). |
| Default when neither given | Unchanged — `SystemdInstaller` resolves `None` to the invoking user. |
| Naming style | `--run_as_user` (underscores), matching the user's request verbatim. |
| Installer changes | None. |
| Version | Minor bump `1.0.0` → `1.1.0` (additive feature). |

## Implementation

Single change in `src/sdci/server.py`, on the `setup` command's option:

```python
@click.option(
    "--user",
    "--run_as_user",
    "user",
    default=None,
    help="User to run the service as (default: invoking user). Alias: --run_as_user",
)
```

The explicit third positional (`"user"`) pins the parameter name, so the
`def setup(..., user, ...)` signature and the `SystemdInstaller(user=user)` call
are untouched.

## Testing (TDD)

Add to `tests/test_server_cli.py`:

1. `--run_as_user deploy` forwards `user="deploy"` to `SystemdInstaller`
   (alongside the existing `--user deploy` coverage).
2. The `setup` command's parameter exposes both option strings
   (`--user` and `--run_as_user`).

Existing `setup` tests (defaults, `--user` forwarding, success/failure paths)
must continue to pass unchanged.

## Documentation

Update `docs/manual/systemd-setup.md` to mention the `--run_as_user` alias in the
options reference.
