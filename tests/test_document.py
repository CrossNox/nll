from pathlib import Path

import pytest

from nll.document import Document


def test_document_reads_utf8_text_from_a_path(tmp_path: Path) -> None:
    path = tmp_path / "notes.md"
    path.write_text("first\nsecond\n", encoding="utf-8")

    document = Document(path=path)

    assert document.path == path
    assert document.prose == "first\nsecond\n"
    assert document.lines == ["first", "second", ""]


def test_document_accepts_prose_without_a_path() -> None:
    document = Document(prose="one\ntwo")

    assert document.path is None
    assert document.lines == ["one", "two"]


def test_document_requires_a_path_or_prose() -> None:
    with pytest.raises(ValueError, match="Either 'prose' or 'path'"):
        Document()


def test_prose_takes_precedence_over_a_path(tmp_path: Path) -> None:
    path = tmp_path / "notes.md"
    path.write_text("from file", encoding="utf-8")

    document = Document(path=path, prose="explicit")

    assert document.prose == "explicit"
