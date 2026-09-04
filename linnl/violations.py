"""Represent rule violations."""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from linnl.rules import Rule

QUOTE_WIDTH = 100


@dataclass(frozen=True)
class Violation:
    rule: "Rule"
    path: Path | None = None
    line: int | None = None
    offset: int | None = None
    quote: str | None = None

    def __str__(self) -> str:
        if self.line is None or self.offset is None or self.quote is None:
            return str(self.rule)

        quote = self.quote

        if len(quote) > QUOTE_WIDTH:
            quote = f"{quote[:QUOTE_WIDTH]}...[{len(quote) - QUOTE_WIDTH} chars]"

        return f"line {self.line}:\n\t> {quote}\n{self.rule}"


class Violations:
    def __init__(self, violations: Iterable[Violation] = ()):
        self.violations = sorted(
            violations,
            key=lambda violation: (
                violation.path is not None,
                str(violation.path),
                violation.line is not None,
                violation.line,
                violation.offset,
            ),
        )

    def __len__(self) -> int:
        return len(self.violations)

    def __iter__(self) -> Iterator[Violation]:
        return iter(self.violations)

    @classmethod
    def collect(cls, parts: Iterable["Violations"]) -> "Violations":
        """Gather the violations of many documents into one set."""
        return cls(violation for part in parts for violation in part)

    def __str__(self) -> str:
        blocks = []
        current_path: Path | None = None

        for violation in self.violations:
            if violation.path != current_path:
                current_path = violation.path
                underline = "=" * (len(str(current_path)) + 1)
                blocks.append(f"{current_path}\n{underline}")

            blocks.append(f"{violation}")

        return "\n\n".join(blocks)

    def extend(self, others: "Violations") -> None:
        """Take in another document's violations, keeping them in reading order."""
        self.violations = sorted(
            [*self.violations, *others],
            key=lambda violation: (
                violation.path is not None,
                str(violation.path),
                violation.line is not None,
                violation.line,
                violation.offset,
            ),
        )
