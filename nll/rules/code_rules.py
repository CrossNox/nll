"""The rules the library checks itself."""

import re
from collections.abc import Callable
from typing import ClassVar

from nll.document import Document
from nll.rules.rules import CodeRule
from nll.violations import Violation, Violations

SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
HAS_LETTER = re.compile(r"[A-Za-z]")
ASCII_IGNORE_CASE = re.ASCII | re.IGNORECASE

MatchSpan = tuple[int, int]
ClicheMatchFinder = Callable[[str], list[MatchSpan]]


class ForbiddenCharacter(CodeRule, identifier=None):
    """Report every occurrence of one character."""

    character: ClassVar[str]

    def __call__(self, document: Document) -> Violations:
        violations = []

        for line_number, line in enumerate(document.lines, start=1):
            index = line.find(self.character)

            while index != -1:
                violations.append(
                    Violation(
                        rule=self,
                        path=document.path,
                        line=line_number,
                        offset=index + 1,
                        quote=line,
                    )
                )
                index = line.find(self.character, index + 1)

        return Violations(violations)


class EmDash(ForbiddenCharacter, identifier="CHR001"):
    character = "—"


class EnDash(ForbiddenCharacter, identifier="CHR002"):
    character = "–"  # noqa: RUF001


class MiddleDot(ForbiddenCharacter, identifier="CHR003"):
    character = "·"


class Semicolon(ForbiddenCharacter, identifier="CHR004"):
    character = ";"


class OtherNonAscii(CodeRule, identifier="CHR000"):
    """Report every non-ASCII character no other character rule covers."""

    def __call__(self, document: Document) -> Violations:
        covered = {
            rule.character
            for rule in CodeRule.registry.values()
            if issubclass(rule, ForbiddenCharacter)
        }
        violations = []

        for line_number, line in enumerate(document.lines, start=1):
            if line.isascii():
                continue

            for offset, found in enumerate(line, start=1):
                if found.isascii() or found in covered:
                    continue

                violations.append(
                    Violation(
                        rule=self,
                        path=document.path,
                        line=line_number,
                        offset=offset,
                        quote=line,
                    )
                )

        return Violations(violations)


class TooManySentences(CodeRule, identifier="LEN001"):
    """Report the text when it runs past the sentence limit."""

    def __call__(self, document: Document) -> Violations:
        sentences = [
            sentence
            for sentence in SENTENCE_END.split(document.prose)
            if HAS_LETTER.search(sentence)
        ]

        if len(sentences) <= self.arguments["max_sentences"]:
            return Violations([])

        return Violations([Violation(rule=self, path=document.path)])


def find_matches_for_regex(
    pattern: str, flags: int = ASCII_IGNORE_CASE
) -> ClicheMatchFinder:
    """Build a finder that returns every span matching a regular expression."""
    compiled = re.compile(pattern, flags)

    def find_matches(text: str) -> list[MatchSpan]:
        return [(match.start(), match.end()) for match in compiled.finditer(text)]

    return find_matches


CHAIN_BODY = r"[^,.;:!?\n\u2013\u2014\u2026]*"
CHAIN_SEPARATOR = (
    r"(?:\s*,\s*(?:and\s+|or\s+)?|\s+(?:and|or)\s+|"
    r"\s*[;&\u2013\u2014]\s*(?:and\s+|or\s+)?|\s+-{1,2}\s+)"
)


def find_matches_for_chain(head: str) -> ClicheMatchFinder:
    """Build a finder for a repeated phrase joined into a list."""
    pattern = re.compile(
        rf"\b{head}{CHAIN_BODY}(?:{CHAIN_SEPARATOR}{head}{CHAIN_BODY})+",
        ASCII_IGNORE_CASE,
    )

    def find_matches(text: str) -> list[MatchSpan]:
        spans = []

        for match in pattern.finditer(text):
            end = match.end()

            while end > match.start() and text[end - 1].isspace():
                end -= 1

            spans.append((match.start(), end))

        return spans

    return find_matches


