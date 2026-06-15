"""Tests for the sdci-server Click group (serve + setup subcommands).

TDD — tests written BEFORE the implementation is restructured.
"""

from unittest.mock import MagicMock

from click.testing import CliRunner

from sdci.exceptions import SDCIServerException

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_installer_cls(*, fail=False):
    """Return a fake SystemdInstaller class that records constructor kwargs."""
    instance = MagicMock()
    if fail:
        instance.install.side_effect = SDCIServerException("mocked failure")

    cls = MagicMock(return_value=instance)
    cls._instance = instance
    return cls


# ---------------------------------------------------------------------------
# Group structure
# ---------------------------------------------------------------------------


class TestGroupStructure:
    def test_main_is_click_group_with_serve_and_setup(self):
        """main must be a Click group exposing both 'serve' and 'setup' subcommands."""
        from sdci.server import main

        assert hasattr(main, "commands"), "main must be a Click group"
        assert "serve" in main.commands, "'serve' subcommand must be registered"
        assert "setup" in main.commands, "'setup' subcommand must be registered"

    def test_serve_has_expected_params(self):
        """serve subcommand must expose --host, --port, --server-token, --tasks-dir."""
        from sdci.server import main

        serve = main.commands["serve"]
        param_names = {p.name for p in serve.params}
        assert "host" in param_names
        assert "port" in param_names
        assert "server_token" in param_names
        assert "tasks_dir" in param_names

    def test_serve_help_exits_zero(self):
        """sdci-server serve --help should exit 0."""
        from sdci.server import main

        runner = CliRunner()
        result = runner.invoke(main, ["serve", "--help"])
        assert result.exit_code == 0

    def test_setup_help_exits_zero(self):
        """sdci-server setup --help should exit 0."""
        from sdci.server import main

        runner = CliRunner()
        result = runner.invoke(main, ["setup", "--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# setup subcommand — constructor forwarding
# ---------------------------------------------------------------------------


class TestSetupDefaults:
    def test_setup_constructs_installer_with_expected_defaults(self, monkeypatch):
        """setup --ip X --token Y must build SystemdInstaller with correct defaults."""
        from sdci.server import main

        fake_cls = _make_installer_cls()
        monkeypatch.setattr("sdci.server.SystemdInstaller", fake_cls)

        runner = CliRunner()
        result = runner.invoke(main, ["setup", "--ip", "1.2.3.4", "--token", "T"])

        assert result.exit_code == 0, result.output
        fake_cls.assert_called_once_with(
            ip="1.2.3.4",
            token="T",
            port=8842,
            tasks_dir=None,
            user=None,
            service_name="sdci",
            force=False,
        )
        fake_cls._instance.install.assert_called_once()

    def test_setup_success_prints_systemctl_hint(self, monkeypatch):
        """Successful setup must print 'systemctl status <service_name>'."""
        from sdci.server import main

        fake_cls = _make_installer_cls()
        monkeypatch.setattr("sdci.server.SystemdInstaller", fake_cls)

        runner = CliRunner()
        result = runner.invoke(main, ["setup", "--ip", "1.2.3.4", "--token", "T"])

        assert result.exit_code == 0
        assert "systemctl status sdci" in result.output


class TestSetupCustomOptions:
    def test_setup_forwards_custom_options(self, monkeypatch):
        """--port, --tasks-dir, --user, --service-name, --force must be forwarded."""
        from sdci.server import main

        fake_cls = _make_installer_cls()
        monkeypatch.setattr("sdci.server.SystemdInstaller", fake_cls)

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "setup",
                "--ip",
                "10.0.0.1",
                "--token",
                "secret",
                "--port",
                "9000",
                "--tasks-dir",
                "/opt/tasks",
                "--user",
                "deploy",
                "--service-name",
                "my-sdci",
                "--force",
            ],
        )

        assert result.exit_code == 0, result.output
        fake_cls.assert_called_once_with(
            ip="10.0.0.1",
            token="secret",
            port=9000,
            tasks_dir="/opt/tasks",
            user="deploy",
            service_name="my-sdci",
            force=True,
        )
        fake_cls._instance.install.assert_called_once()

    def test_setup_custom_service_name_in_success_hint(self, monkeypatch):
        """The success hint must use the custom service name."""
        from sdci.server import main

        fake_cls = _make_installer_cls()
        monkeypatch.setattr("sdci.server.SystemdInstaller", fake_cls)

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "setup",
                "--ip",
                "10.0.0.1",
                "--token",
                "secret",
                "--service-name",
                "my-sdci",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "systemctl status my-sdci" in result.output


# ---------------------------------------------------------------------------
# setup subcommand — failure handling
# ---------------------------------------------------------------------------


class TestSetupFailure:
    def test_setup_exits_nonzero_on_sdci_exception(self, monkeypatch):
        """When installer.install() raises SDCIServerException, exit code must be non-zero."""
        from sdci.server import main

        fake_cls = _make_installer_cls(fail=True)
        monkeypatch.setattr("sdci.server.SystemdInstaller", fake_cls)

        runner = CliRunner()
        result = runner.invoke(main, ["setup", "--ip", "1.2.3.4", "--token", "T"])

        assert result.exit_code != 0

    def test_setup_failure_prints_error_message(self, monkeypatch):
        """On failure, the error message must be printed (stderr mixed into output in test runner)."""
        from sdci.server import main

        fake_cls = _make_installer_cls(fail=True)
        monkeypatch.setattr("sdci.server.SystemdInstaller", fake_cls)

        runner = CliRunner()
        result = runner.invoke(main, ["setup", "--ip", "1.2.3.4", "--token", "T"])

        assert result.exit_code != 0
        # CliRunner mixes stderr into output by default in Click 8.x
        assert "SETUP FAILED" in result.output

    def test_setup_missing_required_ip_exits_nonzero(self):
        """setup without --ip should exit non-zero (Click validation)."""
        from sdci.server import main

        runner = CliRunner()
        result = runner.invoke(main, ["setup", "--token", "T"])
        assert result.exit_code != 0

    def test_setup_missing_required_token_exits_nonzero(self):
        """setup without --token should exit non-zero (Click validation)."""
        from sdci.server import main

        runner = CliRunner()
        result = runner.invoke(main, ["setup", "--ip", "1.2.3.4"])
        assert result.exit_code != 0
