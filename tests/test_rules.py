from typing import Any

import pytest

from nll.config import SHIPPED_CONFIG_FILE
from nll.document import Document
from nll.rules import CodeRule, ModelRule, RegexRule, RuleBook, RulesDefinitions


def get_rule(rulebook: RuleBook, identifier: str) -> Any:
    return next(
        rule
        for rule in rulebook.rules_definitions.iter_rules()
        if rule.identifier == identifier
    )


def test_builtin_rules_are_parsed_into_sections(rulebook: RuleBook) -> None:
    assert [section.name for section in rulebook.all_rules.sections] == [
        "SCH",
        "SLO",
        "ZIN",
        "CHR",
        "LEN",
        "RGX",
    ]
    assert get_rule(rulebook, "SCH000").description.startswith("Other scheme")
    assert isinstance(get_rule(rulebook, "SCH001"), ModelRule)
    assert isinstance(get_rule(rulebook, "CHR001"), CodeRule)


def test_rule_formats_arguments_in_its_description(rulebook: RuleBook) -> None:
    rule = get_rule(rulebook, "LEN001")

    assert rule.arguments == {"max_sentences": 3}
    assert rule.description == "The text has more than 3 sentences."
    assert str(rule) == "LEN001: The text has more than 3 sentences."


def test_rulebook_selects_and_splits_enabled_rules(default_linter: Any) -> None:
    linter = default_linter.from_config(
        SHIPPED_CONFIG_FILE, select=["CHR", "LEN001"], ignore=[]
    )

    assert [rule.identifier for rule in linter.rules.code_rules] == [
        "CHR001",
        "CHR002",
        "CHR003",
        "CHR004",
        "CHR000",
        "LEN001",
    ]
    assert linter.rules.model_rules == []


def test_rulebook_extend_selection_and_ignore_are_prefix_based(
    default_linter: Any,
) -> None:
    linter = default_linter.from_config(
        SHIPPED_CONFIG_FILE,
        select=["CHR004"],
        extend_select=["LEN"],
        ignore=["LEN001"],
    )

    assert [rule.identifier for rule in linter.rules.code_rules] == ["CHR004"]
    assert [rule.identifier for rule in linter.rules.model_rules] == ["LEN002"]


def test_regex_rules_compile_and_report_matches() -> None:
    definitions = RulesDefinitions.model_validate(
        {"RGX": {"description": "Patterns", "001": r"X is not [^,]+, it's [^.]+"}}
    )
    rule = definitions.sections[0].rules[0]

    assert isinstance(rule, RegexRule)
    violations = list(rule(Document(prose="X is not slow, it's fast", path="x")))

    assert [(item.line, item.offset, item.quote) for item in violations] == [
        (1, 1, "X is not slow, it's fast")
    ]


def test_invalid_regex_is_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid regular expression for RGX001"):
        RulesDefinitions.model_validate(
            {"RGX": {"description": "Patterns", "001": "["}}
        )


@pytest.mark.parametrize(
    ("groups", "message"),
    [
        ({"SEC": {"001": "missing group description"}}, "no description"),
        ({"SEC": {"description": "x", "001": 1}}, "must be a description"),
        (
            {"SEC": {"description": "x", "001": {"max": 1}}},
            "no description",
        ),
    ],
)
def test_malformed_rule_definitions_raise_clear_errors(
    groups: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        RulesDefinitions.model_validate(groups)


def test_rulebook_string_shows_state_and_checker(rulebook: RuleBook) -> None:
    rendered = str(rulebook)

    assert "CHR - Characters that must not appear in prose" in rendered
    assert "[ON] CHR001: Em dash (U+2014)." in rendered
    assert "[OFF] CHR000: Any non-ASCII character not covered" in rendered
