"""Find and parse the selected configuration file.

Linter settings layer the selected configuration over the shipped defaults.
"""

import logging
import os
import tomllib
from importlib import resources
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

NLL_CONFIG_FILE_NAME = "nll.toml"
PYPROJECT_FILE_NAME = "pyproject.toml"
SHIPPED_CONFIG_FILE = Path(
    str(resources.files("nll").joinpath("resources", "config.toml"))
)


def locate_user_config_file() -> Path:
    """Return the user config path under $XDG_CONFIG_HOME, or ~/.config when unset."""
    base = os.environ.get("XDG_CONFIG_HOME", "")
    if base == "":
        return Path.home() / ".config" / "nll" / "config.toml"

    return Path(base) / "nll" / "config.toml"


def has_nll_section(pyproject: Path) -> bool:
    with pyproject.open("rb") as handle:
        return "nll" in tomllib.load(handle).get("tool", {})


def discover_config_file(start: Path) -> Path:
    """Find the config file to be used, starting at a given directory.

    Walking upward, a pyproject.toml with a [tool.nll] table wins over an
    nll.toml in the same directory. Below both comes the user config, and
    below that the shipped config.
    """
    for directory in (start, *start.parents):
        pyproject = directory / PYPROJECT_FILE_NAME
        nll_config = directory / NLL_CONFIG_FILE_NAME
        pyproject_applies = pyproject.is_file() and has_nll_section(pyproject)

        if pyproject_applies and nll_config.is_file():
            logger.warning(
                "%s: both %s and %s configure nll, using %s",
                directory,
                pyproject.name,
                nll_config.name,
                pyproject.name,
            )

        if pyproject_applies:
            logger.info("Using pyproject.toml at %s", pyproject)
            return pyproject

        if nll_config.is_file():
            logger.info("Using nll.toml at %s", nll_config)
            return nll_config

    user_file = locate_user_config_file()
    if user_file.is_file():
        logger.info("Using user config at %s", user_file)
        return user_file

    logger.info("Using default config at %s", SHIPPED_CONFIG_FILE)
    return SHIPPED_CONFIG_FILE


def read_config_file(path: Path) -> dict[str, Any]:
    """Parse the config file, unwrapping [tool.nll] for pyproject.toml."""
    with path.open("rb") as handle:
        data = tomllib.load(handle)

    logger.info("Settings loaded from %s", path)

    if path.name != PYPROJECT_FILE_NAME:
        return data

    section = data.get("tool", {}).get("nll")
    if not isinstance(section, dict):
        raise ValueError(f"{path}: no [tool.nll] table")

    return section
