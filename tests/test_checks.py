from collections.abc import Iterable

import pytest

from nll.checks import check_characters, run_python_checks
from nll.document import Document
from nll.rules import Rule, RuleBook
from nll.violations import RuleViolation


@pytest.fixture
def character_rules(rulebook: RuleBook) -> list[Rule]:
    return rulebook.select(["CHR"], [], [])


def list_positions(violations: Iterable[RuleViolation]) -> list[tuple[str, int, int]]:
    """Return (code, line, column) per violation, failing on a missing position."""
    positions = []
    for item in violations:
        assert item.position is not None
        positions.append((item.rule.code, item.position.line, item.position.column))
    return positions


def test_check_characters_reports_each_named_character(
    character_rules: list[Rule],
) -> None:
    document = Document("a — b\nc – d\ne · f\ng; h\n", "x")

    violations = check_characters(document, character_rules, ignore_code=True)

    assert list_positions(violations) == [
        ("CHR001", 1, 3),
        ("CHR002", 2, 3),
        ("CHR003", 3, 3),
        ("CHR004", 4, 2),
    ]
    assert violations[0].quote == "a — b"


def test_chr000_covers_other_non_ascii_only_when_selected(
    rulebook: RuleBook, character_rules: list[Rule]
) -> None:
    document = Document("café —", "x")

    with_chr000 = check_characters(document, character_rules, ignore_code=True)
    only_chr001 = check_characters(document, [rulebook["CHR001"]], ignore_code=True)

    assert [item.rule.code for item in with_chr000] == ["CHR000", "CHR001"]
    assert "LATIN SMALL LETTER E WITH ACUTE" in with_chr000[0].message
    assert [item.rule.code for item in only_chr001] == ["CHR001"]


def test_chr000_names_an_unassigned_code_point_as_unnamed(
    character_rules: list[Rule],
) -> None:
    document = Document("a\U000e0080b", "x")

    violations = check_characters(document, character_rules, ignore_code=True)

    assert [item.rule.code for item in violations] == ["CHR000"]
    assert "(unnamed)" in violations[0].message


def test_code_is_masked_unless_ignore_code_is_off(character_rules: list[Rule]) -> None:
    document = Document("prose; here\n```sh\na; b\n```\nand `x; y` end; ok\n", "x")

    masked = check_characters(document, character_rules, ignore_code=True)
    assert list_positions(masked) == [("CHR004", 1, 6), ("CHR004", 5, 15)]

    unmasked = check_characters(document, character_rules, ignore_code=False)
    assert len(unmasked) == 4


def test_run_python_checks_dispatches_to_each_registered_check(
    rulebook: RuleBook,
) -> None:
    rules = rulebook.select(["CHR004", "LEN001"], [], [])
    document = Document("One; two. Three! Four? Five.\n", "x")

    violations = run_python_checks(document, rules, ignore_code=True)

    assert [item.rule.code for item in violations] == ["CHR004", "LEN001"]
    assert "4 sentences" in violations[1].message

    relaxed = rulebook.merge({"LEN": {"001": {"max-sentences": 4}}}, "test")
    relaxed_rules = relaxed.select(["CHR004", "LEN001"], [], [])
    assert (
        run_python_checks(document, relaxed_rules, ignore_code=True) == violations[:1]
    )
