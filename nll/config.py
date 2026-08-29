"""Turn configuration files into a Config."""

import logging
import os
import tomllib
from importlib import resources
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, ValidationError

from nll.rules import Rule, RuleBook

logger = logging.getLogger(__name__)

PROJECT_FILE_NAME = "nll.toml"
RULES_KEY = "rules"

Effort = Literal["low", "medium", "high", "xhigh", "max"]


class Config(BaseModel):
    """The settings and rule book a run works with."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", populate_by_name=True, strict=True
    )

    select: list[str]
    extend_select: list[str] = Field(alias="extend-select")
    ignore: list[str]
    model: str
    effort: Effort
    ignore_code: bool = Field(alias="ignore-code")
    max_concurrency: PositiveInt = Field(alias="max-concurrency")
    include: list[str]
    rules: RuleBook
    source: Path | None = None

    def with_selection(
        self, select: list[str] | None, extend_select: list[str], ignore: list[str]
    ) -> "Config":
        """Apply command line selectors.

        A command line `select` means exactly those rules: it replaces the
        file's select, extend-select and ignore, and only the command line
        `ignore` applies on top. Without it, the other two append to the file's.
        """
        if select is not None:
            return self.model_copy(
                update={
                    "select": select,
                    "extend_select": extend_select,
                    "ignore": ignore,
                }
            )

        return self.model_copy(
            update={
                "extend_select": [*self.extend_select, *extend_select],
                "ignore": [*self.ignore, *ignore],
            }
        )

    def enabled_rules(self) -> list[Rule]:
        return self.rules.select(self.select, self.extend_select, self.ignore)


def locate_user_config_file() -> Path:
    """Return the user config path under $XDG_CONFIG_HOME, or ~/.config when unset."""
    base = os.environ.get("XDG_CONFIG_HOME", "")
    if base == "":
        return Path.home() / ".config" / "nll" / "config.toml"

    return Path(base) / "nll" / "config.toml"


def find_config_file(start: Path) -> Path | None:
    """Return the nearest project config above `start`, else the user config file."""
    for directory in (start, *start.parents):
        candidate = directory / PROJECT_FILE_NAME
        if candidate.is_file():
            return candidate

        pyproject = directory / "pyproject.toml"
        if pyproject.is_file():
            with pyproject.open("rb") as handle:
                data = tomllib.load(handle)
            if "nll" in data.get("tool", {}):
                return pyproject

    user_file = locate_user_config_file()
    if user_file.is_file():
        return user_file

    return None


def read_config_file(path: Path) -> dict[str, Any]:
    """Parse one config file, unwrapping [tool.nll] for pyproject.toml."""
    with path.open("rb") as handle:
        data = tomllib.load(handle)

    if path.name == "pyproject.toml":
        data = data["tool"]["nll"]

    return data


def read_shipped_config() -> dict[str, Any]:
    with (
        resources.files("nll").joinpath("resources", "config.toml").open("rb") as handle
    ):
        return tomllib.load(handle)


def split_rules(data: dict[str, Any]) -> tuple[dict[str, Any], Any]:
    """Separate the settings of a config table from its `rules` groups."""
    settings = {key: value for key, value in data.items() if key != RULES_KEY}

    return settings, data.get(RULES_KEY, {})


def validate_config(
    settings: dict[str, Any], rules: RuleBook, source: Path | None
) -> Config:
    try:
        return Config.model_validate({**settings, RULES_KEY: rules, "source": source})
    except ValidationError as error:
        raise ValueError(f"{source or 'shipped config.toml'}: {error}") from error


def load_config(config_path: Path | None, start: Path) -> Config:
    """Build the Config for a run from the shipped defaults and the user's file."""
    shipped_settings, shipped_groups = split_rules(read_shipped_config())
    rules = RuleBook.parse(shipped_groups, "shipped config.toml")
    validate_config(shipped_settings, rules, None)

    if config_path is None:
        config_path = find_config_file(start)

    if config_path is None:
        logger.info("No config file found, using the shipped defaults")
        return validate_config(shipped_settings, rules, None)

    user_settings, user_groups = split_rules(read_config_file(config_path))
    rules = rules.merge(user_groups, str(config_path))
    logger.info("Settings loaded from %s", config_path)

    return validate_config({**shipped_settings, **user_settings}, rules, config_path)
