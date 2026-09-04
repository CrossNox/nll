"""Define writing-pattern rules adapted from LLM Cliche Highlighter."""

import re

from linnl.document import Document
from linnl.rules.pattern_rules import (
    ASCII_IGNORE_CASE,
    TextPatternRule,
)
from linnl.rules.rules import CodeRule
from linnl.violations import Violation, Violations

TextMatch = tuple[int, int]

CHAIN_BODY = r"[^,.;:!?\n\u2013\u2014\u2026]*"
CHAIN_SEPARATOR = (
    r"(?:\s*,\s*(?:and\s+|or\s+)?|\s+(?:and|or)\s+|"
    r"\s*[;&\u2013\u2014]\s*(?:and\s+|or\s+)?|\s+-{1,2}\s+)"
)


def build_violations_for_matches(
    rule: CodeRule, document: Document, matches: list[TextMatch]
) -> Violations:
    """Build violations for source spans."""
    violations = []

    for start, end in matches:
        line = document.prose.count("\n", 0, start) + 1
        line_start = document.prose.rfind("\n", 0, start) + 1

        violations.append(
            Violation(
                rule=rule,
                path=document.path,
                line=line,
                offset=start - line_start + 1,
                quote=document.prose[start:end],
            )
        )

    return Violations(violations)


class Cliche001(CodeRule, identifier="CLH001"):
    """Flag repeated no clauses.

    Example: "No setup, no surprises."
    """

    pattern = re.compile(
        rf"\bno[-\s]{CHAIN_BODY}(?:{CHAIN_SEPARATOR}no[-\s]{CHAIN_BODY})+",
        ASCII_IGNORE_CASE,
    )

    def __call__(self, document: Document) -> Violations:
        matches = []

        for match in self.pattern.finditer(document.prose):
            end = match.end()

            while end > match.start() and document.prose[end - 1].isspace():
                end -= 1

            matches.append((match.start(), end))

        return build_violations_for_matches(self, document, matches)


class Cliche002(TextPatternRule, identifier="CLH002"):
    """Flag that's the whole point phrasing.

    Example: "That's the whole point."
    """

    pattern = r"\b(?:that|this)(?:['\u2019]s|\s+(?:is|was))\s+the\s+whole\b(?:\s+\w+)?"


class Cliche003(CodeRule, identifier="CLH003"):
    """Flag repeated did not clauses.

    Example: "It did not help, did not matter."
    """

    pattern = re.compile(
        rf"\b(?:did\s+not|didn['\u2019]t)\s{CHAIN_BODY}(?:{CHAIN_SEPARATOR}"
        rf"(?:did\s+not|didn['\u2019]t)\s{CHAIN_BODY})+",
        ASCII_IGNORE_CASE,
    )

    def __call__(self, document: Document) -> Violations:
        matches = []

        for match in self.pattern.finditer(document.prose):
            end = match.end()

            while end > match.start() and document.prose[end - 1].isspace():
                end -= 1

            matches.append((match.start(), end))

        return build_violations_for_matches(self, document, matches)


class Cliche004(TextPatternRule, identifier="CLH004"):
    """Flag don't verb it, verb it phrasing.

    Example: "Don't explain it, show it."
    """

    pattern = (
        r"\b(?:do\s+not|don['\u2019]t)\s+(?:just\s+|simply\s+|merely\s+)?(\w+)"
        r"(?:\s+(?:of|about|at|on|for|with|to))?\s+it\b[^.!?\n]*?[.!?;,"
        r":\u2013\u2014]['\"\u201d\u2019]*\s*(?:just\s+|simply\s+|merely\s+)?\1"
        r"(?:\s+(?:of|about|at|on|for|with|to))?\s+it\b"
    )


class Cliche005(TextPatternRule, identifier="CLH005"):
    """Flag sit with that phrasing.

    Example: "Sit with that discomfort."
    """

    pattern = (
        r"\bsit(?:s|ting)?\s+with\s+(?:that|this|it|(?:the|your)\s+"
        r"(?:discomfort|feelings?|tension|weight|uncertainty|ambiguity|grief|"
        r"silence|unease))\b(?:\s+for\s+a\s+\w+)?"
    )


