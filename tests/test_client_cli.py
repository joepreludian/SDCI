"""Tests for the sdci-cli Click group (client entrypoint)."""

from types import SimpleNamespace

import pytest
from click.testing import CliRunner


class TestVersionFlag:
    def test_version_flag_prints_version_and_exits_zero(self):
        """sdci-cli --version must print the package version and exit 0."""
        from sdci.cli import __version__, entrypoint

        runner = CliRunner()
        result = runner.invoke(entrypoint, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_version_flag_skips_banner(self):
        """--version is eager: it must exit before the group banner is printed."""
        from sdci.cli import entrypoint

        runner = CliRunner()
        result = runner.invoke(entrypoint, ["--version"])
        assert "[ SDCI-CLI v" not in result.output


class TestUploadAssetTimeout:
    @pytest.fixture
    def recorded_clients(self, monkeypatch):
        """Replaces SDCIClient in the CLI, capturing how it was built."""
        import sdci.cli as cli

        created = []

        class RecordingClient:
            def __init__(self, server, token, timeout=None):
                created.append({"server": server, "token": token, "timeout": timeout})

            def upload(self, local_file, remote_path):
                return SimpleNamespace(path=f"{remote_path}/app.zip", size=12)

        monkeypatch.setattr(cli, "SDCIClient", RecordingClient)
        return created

    def _invoke(self, tmp_path, extra_args):
        from sdci.cli import entrypoint

        local_file = tmp_path / "app.zip"
        local_file.write_bytes(b"payload")

        return CliRunner().invoke(
            entrypoint,
            [
                "upload-asset",
                "--token",
                "tok",
                *extra_args,
                "http://server",
                str(local_file),
                "releases/v1",
            ],
        )

    def test_timeout_option_reaches_the_client(self, tmp_path, recorded_clients):
        result = self._invoke(tmp_path, ["--timeout", "42"])

        assert result.exit_code == 0
        assert recorded_clients[0]["timeout"] == 42

    def test_timeout_defaults_to_none_so_settings_apply(
        self, tmp_path, recorded_clients
    ):
        result = self._invoke(tmp_path, [])

        assert result.exit_code == 0
        assert recorded_clients[0]["timeout"] is None
