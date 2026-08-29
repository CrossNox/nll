from typing import Any

import pytest

from nll.rules import RuleBook

SEC_GROUP: dict[str, Any] = {
    "SEC": {
        "description": "Infrastructure details",
        "001": "Names an internal host",
        "abc": "Shows a token",
    }
}


def test_builtin_rulebook_has_every_documented_group(rulebook: RuleBook) -> None:
    assert rulebook.prefixes() == {"SCH", "SLO", "ZIN", "CHR", "LEN"}
    assert "SCH000" in rulebook
    assert rulebook["ZIN001"].group_description.startswith("Zinsser")


def test_builtin_len001_carries_its_option_and_renders_it(rulebook: RuleBook) -> None:
    assert rulebook["LEN001"].options == {"max-sentences": 3}
    assert rulebook["LEN001"].description == (
        "The text has more than {{ max_sentences }} sentences."
    )
    assert rulebook["LEN001"].render_description() == (
        "The text has more than 3 sentences."
    )


def test_select_expands_prefixes(rulebook: RuleBook) -> None:
    codes = {rule.code for rule in rulebook.select(["CHR"], [], [])}

    assert codes == {"CHR000", "CHR001", "CHR002", "CHR003", "CHR004"}


def test_extend_select_and_ignore_apply_on_top(rulebook: RuleBook) -> None:
    rules = rulebook.select(["SCH", "CHR004"], ["LEN001"], ["SCH00", "CHR004"])

    assert [rule.code for rule in rules] == ["LEN001"]


def test_unknown_selector_raises(rulebook: RuleBook) -> None:
    with pytest.raises(ValueError, match="matches no rule"):
        rulebook.expand("XYZ")

    with pytest.raises(ValueError, match="matches no rule"):
        rulebook.expand("ALL")


def test_merge_adds_a_new_group_after_the_existing_ones(rulebook: RuleBook) -> None:
    merged = rulebook.merge(SEC_GROUP, "nll.toml")

    assert [rule.code for rule in merged][-2:] == ["SEC001", "SECabc"]
    assert merged["SEC001"].group_description == "Infrastructure details"
    assert merged["SECabc"].options == {}


def test_merge_overrides_options_of_an_existing_rule(rulebook: RuleBook) -> None:
    merged = rulebook.merge({"LEN": {"001": {"max-sentences": 5}}}, "nll.toml")

    assert merged["LEN001"].options == {"max-sentences": 5}
    assert merged["LEN001"].render_description() == (
        "The text has more than 5 sentences."
    )
    assert merged["LEN002"] == rulebook["LEN002"]


@pytest.mark.parametrize(
    ("groups", "message"),
    [
        ({"sec": {"description": "x", "001": "y"}}, "uppercase"),
        ({"SEC": {"001": "y"}}, "needs a description string"),
        ({"SEC": {"description": "x", "0-1": "y"}}, "must be letters or digits"),
        ({"SEC": {"description": "x", "001": 1}}, "must be a description or a table"),
        (
            {"SEC": {"description": "x", "001": {"max-sentences": 3}}},
            "must be a description or a table",
        ),
        (
            {"SEC": {"description": "x", "001": {"description": "y", "limit": 3}}},
            "rule SEC001 options are invalid",
        ),
        ({"SCH": {"description": "again"}}, "group SCH is already defined"),
        ({"SCH": {"999": "new rule"}}, "group SCH is already defined"),
        ({"SCH": 3}, "group SCH is already defined"),
        ({"LEN": {"001": {"description": "changed"}}}, "group LEN is already defined"),
        ({"LEN": {"001": {"max-sentences": 0}}}, "rule LEN001 options are invalid"),
        ({"LEN": {"001": {"max-words": 3}}}, "rule LEN001 options are invalid"),
        ({"SEC": {"description": "x", "001": "Over {{ limit }}."}}, "cannot render"),
    ],
)
def test_merge_rejects_bad_groups_and_overrides(
    rulebook: RuleBook, groups: Any, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        rulebook.merge(groups, "nll.toml")
