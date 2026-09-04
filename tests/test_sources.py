from pathlib import Path

import pytest

from nll.linter import Linter


def test_linter_collects_named_files_and_matching_directory_files(
    default_linter: Linter, tmp_path: Path
) -> None:
    (tmp_path / "notes.py").write_text("explicit", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "readme.md").write_text("walked", encoding="utf-8")
    (tmp_path / "docs" / "skip.py").write_text("ignored", encoding="utf-8")

    files = default_linter._collect_lintable_files(
        [tmp_path / "notes.py", tmp_path / "docs"]
    )

    assert files == [tmp_path / "notes.py", tmp_path / "docs" / "readme.md"]


def test_linter_skips_hidden_directories_and_matches_extensions(
    default_linter: Linter, tmp_path: Path
) -> None:
    (tmp_path / "visible.md").write_text("visible", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "hidden.md").write_text("hidden", encoding="utf-8")
    (tmp_path / "UPPER.MD").write_text("uppercase", encoding="utf-8")

    assert default_linter._collect_matching_files(tmp_path) == [
        tmp_path / "UPPER.MD",
        tmp_path / "visible.md",
    ]


def test_linter_rejects_a_missing_input_path(
    default_linter: Linter, tmp_path: Path
) -> None:
    missing = tmp_path / "missing.md"

    with pytest.raises(RuntimeError, match="not a file or a directory"):
        default_linter._collect_lintable_files([missing])


def test_linter_rejects_a_directory_without_matching_files(
    default_linter: Linter, tmp_path: Path
) -> None:
    (tmp_path / "code.py").write_text("code", encoding="utf-8")

    with pytest.raises(RuntimeError, match="no files to lint"):
        default_linter._collect_lintable_files([tmp_path])
