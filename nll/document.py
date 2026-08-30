"""Represent a text under lint."""

import bisect
import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

FENCED_CODE = re.compile(r"^(```|~~~).*?^\1[ \t]*$", re.MULTILINE | re.DOTALL)
INLINE_CODE = re.compile(r"`[^`\n]+`")


@dataclass(frozen=True)
class Position:
    line: int
    column: int


@dataclass(frozen=True)
class Document:
    text: str
    path: str

    @classmethod
    def read(cls, path: Path) -> "Document":
        return cls(path.read_text(encoding="utf-8"), str(path))

    @cached_property
    def lines(self) -> list[str]:
        return self.text.split("\n")

    @cached_property
    def line_starts(self) -> list[int]:
        return [0] + [match.end() for match in re.finditer("\n", self.text)]

    def locate_offset(self, offset: int) -> Position:
        """Convert a character offset into a 1-based line and column."""
        line_index = bisect.bisect_right(self.line_starts, offset) - 1
        column = offset - self.line_starts[line_index] + 1

        return Position(line=line_index + 1, column=column)

    def read_line(self, line: int) -> str:
        """Return the content of a 1-based line without its newline."""
        return self.lines[line - 1]

    def extract_prose(self, ignore_code: bool) -> str:
        """Return the text with code masked to spaces so offsets stay aligned."""
        if not ignore_code:
            return self.text

        def blank_out(match: re.Match[str]) -> str:
            return "".join("\n" if char == "\n" else " " for char in match.group(0))

        without_fences = FENCED_CODE.sub(blank_out, self.text)

        return INLINE_CODE.sub(blank_out, without_fences)

    def locate(self, quote: str) -> Position | None:
        """Find where a quoted span sits in the text, whatever its whitespace."""
        words = quote.split()
        if len(words) == 0:
            return None

        match = re.search(r"\s+".join(re.escape(word) for word in words), self.text)
        if match is None:
            return None

        return self.locate_offset(match.start())
