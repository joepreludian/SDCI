"""Tests for SystemdInstaller service class (TDD - written before implementation)."""

import os
import sys

import pytest

from sdci.exceptions import SDCIServerException
from sdci.server_setup import SystemdInstaller

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

FAKE_BINARY = "/usr/local/bin/sdci-server"
FAKE_TOKEN = "supersecrettoken"
FAKE_IP = "192.168.1.10"
FAKE_PORT = 8842
FAKE_USER = "deployuser"


# ---------------------------------------------------------------------------
# Path / property tests
# ---------------------------------------------------------------------------


class TestPaths:
    def test_unit_path_default_service_name(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(tmp_path / "home" / FAKE_USER) if p == f"~{FAKE_USER}" else p,
        )
        installer = SystemdInstaller(ip=FAKE_IP, token=FAKE_TOKEN, user=FAKE_USER)
        assert installer.unit_path == "/etc/systemd/system/sdci.service"

    def test_unit_path_custom_service_name(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(tmp_path / "home" / FAKE_USER) if p == f"~{FAKE_USER}" else p,
        )
        installer = SystemdInstaller(
            ip=FAKE_IP, token=FAKE_TOKEN, user=FAKE_USER, service_name="myapp"
        )
        assert installer.unit_path == "/etc/systemd/system/myapp.service"

    def test_env_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(tmp_path / "home" / FAKE_USER) if p == f"~{FAKE_USER}" else p,
        )
        installer = SystemdInstaller(ip=FAKE_IP, token=FAKE_TOKEN, user=FAKE_USER)
        assert installer.env_path == "/etc/sdci/sdci.env"

    def test_working_dir(self, tmp_path, monkeypatch):
        home = tmp_path / "home" / FAKE_USER
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(home) if p == f"~{FAKE_USER}" else p,
        )
        installer = SystemdInstaller(ip=FAKE_IP, token=FAKE_TOKEN, user=FAKE_USER)
        assert installer.working_dir == str(home / ".sdci")

    def test_default_tasks_dir(self, tmp_path, monkeypatch):
        home = tmp_path / "home" / FAKE_USER
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(home) if p == f"~{FAKE_USER}" else p,
        )
        installer = SystemdInstaller(ip=FAKE_IP, token=FAKE_TOKEN, user=FAKE_USER)
        assert installer.tasks_dir == str(home / ".sdci" / "tasks")

    def test_user_defaults_to_current_user(self, monkeypatch):
        monkeypatch.setattr("getpass.getuser", lambda: "currentuser")
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: "/home/currentuser" if "currentuser" in p else p,
        )
        installer = SystemdInstaller(ip=FAKE_IP, token=FAKE_TOKEN)
        assert installer.user == "currentuser"


# ---------------------------------------------------------------------------
# render_unit() tests
# ---------------------------------------------------------------------------


