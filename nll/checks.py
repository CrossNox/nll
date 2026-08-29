"""Run the checks Python can do without the model."""

import logging
import re
import unicodedata
from collections.abc import Callable

from nll.document import Document, Position
from nll.rules import Rule
from nll.violations import RuleViolation

logger = logging.getLogger(__name__)

SENTENCE_END = re.compile(r"(?<=[.!?])\s+")

FORBIDDEN_CHARACTERS: dict[str, tuple[str, str, str]] = {
    "CHR001": ("—", "Em dash (U+2014)", "Use a comma, a period or parentheses"),
    "CHR002": ("–", "En dash (U+2013)", "Write 'to' for ranges, or a hyphen"),
    "CHR003": ("·", "Middle dot (U+00B7)", "Use a comma or a period"),
    "CHR004": (";", "Semicolon", "Split into two sentences or join with a comma"),
}


def describe_character(character: str) -> tuple[str, str, str]:
    """Return the code, message and suggestion for a character outside plain ASCII."""
    for code, (forbidden, message, suggestion) in FORBIDDEN_CHARACTERS.items():
        if character == forbidden:
            return code, message, suggestion

    name = unicodedata.name(character, "unnamed")

    return (
        "CHR000",
        f"Non-ASCII character {character!r} ({name})",
        "Replace with an ASCII equivalent",
    )


def check_characters(
    document: Document, rules: list[Rule], ignore_code: bool
) -> list[RuleViolation]:
    """Report every forbidden character the given CHR rules cover."""
    rules_by_code = {rule.code: rule for rule in rules}
    violations: list[RuleViolation] = []

    for offset, character in enumerate(document.extract_prose(ignore_code)):
        if character != ";" and ord(character) < 128:
            continue

        code, message, suggestion = describe_character(character)
        if code not in rules_by_code:
            continue

        position = document.locate_offset(offset)
        violations.append(
            RuleViolation(
                rule=rules_by_code[code],
                path=document.path,
                position=position,
                message=message,
                quote=document.read_line(position.line).strip(),
                suggestion=suggestion,
            )
        )

    return violations


def count_sentences(text: str) -> int:
    """Count sentences as runs of text ending in ., ! or ?."""
    pieces = SENTENCE_END.split(text)

    return sum(1 for piece in pieces if re.search(r"[A-Za-z]", piece))


def check_sentence_count(
    document: Document, rules: list[Rule], ignore_code: bool
) -> list[RuleViolation]:
    """Report LEN001 when the document exceeds its max-sentences option."""
    count = count_sentences(document.extract_prose(ignore_code))
    violations = []

    for rule in rules:
        limit = rule.options["max-sentences"]
        if count <= limit:
            continue

        violations.append(
            RuleViolation(
                rule=rule,
                path=document.path,
                position=Position(line=1, column=1),
                message=f"Text has {count} sentences, the limit is {limit}",
                quote=None,
                suggestion="Cut to the sentences that answer the question",
            )
        )

    return violations


PythonCheck = Callable[[Document, list[Rule], bool], list[RuleViolation]]

PYTHON_CHECKS_BY_CODE: dict[str, PythonCheck] = {
    "CHR000": check_characters,
    "CHR001": check_characters,
    "CHR002": check_characters,
    "CHR003": check_characters,
    "CHR004": check_characters,
    "LEN001": check_sentence_count,
}


def is_checked_in_python(rule: Rule) -> bool:
    return rule.code in PYTHON_CHECKS_BY_CODE


def run_python_checks(
    document: Document, rules: list[Rule], ignore_code: bool
) -> list[RuleViolation]:
    """Run each registered check once, with the enabled rules it owns."""
    rules_by_check: dict[PythonCheck, list[Rule]] = {}
    for rule in rules:
        rules_by_check.setdefault(PYTHON_CHECKS_BY_CODE[rule.code], []).append(rule)

    violations: list[RuleViolation] = []
    for check, owned_rules in rules_by_check.items():
        violations.extend(check(document, owned_rules, ignore_code))

    logger.info("%s: python checks found %d violations", document.path, len(violations))

    return violations
