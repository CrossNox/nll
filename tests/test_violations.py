import json

from nll.document import Position
from nll.violations import (
    OutputFormat,
    Violation,
    render_violations,
    sort_violations_by_position,
)


def violation(
    path: str, position: Position | None, quote: str | None, suggestion: str | None
) -> Violation:
    return Violation(
        code="CHR004",
        path=path,
        position=position,
        message="Semicolon.",
        quote=quote,
        suggestion=suggestion,
    )


def test_render_text_ends_with_the_count() -> None:
    violations = [violation("x.md", Position(line=2, column=5), "a; b", "Split it")]

    assert render_violations(violations, OutputFormat.TEXT).splitlines() == [
        "x.md:2:5: CHR004 Semicolon.",
        "    > a; b",
        "    Fix: Split it",
        "Found 1 violations.",
    ]


def test_render_text_marks_an_unlocated_violation() -> None:
    violations = [violation("x.md", None, None, None)]

    assert render_violations(violations, OutputFormat.TEXT).splitlines() == [
        "x.md:?:?: CHR004 Semicolon.",
        "Found 1 violations.",
    ]


def test_render_json_keeps_unlocated_positions_null() -> None:
    violations = [violation("x.md", None, None, None)]

    assert json.loads(render_violations(violations, OutputFormat.JSON)) == [
        {
            "code": "CHR004",
            "path": "x.md",
            "line": None,
            "column": None,
            "message": "Semicolon.",
            "quote": None,
            "suggestion": None,
        }
    ]


def test_sort_orders_by_position_with_unlocated_last() -> None:
    late = violation("a.md", Position(line=3, column=1), None, None)
    early = violation("a.md", Position(line=1, column=9), None, None)
    unlocated = violation("a.md", None, None, None)

    assert sort_violations_by_position([unlocated, late, early]) == [
        early,
        late,
        unlocated,
    ]