def find_matches_for_echoing_sentences(text: str) -> list[MatchSpan]:
    """Find adjacent sentence runs that repeat a four-word skeleton."""
    sentence_pattern = re.compile(r"[^.!?\n]+[.!?]?")
    word_pattern = re.compile(r"[a-z0-9'\u2019\u2013]+", re.IGNORECASE | re.ASCII)
    sentences: list[tuple[int, int, str]] = []

    for match in sentence_pattern.finditer(text):
        if len(re.findall(r"\S+", match.group(0))) >= 4:
            sentences.append((match.start(), match.end(), match.group(0)))

    spans = []
    index = 0

    while index < len(sentences):
        last_index = index
        shared_gram: str | None = None

        while last_index + 1 < len(sentences):
            current = sentences[last_index]
            following = sentences[last_index + 1]

            if following[0] - current[1] > 3:
                break

            current_grams = {
                " ".join(words[position : position + 4])
                for words in [word_pattern.findall(current[2].lower())]
                for position in range(len(words) - 3)
            }
            following_grams = {
                " ".join(words[position : position + 4])
                for words in [word_pattern.findall(following[2].lower())]
                for position in range(len(words) - 3)
            }
            common_grams = current_grams & following_grams

            if len(common_grams) == 0:
                break

            shared_gram = max(common_grams, key=len)
            last_index += 1

        if last_index - index + 1 >= 2 and shared_gram is not None:
            start = sentences[index][0]
            end = sentences[last_index][1]

            while end > start and text[end - 1].isspace():
                end -= 1

            spans.append((start, end))
            index = last_index + 1
        else:
            index += 1

    return spans


def find_matches_for_question_chains(text: str) -> list[MatchSpan]:
    """Find two or more adjacent question sentences."""
    pattern = re.compile(r"[^.!?\n]+\?(?:\s+[^.!?\n]+\?)+")
    spans = []

    for match in pattern.finditer(text):
        start = match.start()

        while start < match.end() and text[start].isspace():
            start += 1

        spans.append((start, match.end()))

    return spans


ANAPHORA_SKIP = re.compile(
    r"^(?:i|it|the|a|an|this|that|we|you|they|he|she|there|but|and|so|in|"
    r"as|if|my|his|her|their|its|these|those|for|at|on|of|to|is|was)$",
    ASCII_IGNORE_CASE,
)


def find_matches_for_repeated_sentence_openers(text: str) -> list[MatchSpan]:
    """Find three adjacent sentences that begin with the same useful word."""
    sentence_pattern = re.compile(r"[^.!?\n]+[.!?]")
    word_pattern = re.compile(r"[A-Za-z'\u2019\u2013]+")
    sentences: list[tuple[int, int, str]] = []

    for match in sentence_pattern.finditer(text):
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

        if last_index - index + 1 >= 3 and not ANAPHORA_SKIP.fullmatch(
            sentences[index][2]
        ):
            spans.append((sentences[index][0], sentences[last_index][1]))
            index = last_index + 1
        else:
            index += 1

    return spans


class ClicheRule(CodeRule, identifier=None):
    """Report every match from one imported LLM-cliche pattern."""

    finder: ClassVar[ClicheMatchFinder]

    def __call__(self, document: Document) -> Violations:
        violations = []

        for start, end in self.finder(document.prose):
            line = document.prose.count("\n", 0, start) + 1
            line_start = document.prose.rfind("\n", 0, start) + 1

            violations.append(
                Violation(
                    rule=self,
                    path=document.path,
                    line=line,
                    offset=start - line_start + 1,
                    quote=document.prose[start:end],
                )
            )

        return Violations(violations)


