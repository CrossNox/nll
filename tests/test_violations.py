import json

from nll.document import Position
from nll.rules import Rule
from nll.violations import OutputFormat, RuleViolation, RuleViolations

RULE = Rule(
    code="CHR004",
    group_prefix="CHR",
    group_description="Characters",
    description="Semicolon.",
)


def violation(
    path: str, position: Position | None, quote: str | None, suggestion: str | None
) -> RuleViolation:
    return RuleViolation(
        rule=RULE,
        path=path,
        position=position,
        message="Semicolon",
        quote=quote,
        suggestion=suggestion,
    )


def test_render_text_ends_with_the_count() -> None:
    violations = RuleViolations.collect(
        [violation("x.md", Position(line=2, column=5), "a; b", "")]
    )

    assert violations.render(OutputFormat.TEXT).splitlines() == [
        "x.md:2:5: CHR004 Semicolon",
        "    > a; b",
        "    Fix: delete the span",
        "Found 1 violations.",
    ]


def test_render_json_keeps_unlocated_positions_null() -> None:
    violations = RuleViolations.collect([violation("x.md", None, None, None)])

    assert json.loads(violations.render(OutputFormat.JSON)) == [
        {
            "code": "CHR004",
            "path": "x.md",
            "line": None,
            "column": None,
            "message": "Semicolon",
            "quote": None,
            "suggestion": None,
        }
    ]


def test_collect_orders_by_path_then_position_with_unlocated_last() -> None:
    late = violation("a.md", Position(line=3, column=1), None, None)
    early = violation("a.md", Position(line=1, column=9), None, None)
    unlocated = violation("a.md", None, None, None)
    other_file = violation("b.md", Position(line=1, column=1), None, None)

    violations = RuleViolations.collect([other_file, unlocated, late, early])

    assert list(violations) == [early, late, unlocated, other_file]


def test_concatenate_keeps_part_order_and_counts() -> None:
    first = RuleViolations.collect(
        [violation("b.md", Position(line=1, column=1), None, None)]
    )
    second = RuleViolations.collect(
        [violation("a.md", Position(line=1, column=1), None, None)]
    )

    joined = RuleViolations.concatenate([first, second])

    assert [item.path for item in joined] == ["b.md", "a.md"]
    assert len(joined) == 2
