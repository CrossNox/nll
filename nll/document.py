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