class TestRenderUnit:
    def _make_installer(self, tmp_path, monkeypatch, **kwargs):
        home = tmp_path / "home" / FAKE_USER
        home.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(home) if p == f"~{FAKE_USER}" else p,
        )
        monkeypatch.setattr(
            "shutil.which", lambda name: FAKE_BINARY if name == "sdci-server" else None
        )
        return SystemdInstaller(ip=FAKE_IP, token=FAKE_TOKEN, user=FAKE_USER, **kwargs)

    def test_exec_start_contains_binary(self, tmp_path, monkeypatch):
        installer = self._make_installer(tmp_path, monkeypatch)
        unit = installer.render_unit()
        assert FAKE_BINARY in unit

    def test_exec_start_contains_serve_subcommand(self, tmp_path, monkeypatch):
        installer = self._make_installer(tmp_path, monkeypatch)
        unit = installer.render_unit()
        assert f"{FAKE_BINARY} serve" in unit

    def test_exec_start_contains_host(self, tmp_path, monkeypatch):
        installer = self._make_installer(tmp_path, monkeypatch)
        unit = installer.render_unit()
        assert f"--host {FAKE_IP}" in unit

    def test_exec_start_contains_port(self, tmp_path, monkeypatch):
        installer = self._make_installer(tmp_path, monkeypatch)
        unit = installer.render_unit()
        assert f"--port {FAKE_PORT}" in unit

    def test_exec_start_contains_tasks_dir(self, tmp_path, monkeypatch):
        home = tmp_path / "home" / FAKE_USER
        home.mkdir(parents=True, exist_ok=True)
        installer = self._make_installer(tmp_path, monkeypatch)
        unit = installer.render_unit()
        assert "--tasks-dir" in unit
        assert str(home / ".sdci" / "tasks") in unit

    def test_no_upload_dir_in_unit(self, tmp_path, monkeypatch):
        installer = self._make_installer(tmp_path, monkeypatch)
        unit = installer.render_unit()
        assert "--upload-dir" not in unit

    def test_user_field_present(self, tmp_path, monkeypatch):
        installer = self._make_installer(tmp_path, monkeypatch)
        unit = installer.render_unit()
        assert f"User={FAKE_USER}" in unit

    def test_environment_file_present(self, tmp_path, monkeypatch):
        installer = self._make_installer(tmp_path, monkeypatch)
        unit = installer.render_unit()
        assert "EnvironmentFile=/etc/sdci/sdci.env" in unit

    def test_restart_on_failure(self, tmp_path, monkeypatch):
        installer = self._make_installer(tmp_path, monkeypatch)
        unit = installer.render_unit()
        assert "Restart=on-failure" in unit

    def test_token_not_in_unit(self, tmp_path, monkeypatch):
        installer = self._make_installer(tmp_path, monkeypatch)
        unit = installer.render_unit()
        assert FAKE_TOKEN not in unit

    def test_working_directory_in_unit(self, tmp_path, monkeypatch):
        home = tmp_path / "home" / FAKE_USER
        home.mkdir(parents=True, exist_ok=True)
        installer = self._make_installer(tmp_path, monkeypatch)
        unit = installer.render_unit()
        assert f"WorkingDirectory={str(home / '.sdci')}" in unit

    def test_custom_port_reflected_in_unit(self, tmp_path, monkeypatch):
        installer = self._make_installer(tmp_path, monkeypatch, port=9999)
        unit = installer.render_unit()
        assert "--port 9999" in unit

    def test_explicit_tasks_dir_in_unit(self, tmp_path, monkeypatch):
        tasks = tmp_path / "custom_tasks"
        tasks.mkdir()
        home = tmp_path / "home" / FAKE_USER
        home.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(home) if p == f"~{FAKE_USER}" else p,
        )
        monkeypatch.setattr(
            "shutil.which", lambda name: FAKE_BINARY if name == "sdci-server" else None
        )
        installer = SystemdInstaller(
            ip=FAKE_IP, token=FAKE_TOKEN, user=FAKE_USER, tasks_dir=str(tasks)
        )
        unit = installer.render_unit()
        assert str(tasks) in unit


# ---------------------------------------------------------------------------
# render_env() tests
# ---------------------------------------------------------------------------


class TestRenderEnv:
    def test_env_contains_token(self, tmp_path, monkeypatch):
        home = tmp_path / "home" / FAKE_USER
        home.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(home) if p == f"~{FAKE_USER}" else p,
        )
        installer = SystemdInstaller(ip=FAKE_IP, token=FAKE_TOKEN, user=FAKE_USER)
        env = installer.render_env()
        assert f"SDCI_SERVER_TOKEN={FAKE_TOKEN}" in env

    def test_env_ends_with_newline(self, tmp_path, monkeypatch):
        home = tmp_path / "home" / FAKE_USER
        home.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(home) if p == f"~{FAKE_USER}" else p,
        )
        installer = SystemdInstaller(ip=FAKE_IP, token=FAKE_TOKEN, user=FAKE_USER)
        env = installer.render_env()
        assert env.endswith("\n")


# ---------------------------------------------------------------------------
# check_platform() tests
# ---------------------------------------------------------------------------


