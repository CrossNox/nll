import pytest

from nll.document import Document
from nll.rules import CodeRule, RuleBook


def get_rule(rulebook: RuleBook, identifier: str) -> CodeRule:
    return next(
        rule
        for rule in rulebook.rules_definitions.iter_rules()
        if rule.identifier == identifier
    )


@pytest.mark.parametrize(
    ("code", "prose", "expected_matches"),
    [
        ("001", "No sign-ups, no downloads, no hassle - just paste and go.", 1),
        ("001", "The plan has no hidden fees and no long-term contracts.", 1),
        ("001", "No fluff, no filler, no jargon, no corporate buzzwords.", 1),
        ("001", "There is no catch here, honestly.", 0),
        ("001", "It ships with no bells and whistles, no fluff.", 1),
        ("001", "No, no, I insist.", 0),
        ("001", "no no no", 0),
        ("001", "with no list patterns at all, so nothing lights up.", 0),
        ("001", "NO FEES, NO CONTRACTS, NO SURPRISES", 1),
        ("001", "no fluff; no filler", 1),
        ("001", "no time, no money, no way to say no thanks", 1),
        ("001", "no-code, no-fuss setup", 1),
        ("001", "I know nothing, notice nothing.", 0),
        ("001", "No fluff, no filler.\nNo ads here.", 1),
        ("002", "That's the whole point.", 1),
        ("002", "This is the whole game, really.", 1),
        ("002", "That was the whole pitch.", 1),
        ("002", "The whole team showed up.", 0),
        ("003", "Did not flinch, did not blink, did not apologize.", 1),
        ("003", "He didn't call and didn't write.", 1),
        ("003", "She did not go.", 0),
        ("003", "Did not know why, did not care.", 1),
        ("004", "Don't call it a comeback. Call it a return.", 1),
        ("004", "Do not think of it as a burden. Think of it as fuel.", 1),
        ("004", "Don't fear it. Name it.", 0),
        ("004", "Don't call it \"luck.\" Call it preparation.", 1),
        ("004", "Don't just read it — read it aloud.", 1),
        ("004", "Don't overthink it.", 0),
        ("005", "Sit with that for a moment.", 1),
        ("005", "Just sit with it.", 1),
        ("005", "She was sitting with the discomfort.", 1),
        ("005", "Come sit with us at lunch.", 0),
        ("006", "You already know the answer.", 1),
        ("006", "Deep down, you already know.", 1),
        ("006", "If you already know Python, skip ahead.", 0),
        ("006", "You already know what to do.", 1),
        ("006", "Part of you already knows it.", 1),
        ("007", "Consistency is the entire game.", 1),
        ("007", "That's the entire business model.", 1),
        ("007", "He toured the entire factory.", 0),
        ("008", "The entire point is that nobody reads.", 1),
        ("008", "The entire business model is built on churn.", 1),
        ("008", "The entire point of the exercise is repetition.", 1),
        ("008", "He ate the entire pizza.", 0),
        ("008", "The entire team was exhausted.", 1),
        (
            "008",
            "The entire history of the modern industrial world economy is complex.",
            0,
        ),
        ("009", "The improvement is real, and it's not subtle.", 1),
        ("009", "This is the real work, and it never ends.", 1),
        ("009", "The demand is real and growing.", 1),
        ("009", "He is a real estate agent and it shows.", 0),
        ("009", "Is it real? And does it matter?", 0),
        ("009", "The painting is real, but stolen.", 0),
        ("010", "The punchline is that nobody laughed.", 1),
        ("010", "The punchline: nothing changed.", 1),
        ("010", "And the punchline? You knew.", 1),
        ("010", "He forgot the punchline entirely.", 0),
        ("011", "That loss is real and it's worth naming.", 1),
        ("011", "It's worth naming that this hurts.", 1),
        ("011", "The grief here is worth naming.", 1),
        ("011", "That anger feels worth naming out loud.", 1),
        ("011", "Worth naming: nobody asked for this.", 1),
        ("011", "It's not worth naming names here.", 0),
        ("011", "They spent the meeting naming the new mascot.", 0),
        ("011", "The naming convention is worth documenting.", 0),
        ("012", "That's not nothing.", 1),
        ("012", "Ten sign-ups in a week - that is not nothing.", 1),
        ("012", "It's not nothing, even if it's not everything.", 1),
        ("012", "The launch drew a small crowd, which was not nothing.", 1),
        ("012", "She insisted that nothing was wrong.", 0),
        ("012", "There is nothing left to say.", 0),
        ("013", "Distribution is the whole game.", 1),
        ("013", "Here's the whole pitch in one slide.", 1),
        ("013", "That was the whole point of the meeting.", 1),
        ("013", "The whole team showed up.", 0),
        (
            "014",
            "A shopping cart is an object in the system. "
            "A chat room is an object in the system.",
            1,
        ),
        (
            "014",
            "The parser is a state machine. The renderer is a state machine. "
            "The scheduler is a state machine.",
            1,
        ),
        ("014", "The parser is fast today. The renderer is fast today.", 0),
        ("014", "The parser is fast. The tests are slow.", 0),
        ("015", "I won't pretend the migration was painless.", 1),
        ("015", "Let's be honest: nobody reads the docs.", 1),
        ("015", "To be clear, the API is unchanged.", 1),
        ("015", "Honestly, it was fine.", 1),
        ("015", "She answered honestly.", 0),
        ("015", "Look at the diagram.", 0),
        ("016", "That's the part a counter can't reach.", 1),
        ("016", "The part that makes me trust the rest is the errata.", 1),
        ("016", "My favorite part of the demo was the undo.", 1),
        ("016", "He played the part of the villain.", 0),
        ("017", "It's the only marketing I trust.", 1),
        ("017", "The only benchmark that matters is retention.", 1),
        ("017", "The only thing it needs is a cache.", 1),
        ("017", "She was the only engineer on call.", 0),
        ("018", "You don't have to take my word for it.", 1),
        ("018", "Don't take my word for any of this.", 1),
        ("018", "He kept his word.", 0),
        ("019", "Turns out the cache was never warm.", 1),
        ("019", "It turns out that nobody tested it.", 1),
        ("019", "She turns out solid work every week.", 0),
        ("020", "The design is small enough to hold in your head.", 1),
        ("020", "It ships with sane defaults and zero config.", 2),
        ("020", "Install it and it just works.", 1),
        ("020", "We choose boring technology on purpose.", 0),
        ("020", "The helmet fits your head.", 0),
        (
            "021",
            "Do I know how it works? Where it breaks? Which corners it cut?",
            1,
        ),
        ("021", "Was it worth it? Would I do it again?", 1),
        ("021", "Did it work? Yes, and then some.", 0),
        ("021", "What changed?", 0),
        (
            "022",
            "Maybe nobody needed it. Maybe the timing was off. Maybe both.",
            1,
        ),
        ("022", "Maybe nobody needed it. Maybe the timing was off.", 0),
        (
            "022",
            "The parser is small. The renderer is small. The scheduler is small.",
            0,
        ),
        (
            "022",
            "Everything changed. Everything slowed down. Everything cost more.",
            1,
        ),
        (
            "023",
            "The fix needs three things: separate ports, separate processes, "
            "and separate state.",
            1,
        ),
        (
            "023",
            "Each service gets its own everything: ports, processes, local state.",
            1,
        ),
        ("023", "The recipe calls for flour, butter, and sugar.", 0),
        ("023", "Note: the flag is off by default.", 0),
        ("024", "Here's the twist: nobody clicked it.", 1),
        ("024", "Here is the thing. The demo was fake.", 1),
        ("024", "Here's a surprising result: it got faster.", 1),
        ("024", "Here's the door code.", 0),
        ("025", "Peer code review is dead.", 1),
        ("025", "The old importer is dead; long live the importer.", 2),
        ("025", "Long live the king.", 1),
        ("025", "He played dead until the bear left.", 0),
        ("026", "That's why being able to open the environment mattered.", 1),
        ("026", "This is why preserving every conversation mattered.", 1),
        ("026", "That's why the deadline counts.", 1),
        ("026", "That is why we left early.", 0),
        ("027", "The tool died; the data didn't.", 1),
        ("027", "Reading mostly passed, writing didn't.", 1),
        ("027", "Maybe it wouldn't have.", 1),
        ("027", "The test passed and the build was green.", 0),
        ("028", "We delve into the intricacies of the interplay.", 3),
        ("028", "Her vibrant tapestry hung in the bustling hall.", 3),
        ("028", "A meticulously curated, seamless experience.", 2),
        ("028", "The report was thorough and well organized.", 0),
        ("029", "This is not just a tool, but a philosophy.", 1),
        ("029", "Not only fast but also reliable.", 1),
        ("029", "It's not a bug — it's a feature.", 1),
        ("029", "He did not buy it.", 0),
        ("029", "She was not sure about the plan.", 0),
        ("030", "It is important to note that timing matters.", 1),
        ("030", "It's worth noting the fees are separate.", 1),
        ("030", "It should be noted that this changed in 2020.", 1),
        ("030", "It's worth pausing on that number.", 1),
        ("030", "It is worth asking who benefits.", 1),
        ("030", "Please note the door code.", 0),
        ("031", "The building stands as a testament to postwar optimism.", 1),
        ("031", "Her career is a testament to persistence.", 1),
        ("031", "It serves as a stark reminder that nothing lasts.", 1),
        ("031", "He read from the Old Testament.", 0),
        ("032", "Volunteers play a crucial role in the program.", 1),
        ("032", "She played a truly pivotal role in the merger.", 1),
        ("032", "He plays the role of the villain.", 0),
        ("033", "Adapting to an ever-evolving landscape.", 1),
        ("033", "The rapidly changing landscape of retail.", 1),
        ("033", "In today's fast-paced world, attention is scarce.", 1),
        ("033", "The landscape outside the window was gray.", 0),
        ("034", "Experts argue that the policy failed.", 1),
        ("034", "Some critics have noted a decline in quality.", 1),
        ("034", "Industry reports suggest strong demand.", 1),
        ("034", "Dr. Chen argued the opposite in her paper.", 0),
        ("035", "Despite these challenges, growth continued.", 1),
        ("035", "The sector faces several challenges.", 1),
        ("035", "Whether it works remains to be seen.", 1),
        ("035", "Only time will tell whether it sticks.", 1),
        ("035", "Time will tell.", 1),
        ("035", "He arrived on time and will tell you himself.", 0),
        ("035", "The climb was a challenge.", 0),
        (
            "036",
            "The bridge reopened in June, highlighting the city's investment "
            "in infrastructure.",
            1,
        ),
        ("036", "Sales doubled, underscoring the strength of the brand.", 1),
        ("036", "She kept highlighting passages in yellow.", 0),
        ("036", "The team, reflecting on the loss, regrouped.", 0),
        ("037", "The inn is nestled in a quiet valley.", 1),
        ("037", "The museum boasts a rich tapestry of exhibits.", 2),
        ("037", "Located in the heart of downtown.", 1),
        ("037", "A hidden gem with breathtaking views.", 2),
        ("037", "The soup was rich and hearty.", 0),
        ("038", "As of my last update, the API was in beta.", 1),
        ("038", "As an AI language model, I cannot form opinions.", 1),
        ("038", "See example.com/page?utm_source=chatgpt.com for details.", 1),
        ("038", "contentReference[oaicite:0]{index=0}", 2),
        ("038", "The last update shipped on Tuesday.", 0),
    ],
)
def test_cliche_rule_matches_source_cases(
    rulebook: RuleBook, code: str, prose: str, expected_matches: int
) -> None:
    rule = get_rule(rulebook, f"CLH{code}")

    violations = list(rule(Document(prose=prose, path="notes.md")))

    assert len(violations) == expected_matches


def test_cliche_rule_reports_match_location_and_quote(rulebook: RuleBook) -> None:
    rule = get_rule(rulebook, "CLH001")
    prose = "Before.\nNo fluff, no filler.\nAfter."

    violations = list(rule(Document(prose=prose, path="notes.md")))

    assert [(item.line, item.offset, item.quote) for item in violations] == [
        (2, 1, "No fluff, no filler"),
    ]


def test_cliche_rules_are_enabled_code_rules(rulebook: RuleBook) -> None:
    cliche_rules = [
        rule
        for rule in rulebook.rules_definitions.iter_rules()
        if rule.identifier.startswith("CLH")
    ]

    assert [rule.identifier for rule in cliche_rules] == [
        f"CLH{code:03}" for code in range(1, 39)
    ]
    assert all(isinstance(rule, CodeRule) for rule in cliche_rules)
    assert all(rule.identifier in rulebook.rules_on for rule in cliche_rules)
