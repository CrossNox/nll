from pathlib import Path

import pytest

from nll.document import Document
from nll.rules import CodeRule, RuleBook


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
        ("CLH001", "No sign-ups, no downloads, no hassle - just paste and go.", 1),
        ("CLH001", "The plan has no hidden fees and no long-term contracts.", 1),
        ("CLH001", "No fluff, no filler, no jargon, no corporate buzzwords.", 1),
        ("CLH001", "There is no catch here, honestly.", 0),
        ("CLH001", "It ships with no bells and whistles, no fluff.", 1),
        ("CLH001", "No, no, I insist.", 0),
        ("CLH001", "no no no", 0),
        ("CLH001", "with no list patterns at all, so nothing lights up.", 0),
        ("CLH001", "NO FEES, NO CONTRACTS, NO SURPRISES", 1),
        ("CLH001", "no fluff; no filler", 1),
        ("CLH001", "no time, no money, no way to say no thanks", 1),
        ("CLH001", "no-code, no-fuss setup", 1),
        ("CLH001", "I know nothing, notice nothing.", 0),
        ("CLH001", "No fluff, no filler.\nNo ads here.", 1),
        ("CLH002", "That's the whole point.", 1),
        ("CLH002", "This is the whole game, really.", 1),
        ("CLH002", "That was the whole pitch.", 1),
        ("CLH002", "The whole team showed up.", 0),
        ("CLH003", "Did not flinch, did not blink, did not apologize.", 1),
        ("CLH003", "He didn't call and didn't write.", 1),
        ("CLH003", "She did not go.", 0),
        ("CLH003", "Did not know why, did not care.", 1),
        ("CLH004", "Don't call it a comeback. Call it a return.", 1),
        ("CLH004", "Do not think of it as a burden. Think of it as fuel.", 1),
        ("CLH004", "Don't fear it. Name it.", 0),
        ("CLH004", 'Don\'t call it "luck." Call it preparation.', 1),
        ("CLH004", "Don't just read it — read it aloud.", 1),
        ("CLH004", "Don't overthink it.", 0),
        ("CLH005", "Sit with that for a moment.", 1),
        ("CLH005", "Just sit with it.", 1),
        ("CLH005", "She was sitting with the discomfort.", 1),
        ("CLH005", "Come sit with us at lunch.", 0),
        ("CLH006", "You already know the answer.", 1),
        ("CLH006", "Deep down, you already know.", 1),
        ("CLH006", "If you already know Python, skip ahead.", 0),
        ("CLH006", "You already know what to do.", 1),
        ("CLH006", "Part of you already knows it.", 1),
        ("CLH007", "Consistency is the entire game.", 1),
        ("CLH007", "That's the entire business model.", 1),
        ("CLH007", "He toured the entire factory.", 0),
        ("CLH008", "The entire point is that nobody reads.", 1),
        ("CLH008", "The entire business model is built on churn.", 1),
        ("CLH008", "The entire point of the exercise is repetition.", 1),
        ("CLH008", "He ate the entire pizza.", 0),
        ("CLH008", "The entire team was exhausted.", 1),
        (
            "CLH008",
            "The entire history of the modern industrial world economy is complex.",
            0,
        ),
        ("CLH009", "The improvement is real, and it's not subtle.", 1),
        ("CLH009", "This is the real work, and it never ends.", 1),
        ("CLH009", "The demand is real and growing.", 1),
        ("CLH009", "He is a real estate agent and it shows.", 0),
        ("CLH009", "Is it real? And does it matter?", 0),
        ("CLH009", "The painting is real, but stolen.", 0),
        ("CLH010", "The punchline is that nobody laughed.", 1),
        ("CLH010", "The punchline: nothing changed.", 1),
        ("CLH010", "And the punchline? You knew.", 1),
        ("CLH010", "He forgot the punchline entirely.", 0),
        ("CLH011", "That loss is real and it's worth naming.", 1),
        ("CLH011", "It's worth naming that this hurts.", 1),
        ("CLH011", "The grief here is worth naming.", 1),
        ("CLH011", "That anger feels worth naming out loud.", 1),
        ("CLH011", "Worth naming: nobody asked for this.", 1),
        ("CLH011", "It's not worth naming names here.", 0),
        ("CLH011", "They spent the meeting naming the new mascot.", 0),
        ("CLH011", "The naming convention is worth documenting.", 0),
        ("CLH012", "That's not nothing.", 1),
        ("CLH012", "Ten sign-ups in a week - that is not nothing.", 1),
        ("CLH012", "It's not nothing, even if it's not everything.", 1),
        ("CLH012", "The launch drew a small crowd, which was not nothing.", 1),
        ("CLH012", "She insisted that nothing was wrong.", 0),
        ("CLH012", "There is nothing left to say.", 0),
        ("CLH013", "Distribution is the whole game.", 1),
        ("CLH013", "Here's the whole pitch in one slide.", 1),
        ("CLH013", "That was the whole point of the meeting.", 1),
        ("CLH013", "The whole team showed up.", 0),
        (
            "CLH014",
            "A shopping cart is an object in the system. "
            "A chat room is an object in the system.",
            1,
        ),
        (
            "CLH014",
            "The parser is a state machine. The renderer is a state machine. "
            "The scheduler is a state machine.",
            1,
        ),
        ("CLH014", "The parser is fast today. The renderer is fast today.", 0),
        ("CLH014", "The parser is fast. The tests are slow.", 0),
        ("CLH015", "I won't pretend the migration was painless.", 1),
        ("CLH015", "Let's be honest: nobody reads the docs.", 1),
        ("CLH015", "To be clear, the API is unchanged.", 1),
        ("CLH015", "Honestly, it was fine.", 1),
        ("CLH015", "She answered honestly.", 0),
        ("CLH015", "Look at the diagram.", 0),
        ("CLH016", "That's the part a counter can't reach.", 1),
        ("CLH016", "The part that makes me trust the rest is the errata.", 1),
        ("CLH016", "My favorite part of the demo was the undo.", 1),
        ("CLH016", "He played the part of the villain.", 0),
        ("CLH017", "It's the only marketing I trust.", 1),
        ("CLH017", "The only benchmark that matters is retention.", 1),
        ("CLH017", "The only thing it needs is a cache.", 1),
        ("CLH017", "She was the only engineer on call.", 0),
        ("CLH018", "You don't have to take my word for it.", 1),
        ("CLH018", "Don't take my word for any of this.", 1),
        ("CLH018", "He kept his word.", 0),
        ("CLH019", "Turns out the cache was never warm.", 1),
        ("CLH019", "It turns out that nobody tested it.", 1),
        ("CLH019", "She turns out solid work every week.", 0),
        ("CLH020", "The design is small enough to hold in your head.", 1),
        ("CLH020", "It ships with sane defaults and zero config.", 2),
        ("CLH020", "Install it and it just works.", 1),
        ("CLH020", "We choose boring technology on purpose.", 0),
        ("CLH020", "The helmet fits your head.", 0),
        (
            "CLH021",
            "Do I know how it works? Where it breaks? Which corners it cut?",
            1,
        ),
        ("CLH021", "Was it worth it? Would I do it again?", 1),
        ("CLH021", "Did it work? Yes, and then some.", 0),
        ("CLH021", "What changed?", 0),
        (
            "CLH022",
            "Maybe nobody needed it. Maybe the timing was off. Maybe both.",
            1,
        ),
        ("CLH022", "Maybe nobody needed it. Maybe the timing was off.", 0),
        (
            "CLH022",
            "The parser is small. The renderer is small. The scheduler is small.",
            0,
        ),
        (
            "CLH022",
            "Everything changed. Everything slowed down. Everything cost more.",
            1,
        ),
        (
            "CLH023",
            "The fix needs three things: separate ports, separate processes, "
            "and separate state.",
            1,
        ),
        (
            "CLH023",
            "Each service gets its own everything: ports, processes, local state.",
            1,
        ),
        ("CLH023", "The recipe calls for flour, butter, and sugar.", 0),
        ("CLH023", "Note: the flag is off by default.", 0),
        ("CLH024", "Here's the twist: nobody clicked it.", 1),
        ("CLH024", "Here is the thing. The demo was fake.", 1),
        ("CLH024", "Here's a surprising result: it got faster.", 1),
        ("CLH024", "Here's the door code.", 0),
        ("CLH025", "Peer code review is dead.", 1),
        ("CLH025", "The old importer is dead; long live the importer.", 2),
        ("CLH025", "Long live the king.", 1),
        ("CLH025", "He played dead until the bear left.", 0),
        ("CLH026", "That's why being able to open the environment mattered.", 1),
        ("CLH026", "This is why preserving every conversation mattered.", 1),
        ("CLH026", "That's why the deadline counts.", 1),
        ("CLH026", "That is why we left early.", 0),
        ("CLH027", "The tool died; the data didn't.", 1),
        ("CLH027", "Reading mostly passed, writing didn't.", 1),
        ("CLH027", "Maybe it wouldn't have.", 1),
        ("CLH027", "The test passed and the build was green.", 0),
    ],
)
def test_writing_pattern_rule_matches_cases(
    rulebook: RuleBook, identifier: str, prose: str, expected_matches: int
) -> None:
    rule = get_rule(rulebook, identifier)

    violations = list(rule(Document(prose=prose, path=Path("notes.md"))))

    assert len(violations) == expected_matches