CLICHE_MATCH_FINDERS: dict[str, ClicheMatchFinder] = {
    "001": find_matches_for_chain(r"no[-\s]"),
    "002": find_matches_for_regex(
        r"\b(?:that|this)(?:['\u2019]s|\s+(?:is|was))\s+the\s+whole\b(?:\s+\w+)?"
    ),
    "003": find_matches_for_chain(r"(?:did\s+not|didn['\u2019]t)\s"),
    "004": find_matches_for_regex(
        r"\b(?:do\s+not|don['\u2019]t)\s+(?:just\s+|simply\s+|merely\s+)?(\w+)"
        r"(?:\s+(?:of|about|at|on|for|with|to))?\s+it\b[^.!?\n]*?[.!?;,"
        r":\u2013\u2014]['\"\u201d\u2019]*\s*(?:just\s+|simply\s+|merely\s+)?\1"
        r"(?:\s+(?:of|about|at|on|for|with|to))?\s+it\b"
    ),
    "005": find_matches_for_regex(
        r"\bsit(?:s|ting)?\s+with\s+(?:that|this|it|(?:the|your)\s+"
        r"(?:discomfort|feelings?|tension|weight|uncertainty|ambiguity|grief|"
        r"silence|unease))\b(?:\s+for\s+a\s+\w+)?"
    ),
    "006": find_matches_for_regex(
        r"\byou\s+already\s+knows?\s+(?:the\s+answer|what|how|why|this|that|"
        r"it|who|where)\b|\byou\s+already\s+knows?\b(?![ \t]+\w)"
    ),
    "007": find_matches_for_regex(
        r"(?:\b(?:is|was|are|were)|['\u2019]s)\s+the\s+entire\b(?:\s+\w+)?"
    ),
    "008": find_matches_for_regex(
        r"\bthe\s+entire\s+[\w'\u2019-]+(?:\s+[\w'\u2019-]+){0,4}?\s+"
        r"(?:is|was|are|were)\b"
    ),
    "009": find_matches_for_regex(
        r"\bis\s+(?:(?:the|a)\s+real\b(?![\s-]+(?:estate|time|life|world|quick)\b)"
        r"[^.!?\n]*?\b(?:and|not)\s+it\b|real\b(?![\s-]+(?:estate|time|life|"
        r"world|quick)\b)[^.!?\n]*?\b(?:and|not)\b)"
    ),
    "010": find_matches_for_regex(
        r"\bthe\s+punchline(?:\s+(?:is|was|being)\b|\s*[:?])"
    ),
    "011": find_matches_for_regex(
        r"(?:\b(?:is|are|was|were|feels?|felt|seems?|seemed)|['\u2019]s)\s+"
        r"(?:\w+\s+){0,2}?worth\s+naming\b(?!\s+names\b)|\bworth\s+naming\s*:"
    ),
    "012": find_matches_for_regex(
        r"\b(?:that|this|it|which)(?:['\u2019]s|\s+(?:is|was))\s+not\s+nothing\b"
    ),
    "013": find_matches_for_regex(
        r"(?:\b(?:is|was|are|were)|['\u2019]s)\s+the\s+whole\b(?:\s+\w+)?|"
        r"\bhere(?:['\u2019]s|\s+is)\s+the\s+whole\b(?:\s+\w+)?"
    ),
    "014": find_matches_for_echoing_sentences,
    "015": find_matches_for_regex(
        r"\bI\s+(?:will\s+not|won['\u2019]t)\s+pretend\b|\b(?:I['\u2019]ll|"
        r"let['\u2019]s|to)\s+be\s+(?:honest|clear|blunt|real)\b|"
        r"(?:^|[.!?\u2013\u2014]\s+|\n)(?:Honestly|Look|Truthfully|Frankly)\s*,"
    ),
    "016": find_matches_for_regex(
        r"\b(?:that|this|it)(?:['\u2019]s|\s+(?:is|was))\s+the\s+part\b|"
        r"\bthe\s+part\s+that\s+(?:makes|made|gets|got|keeps|kept)\s+"
        r"(?:me|you|us|it)\b|\bmy\s+favou?rite\s+part\s+of\b"
    ),
    "017": find_matches_for_regex(
        r"\bthe\s+only\s+[\w'\u2019\u2013-]+(?:\s+[\w'\u2019\u2013-]+){0,2}?\s+"
        r"(?:I|you|we|it|he|she|they)\s+(?:trust|need|needs|care|want|wants|use|"
        r"uses|believe)\b|\bthe\s+only\s+[\w'\u2019\u2013-]+\s+that\s+"
        r"(?:matters|counts|works|survives)\b"
    ),
    "018": find_matches_for_regex(
        r"\b(?:you\s+)?(?:do\s+not|don['\u2019]t)\s+(?:have\s+to\s+)?take\s+"
        r"my\s+word\s+for\s+(?:it|any\s+of\s+(?:it|this|that))\b"
    ),
    "019": find_matches_for_regex(
        r"(?:^|[.!?\u2013\u2014]\s+|\n)Turns\s+out\b|\bit\s+turns\s+out\s+that\b"
    ),
    "020": find_matches_for_regex(
        r"\b(?:hold|fit|fits|holds|held)\s+(?:it\s+)?in\s+your\s+head\b|"
        r"\bbatteries[-\s]included\b|\bit\s+just\s+works\b|"
        r"\bzero[-\s]config(?:uration)?\b|\bsane\s+defaults\b"
    ),
    "021": find_matches_for_question_chains,
    "022": find_matches_for_repeated_sentence_openers,
    "023": find_matches_for_regex(
        r":\s+[^.!?;:\n]{2,40},\s+[^.!?;:\n]{2,40},\s+(?:and\s+|or\s+)?"
        r"[^.!?;:\n]{2,40}(?=[.!?\n])",
        re.ASCII,
    ),
    "024": find_matches_for_regex(
        r"\bhere(?:['\u2019]s|\s+is)\s+(?:the|a|my|one)\s+(?:twist|thing|catch|"
        r"kicker|rub|problem|first|second|third|next|recent|real|best|worst|"
        r"surprising|interesting|key|important)\b[\w\s-]{0,20}[:.]"
    ),
    "025": find_matches_for_regex(
        r"\b[\w\s]{3,30}\s+(?:is|are)\s+dead\b|\blong\s+live\s+\w+"
    ),
    "026": find_matches_for_regex(
        r"\b(?:that|this)(?:['\u2019]s|\s+(?:is|was))\s+why\b[^.!?\n]{0,80}?\b"
        r"(?:matter(?:s|ed)?|count(?:s|ed)?)\b"
    ),
    "027": find_matches_for_regex(
        r"[;:,]\s+[^.;:!?\n]{2,50}\s(?:did|does|do|was|were|is|are|has|have|had|"
        r"can|could|would|will)(?:n['\u2019]t)?\s*[.;]|\b(?:Maybe|Perhaps)\s+\w+"
        r"[^.!?\n]{0,40}\s(?:would|could|might|should|did|had|was|is)(?:n['\u2019]t)?"
        r"\s+(?:have\s*)?\."
    ),
}


