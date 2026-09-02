"""The rules the library checks itself."""

import re
from typing import ClassVar

from nll.document import Document
from nll.rules.rules import CodeRule
from nll.violations import Violation, Violations

SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
HAS_LETTER = re.compile(r"[A-Za-z]")


class ForbiddenCharacter(CodeRule, identifier=None):
    """Report every occurrence of one character."""

    character: ClassVar[str]

    def __call__(self, document: Document) -> Violations:
        violations = []

        for line_number, line in enumerate(document.lines, start=1):
            index = line.find(self.character)

            while index != -1:
                violations.append(
                    Violation(rule=self, line=line_number, offset=index + 1)
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

                violations.append(Violation(rule=self, line=line_number, offset=offset))

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

        return Violations([Violation(rule=self)])
