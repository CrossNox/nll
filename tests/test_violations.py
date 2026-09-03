from pathlib import Path

from nll.rules import Rule
from nll.violations import Violation, Violations


def make_violation(
    path: Path | None, line: int | None, offset: int | None, quote: str | None
) -> Violation:
    return Violation(
        rule=Rule("CHR", "004", "Semicolon."),
        path=path,
        line=line,
        offset=offset,
        quote=quote,
    )


def test_violation_without_location_renders_only_the_rule() -> None:
    violation = make_violation(Path("x.md"), None, None, None)

    assert str(violation) == "CHR004: Semicolon."


def test_violation_renders_location_quote_and_truncated_long_quote() -> None:
    quote = "x" * 105
    violation = make_violation(Path("x.md"), 2, 5, quote)

    rendered = str(violation)

    assert rendered.startswith("line 2:\n\t> " + "x" * 100)
    assert rendered.endswith("...[5 chars]\nCHR004: Semicolon.")


def test_violations_sort_by_path_then_location() -> None:
    late = make_violation(Path("a.md"), 3, 1, "late")
    early = make_violation(Path("a.md"), 1, 9, "early")
    other = make_violation(Path("b.md"), 1, 1, "other")
    unlocated = make_violation(Path("a.md"), None, None, None)

    violations = Violations([unlocated, other, late, early])

    assert list(violations) == [unlocated, early, late, other]


def test_extend_keeps_all_items_in_sorted_order() -> None:
    first = Violations([make_violation(Path("b.md"), 1, 1, "b")])
    second = Violations([make_violation(Path("a.md"), 2, 1, "a2")])

    first.extend(second)

    assert [item.path for item in first] == [Path("a.md"), Path("b.md")]


def test_collect_flattens_parts_and_sorts_them() -> None:
    first = Violations([make_violation(Path("b.md"), 1, 1, "b")])
    second = Violations([make_violation(Path("a.md"), 1, 1, "a")])

    collected = Violations.collect([first, second])

    assert [item.path for item in collected] == [Path("a.md"), Path("b.md")]


def test_violations_render_groups_items_by_path() -> None:
    violations = Violations(
        [
            make_violation(Path("a.md"), 1, 1, "a"),
            make_violation(Path("b.md"), 2, 1, "b"),
        ]
    )

    assert str(violations).splitlines() == [
        "a.md",
        "=====",
        "",
        "line 1:",
        "\t> a",
        "CHR004: Semicolon.",
        "",
        "b.md",
        "=====",
        "",
        "line 2:",
        "\t> b",
        "CHR004: Semicolon.",
    ]
