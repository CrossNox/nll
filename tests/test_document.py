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


@pytest.mark.parametrize("fence", ["```", "~~~"])
def test_remove_code_blocks_omits_markdown_fences_and_keeps_source_lines(
    fence: str,
) -> None:
    document = Document(
        prose=(f"Before;\n{fence}python\nprint('inside;')\n{fence}\nAfter;\n")
    )

    without_code_blocks = document.remove_code_blocks()

    assert without_code_blocks.prose == "Before;\n\n\n\nAfter;\n"
    assert without_code_blocks.prose.count("\n") == document.prose.count("\n")


@pytest.mark.parametrize("directive", ["code", "code-block"])
def test_remove_code_blocks_omits_rst_code_directives(
    directive: str,
) -> None:
    document = Document(
        prose=(
            "Before;\n"
            f".. {directive}:: python\n"
            "   :linenos:\n"
            "\n"
            "   print('inside;')\n"
            "After;\n"
        )
    )

    without_code_blocks = document.remove_code_blocks()

    assert without_code_blocks.prose == "Before;\n\n\n\n\nAfter;\n"


def test_remove_code_blocks_omits_rst_literal_bodies_and_keeps_introducers() -> None:
    document = Document(prose=("Before;\nRun this::\n\n   print('inside;')\nAfter;\n"))

    without_code_blocks = document.remove_code_blocks()

    assert without_code_blocks.prose == "Before;\nRun this::\n\n\nAfter;\n"


def test_remove_code_blocks_rejects_an_unclosed_markdown_fence() -> None:
    document = Document(prose="Before\n```python\nprint('inside')\n")

    with pytest.raises(ValueError, match="Unclosed Markdown fence opened on line 2"):
        document.remove_code_blocks()