class TestCheckPlatform:
    def test_raises_when_not_linux(self, tmp_path, monkeypatch):
        home = tmp_path / "home" / FAKE_USER
        home.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(home) if p == f"~{FAKE_USER}" else p,
        )
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setattr("shutil.which", lambda name: "/bin/systemctl")
        installer = SystemdInstaller(ip=FAKE_IP, token=FAKE_TOKEN, user=FAKE_USER)
        with pytest.raises(SDCIServerException, match="linux"):
            installer.check_platform()

    def test_raises_when_systemctl_missing(self, tmp_path, monkeypatch):
        home = tmp_path / "home" / FAKE_USER
        home.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(home) if p == f"~{FAKE_USER}" else p,
        )
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr("shutil.which", lambda name: None)
        installer = SystemdInstaller(ip=FAKE_IP, token=FAKE_TOKEN, user=FAKE_USER)
        with pytest.raises(SDCIServerException, match="systemctl"):
            installer.check_platform()

    def test_passes_on_linux_with_systemctl(self, tmp_path, monkeypatch):
        home = tmp_path / "home" / FAKE_USER
        home.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(home) if p == f"~{FAKE_USER}" else p,
        )
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(
            "shutil.which",
            lambda name: "/bin/systemctl" if name == "systemctl" else None,
        )
        installer = SystemdInstaller(ip=FAKE_IP, token=FAKE_TOKEN, user=FAKE_USER)
        # Should not raise
        installer.check_platform()


# ---------------------------------------------------------------------------
# resolve_binary() tests
# ---------------------------------------------------------------------------


class TestResolveBinary:
    def test_raises_when_binary_not_found(self, tmp_path, monkeypatch):
        home = tmp_path / "home" / FAKE_USER
        home.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(home) if p == f"~{FAKE_USER}" else p,
        )
        monkeypatch.setattr("shutil.which", lambda name: None)
        installer = SystemdInstaller(ip=FAKE_IP, token=FAKE_TOKEN, user=FAKE_USER)
        with pytest.raises(SDCIServerException, match="sdci-server"):
            installer.resolve_binary()

    def test_returns_absolute_path_when_found(self, tmp_path, monkeypatch):
        home = tmp_path / "home" / FAKE_USER
        home.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(home) if p == f"~{FAKE_USER}" else p,
        )
        monkeypatch.setattr(
            "shutil.which", lambda name: FAKE_BINARY if name == "sdci-server" else None
        )
        installer = SystemdInstaller(ip=FAKE_IP, token=FAKE_TOKEN, user=FAKE_USER)
        result = installer.resolve_binary()
        assert result == FAKE_BINARY


# ---------------------------------------------------------------------------
# prepare_dirs() tests
# ---------------------------------------------------------------------------


class TestPrepareDirs:
    def test_creates_working_dir_when_missing(self, tmp_path, monkeypatch):
        home = tmp_path / "home" / FAKE_USER
        home.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(home) if p == f"~{FAKE_USER}" else p,
        )
        installer = SystemdInstaller(ip=FAKE_IP, token=FAKE_TOKEN, user=FAKE_USER)
        installer.prepare_dirs()
        assert os.path.isdir(installer.working_dir)

    def test_creates_default_tasks_dir(self, tmp_path, monkeypatch):
        home = tmp_path / "home" / FAKE_USER
        home.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(home) if p == f"~{FAKE_USER}" else p,
        )
        installer = SystemdInstaller(ip=FAKE_IP, token=FAKE_TOKEN, user=FAKE_USER)
        installer.prepare_dirs()
        assert os.path.isdir(installer.tasks_dir)

    def test_raises_for_explicit_missing_tasks_dir(self, tmp_path, monkeypatch):
        home = tmp_path / "home" / FAKE_USER
        home.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(home) if p == f"~{FAKE_USER}" else p,
        )
        missing = str(tmp_path / "nonexistent_tasks")
        installer = SystemdInstaller(
            ip=FAKE_IP, token=FAKE_TOKEN, user=FAKE_USER, tasks_dir=missing
        )
        with pytest.raises(SDCIServerException, match="tasks_dir"):
            installer.prepare_dirs()

    def test_does_not_create_explicit_missing_tasks_dir(self, tmp_path, monkeypatch):
        home = tmp_path / "home" / FAKE_USER
        home.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(home) if p == f"~{FAKE_USER}" else p,
        )
        missing = str(tmp_path / "nonexistent_tasks")
        installer = SystemdInstaller(
            ip=FAKE_IP, token=FAKE_TOKEN, user=FAKE_USER, tasks_dir=missing
        )
        try:
            installer.prepare_dirs()
        except SDCIServerException:
            pass
        assert not os.path.exists(missing)

    def test_accepts_explicit_existing_tasks_dir(self, tmp_path, monkeypatch):
        home = tmp_path / "home" / FAKE_USER
        home.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(home) if p == f"~{FAKE_USER}" else p,
        )
        existing = tmp_path / "real_tasks"
        existing.mkdir()
        installer = SystemdInstaller(
            ip=FAKE_IP, token=FAKE_TOKEN, user=FAKE_USER, tasks_dir=str(existing)
        )
        # Should not raise
        installer.prepare_dirs()


