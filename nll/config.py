"""Find and read the configuration files."""

import logging
import os
import tomllib
from importlib import resources
from pathlib import Path
from typing import Any

from nll.checks import PYTHON_CHECKS
from nll.rules import RuleBook

logger = logging.getLogger(__name__)

NLL_CONFIG_FILE_NAME = "nll.toml"
PYPROJECT_FILE_NAME = "pyproject.toml"
RULES_KEY = "rules"
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


def discover_config_file(start: Path) -> Path | None:
    """Find the config file that applies to `start`, or None for the shipped one.

    Walking upward, a pyproject.toml with a [tool.nll] table wins over an
    nll.toml in the same directory. Below both comes the user config.
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
            return pyproject

        if nll_config.is_file():
            return nll_config

    user_file = locate_user_config_file()
    if user_file.is_file():
        return user_file

    return None


def read_config_file(path: Path) -> dict[str, Any]:
    """Parse one config file, unwrapping [tool.nll] for pyproject.toml."""
    with path.open("rb") as handle:
        data = tomllib.load(handle)

    if path.name != PYPROJECT_FILE_NAME:
        return data

    section = data.get("tool", {}).get("nll")
    if not isinstance(section, dict):
        raise ValueError(f"{path}: no [tool.nll] table")

    return section


def read_config_layers(config_file: Path | None) -> dict[str, Any]:
    """Read the shipped config, then `config_file` over it, key by key.

    The `rules` entry of the result is a RuleBook. The Python checks bind to
    the shipped rules by code. A user file may add model-judged groups and set
    options of existing rules.
    """
    settings = read_config_file(SHIPPED_CONFIG_FILE)
    rules = RuleBook.from_toml(
        settings.pop(RULES_KEY, {}), PYTHON_CHECKS, str(SHIPPED_CONFIG_FILE)
    )

    unbound = PYTHON_CHECKS.keys() - {rule.code for rule in rules}
    if len(unbound) > 0:
        raise ValueError(
            f"{SHIPPED_CONFIG_FILE}: no rule for the Python checks "
            + ", ".join(sorted(unbound))
        )

    if config_file is not None:
        overrides = read_config_file(config_file)
        rules = rules.merge(overrides.pop(RULES_KEY, {}), str(config_file))
        settings.update(overrides)
        logger.info("Settings loaded from %s", config_file)

    settings[RULES_KEY] = rules

    return settings
