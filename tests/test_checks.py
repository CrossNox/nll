from collections.abc import Iterable

import pytest

from nll.document import Document
from nll.rules import RuleBook
from nll.violations import Violation


def list_positions(violations: Iterable[Violation]) -> list[tuple[str, int, int]]:
    """Return (code, line, column) per violation, failing on a missing position."""
    positions = []
    for item in violations:
        assert item.position is not None
        positions.append((item.code, item.position.line, item.position.column))
    return positions


def run_checks(
    rulebook: RuleBook, codes: list[str], document: Document
) -> list[Violation]:
    """Run the named Python rules over the document with code masked."""
    prose = document.extract_prose(ignore_code=True)
    violations: list[Violation] = []
    for code in codes:
        violations.extend(rulebook[code].run_check(document, prose))
    return violations


def test_each_character_rule_reports_its_character(rulebook: RuleBook) -> None:
    document = Document("a — b\nc – d\ne · f\ng; h\n", "x")

    violations = run_checks(
        rulebook, ["CHR001", "CHR002", "CHR003", "CHR004"], document
    )

    assert list_positions(violations) == [
        ("CHR001", 1, 3),
        ("CHR002", 2, 3),
        ("CHR003", 3, 3),
        ("CHR004", 4, 2),
    ]
    assert violations[0].message == "Em dash (U+2014)."
    assert violations[0].quote == "a — b"
    assert violations[3].suggestion == "Split into two sentences or join with a comma"


def test_chr000_skips_characters_other_chr_rules_cover(rulebook: RuleBook) -> None:
    document = Document("café — · –", "x")

    violations = run_checks(rulebook, ["CHR000"], document)

    assert list_positions(violations) == [("CHR000", 1, 4)]
    assert "LATIN SMALL LETTER E WITH ACUTE" in violations[0].message


def test_chr000_names_an_unassigned_code_point_as_unnamed(rulebook: RuleBook) -> None:
    document = Document("a\U000e0080b", "x")

    violations = run_checks(rulebook, ["CHR000"], document)

    assert [item.code for item in violations] == ["CHR000"]
    assert "(unnamed)" in violations[0].message


def test_checks_see_only_the_prose_they_are_given(rulebook: RuleBook) -> None:
    document = Document("prose; here\n```sh\na; b\n```\nand `x; y` end; ok\n", "x")
    rule = rulebook["CHR004"]

    masked = rule.run_check(document, document.extract_prose(ignore_code=True))
    assert list_positions(masked) == [("CHR004", 1, 6), ("CHR004", 5, 15)]

    unmasked = rule.run_check(document, document.text)
    assert len(unmasked) == 4


def test_len001_reports_over_its_configured_limit(rulebook: RuleBook) -> None:
    document = Document("One; two. Three! Four? Five.\n", "x")

    violations = run_checks(rulebook, ["LEN001"], document)

    assert list_positions(violations) == [("LEN001", 1, 1)]
    assert violations[0].message == "Text has 4 sentences, the limit is 3"
    assert violations[0].quote is None

    relaxed = rulebook.merge({"LEN": {"001": {"max-sentences": 4}}}, "test")
    assert run_checks(relaxed, ["LEN001"], document) == []


def test_a_model_rule_has_no_python_check_to_run(rulebook: RuleBook) -> None:
    with pytest.raises(TypeError, match="SCH001 is judged by the model"):
        rulebook["SCH001"].run_check(Document("x", "x"), "x")
