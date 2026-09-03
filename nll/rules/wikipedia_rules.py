"""Define writing-pattern rules adapted from Wikipedia's AI-writing guidance."""

from nll.rules.pattern_rules import TextPatternRule


class Wikipedia001(TextPatternRule, identifier="WIK001"):
    pattern = (
        r"\b(?:delv(?:e|es|ed|ing)|tapestr(?:y|ies)|meticulous(?:ly)?|pivotal|"
        r"intricate(?:ly)?|intricacies|interplay|underscor(?:e|es|ed|ing)|"
        r"garner(?:s|ed|ing)?|bolster(?:s|ed|ing)?|vibrant|bustling|multifaceted|"
        r"seamless(?:ly)?|commendable|ever-evolving)\b"
    )


class Wikipedia002(TextPatternRule, identifier="WIK002"):
    pattern = (
        r"\bnot\s+(?:just|only|merely|simply)\s+[^.!?\n;]*?\bbut(?:\s+also)?\b|"
        r"\b(?:it|this|that)(?:['\u2019]s|\s+(?:is|was))\s+not\s+"
        r"[^.!?\n,;\u2014\u2013]{1,60}[,;\u2014\u2013]\s*(?:it|this|that)"
        r"(?:['\u2019]s|\s+(?:is|was))\b"
    )


class Wikipedia003(TextPatternRule, identifier="WIK003"):
    pattern = (
        r"\bit(?:['\u2019]s|\s+(?:is|was))\s+(?:also\s+)?"
        r"(?:important|worth|crucial|essential|vital)\s+(?:to\s+(?:note|remember|"
        r"understand|recognize|mention|pause|consider|ask)|noting|mentioning|"
        r"remembering|pausing|considering|asking)\b(?:\s+that\b)?|"
        r"\bit\s+should\s+be\s+noted\b"
    )


class Wikipedia004(TextPatternRule, identifier="WIK004"):
    pattern = (
        r"\b(?:stand|stands|stood|serve|serves|served|standing|serving)\s+as\s+"
        r"(?:a|an)\s+(?:\w+\s+)?(?:testament|reminder)\b|"
        r"\b(?:is|was|are|were|remain|remains)\s+a\s+(?:\w+\s+)?testament\s+to\b"
    )


class Wikipedia005(TextPatternRule, identifier="WIK005"):
    pattern = (
        r"\bplay(?:s|ed|ing)?\s+(?:a|an)\s+(?:\w+\s+)?"
        r"(?:crucial|pivotal|vital|key|significant|central|critical|important)\s+role\b"
    )


class Wikipedia006(TextPatternRule, identifier="WIK006"):
    pattern = (
        r"\b(?:ever-)?(?:evolving|changing|shifting)\s+landscape\b|"
        r"\bin\s+today['\u2019]s\s+(?:fast-paced|ever-changing|ever-evolving|"
        r"digital|modern|competitive)\s+\w+"
    )


class Wikipedia007(TextPatternRule, identifier="WIK007"):
    pattern = (
        r"\b(?:many|some|several|most|numerous)?\s*(?:experts|critics|observers|"
        r"scholars|analysts|commentators)\s+(?:have\s+|often\s+|widely\s+)?"
        r"(?:argu(?:e|es|ed)|not(?:e|es|ed)|suggest(?:s|ed)?|believ(?:e|es|ed)|"
        r"agree[ds]?|contend(?:s|ed)?|observ(?:e|es|ed)|caution(?:s|ed)?|"
        r"claim(?:s|ed)?|cit(?:e|es|ed)|point(?:s|ed)?\s+out)\b|"
        r"\bindustry\s+reports?\s+(?:suggest|indicate|show)\w*\b"
    )


class Wikipedia008(TextPatternRule, identifier="WIK008"):
    pattern = (
        r"\bdespite\s+(?:these|those|such|its|their|the|numerous|significant|"
        r"ongoing)\s+(?:\w+\s+)?challenges\b|\bfac(?:e|es|ed|ing)\s+(?:several|"
        r"numerous|many|significant|various|a\s+number\s+of)\s+challenges\b|"
        r"\bchallenges\s+remain\b|\bremains\s+to\s+be\s+seen\b|"
        r"\b(?:only\s+)?time\s+will\s+tell\b"
    )


class Wikipedia009(TextPatternRule, identifier="WIK009"):
    pattern = (
        r",\s+(?:highlighting|underscoring|emphasizing|showcasing|reflecting|"
        r"demonstrating|illustrating|signaling|solidifying|cementing|reinforcing|"
        r"underlining)\s+(?:its|his|her|their|our|the|a|an|how|that|what|both)\b"
        r"[^.!?\n]*"
    )


class Wikipedia010(TextPatternRule, identifier="WIK010"):
    pattern = (
        r"\bnestled\s+(?:in|on|among|between|along|at)\b|\bin\s+the\s+heart\s+of\b|"
        r"\brich\s+(?:cultural\s+|historical\s+)?(?:heritage|history|tapestry)\b|"
        r"\bhidden\s+gem\b|\bmust-(?:visit|see|try)\b|\bbreathtaking\b|"
        r"\bboasts?\s+(?:a|an|the)\b|\bstunning\s+(?:views?|scenery|architecture|"
        r"backdrop)\b"
    )


class Wikipedia011(TextPatternRule, identifier="WIK011"):
    pattern = (
        r"\bas\s+an\s+ai(?:\s+language)?\s+model\b|\bas\s+of\s+my\s+last\s+"
        r"(?:update|training)\b|\bknowledge\s+cutoff\b|\bI\s+(?:cannot|can['\u2019]t|"
        r"do\s+not|don['\u2019]t)\s+(?:browse\s+the\s+internet|access\s+real-?time)\b|"
        r"contentReference|oaicite|turn0(?:search|news|image)\d*|attributableIndex|"
        r"utm_source="
    )
