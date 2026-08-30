import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from nll.cli import app, lint
from tests.conftest import FakeModel

runner = CliRunner()


def test_lint_prints_violations_and_exits_with_one(
    no_user_config: Path, fake_model: FakeModel, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(no_user_config)
    fake_model(
        {
            "violations": [
                {
                    "code": "SLO001",
                    "quote": "Ship less, sleep more",
                    "message": "slogan",
                    "suggestion": "Ship less.",
                }
            ]
        }
    )
    (no_user_config / "notes.md").write_text("Ship less, sleep more; really.\n")

    result = runner.invoke(app, ["lint", "notes.md"])

    assert result.exit_code == 1
    assert result.stdout.splitlines() == [
        "notes.md:1:1: SLO001 slogan",
        "    > Ship less, sleep more",
        "    Fix: Ship less.",
        "notes.md:1:22: CHR004 Semicolon.",
        "    > Ship less, sleep more; really.",
        "    Fix: Split into two sentences or join with a comma",
        "Found 2 violations.",
    ]


def test_lint_clean_file_as_json_exits_with_zero(
    no_user_config: Path, fake_model: FakeModel, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(no_user_config)
    fake_model({"violations": []})
    (no_user_config / "notes.md").write_text("Plain text.\n")

    result = runner.invoke(app, ["lint", "--output-format", "json", "notes.md"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == []


def test_lint_reads_stdin_when_no_paths_are_given(
    no_user_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(no_user_config)

    result = runner.invoke(app, ["lint", "--select", "CHR004"], input="a; b\n")

    assert result.exit_code == 1
    assert "<stdin>:1:2: CHR004 Semicolon." in result.stdout


def test_lint_refuses_a_terminal_on_stdin(
    no_user_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(no_user_config)

    class Terminal:
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr("nll.cli.sys.stdin", Terminal())

    with pytest.raises(typer.BadParameter, match="nothing piped to stdin"):
        lint(extend_select=[], ignore=[], paths=None, select=["CHR004"])


def test_lint_walks_directories(
    no_user_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(no_user_config)
    docs = no_user_config / "docs"
    (docs / "nested").mkdir(parents=True)
    (docs / "a.md").write_text("a; b\n")
    (docs / "nested" / "b.txt").write_text("c; d\n")
    (docs / "skip.py").write_text("e; f\n")

    result = runner.invoke(app, ["lint", "--select", "CHR004", "docs"])

    assert result.exit_code == 1
    assert "docs/a.md:1:2: CHR004" in result.stdout
    assert "docs/nested/b.txt:1:2: CHR004" in result.stdout
    assert "skip.py" not in result.stdout


def test_lint_reads_project_config_with_user_rules_inline(
    no_user_config: Path, fake_model: FakeModel, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(no_user_config)
    calls = fake_model(
        {"violations": [{"code": "SEC001", "quote": "10.0.0.12", "message": "ip"}]}
    )
    (no_user_config / "nll.toml").write_text(
        'select = ["SEC"]\n\n[rules.SEC]\ndescription = "Leaks"\n001 = "Names an IP"\n'
    )
    (no_user_config / "notes.md").write_text("Host is 10.0.0.12.\n")

    result = runner.invoke(app, ["lint", "notes.md"])

    assert result.exit_code == 1
    assert "notes.md:1:9: SEC001 ip" in result.stdout
    schema = calls[0][1].output_format["schema"]
    assert schema["$defs"]["RuleCode"]["enum"] == ["SEC001"]


def test_rules_lists_the_rulebook_with_cli_selectors(
    no_user_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(no_user_config)

    result = runner.invoke(app, ["rules", "--select", "CHR004"])

    assert result.exit_code == 0
    assert "  CHR004   on   python  Semicolon." in result.stdout
    assert "  CHR001   off  python  Em dash (U+2014)." in result.stdout


def test_bad_config_value_fails_loudly(
    no_user_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(no_user_config)
    (no_user_config / "nll.toml").write_text(
        "[rules.LEN.001]\nmax-sentences = 'three'\n"
    )

    result = runner.invoke(app, ["rules"])

    assert result.exit_code != 0
    assert isinstance(result.exception, ValueError)
    assert "rule LEN001 options are invalid" in str(result.exception)
