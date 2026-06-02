import pytest

from sdci.exceptions import SDCIServerException
from sdci.server_runner import AvailableCommandsDescriber, CommandRunner
from sdci.settings import Settings


@pytest.fixture
def tasks_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(Settings, "TASKS_DIR", str(tmp_path))
    return tmp_path


def test_get_available_commands_lists_sh_files_without_extension(tasks_dir):
    (tasks_dir / "deploy.sh").write_text("echo deploy")
    (tasks_dir / "rollback.sh").write_text("echo rollback")
    (tasks_dir / "notes.txt").write_text("ignored")

    commands = AvailableCommandsDescriber.get_available_commands()

    assert sorted(commands) == ["deploy", "rollback"]


def test_get_available_commands_raises_when_dir_missing(monkeypatch):
    monkeypatch.setattr(Settings, "TASKS_DIR", "/nonexistent/tasks/dir")

    with pytest.raises(SDCIServerException):
        AvailableCommandsDescriber.get_available_commands()


def test_command_runner_raises_for_unknown_task(tasks_dir):
    with pytest.raises(SDCIServerException):
        CommandRunner("does-not-exist")
