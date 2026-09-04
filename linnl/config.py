"""Configuration for the linter."""

import logging
import os
import tomllib
from importlib import resources
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

LINNL_CONFIG_FILE_NAME = "linnl.toml"
PYPROJECT_FILE_NAME = "pyproject.toml"
SHIPPED_CONFIG_FILE = Path(
    str(resources.files("linnl").joinpath("resources", "config.toml"))
)


def locate_user_config_file() -> Path:
    """Return the user config path under $XDG_CONFIG_HOME, or ~/.config when unset."""
    base = os.environ.get("XDG_CONFIG_HOME", "")
    if base == "":
        return Path.home() / ".config" / "linnl" / "config.toml"

    return Path(base) / "linnl" / "config.toml"


def has_linnl_section(pyproject: Path) -> bool:
    with pyproject.open("rb") as handle:
        return "linnl" in tomllib.load(handle).get("tool", {})


def discover_config_file(start: Path) -> Path:
    """Find the config file to be used, starting at a given directory.

    Walking upward, a pyproject.toml with a [tool.linnl] table wins over an
    linnl.toml in the same directory. Below both comes the user config, and
    below that the shipped config.
    """
    for directory in (start, *start.parents):
        pyproject = directory / PYPROJECT_FILE_NAME
        linnl_config = directory / LINNL_CONFIG_FILE_NAME
        pyproject_applies = pyproject.is_file() and has_linnl_section(pyproject)

        if pyproject_applies and linnl_config.is_file():
            logger.warning(
                "%s: both %s and %s configure linnl, using %s",
                directory,
                pyproject.name,
                linnl_config.name,
                pyproject.name,
            )

        if pyproject_applies:
            logger.info("Using pyproject.toml at %s", pyproject)
            return pyproject

        if linnl_config.is_file():
            logger.info("Using linnl.toml at %s", linnl_config)
            return linnl_config

    user_file = locate_user_config_file()
    if user_file.is_file():
        logger.info("Using user config at %s", user_file)
        return user_file

    logger.info("Using default config at %s", SHIPPED_CONFIG_FILE)
    return SHIPPED_CONFIG_FILE


def read_config_file(path: Path) -> dict[str, Any]:
    """Parse the config file, unwrapping [tool.linnl] for pyproject.toml."""
    with path.open("rb") as handle:
        data = tomllib.load(handle)

    logger.info("Settings loaded from %s", path)

    if path.name != PYPROJECT_FILE_NAME:
        return data

    section = data.get("tool", {}).get("linnl")
    if not isinstance(section, dict):
        raise ValueError(f"{path}: no [tool.linnl] table")

    return section
