from pathlib import Path
from typing import ClassVar

import pytest
import typer
from typer.testing import CliRunner

from linnl.cli import app, lint
from linnl.plugins import Plugin

runner = CliRunner()


def test_lint_prints_code_violations_and_exits_one(
    no_user_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(no_user_config)
    (no_user_config / "notes.md").write_text(
        "Ship less; sleep more.\n", encoding="utf-8"
    )

    result = runner.invoke(app, ["lint", "--select", "CHR004", "notes.md"])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "notes.md" in result.stdout
    assert "CHR004: Semicolon." in result.stdout


def test_lint_prints_a_clean_message_and_exits_zero(
    no_user_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(no_user_config)
    (no_user_config / "notes.md").write_text("Plain text.\n", encoding="utf-8")

    result = runner.invoke(app, ["lint", "--select", "CHR004", "notes.md"])

    assert result.exit_code == 0
    assert result.stdout == "No violations found.\n"


def test_lint_ignores_fenced_code_and_preserves_reported_line_numbers(
    no_user_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(no_user_config)
    (no_user_config / "notes.md").write_text(
        "Before.\n```python\ninside;\n```\nAfter;\n", encoding="utf-8"
    )

    result = runner.invoke(app, ["lint", "--select", "CHR004", "notes.md"])

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit)
    assert "line 5:" in result.stdout
    assert "inside;" not in result.stdout


def test_lint_ignore_code_blocks_cli_flags_override_the_config(
    no_user_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(no_user_config)
    (no_user_config / "linnl.toml").write_text(
        "ignore-code-blocks = false\n", encoding="utf-8"
    )
    (no_user_config / "notes.md").write_text(
        "```python\ninside;\n```\n", encoding="utf-8"
    )

    ignored = runner.invoke(
        app,
        ["lint", "--select", "CHR004", "--ignore-code-blocks", "notes.md"],
    )
    included = runner.invoke(
        app,
        ["lint", "--select", "CHR004", "--lint-code-blocks", "notes.md"],
    )

    assert ignored.exit_code == 0
    assert included.exit_code == 1
    assert "line 2:" in included.stdout


def test_lint_reads_stdin_when_no_paths_are_given(
    no_user_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(no_user_config)

    result = runner.invoke(app, ["lint", "--select", "CHR004"], input="a; b\n")

    assert result.exit_code == 1
    assert "CHR004: Semicolon." in result.stdout


def test_lint_rejects_terminal_stdin(
    no_user_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(no_user_config)

    class Terminal:
        def isatty(self) -> bool:
            return True

        def read(self) -> str:
            return ""

    monkeypatch.setattr("linnl.cli.sys.stdin", Terminal())

    with pytest.raises(typer.Exit) as raised:
        lint(select=["CHR004"], paths=None)

    assert raised.value.exit_code == 2


def test_lint_walks_directories_and_uses_configured_extensions(
    no_user_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(no_user_config)
    docs = no_user_config / "docs"
    (docs / "nested").mkdir(parents=True)
    (docs / "a.md").write_text("a; b", encoding="utf-8")
    (docs / "nested" / "b.txt").write_text("c; d", encoding="utf-8")
    (docs / "skip.py").write_text("e; f", encoding="utf-8")

    result = runner.invoke(app, ["lint", "--select", "CHR004", "docs"])

    assert result.exit_code == 1
    assert "docs/a.md" in result.stdout
    assert "docs/nested/b.txt" in result.stdout
    assert "skip.py" not in result.stdout


def test_rules_lists_enabled_and_disabled_rules(
    no_user_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(no_user_config)

    result = runner.invoke(app, ["rules", "--select", "CHR004"])

    assert result.exit_code == 0
    assert "[ON] CHR004: Semicolon." in result.stdout
    assert "[OFF] CHR001: Em dash (U+2014)." in result.stdout


def test_config_prints_the_shipped_configuration() -> None:
    result = runner.invoke(app, ["config"])

    assert result.exit_code == 0
    assert (
        'select = ["SCH", "SLO", "ZIN", "CHR", "LEN", "RGX", "CLH", "WIK"]'
        in result.stdout
    )


def test_plugins_lists_enabled_packages(
    no_user_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(no_user_config)
    (no_user_config / "linnl.toml").write_text(
        'plugins = ["acme-rules"]\n', encoding="utf-8"
    )

    class FakeEntryPoint:
        name = "acme-rules"

        def load(self) -> type[Plugin]:
            return AcmePlugin

    class AcmePlugin(Plugin):
        name = "acme-rules"
        rules: ClassVar = {
            "ACM": {"description": "Acme", "001": "An Acme rule."}
        }

    monkeypatch.setattr(
        "linnl.plugins.entry_points", lambda *, group: [FakeEntryPoint()]
    )

    result = runner.invoke(app, ["plugins"])

    assert result.exit_code == 0
    assert result.stdout == "['acme-rules']\n"


def test_plugins_rejects_a_missing_enabled_package(
    no_user_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(no_user_config)
    (no_user_config / "linnl.toml").write_text(
        'plugins = ["missing-rules"]\n', encoding="utf-8"
    )
    monkeypatch.setattr("linnl.plugins.entry_points", lambda *, group: [])

    result = runner.invoke(app, ["plugins"])

    assert result.exit_code != 0
    assert isinstance(result.exception, ValueError)


def test_bad_config_fails_with_a_cli_error(
    no_user_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(no_user_config)
    (no_user_config / "linnl.toml").write_text(
        "max-concurrency = 0\n", encoding="utf-8"
    )

    result = runner.invoke(app, ["rules"])

    assert result.exit_code != 0
    assert isinstance(result.exception, ValueError)


def test_install_hook_command_uses_the_selected_agent(
    no_user_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(no_user_config)

    result = runner.invoke(app, ["install-hook", "claude", "--local"])

    assert result.exit_code == 0
    assert (no_user_config / ".claude" / "commands" / "linnl.md").exists()
    assert "Installed linnl command" in result.stdout
