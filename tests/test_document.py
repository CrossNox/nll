from nll.document import Document, Position


def test_locate_offset_maps_offsets_to_lines_and_columns() -> None:
    document = Document("ab\ncd\n", "x")

    assert document.locate_offset(0) == Position(line=1, column=1)
    assert document.locate_offset(3) == Position(line=2, column=1)
    assert document.locate_offset(4) == Position(line=2, column=2)


def test_read_line_returns_the_line_without_newline() -> None:
    document = Document("first\nsecond\n", "x")

    assert document.read_line(2) == "second"


def test_extract_prose_masks_code_without_moving_offsets() -> None:
    document = Document("a\n```sh\nx; y\n```\nb `c` d\n", "x")

    masked = document.extract_prose(ignore_code=True)

    assert len(masked) == len(document.text)
    assert masked == "a\n     \n    \n   \nb     d\n"
    assert document.extract_prose(ignore_code=False) == document.text


def test_locate_exact_and_whitespace_tolerant() -> None:
    document = Document("First line here.\nSecond line\nwraps over.\n", "x")

    assert document.locate("Second line") == Position(line=2, column=1)
    assert document.locate("Second line wraps over.") == Position(line=2, column=1)
    assert document.locate("not in text") is None
    assert document.locate("   ") is None
