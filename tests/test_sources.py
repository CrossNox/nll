from pathlib import Path

import pytest

from nll.sources import find_files_to_lint, find_matching_files


def test_find_matching_files_walks_recursively_and_skips_hidden_directories(
    tmp_path: Path,
) -> None:
    (tmp_path / "a.md").write_text("a")
    (tmp_path / "b.py").write_text("b")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "c.txt").write_text("c")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "d.md").write_text("d")

    files = find_matching_files(tmp_path, ["*.md", "*.txt"])

    assert files == [tmp_path / "a.md", tmp_path / "docs" / "c.txt"]


def test_find_files_to_lint_keeps_named_files_and_walks_directories(
    tmp_path: Path,
) -> None:
    (tmp_path / "notes.py").write_text("explicit")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "c.md").write_text("walked")

    files = find_files_to_lint([tmp_path / "notes.py", tmp_path / "docs"], ["*.md"])

    assert files == [tmp_path / "notes.py", tmp_path / "docs" / "c.md"]


def test_find_files_to_lint_warns_about_a_directory_with_no_matching_files(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / "code.py").write_text("x")

    assert find_files_to_lint([tmp_path], ["*.md"]) == []
    assert f"{tmp_path}: no files match *.md" in caplog.text
