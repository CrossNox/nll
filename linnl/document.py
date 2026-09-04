from pathlib import Path

from docutils import nodes
from docutils.core import publish_doctree
from markdown_it import MarkdownIt

from linnl.constants import DEFAULT_IGNORE_CODE_BLOCKS

MARKDOWN_PARSER = MarkdownIt("commonmark")


class Document:
    def __init__(
        self,
        path: Path | None = None,
        prose: str | None = None,
        ignore_code_blocks: bool = DEFAULT_IGNORE_CODE_BLOCKS,
    ):
        if prose is None:
            if path is None:
                raise ValueError("Either 'prose' or 'path' must be provided.")

            prose = path.read_text(encoding="utf-8")

        self.ignore_code_blocks = ignore_code_blocks
        self._prose = prose
        self.path = path

    @property
    def prose(self) -> str:
        if self.ignore_code_blocks:
            return self._omit_code_blocks()
        return self._prose

    @property
    def lines(self) -> list[str]:
        return self.prose.split("\n")

    def _omit_code_blocks(self) -> str:
        """Omit code content while preserving source line positions."""
        if self.path is None:
            return self._prose

        if self.path.suffix.lower() == ".md":
            omitted_ranges = self._find_markdown_code_block_ranges()
        elif self.path.suffix.lower() == ".rst":
            omitted_ranges = self._find_rst_code_block_ranges()
        else:
            return self._prose

        lines = self._prose.splitlines(keepends=True)
        omitted_lines = [False] * len(lines)

        for start_line, end_line in omitted_ranges:
            for line_index in range(start_line, end_line):
                omitted_lines[line_index] = True

        return "".join(
            self._extract_line_ending(line) if omitted else line
            for line, omitted in zip(lines, omitted_lines, strict=True)
        )

    def _find_markdown_code_block_ranges(self) -> list[tuple[int, int]]:
        """Find source ranges for Markdown code blocks."""
        ranges = []

        for token in MARKDOWN_PARSER.parse(self._prose):
            if token.type in {"code_block", "fence"} and token.map is not None:
                ranges.append((token.map[0], token.map[1]))

        return ranges

    def _find_rst_code_block_ranges(self) -> list[tuple[int, int]]:
        """Find source ranges for reStructuredText literal blocks."""
        tree = publish_doctree(
            self._prose,
            settings_overrides={
                "file_insertion_enabled": False,
                "halt_level": 6,
                "raw_enabled": False,
                "report_level": 5,
            },
        )
        ranges = []
        source_offset = 0

        for block in tree.findall(nodes.literal_block):
            if isinstance(
                block.parent, nodes.system_message
            ) and not block.rawsource.lstrip().startswith(
                (".. code::", ".. code-block::")
            ):
                continue

            start_offset = self._find_source_offset_for_rst_block(
                block.rawsource,
                source_offset,
                block.line,
            )

            start_line = self._prose.count("\n", 0, start_offset)
            end_line = start_line + len(block.rawsource.splitlines())
            ranges.append((start_line, end_line))
            source_offset = start_offset + len(block.rawsource)

        return ranges

    def _find_source_offset_for_rst_block(
        self,
        rawsource: str,
        source_offset: int,
        reported_line: int | None,
    ) -> int:
        """Find the source offset for a reStructuredText literal block."""
        offset = self._prose.find(rawsource, source_offset)

        if offset == -1:
            raise ValueError("Could not locate a reStructuredText code block.")

        if reported_line is None:
            return offset

        expected_offset = offset

        while offset != -1:
            line_number = self._prose.count("\n", 0, offset) + 1

            if line_number > reported_line:
                break

            expected_offset = offset
            offset = self._prose.find(rawsource, offset + 1)

        return expected_offset

    @staticmethod
    def _extract_line_ending(line: str) -> str:
        return line[len(line.rstrip("\r\n")) :]
