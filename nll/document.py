"""Represent a text under lint."""

import bisect
import re

from pydantic import BaseModel, ConfigDict

FENCED_CODE = re.compile(r"^(```|~~~).*?^\1[ \t]*$", re.MULTILINE | re.DOTALL)
INLINE_CODE = re.compile(r"`[^`\n]+`")


class Position(BaseModel):
    model_config = ConfigDict(frozen=True)

    line: int
    column: int


class Document:
    def __init__(self, text: str, path: str):
        self.text = text
        self.path = path
        self._line_starts = [0] + [match.end() for match in re.finditer("\n", text)]

    def locate_offset(self, offset: int) -> Position:
        """Convert a character offset into a 1-based line and column."""
        line_index = bisect.bisect_right(self._line_starts, offset) - 1
        column = offset - self._line_starts[line_index] + 1

        return Position(line=line_index + 1, column=column)

    def read_line(self, line: int) -> str:
        """Return the content of a 1-based line without its newline."""
        return self.text.split("\n")[line - 1]

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
