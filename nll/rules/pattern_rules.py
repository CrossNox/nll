"""Report configured text-pattern matches."""

import re
from typing import ClassVar

from nll.document import Document
from nll.rules.rules import CodeRule
from nll.violations import Violation, Violations

ASCII_IGNORE_CASE = re.ASCII | re.IGNORECASE


class TextPatternRule(CodeRule, identifier=None):
    """Check a regular expression."""

    pattern: ClassVar[str]
    flags: ClassVar[int] = ASCII_IGNORE_CASE

    def __init__(
        self,
        section: str,
        code: str,
        description: str,
        **arguments: object,
    ) -> None:
        super().__init__(section, code, description, **arguments)
        self.compiled_pattern = re.compile(self.pattern, self.flags)

    def __call__(self, document: Document) -> Violations:
        violations = []

        for match in self.compiled_pattern.finditer(document.prose):
            line = document.prose.count("\n", 0, match.start()) + 1
            line_start = document.prose.rfind("\n", 0, match.start()) + 1

            violations.append(
                Violation(
                    rule=self,
                    path=document.path,
                    line=line,
                    offset=match.start() - line_start + 1,
                    quote=match.group(0),
                )
            )

        return Violations(violations)
