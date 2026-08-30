from typing import Any

import pytest

from nll.checks import SentenceCountOptions
from nll.rules import NoOptions, RuleBook

SEC_GROUP: dict[str, Any] = {
    "SEC": {
        "description": "Infrastructure details",
        "001": "Names an internal host",
        "abc": "Shows a token",
    }
}


def test_builtin_rulebook_has_every_documented_group(rulebook: RuleBook) -> None:
    assert [group.prefix for group in rulebook.groups] == [
        "SCH",
        "SLO",
        "ZIN",
        "CHR",
        "LEN",
    ]
    assert rulebook["SCH000"].code == "SCH000"
    assert rulebook.groups[2].description.startswith("Zinsser")

    with pytest.raises(KeyError):
        rulebook["XYZ001"]


def test_builtin_rules_know_who_checks_them(rulebook: RuleBook) -> None:
    assert rulebook["CHR001"].is_checked_in_python
    assert rulebook["LEN001"].is_checked_in_python
    assert not rulebook["LEN002"].is_checked_in_python
    assert rulebook["SCH001"].options == NoOptions()


def test_builtin_len001_carries_its_option_and_renders_it(rulebook: RuleBook) -> None:
    rule = rulebook["LEN001"]

    assert rule.options == SentenceCountOptions(max_sentences=3)
    assert (
        rule.description_template == "The text has more than {max_sentences} sentences."
    )
    assert rule.description == "The text has more than 3 sentences."


def test_select_expands_prefixes_and_marks_enabled(rulebook: RuleBook) -> None:
    selected = rulebook.select(["CHR"], [], [])

    assert selected.enabled_codes == {
        "CHR000",
        "CHR001",
        "CHR002",
        "CHR003",
        "CHR004",
    }
    assert len(selected) == len(rulebook)


def test_extend_select_and_ignore_apply_on_top(rulebook: RuleBook) -> None:
    selected = rulebook.select(["SCH", "CHR004"], ["LEN001"], ["SCH00", "CHR004"])

    assert selected.enabled_codes == {"LEN001"}


def test_python_and_model_rules_split_the_enabled_ones(rulebook: RuleBook) -> None:
    selected = rulebook.select(["SCH003", "CHR004", "LEN"], [], [])

    assert [rule.code for rule in selected.python_rules] == ["CHR004", "LEN001"]
    assert [rule.code for rule in selected.model_rules] == ["SCH003", "LEN002"]


def test_unknown_selector_raises(rulebook: RuleBook) -> None:
    with pytest.raises(ValueError, match="matches no rule"):
        rulebook.expand("XYZ")

    with pytest.raises(ValueError, match="matches no rule"):
        rulebook.select(["ALL"], [], [])


def test_str_lists_groups_with_state_and_checker(rulebook: RuleBook) -> None:
    rendered = str(rulebook.select(["CHR001"], [], []))

    assert "CHR  Characters that must not appear in prose" in rendered
    assert "  CHR001   on   python  Em dash (U+2014)." in rendered
    assert "  SCH001   off  model   Tricolon." in rendered
    assert "  LEN001   off  python  The text has more than 3 sentences." in rendered


def test_markdown_lists_only_enabled_model_rules_under_their_groups(
    rulebook: RuleBook,
) -> None:
    rendered = rulebook.select(["SCH003", "CHR004", "LEN"], [], [])

    assert rendered.render_model_rules_as_markdown().splitlines() == [
        "## SCH: Schemes: figures that work through the arrangement or repetition "
        "of words rather than through meaning",
        "- SCH003: " + rulebook["SCH003"].description,
        "",
        "## LEN: Length and concision",
        "- LEN002: " + rulebook["LEN002"].description,
    ]


def test_merge_adds_a_new_model_group_after_the_existing_ones(
    rulebook: RuleBook,
) -> None:
    merged = rulebook.merge(SEC_GROUP, "nll.toml")

    assert [rule.code for rule in merged][-2:] == ["SEC001", "SECabc"]
    assert merged.groups[-1].description == "Infrastructure details"
    assert merged["SECabc"].options == NoOptions()
    assert not merged["SEC001"].is_checked_in_python


def test_merge_overrides_options_of_an_existing_rule(rulebook: RuleBook) -> None:
    merged = rulebook.merge({"LEN": {"001": {"max-sentences": 5}}}, "nll.toml")

    assert merged["LEN001"].options == SentenceCountOptions(max_sentences=5)
    assert merged["LEN001"].description == "The text has more than 5 sentences."
    assert merged["LEN001"].check is rulebook["LEN001"].check
    assert merged["LEN002"] == rulebook["LEN002"]


@pytest.mark.parametrize(
    ("groups", "message"),
    [
        ("not a table", "rules must be a table of groups"),
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
        (
            {"SEC": {"description": "x", "001": "Over {limit}."}},
            "rule SEC001 description names an unknown option 'limit'",
        ),
    ],
)
def test_merge_rejects_bad_groups_and_overrides(
    rulebook: RuleBook, groups: Any, message: str
) -> None:
    with pytest.raises(ValueError, match=message) as raised:
        rulebook.merge(groups, "nll.toml")

    assert "nll.toml" in str(raised.value)
