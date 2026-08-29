import io
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nll.cli import app, collect_documents, find_files
from tests.conftest import FakeModel

runner = CliRunner()


def test_find_files_walks_recursively_and_skips_hidden_directories(
    tmp_path: Path,
) -> None:
    (tmp_path / "a.md").write_text("a")
    (tmp_path / "b.py").write_text("b")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "c.txt").write_text("c")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "d.md").write_text("d")

    files = find_files(tmp_path, ["*.md", "*.txt"])

    assert files == [tmp_path / "a.md", tmp_path / "docs" / "c.txt"]


def test_collect_documents_mixes_files_and_directories(tmp_path: Path) -> None:
    (tmp_path / "notes.py").write_text("explicit")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "c.md").write_text("walked")

    documents = collect_documents([tmp_path / "notes.py", tmp_path / "docs"], ["*.md"])

    assert [(document.path, document.text) for document in documents] == [
        (str(tmp_path / "notes.py"), "explicit"),
        (str(tmp_path / "docs" / "c.md"), "walked"),
    ]


def test_collect_documents_reads_stdin_when_no_paths_are_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("piped"))

    documents = collect_documents([], ["*.md"])

    assert [(document.path, document.text) for document in documents] == [
        ("<stdin>", "piped")
    ]


def test_collect_documents_refuses_a_terminal_on_stdin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Terminal:
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr("sys.stdin", Terminal())

    with pytest.raises(Exception, match="nothing piped to stdin"):
        collect_documents([], ["*.md"])


def test_lint_prints_violations_and_exits_with_one(
    no_user_config: Path, fake_model: FakeModel, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(no_user_config)
    fake_model(
        {
            "findings": [
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
        "notes.md:1:22: CHR004 Semicolon",
        "    > Ship less, sleep more; really.",
        "    Fix: Split into two sentences or join with a comma",
        "Found 2 violations.",
    ]


def test_lint_clean_file_as_json_exits_with_zero(
    no_user_config: Path, fake_model: FakeModel, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(no_user_config)
    fake_model({"findings": []})
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
    assert "<stdin>:1:2: CHR004 Semicolon" in result.stdout


def test_lint_walks_directories_and_warns_about_empty_ones(
    no_user_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(no_user_config)
    docs = no_user_config / "docs"
    (docs / "nested").mkdir(parents=True)
    (docs / "a.md").write_text("a; b\n")
    (docs / "nested" / "b.txt").write_text("c; d\n")
    (docs / "skip.py").write_text("e; f\n")
    (no_user_config / "empty").mkdir()

    result = runner.invoke(app, ["lint", "--select", "CHR004", "docs", "empty"])

    assert result.exit_code == 1
    assert "docs/a.md:1:2: CHR004" in result.stdout
    assert "docs/nested/b.txt:1:2: CHR004" in result.stdout
    assert "skip.py" not in result.stdout
    assert "empty: no files match *.md *.txt *.rst" in result.stderr


def test_lint_reads_project_config_with_user_rules_inline(
    no_user_config: Path, fake_model: FakeModel, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(no_user_config)
    calls = fake_model(
        {"findings": [{"code": "SEC001", "quote": "10.0.0.12", "message": "ip"}]}
    )
    (no_user_config / "nll.toml").write_text(
        'select = ["SEC"]\n\n[rules.SEC]\ndescription = "Leaks"\n001 = "Names an IP"\n'
    )
    (no_user_config / "notes.md").write_text("Host is 10.0.0.12.\n")

    result = runner.invoke(app, ["lint", "notes.md"])

    assert result.exit_code == 1
    assert "notes.md:1:9: SEC001 ip" in result.stdout
    schema = calls[0][1].output_format["schema"]
    assert schema["properties"]["findings"]["items"]["properties"]["code"]["enum"] == [
        "SEC001"
    ]


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