class Cliche006(TextPatternRule, identifier="CLH006"):
    """Flag you already know phrasing.

    Example: "You already know the answer."
    """

    pattern = (
        r"\byou\s+already\s+knows?\s+(?:the\s+answer|what|how|why|this|that|"
        r"it|who|where)\b|\byou\s+already\s+knows?\b(?![ \t]+\w)"
    )


class Cliche007(TextPatternRule, identifier="CLH007"):
    """Flag is the entire point phrasing.

    Example: "That is the entire point."
    """

    pattern = r"(?:\b(?:is|was|are|were)|['\u2019]s)\s+the\s+entire\b(?:\s+\w+)?"


class Cliche008(TextPatternRule, identifier="CLH008"):
    """Flag the entire point is phrasing.

    Example: "The entire point is clarity."
    """

    pattern = (
        r"\bthe\s+entire\s+[\w'\u2019-]+(?:\s+[\w'\u2019-]+){0,4}?\s+"
        r"(?:is|was|are|were)\b"
    )


class Cliche009(TextPatternRule, identifier="CLH009"):
    """Flag is real and or not phrasing.

    Example: "The risk is real, and it matters."
    """

    pattern = (
        r"\bis\s+(?:(?:the|a)\s+real\b(?![\s-]+(?:estate|time|life|world|quick)\b)"
        r"[^.!?\n]*?\b(?:and|not)\s+it\b|real\b(?![\s-]+(?:estate|time|life|"
        r"world|quick)\b)[^.!?\n]*?\b(?:and|not)\b)"
    )


class Cliche010(TextPatternRule, identifier="CLH010"):
    """Flag the punchline is phrasing.

    Example: "The punchline is simple."
    """

    pattern = r"\bthe\s+punchline(?:\s+(?:is|was|being)\b|\s*[:?])"


class Cliche011(TextPatternRule, identifier="CLH011"):
    """Flag worth naming phrasing.

    Example: "That is worth naming."
    """

    pattern = (
        r"(?:\b(?:is|are|was|were|feels?|felt|seems?|seemed)|['\u2019]s)\s+"
        r"(?:\w+\s+){0,2}?worth\s+naming\b(?!\s+names\b)|\bworth\s+naming\s*:"
    )


class Cliche012(TextPatternRule, identifier="CLH012"):
    """Flag that's not nothing phrasing.

    Example: "That's not nothing."
    """

    pattern = r"\b(?:that|this|it|which)(?:['\u2019]s|\s+(?:is|was))\s+not\s+nothing\b"


class Cliche013(TextPatternRule, identifier="CLH013"):
    """Flag is the whole point phrasing.

    Example: "That is the whole point."
    """

    pattern = (
        r"(?:\b(?:is|was|are|were)|['\u2019]s)\s+the\s+whole\b(?:\s+\w+)?|"
        r"\bhere(?:['\u2019]s|\s+is)\s+the\s+whole\b(?:\s+\w+)?"
    )


class Cliche014(CodeRule, identifier="CLH014"):
    """Flag adjacent sentences that repeat four words.

    Example: "The tool is fast and simple. The tool is fast and portable."
    """

    def __call__(self, document: Document) -> Violations:
        sentence_pattern = re.compile(r"[^.!?\n]+[.!?]?")
        word_pattern = re.compile(r"[a-z0-9'\u2019\u2013]+", re.IGNORECASE | re.ASCII)
        sentences: list[tuple[int, int, str]] = []

        for match in sentence_pattern.finditer(document.prose):
            if len(re.findall(r"\S+", match.group(0))) >= 4:
                sentences.append((match.start(), match.end(), match.group(0)))

        spans = []
        index = 0

        while index < len(sentences):
            last_index = index

            while last_index + 1 < len(sentences):
                current = sentences[last_index]
                following = sentences[last_index + 1]

                if following[0] - current[1] > 3:
                    break

                current_words = word_pattern.findall(current[2].lower())
                current_grams = {
                    " ".join(current_words[position : position + 4])
                    for position in range(len(current_words) - 3)
                }
                following_words = word_pattern.findall(following[2].lower())
                following_grams = {
                    " ".join(following_words[position : position + 4])
                    for position in range(len(following_words) - 3)
                }

                if len(current_grams & following_grams) == 0:
                    break

                last_index += 1

            if last_index - index + 1 >= 2:
                start = sentences[index][0]
                end = sentences[last_index][1]

                while end > start and document.prose[end - 1].isspace():
                    end -= 1

                spans.append((start, end))
                index = last_index + 1
            else:
                index += 1

        return build_violations_for_matches(self, document, spans)


