from pathlib import Path

from nll.document import Document
from nll.rules import CodeRule, RuleBook


def find_code_rule(rulebook: RuleBook, identifier: str) -> CodeRule:
    """Find one code rule from a rule book."""
    rule = next(
        rule
        for rule in rulebook.rules_definitions.iter_rules()
        if rule.identifier == identifier
    )
    assert isinstance(rule, CodeRule)
    return rule


def test_character_rule_reports_each_occurrence_with_line_positions(
    rulebook: RuleBook,
) -> None:
    rule = find_code_rule(rulebook, "CHR004")

    violations = list(rule(Document(prose="one; two;\nthree", path=Path("notes.md"))))

    assert [(item.line, item.offset, item.quote) for item in violations] == [
        (1, 4, "one; two;"),
        (1, 9, "one; two;"),
    ]
    assert all(item.rule is rule for item in violations)


def test_other_non_ascii_skips_characters_with_dedicated_rules(
    rulebook: RuleBook,
) -> None:
    rule = find_code_rule(rulebook, "CHR000")

    violations = list(rule(Document(prose="café — · –", path=Path("notes.md"))))

    assert len(violations) == 1
    assert violations[0].offset == 4
    assert violations[0].quote == "café — · –"


def test_other_non_ascii_reports_unassigned_unicode_characters(
    rulebook: RuleBook,
) -> None:
    rule = find_code_rule(rulebook, "CHR000")

    violations = list(rule(Document(prose="a\U000e0080b", path=Path("notes.md"))))

    assert len(violations) == 1
    assert violations[0].offset == 2


def test_sentence_rule_counts_sentences_ending_in_punctuation(
    rulebook: RuleBook,
) -> None:
    rule = find_code_rule(rulebook, "LEN001")

    violations = list(
        rule(Document(prose="One. Two! Three? Four.", path=Path("notes.md")))
    )

    assert len(violations) == 1
    assert violations[0].path == Path("notes.md")


def test_sentence_rule_ignores_text_at_or_below_the_limit(
    rulebook: RuleBook,
) -> None:
    rule = find_code_rule(rulebook, "LEN001")

    assert list(rule(Document(prose="One. Two. Three.", path=Path("notes.md")))) == []
