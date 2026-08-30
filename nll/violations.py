"""Represent rule violations and render them for people or for machines."""

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Any

from nll.document import Position


class OutputFormat(StrEnum):
    TEXT = auto()
    JSON = auto()


@dataclass(frozen=True)
class Violation:
    code: str
    path: str
    position: Position | None
    message: str
    quote: str | None
    suggestion: str | None

    def render_text(self) -> str:
        """Render the violation in the `path:line:col: CODE message` layout."""
        if self.position is None:
            location = f"{self.path}:?:?"
        else:
            location = f"{self.path}:{self.position.line}:{self.position.column}"

        lines = [f"{location}: {self.code} {self.message}"]

        if self.quote is not None:
            lines.append(f"    > {self.quote}")

        if self.suggestion is not None:
            lines.append(f"    Fix: {self.suggestion}")

        return "\n".join(lines)

    def serialize(self) -> dict[str, Any]:
        """Flatten the violation for JSON output."""
        return {
            "code": self.code,
            "path": self.path,
            "line": None if self.position is None else self.position.line,
            "column": None if self.position is None else self.position.column,
            "message": self.message,
            "quote": self.quote,
            "suggestion": self.suggestion,
        }


def sort_violations_by_position(violations: Iterable[Violation]) -> list[Violation]:
    """Order the violations of one document by position, unlocated ones last."""

    def position_key(violation: Violation) -> tuple[bool, int, int, str]:
        if violation.position is None:
            return (True, 0, 0, violation.code)

        return (
            False,
            violation.position.line,
            violation.position.column,
            violation.code,
        )

    return sorted(violations, key=position_key)


def render_violations(
    violations: Sequence[Violation], output_format: OutputFormat
) -> str:
    """Render as text with a closing count, or as a JSON array."""
    if output_format is OutputFormat.JSON:
        return json.dumps(
            [violation.serialize() for violation in violations],
            indent=2,
            ensure_ascii=False,
        )

    lines = [violation.render_text() for violation in violations]
    lines.append(f"Found {len(violations)} violations.")

    return "\n".join(lines)
