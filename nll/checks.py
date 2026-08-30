"""Check rules in Python, and bind each check to its rule code."""

import re
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, PositiveInt

from nll.document import Document, Position
from nll.rules import CheckFunction, PythonCheck, Rule
from nll.violations import Violation

SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def report_character(
    rule: Rule, document: Document, offset: int, message: str, suggestion: str
) -> Violation:
    """Build the violation for a character found at `offset` of the prose."""
    position = document.locate_offset(offset)

    return Violation(
        code=rule.code,
        path=document.path,
        position=position,
        message=message,
        quote=document.read_line(position.line).strip(),
        suggestion=suggestion,
    )


def forbid_character(character: str, suggestion: str) -> CheckFunction:
    """Build the check that reports every occurrence of one character."""

    def check(rule: Rule, document: Document, prose: str) -> list[Violation]:
        return [
            report_character(rule, document, offset, rule.description, suggestion)
            for offset, found in enumerate(prose)
            if found == character
        ]

    return check


def forbid_other_non_ascii(covered: str) -> CheckFunction:
    """Build the check that reports non-ASCII characters no other rule covers."""

    def check(rule: Rule, document: Document, prose: str) -> list[Violation]:
        violations = []
        for offset, character in enumerate(prose):
            if ord(character) < 128 or character in covered:
                continue

            name = unicodedata.name(character, "unnamed")
            violations.append(
                report_character(
                    rule,
                    document,
                    offset,
                    f"Non-ASCII character {character!r} ({name})",
                    "Replace with an ASCII equivalent",
                )
            )

        return violations

    return check


class SentenceCountOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, strict=True)

    max_sentences: PositiveInt = Field(alias="max-sentences")


def count_sentences(text: str) -> int:
    """Count sentences as runs of text ending in ., ! or ?."""
    pieces = SENTENCE_END.split(text)

    return sum(1 for piece in pieces if re.search(r"[A-Za-z]", piece))


def limit_sentences(rule: Rule, document: Document, prose: str) -> list[Violation]:
    """Report the rule when the prose has more sentences than its option allows."""
    options = rule.options
    assert isinstance(options, SentenceCountOptions)

    count = count_sentences(prose)
    if count <= options.max_sentences:
        return []

    return [
        Violation(
            code=rule.code,
            path=document.path,
            position=Position(line=1, column=1),
            message=f"Text has {count} sentences, the limit is {options.max_sentences}",
            quote=None,
            suggestion="Cut to the sentences that answer the question",
        )
    ]


EM_DASH, EN_DASH, MIDDLE_DOT = "—", "–", "·"

PYTHON_CHECKS: dict[str, PythonCheck] = {
    "CHR000": PythonCheck(
        forbid_other_non_ascii(covered=EM_DASH + EN_DASH + MIDDLE_DOT)
    ),
    "CHR001": PythonCheck(
        forbid_character(EM_DASH, "Use a comma, a period or parentheses")
    ),
    "CHR002": PythonCheck(
        forbid_character(EN_DASH, "Write 'to' for ranges, or a hyphen")
    ),
    "CHR003": PythonCheck(forbid_character(MIDDLE_DOT, "Use a comma or a period")),
    "CHR004": PythonCheck(
        forbid_character(";", "Split into two sentences or join with a comma")
    ),
    "LEN001": PythonCheck(limit_sentences, options=SentenceCountOptions),
}