class Cliche015(TextPatternRule, identifier="CLH015"):
    """Flag performative honesty.

    Example: "To be honest, this is difficult."
    """

    pattern = (
        r"\bI\s+(?:will\s+not|won['\u2019]t)\s+pretend\b|\b(?:I['\u2019]ll|"
        r"let['\u2019]s|to)\s+be\s+(?:honest|clear|blunt|real)\b|"
        r"(?:^|[.!?\u2013\u2014]\s+|\n)(?:Honestly|Look|Truthfully|Frankly)\s*,"
    )


class Cliche016(TextPatternRule, identifier="CLH016"):
    """Flag that's the part phrasing.

    Example: "That's the part that matters."
    """

    pattern = (
        r"\b(?:that|this|it)(?:['\u2019]s|\s+(?:is|was))\s+the\s+part\b|"
        r"\bthe\s+part\s+that\s+(?:makes|made|gets|got|keeps|kept)\s+"
        r"(?:me|you|us|it)\b|\bmy\s+favou?rite\s+part\s+of\b"
    )


class Cliche017(TextPatternRule, identifier="CLH017"):
    """Flag the only X I trust phrasing.

    Example: "The only metric I trust is retention."
    """

    pattern = (
        r"\bthe\s+only\s+[\w'\u2019\u2013-]+(?:\s+[\w'\u2019\u2013-]+){0,2}?\s+"
        r"(?:I|you|we|it|he|she|they)\s+(?:trust|need|needs|care|want|wants|use|"
        r"uses|believe)\b|\bthe\s+only\s+[\w'\u2019\u2013-]+\s+that\s+"
        r"(?:matters|counts|works|survives)\b"
    )


class Cliche018(TextPatternRule, identifier="CLH018"):
    """Flag don't take my word for it phrasing.

    Example: "Don't take my word for it."
    """

    pattern = (
        r"\b(?:you\s+)?(?:do\s+not|don['\u2019]t)\s+(?:have\s+to\s+)?take\s+"
        r"my\s+word\s+for\s+(?:it|any\s+of\s+(?:it|this|that))\b"
    )


class Cliche019(TextPatternRule, identifier="CLH019"):
    """Flag turns out phrasing.

    Example: "Turns out, the cache was stale."
    """

    pattern = r"(?:^|[.!?\u2013\u2014]\s+|\n)Turns\s+out\b|\bit\s+turns\s+out\s+that\b"


class Cliche020(TextPatternRule, identifier="CLH020"):
    """Flag fits in your head phrasing.

    Example: "The model fits in your head."
    """

    pattern = (
        r"\b(?:hold|fit|fits|holds|held)\s+(?:it\s+)?in\s+your\s+head\b|"
        r"\bbatteries[-\s]included\b|\bit\s+just\s+works\b|"
        r"\bzero[-\s]config(?:uration)?\b|\bsane\s+defaults\b"
    )


class Cliche021(CodeRule, identifier="CLH021"):
    """Flag adjacent rhetorical questions.

    Example: "What changed? Why now?"
    """

    def __call__(self, document: Document) -> Violations:
        pattern = re.compile(r"[^.!?\n]+\?(?:\s+[^.!?\n]+\?)+")
        spans = []

        for match in pattern.finditer(document.prose):
            start = match.start()

            while start < match.end() and document.prose[start].isspace():
                start += 1

            spans.append((start, match.end()))

        return build_violations_for_matches(self, document, spans)