# ---------------------------------------------------------------------------
# _run_privileged() tests
# ---------------------------------------------------------------------------


class TestRunPrivileged:
    def test_raises_on_nonzero_returncode(self, tmp_path, monkeypatch):
        home = tmp_path / "home" / FAKE_USER
        home.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(home) if p == f"~{FAKE_USER}" else p,
        )

        class FakeResult:
            returncode = 1
            stderr = "permission denied"

        monkeypatch.setattr("subprocess.run", lambda *a, **kw: FakeResult())
        installer = SystemdInstaller(ip=FAKE_IP, token=FAKE_TOKEN, user=FAKE_USER)
        with pytest.raises(SDCIServerException, match="permission denied"):
            installer._run_privileged(["chmod", "600", "/etc/sdci/sdci.env"])

    def test_passes_input_to_subprocess(self, tmp_path, monkeypatch):
        home = tmp_path / "home" / FAKE_USER
        home.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(home) if p == f"~{FAKE_USER}" else p,
        )
        captured = {}

        class FakeResult:
            returncode = 0
            stderr = ""

        def fake_run(cmd, **kwargs):
            captured["input"] = kwargs.get("input")
            return FakeResult()

        monkeypatch.setattr("subprocess.run", fake_run)
        installer = SystemdInstaller(ip=FAKE_IP, token=FAKE_TOKEN, user=FAKE_USER)
        installer._run_privileged(
            ["tee", "/etc/sdci/sdci.env"], input="SDCI_SERVER_TOKEN=secret\n"
        )
        assert captured["input"] == "SDCI_SERVER_TOKEN=secret\n"

    def test_prefixes_sudo(self, tmp_path, monkeypatch):
        home = tmp_path / "home" / FAKE_USER
        home.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(home) if p == f"~{FAKE_USER}" else p,
        )
        captured = {}

        class FakeResult:
            returncode = 0
            stderr = ""

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            return FakeResult()

        monkeypatch.setattr("subprocess.run", fake_run)
        installer = SystemdInstaller(ip=FAKE_IP, token=FAKE_TOKEN, user=FAKE_USER)
        installer._run_privileged(["systemctl", "daemon-reload"])
        assert captured["cmd"][0] == "sudo"
        assert "systemctl" in captured["cmd"]


# ---------------------------------------------------------------------------
# install() integration / sequence tests
# ---------------------------------------------------------------------------