WIKIPEDIA_MATCH_FINDERS: dict[str, ClicheMatchFinder] = {
    "001": find_matches_for_regex(
        r"\b(?:delv(?:e|es|ed|ing)|tapestr(?:y|ies)|meticulous(?:ly)?|pivotal|"
        r"intricate(?:ly)?|intricacies|interplay|underscor(?:e|es|ed|ing)|"
        r"garner(?:s|ed|ing)?|bolster(?:s|ed|ing)?|vibrant|bustling|multifaceted|"
        r"seamless(?:ly)?|commendable|ever-evolving)\b"
    ),
    "002": find_matches_for_regex(
        r"\bnot\s+(?:just|only|merely|simply)\s+[^.!?\n;]*?\bbut(?:\s+also)?\b|"
        r"\b(?:it|this|that)(?:['\u2019]s|\s+(?:is|was))\s+not\s+"
        r"[^.!?\n,;\u2014\u2013]{1,60}[,;\u2014\u2013]\s*(?:it|this|that)"
        r"(?:['\u2019]s|\s+(?:is|was))\b"
    ),
    "003": find_matches_for_regex(
        r"\bit(?:['\u2019]s|\s+(?:is|was))\s+(?:also\s+)?"
        r"(?:important|worth|crucial|essential|vital)\s+(?:to\s+(?:note|remember|"
        r"understand|recognize|mention|pause|consider|ask)|noting|mentioning|"
        r"remembering|pausing|considering|asking)\b(?:\s+that\b)?|"
        r"\bit\s+should\s+be\s+noted\b"
    ),
    "004": find_matches_for_regex(
        r"\b(?:stand|stands|stood|serve|serves|served|standing|serving)\s+as\s+"
        r"(?:a|an)\s+(?:\w+\s+)?(?:testament|reminder)\b|"
        r"\b(?:is|was|are|were|remain|remains)\s+a\s+(?:\w+\s+)?testament\s+to\b"
    ),
    "005": find_matches_for_regex(
        r"\bplay(?:s|ed|ing)?\s+(?:a|an)\s+(?:\w+\s+)?"
        r"(?:crucial|pivotal|vital|key|significant|central|critical|important)\s+role\b"
    ),
    "006": find_matches_for_regex(
        r"\b(?:ever-)?(?:evolving|changing|shifting)\s+landscape\b|"
        r"\bin\s+today['\u2019]s\s+(?:fast-paced|ever-changing|ever-evolving|"
        r"digital|modern|competitive)\s+\w+"
    ),
    "007": find_matches_for_regex(
        r"\b(?:many|some|several|most|numerous)?\s*(?:experts|critics|observers|"
        r"scholars|analysts|commentators)\s+(?:have\s+|often\s+|widely\s+)?"
        r"(?:argu(?:e|es|ed)|not(?:e|es|ed)|suggest(?:s|ed)?|believ(?:e|es|ed)|"
        r"agree[ds]?|contend(?:s|ed)?|observ(?:e|es|ed)|caution(?:s|ed)?|"
        r"claim(?:s|ed)?|cit(?:e|es|ed)|point(?:s|ed)?\s+out)\b|"
        r"\bindustry\s+reports?\s+(?:suggest|indicate|show)\w*\b"
    ),
    "008": find_matches_for_regex(
        r"\bdespite\s+(?:these|those|such|its|their|the|numerous|significant|"
        r"ongoing)\s+(?:\w+\s+)?challenges\b|\bfac(?:e|es|ed|ing)\s+(?:several|"
        r"numerous|many|significant|various|a\s+number\s+of)\s+challenges\b|"
        r"\bchallenges\s+remain\b|\bremains\s+to\s+be\s+seen\b|"
        r"\b(?:only\s+)?time\s+will\s+tell\b"
    ),
    "009": find_matches_for_regex(
        r",\s+(?:highlighting|underscoring|emphasizing|showcasing|reflecting|"
        r"demonstrating|illustrating|signaling|solidifying|cementing|reinforcing|"
        r"underlining)\s+(?:its|his|her|their|our|the|a|an|how|that|what|both)\b"
        r"[^.!?\n]*"
    ),
    "010": find_matches_for_regex(
        r"\bnestled\s+(?:in|on|among|between|along|at)\b|\bin\s+the\s+heart\s+of\b|"
        r"\brich\s+(?:cultural\s+|historical\s+)?(?:heritage|history|tapestry)\b|"
        r"\bhidden\s+gem\b|\bmust-(?:visit|see|try)\b|\bbreathtaking\b|"
        r"\bboasts?\s+(?:a|an|the)\b|\bstunning\s+(?:views?|scenery|architecture|"
        r"backdrop)\b"
    ),
    "011": find_matches_for_regex(
        r"\bas\s+an\s+ai(?:\s+language)?\s+model\b|\bas\s+of\s+my\s+last\s+"
        r"(?:update|training)\b|\bknowledge\s+cutoff\b|\bI\s+(?:cannot|can['\u2019]t|"
        r"do\s+not|don['\u2019]t)\s+(?:browse\s+the\s+internet|access\s+real-?time)\b|"
        r"contentReference|oaicite|turn0(?:search|news|image)\d*|attributableIndex|"
        r"utm_source="
    ),
}


def register_cliche_rules() -> None:
    """Register each imported cliche finder as a built-in code rule."""
    for code, finder in CLICHE_MATCH_FINDERS.items():
        type(
            f"Cliche{code}",
            (ClicheRule,),
            {"finder": staticmethod(finder)},
            identifier=f"CLH{code}",
        )


def register_wikipedia_rules() -> None:
    """Register each Wikipedia-derived finder as a built-in code rule."""
    for code, finder in WIKIPEDIA_MATCH_FINDERS.items():
        type(
            f"Wikipedia{code}",
            (ClicheRule,),
            {"finder": staticmethod(finder)},
            identifier=f"WIK{code}",
        )


register_cliche_rules()
register_wikipedia_rules()