def test_cliche_rule_reports_match_location_and_quote(rulebook: RuleBook) -> None:
    rule = get_rule(rulebook, "CLH001")
    prose = "Before.\nNo fluff, no filler.\nAfter."

    violations = list(rule(Document(prose=prose, path=Path("notes.md"))))

    assert [(item.line, item.offset, item.quote) for item in violations] == [
        (2, 1, "No fluff, no filler"),
    ]


def test_imported_rules_are_enabled_code_rules(rulebook: RuleBook) -> None:
    cliche_rules = [
        rule
        for rule in rulebook.rules_definitions.iter_rules()
        if rule.identifier.startswith("CLH")
    ]
    wikipedia_rules = [
        rule
        for rule in rulebook.rules_definitions.iter_rules()
        if rule.identifier.startswith("WIK")
    ]

    assert [rule.identifier for rule in cliche_rules] == [
        f"CLH{code:03}" for code in range(1, 28)
    ]
    assert [rule.identifier for rule in wikipedia_rules] == [
        f"WIK{code:03}" for code in range(1, 12)
    ]
    assert all(isinstance(rule, CodeRule) for rule in [*cliche_rules, *wikipedia_rules])
    assert all(
        rule.identifier in rulebook.rules_on
        for rule in [*cliche_rules, *wikipedia_rules]
    )
