"""Represent rule violations and render them for people or for machines."""

import json
from collections.abc import Iterable, Iterator
from enum import StrEnum, auto
from typing import Any

from pydantic import BaseModel, ConfigDict

from nll.document import Position
from nll.rules import Rule


class OutputFormat(StrEnum):
    TEXT = auto()
    JSON = auto()


class RuleViolation(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule: Rule
    path: str
    position: Position | None
    message: str
    quote: str | None
    suggestion: str | None

    def compute_sort_key(self) -> tuple[str, int, int, str]:
        """Order violations by file, then position, with unlocated ones last."""
        if self.position is None:
            return (self.path, 1 << 30, 0, self.rule.code)

        return (self.path, self.position.line, self.position.column, self.rule.code)

    def render_text(self) -> str:
        """Render one violation in the `path:line:col: CODE message` layout."""
        if self.position is None:
            location = f"{self.path}:?:?"
        else:
            location = f"{self.path}:{self.position.line}:{self.position.column}"

        lines = [f"{location}: {self.rule.code} {self.message}"]

        if self.quote is not None:
            lines.append(f"    > {self.quote}")

        if self.suggestion == "":
            lines.append("    Fix: delete the span")
        elif self.suggestion is not None:
            lines.append(f"    Fix: {self.suggestion}")

        return "\n".join(lines)

    def serialize(self) -> dict[str, Any]:
        """Flatten the violation for JSON output."""
        return {
            "code": self.rule.code,
            "path": self.path,
            "line": None if self.position is None else self.position.line,
            "column": None if self.position is None else self.position.column,
            "message": self.message,
            "quote": self.quote,
            "suggestion": self.suggestion,
        }


class RuleViolations(BaseModel):
    """The violations of a lint run, in the order they should be shown."""

    model_config = ConfigDict(frozen=True)

    items: tuple[RuleViolation, ...]

    @classmethod
    def collect(cls, violations: Iterable[RuleViolation]) -> "RuleViolations":
        """Gather violations in any order into a report sorted by file and position."""
        return cls(items=tuple(sorted(violations, key=RuleViolation.compute_sort_key)))

    @classmethod
    def concatenate(cls, parts: Iterable["RuleViolations"]) -> "RuleViolations":
        """Join per-document reports in the order given."""
        return cls(items=tuple(violation for part in parts for violation in part.items))

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self) -> Iterator[RuleViolation]:  # type: ignore[override]
        return iter(self.items)

    def render(self, output_format: OutputFormat) -> str:
        """Render as text with a closing count, or as a JSON array."""
        if output_format is OutputFormat.JSON:
            return json.dumps(
                [violation.serialize() for violation in self.items],
                indent=2,
                ensure_ascii=False,
            )

        lines = [violation.render_text() for violation in self.items]
        lines.append(f"Found {len(self.items)} violations.")

        return "\n".join(lines)
