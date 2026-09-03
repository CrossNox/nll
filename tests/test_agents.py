from pathlib import Path

import pytest

from nll.agents import NLL_COMMAND, install_hook


def test_install_hook_writes_the_command_to_the_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    command_path = install_hook("claude", local=True)

    assert command_path == tmp_path / ".claude" / "commands" / "nll.md"
    assert command_path.read_text(encoding="utf-8") == NLL_COMMAND


def test_install_hook_writes_the_command_to_the_user_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

    command_path = install_hook("codex", local=False)

    assert command_path == tmp_path / ".codex" / "prompts" / "nll.md"
    assert command_path.read_text(encoding="utf-8") == NLL_COMMAND


def test_install_hook_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    command_path = install_hook("claude", local=True)

    assert install_hook("claude", local=True) == command_path


def test_install_hook_updates_an_existing_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    command_path = tmp_path / ".claude" / "commands" / "nll.md"
    command_path.parent.mkdir(parents=True)
    command_path.write_text("custom command\n", encoding="utf-8")

    install_hook("claude", local=True)

    assert command_path.read_text(encoding="utf-8") == NLL_COMMAND
