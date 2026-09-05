from pathlib import Path

import pytest

from linnl.agents import LINNL_COMMAND, Agent, install_command


def test_install_command_writes_the_command_to_the_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    command_path = install_command(Agent.CLAUDE, local=True)

    assert command_path == tmp_path / ".claude" / "commands" / "linnl.md"
    assert command_path.read_text(encoding="utf-8") == LINNL_COMMAND


def test_install_command_writes_the_command_to_the_user_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

    command_path = install_command(Agent.CODEX, local=False)

    assert command_path == tmp_path / ".codex" / "prompts" / "linnl.md"
    assert command_path.read_text(encoding="utf-8") == LINNL_COMMAND


def test_install_command_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    command_path = install_command(Agent.CLAUDE, local=True)

    assert install_command(Agent.CLAUDE, local=True) == command_path


def test_install_command_updates_an_existing_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    command_path = tmp_path / ".claude" / "commands" / "linnl.md"
    command_path.parent.mkdir(parents=True)
    command_path.write_text("custom command\n", encoding="utf-8")

    install_command(Agent.CLAUDE, local=True)

    assert command_path.read_text(encoding="utf-8") == LINNL_COMMAND
