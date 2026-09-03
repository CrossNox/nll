from pathlib import Path

import pytest

from nll.document import Document, DocumentFormat


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


def test_document_treats_unknown_path_extensions_as_plain_text(tmp_path: Path) -> None:
    document = Document(path=tmp_path / "notes.py", prose="print('text')")

    assert document.format is DocumentFormat.PLAIN_TEXT


@pytest.mark.parametrize("fence", ["```", "~~~"])
def test_remove_code_blocks_omits_markdown_fences_and_keeps_source_lines(
    fence: str,
) -> None:
    document = Document(
        path=Path("notes.md"),
        prose=(f"Before;\n{fence}python\nprint('inside;')\n{fence}\nAfter;\n"),
    )

    without_code_blocks = document.remove_code_blocks()

    assert without_code_blocks.format is DocumentFormat.MARKDOWN
    assert without_code_blocks.prose == "Before;\n\n\n\nAfter;\n"
    assert without_code_blocks.prose.count("\n") == document.prose.count("\n")


@pytest.mark.parametrize("directive", ["code", "code-block"])
def test_remove_code_blocks_omits_rst_code_directives(
    directive: str,
) -> None:
    document = Document(
        prose=(
            "Before;\n"
            "\n"
            f".. {directive}:: python\n"
            "   :linenos:\n"
            "\n"
            "   print('inside;')\n"
            "\n"
            "After;\n"
        ),
        path=Path("notes.rst"),
    )

    without_code_blocks = document.remove_code_blocks()

    assert without_code_blocks.prose == "Before;\n\n\n\n\n\n\nAfter;\n"


def test_remove_code_blocks_omits_rst_literal_bodies_and_keeps_introducers() -> None:
    document = Document(
        path=Path("notes.rst"),
        prose=("Before;\nRun this::\n\n   print('inside;')\n\nAfter;\n"),
    )

    without_code_blocks = document.remove_code_blocks()

    assert without_code_blocks.prose == "Before;\nRun this::\n\n\n\nAfter;\n"


def test_remove_code_blocks_does_not_expand_rst_include_directives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    included = tmp_path / "included.rst"
    included.write_text(".. code:: python\n\n   inside;\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    prose = ".. include:: included.rst\n"

    document = Document(path=tmp_path / "notes.rst", prose=prose)

    assert document.remove_code_blocks().prose == prose


def test_remove_code_blocks_preserves_matching_prose_before_rst_code() -> None:
    document = Document(
        path=Path("notes.rst"),
        prose=("print('inside;')\n\n.. code:: python\n\n   print('inside;')\n\n"),
    )

    without_code_blocks = document.remove_code_blocks()

    assert without_code_blocks.prose == "print('inside;')\n\n.. code:: python\n\n\n\n"


def test_remove_code_blocks_uses_markdown_structure_in_a_block_quote() -> None:
    document = Document(
        path=Path("notes.md"),
        prose=("> ```python\n> print('inside;')\n> ```\nAfter;\n"),
    )

    without_code_blocks = document.remove_code_blocks()

    assert without_code_blocks.prose == "\n\n\nAfter;\n"


def test_remove_code_blocks_keeps_plain_text_unchanged() -> None:
    document = Document(
        path=Path("notes.txt"),
        prose="```python\nprint('inside;')\n```\n",
    )

    assert document.remove_code_blocks() is document
