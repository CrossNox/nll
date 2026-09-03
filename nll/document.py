import re
from pathlib import Path


class Document:
    def __init__(self, path: Path | None = None, prose: str | None = None):
        if prose is None:
            if path is None:
                raise ValueError("Either 'prose' or 'path' must be provided.")

            prose = path.read_text(encoding="utf-8")

        self.prose = prose
        self.path = path
        self.lines = self.prose.split("\n")

    def remove_code_blocks(self) -> "Document":
        """Remove Markdown and reStructuredText code blocks."""
        lines = self.prose.splitlines(keepends=True)
        omitted = [False] * len(lines)
        line_index = 0

        while line_index < len(lines):
            markdown_fence = self._find_markdown_fence_start(lines[line_index])

            if markdown_fence is not None:
                fence_character, fence_length = markdown_fence
                closing_line_index = self._find_markdown_fence_end(
                    lines,
                    line_index + 1,
                    fence_character,
                    fence_length,
                )

                if closing_line_index is None:
                    raise ValueError(
                        f"Unclosed Markdown fence opened on line {line_index + 1}."
                    )

                for omitted_line_index in range(line_index, closing_line_index + 1):
                    omitted[omitted_line_index] = True

                line_index = closing_line_index + 1
                continue

            rst_block_indentation = self._find_rst_block_indentation(lines[line_index])

            if rst_block_indentation is not None:
                block_end_index = self._find_indented_block_end(
                    lines,
                    line_index + 1,
                    rst_block_indentation,
                )

                for omitted_line_index in range(line_index, block_end_index):
                    omitted[omitted_line_index] = True

                line_index = block_end_index
                continue

            literal_block_indentation = self._find_rst_literal_block_indentation(
                lines[line_index]
            )

            if literal_block_indentation is not None:
                block_end_index = self._find_indented_block_end(
                    lines,
                    line_index + 1,
                    literal_block_indentation,
                )

                for omitted_line_index in range(line_index + 1, block_end_index):
                    omitted[omitted_line_index] = True

                line_index = block_end_index
                continue

            line_index += 1

        prose = "".join(
            self._blank_line(line) if omit_line else line
            for line, omit_line in zip(lines, omitted, strict=True)
        )

        return Document(path=self.path, prose=prose)

    @staticmethod
    def _find_markdown_fence_start(line: str) -> tuple[str, int] | None:
        content = line.rstrip("\r\n")
        match = re.match(r"^ {0,3}(?P<fence>`{3,}|~{3,}).*$", content)

        if match is None:
            return None

        fence = match.group("fence")
        return fence[0], len(fence)

    @staticmethod
    def _find_markdown_fence_end(
        lines: list[str],
        start_index: int,
        fence_character: str,
        fence_length: int,
    ) -> int | None:
        pattern = re.compile(
            rf"^ {{0,3}}{re.escape(fence_character)}{{{fence_length},}}[ \t]*$"
        )

        for line_index in range(start_index, len(lines)):
            if pattern.match(lines[line_index].rstrip("\r\n")) is not None:
                return line_index

        return None

    @staticmethod
    def _find_rst_block_indentation(line: str) -> int | None:
        content = line.rstrip("\r\n")
        match = re.match(
            r"^(?P<indent>[ \t]*)\.\.\s+(?:code|code-block)::(?:[ \t].*)?$",
            content,
        )

        if match is None:
            return None

        return Document._find_indentation_width(match.group("indent"))

    @staticmethod
    def _find_rst_literal_block_indentation(line: str) -> int | None:
        content = line.rstrip("\r\n")

        if re.match(r"^[ \t]*\.\.\s+\S+::", content) is not None:
            return None

        if not content.rstrip(" \t").endswith("::"):
            return None

        return Document._find_indentation_width(content)

    @staticmethod
    def _find_indented_block_end(
        lines: list[str], start_index: int, block_indentation: int
    ) -> int:
        line_index = start_index

        while line_index < len(lines):
            content = lines[line_index].rstrip("\r\n")

            if content.strip(" \t") == "":
                line_index += 1
                continue

            indentation = Document._find_indentation_width(content)

            if indentation <= block_indentation:
                return line_index

            line_index += 1

        return line_index

    @staticmethod
    def _find_indentation_width(line: str) -> int:
        indentation = line[: len(line) - len(line.lstrip(" \t"))]
        return len(indentation.expandtabs(8))

    @staticmethod
    def _blank_line(line: str) -> str:
        return line[len(line.rstrip("\r\n")) :]