class Cliche022(CodeRule, identifier="CLH022"):
    """Flag three adjacent sentences with the same opener.

    Example: "Teams decide. Teams build. Teams ship."
    """

    ignored_openers = re.compile(
        r"^(?:i|it|the|a|an|this|that|we|you|they|he|she|there|but|and|so|in|"
        r"as|if|my|his|her|their|its|these|those|for|at|on|of|to|is|was)$",
        ASCII_IGNORE_CASE,
    )

    def __call__(self, document: Document) -> Violations:
        sentence_pattern = re.compile(r"[^.!?\n]+[.!?]")
        word_pattern = re.compile(r"[A-Za-z'\u2019\u2013]+")
        sentences: list[tuple[int, int, str]] = []

        for match in sentence_pattern.finditer(document.prose):
            word = word_pattern.search(match.group(0))

            if word is not None:
                sentences.append(
                    (match.start() + word.start(), match.end(), word.group(0).lower())
                )

        spans = []
        index = 0

        while index < len(sentences):
            last_index = index

            while (
                last_index + 1 < len(sentences)
                and sentences[last_index + 1][2] == sentences[index][2]
                and sentences[last_index + 1][0] - sentences[last_index][1] < 4
            ):
                last_index += 1

            if last_index - index + 1 >= 3 and not self.ignored_openers.fullmatch(
                sentences[index][2]
            ):
                spans.append((sentences[index][0], sentences[last_index][1]))
                index = last_index + 1
            else:
                index += 1

        return build_violations_for_matches(
            self,
            document,
            spans,
        )


class Cliche023(TextPatternRule, identifier="CLH023"):
    """Flag a colon followed by a three-part list.

    Example: "It needs three things: speed, clarity, and care."
    """

    pattern = (
        r":\s+[^.!?;:\n]{2,40},\s+[^.!?;:\n]{2,40},\s+(?:and\s+|or\s+)?"
        r"[^.!?;:\n]{2,40}(?=[.!?\n])"
    )
    flags = re.ASCII


class Cliche024(TextPatternRule, identifier="CLH024"):
    """Flag here's the twist phrasing.

    Example: "Here's the twist: it already works."
    """

    pattern = (
        r"\bhere(?:['\u2019]s|\s+is)\s+(?:the|a|my|one)\s+(?:twist|thing|catch|"
        r"kicker|rub|problem|first|second|third|next|recent|real|best|worst|"
        r"surprising|interesting|key|important)\b[\w\s-]{0,20}[:.]"
    )


class Cliche025(TextPatternRule, identifier="CLH025"):
    """Flag X is dead phrasing.

    Example: "Email is dead."
    """

    pattern = r"\b[\w\s]{3,30}\s+(?:is|are)\s+dead\b|\blong\s+live\s+\w+"


class Cliche026(TextPatternRule, identifier="CLH026"):
    """Flag that's why X mattered phrasing.

    Example: "That's why the detail mattered."
    """

    pattern = (
        r"\b(?:that|this)(?:['\u2019]s|\s+(?:is|was))\s+why\b[^.!?\n]{0,80}?\b"
        r"(?:matter(?:s|ed)?|count(?:s|ed)?)\b"
    )


class Cliche027(TextPatternRule, identifier="CLH027"):
    """Flag a stranded auxiliary contrast.

    Example: "The plan changed, but the goal did not."
    """

    pattern = (
        r"[;:,]\s+[^.;:!?\n]{2,50}\s(?:did|does|do|was|were|is|are|has|have|had|"
        r"can|could|would|will)(?:n['\u2019]t)?\s*[.;]|\b(?:Maybe|Perhaps)\s+\w+"
        r"[^.!?\n]{0,40}\s(?:would|could|might|should|did|had|was|is)(?:n['\u2019]t)?"
        r"\s+(?:have\s*)?\."
    )