class TestInstall:
    """Test the full install() sequence with everything mocked."""

    def _setup(self, tmp_path, monkeypatch, force=False, unit_exists=False):
        home = tmp_path / "home" / FAKE_USER
        home.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(home) if p == f"~{FAKE_USER}" else p,
        )
        # Platform: pretend linux
        monkeypatch.setattr(sys, "platform", "linux")
        # shutil.which: provide both systemctl and sdci-server
        monkeypatch.setattr(
            "shutil.which",
            lambda name: {
                "systemctl": "/bin/systemctl",
                "sdci-server": FAKE_BINARY,
            }.get(name),
        )
        # Track all _run_privileged calls
        calls = []

        installer = SystemdInstaller(
            ip=FAKE_IP, token=FAKE_TOKEN, user=FAKE_USER, force=force
        )

        def fake_run_privileged(args, input=None):
            calls.append({"args": args, "input": input})

        installer._run_privileged = fake_run_privileged

        # Unit exists?
        monkeypatch.setattr(
            "os.path.exists",
            lambda p: p == installer.unit_path if unit_exists else False,
        )

        return installer, calls

    def test_full_sequence_called_in_order(self, tmp_path, monkeypatch):
        installer, calls = self._setup(tmp_path, monkeypatch)
        installer.install()

        # Extract the flat list of commands invoked
        all_commands = [c["args"] for c in calls]

        # Verify key steps appear
        assert any("install" in c and "/etc/sdci" in c for c in all_commands), (
            "Missing: sudo install -d /etc/sdci"
        )
        assert any("tee" in c and installer.env_path in c for c in all_commands), (
            "Missing: tee env_path"
        )
        assert any("tee" in c and installer.unit_path in c for c in all_commands), (
            "Missing: tee unit_path"
        )
        assert any("daemon-reload" in c for c in all_commands), "Missing: daemon-reload"
        assert any("enable" in c for c in all_commands), "Missing: systemctl enable"
        assert any("restart" in c for c in all_commands), "Missing: systemctl restart"

    def test_full_privileged_command_order(self, tmp_path, monkeypatch):
        """Assert the exact relative order of all 8 privileged commands in install()."""
        installer, calls = self._setup(tmp_path, monkeypatch)
        installer.install()

        env_path = installer.env_path
        unit_path = installer.unit_path
        service_name = installer.service_name

        def find_idx(predicate, label):
            for i, c in enumerate(calls):
                if predicate(c):
                    return i
            raise AssertionError(f"Privileged call not found: {label}")

        idx_install_d = find_idx(
            lambda c: c["args"][:4] == ["install", "-d", "-m", "0755"]
            and "/etc/sdci" in c["args"],
            "install -d -m 0755 /etc/sdci",
        )
        idx_tee_env = find_idx(
            lambda c: c["args"][0] == "tee" and env_path in c["args"],
            f"tee {env_path}",
        )
        idx_chmod_env = find_idx(
            lambda c: c["args"][:2] == ["chmod", "600"] and env_path in c["args"],
            f"chmod 600 {env_path}",
        )
        idx_tee_unit = find_idx(
            lambda c: c["args"][0] == "tee" and unit_path in c["args"],
            f"tee {unit_path}",
        )
        idx_chmod_unit = find_idx(
            lambda c: c["args"][:2] == ["chmod", "644"] and unit_path in c["args"],
            f"chmod 644 {unit_path}",
        )
        idx_daemon_reload = find_idx(
            lambda c: "daemon-reload" in c["args"],
            "systemctl daemon-reload",
        )
        idx_enable = find_idx(
            lambda c: "enable" in c["args"] and service_name in c["args"],
            f"systemctl enable {service_name}",
        )
        idx_restart = find_idx(
            lambda c: "restart" in c["args"] and service_name in c["args"],
            f"systemctl restart {service_name}",
        )

        # Assert full ordering
        assert idx_install_d < idx_tee_env, "install -d must precede tee env"
        assert idx_tee_env < idx_chmod_env, "tee env must precede chmod 600 env"
        assert idx_chmod_env < idx_tee_unit, (
            "env file must be chmod'd before unit file is written (security)"
        )
        assert idx_tee_unit < idx_chmod_unit, "tee unit must precede chmod 644 unit"
        assert idx_chmod_unit < idx_daemon_reload, (
            "chmod unit must precede daemon-reload"
        )
        assert idx_daemon_reload < idx_enable, "daemon-reload must precede enable"
        assert idx_enable < idx_restart, "enable must precede restart"

        # Security: token must appear only via stdin input, never in any argv
        for c in calls:
            args_str = " ".join(c["args"])
            assert FAKE_TOKEN not in args_str, f"Token found in argv: {c['args']}"
        env_tee_calls = [
            c for c in calls if c["args"][0] == "tee" and env_path in c["args"]
        ]
        assert len(env_tee_calls) == 1
        assert FAKE_TOKEN in (env_tee_calls[0]["input"] or ""), (
            "Token not passed via stdin to env tee call"
        )

    def test_token_passed_via_stdin_not_argv(self, tmp_path, monkeypatch):
        installer, calls = self._setup(tmp_path, monkeypatch)
        installer.install()

        # Check that no argv list contains the token
        for call in calls:
            args_str = " ".join(call["args"])
            assert FAKE_TOKEN not in args_str, (
                f"Token found in argv of call: {call['args']}"
            )

        # Check the env file tee call has the token in stdin
        env_tee_calls = [
            c for c in calls if "tee" in c["args"] and installer.env_path in c["args"]
        ]
        assert len(env_tee_calls) == 1
        assert FAKE_TOKEN in (env_tee_calls[0]["input"] or ""), (
            "Token not passed via stdin to tee"
        )

    def test_daemon_reload_before_enable(self, tmp_path, monkeypatch):
        installer, calls = self._setup(tmp_path, monkeypatch)
        installer.install()

        all_commands = [c["args"] for c in calls]
        reload_idx = next(
            (i for i, c in enumerate(all_commands) if "daemon-reload" in c), None
        )
        enable_idx = next(
            (i for i, c in enumerate(all_commands) if "enable" in c), None
        )
        assert reload_idx is not None
        assert enable_idx is not None
        assert reload_idx < enable_idx

    def test_enable_before_restart(self, tmp_path, monkeypatch):
        installer, calls = self._setup(tmp_path, monkeypatch)
        installer.install()

        all_commands = [c["args"] for c in calls]
        enable_idx = next(
            (i for i, c in enumerate(all_commands) if "enable" in c), None
        )
        restart_idx = next(
            (i for i, c in enumerate(all_commands) if "restart" in c), None
        )
        assert enable_idx is not None
        assert restart_idx is not None
        assert enable_idx < restart_idx

    def test_chmod_600_applied_to_env_file(self, tmp_path, monkeypatch):
        installer, calls = self._setup(tmp_path, monkeypatch)
        installer.install()

        chmod_calls = [c for c in calls if "chmod" in c["args"] and "600" in c["args"]]
        assert any(installer.env_path in c["args"] for c in chmod_calls)

    def test_chmod_644_applied_to_unit_file(self, tmp_path, monkeypatch):
        installer, calls = self._setup(tmp_path, monkeypatch)
        installer.install()

        chmod_calls = [c for c in calls if "chmod" in c["args"] and "644" in c["args"]]
        assert any(installer.unit_path in c["args"] for c in chmod_calls)

    def test_existing_unit_without_force_aborts_when_declined(
        self, tmp_path, monkeypatch
    ):
        installer, calls = self._setup(
            tmp_path, monkeypatch, unit_exists=True, force=False
        )

        # Inject a confirm callable that always declines
        installer._confirm = lambda msg: False

        with pytest.raises(SDCIServerException, match="aborted"):
            installer.install()

        # No privileged calls should have been made
        assert calls == []

    def test_existing_unit_with_force_skips_prompt(self, tmp_path, monkeypatch):
        installer, calls = self._setup(
            tmp_path, monkeypatch, unit_exists=True, force=True
        )
        # Should not raise and should proceed with privileged calls
        installer.install()
        assert len(calls) > 0

    def test_existing_unit_without_force_proceeds_when_confirmed(
        self, tmp_path, monkeypatch
    ):
        installer, calls = self._setup(
            tmp_path, monkeypatch, unit_exists=True, force=False
        )
        # Inject a confirm callable that accepts
        installer._confirm = lambda msg: True
        installer.install()
        assert len(calls) > 0

    def test_service_name_in_enable_and_restart(self, tmp_path, monkeypatch):
        home = tmp_path / "home" / FAKE_USER
        home.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(home) if p == f"~{FAKE_USER}" else p,
        )
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(
            "shutil.which",
            lambda name: {
                "systemctl": "/bin/systemctl",
                "sdci-server": FAKE_BINARY,
            }.get(name),
        )
        monkeypatch.setattr("os.path.exists", lambda p: False)

        installer = SystemdInstaller(
            ip=FAKE_IP,
            token=FAKE_TOKEN,
            user=FAKE_USER,
            service_name="myapp",
        )
        calls = []
        installer._run_privileged = lambda args, input=None: calls.append(
            {"args": args, "input": input}
        )
        installer.install()

        all_commands = [c["args"] for c in calls]
        assert any("enable" in c and "myapp" in c for c in all_commands)
        assert any("restart" in c and "myapp" in c for c in all_commands)

    def test_install_raises_when_binary_missing(self, tmp_path, monkeypatch):
        """install() must raise SDCIServerException when sdci-server is not on PATH."""
        home = tmp_path / "home" / FAKE_USER
        home.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(
            "os.path.expanduser",
            lambda p: str(home) if p == f"~{FAKE_USER}" else p,
        )
        monkeypatch.setattr(sys, "platform", "linux")
        # systemctl present, sdci-server absent
        monkeypatch.setattr(
            "shutil.which",
            lambda name: "/bin/systemctl" if name == "systemctl" else None,
        )

        installer = SystemdInstaller(ip=FAKE_IP, token=FAKE_TOKEN, user=FAKE_USER)

        calls = []
        installer._run_privileged = lambda args, input=None: calls.append(
            {"args": args, "input": input}
        )

        with pytest.raises(SDCIServerException, match="sdci-server"):
            installer.install()

        # No privileged command should have been executed
        assert calls == []
