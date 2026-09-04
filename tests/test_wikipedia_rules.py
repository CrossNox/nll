from pathlib import Path

import pytest

from linnl.document import Document
from linnl.rules import CodeRule, RuleBook


def get_rule(rulebook: RuleBook, identifier: str) -> CodeRule:
    rule = next(
        rule
        for rule in rulebook.rules_definitions.iter_rules()
        if rule.identifier == identifier
    )
    assert isinstance(rule, CodeRule)
    return rule


@pytest.mark.parametrize(
    ("identifier", "prose", "expected_matches"),
    [
        ("WIK001", "We delve into the intricacies of the interplay.", 3),
        ("WIK001", "Her vibrant tapestry hung in the bustling hall.", 3),
        ("WIK001", "A meticulously curated, seamless experience.", 2),
        ("WIK001", "The report was thorough and well organized.", 0),
        ("WIK002", "This is not just a tool, but a philosophy.", 1),
        ("WIK002", "Not only fast but also reliable.", 1),
        ("WIK002", "It's not a bug — it's a feature.", 1),
        ("WIK002", "He did not buy it.", 0),
        ("WIK002", "She was not sure about the plan.", 0),
        ("WIK003", "It is important to note that timing matters.", 1),
        ("WIK003", "It's worth noting the fees are separate.", 1),
        ("WIK003", "It should be noted that this changed in 2020.", 1),
        ("WIK003", "It's worth pausing on that number.", 1),
        ("WIK003", "It is worth asking who benefits.", 1),
        ("WIK003", "Please note the door code.", 0),
        ("WIK004", "The building stands as a testament to postwar optimism.", 1),
        ("WIK004", "Her career is a testament to persistence.", 1),
        ("WIK004", "It serves as a stark reminder that nothing lasts.", 1),
        ("WIK004", "He read from the Old Testament.", 0),
        ("WIK005", "Volunteers play a crucial role in the program.", 1),
        ("WIK005", "She played a truly pivotal role in the merger.", 1),
        ("WIK005", "He plays the role of the villain.", 0),
        ("WIK006", "Adapting to an ever-evolving landscape.", 1),
        ("WIK006", "The rapidly changing landscape of retail.", 1),
        ("WIK006", "In today's fast-paced world, attention is scarce.", 1),
        ("WIK006", "The landscape outside the window was gray.", 0),
        ("WIK007", "Experts argue that the policy failed.", 1),
        ("WIK007", "Some critics have noted a decline in quality.", 1),
        ("WIK007", "Industry reports suggest strong demand.", 1),
        ("WIK007", "Dr. Chen argued the opposite in her paper.", 0),
        ("WIK008", "Despite these challenges, growth continued.", 1),
        ("WIK008", "The sector faces several challenges.", 1),
        ("WIK008", "Whether it works remains to be seen.", 1),
        ("WIK008", "Only time will tell whether it sticks.", 1),
        ("WIK008", "Time will tell.", 1),
        ("WIK008", "He arrived on time and will tell you himself.", 0),
        ("WIK008", "The climb was a challenge.", 0),
        (
            "WIK009",
            "The bridge reopened in June, highlighting the city's investment "
            "in infrastructure.",
            1,
        ),
        ("WIK009", "Sales doubled, underscoring the strength of the brand.", 1),
        ("WIK009", "She kept highlighting passages in yellow.", 0),
        ("WIK009", "The team, reflecting on the loss, regrouped.", 0),
        ("WIK010", "The inn is nestled in a quiet valley.", 1),
        ("WIK010", "The museum boasts a rich tapestry of exhibits.", 2),
        ("WIK010", "Located in the heart of downtown.", 1),
        ("WIK010", "A hidden gem with breathtaking views.", 2),
        ("WIK010", "The soup was rich and hearty.", 0),
        ("WIK011", "As of my last update, the API was in beta.", 1),
        ("WIK011", "As an AI language model, I cannot form opinions.", 1),
        ("WIK011", "See example.com/page?utm_source=chatgpt.com for details.", 1),
        ("WIK011", "contentReference[oaicite:0]{index=0}", 2),
        ("WIK011", "The last update shipped on Tuesday.", 0),
    ],
)
def test_wikipedia_rule_matches_cases(
    rulebook: RuleBook, identifier: str, prose: str, expected_matches: int
) -> None:
    rule = get_rule(rulebook, identifier)

    violations = list(rule(Document(prose=prose, path=Path("notes.md"))))

    assert len(violations) == expected_matches
