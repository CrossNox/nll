"""Find the files to lint."""

import logging
from collections.abc import Sequence
from fnmatch import fnmatch
from pathlib import Path

logger = logging.getLogger(__name__)


def find_matching_files(directory: Path, include: list[str]) -> list[Path]:
    """Walk a directory for files matching the patterns, skipping hidden directories."""
    files: list[Path] = []

    for child in sorted(directory.iterdir()):
        if child.name.startswith("."):
            continue

        if child.is_dir():
            files.extend(find_matching_files(child, include))
        elif any(fnmatch(child.name, pattern) for pattern in include):
            files.append(child)

    return files


def find_files_to_lint(paths: Sequence[Path], include: list[str]) -> list[Path]:
    """Turn named files and directories into the list of files to lint, in order."""
    files: list[Path] = []

    for path in paths:
        if not path.is_dir():
            files.append(path)
            continue

        found = find_matching_files(path, include)
        if len(found) == 0:
            logger.warning("%s: no files match %s", path, " ".join(include))
        files.extend(found)

    return files
