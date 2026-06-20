"""Tests for the sdci-cli Click group (client entrypoint)."""

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
