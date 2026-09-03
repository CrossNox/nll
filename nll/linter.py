"""Lint documents against the enabled rules."""

import asyncio
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, ValidationError

from nll.agents import DEFAULT_AGENT_MODELS, Agent
from nll.config import SHIPPED_CONFIG_FILE, read_config_file
from nll.document import Document
from nll.judge import ClaudeModelJudge, CodexModelJudge, ModelJudge
from nll.rules import RuleBook, RulesDefinitions
from nll.violations import Violations

logger = logging.getLogger(__name__)


def merge_settings(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    """Merge one settings mapping over another, descending into nested tables."""
    merged = dict(base)

    for key, value in over.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = merge_settings(current, value)
        else:
            merged[key] = value

    return merged


def merge_shipped_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Layer a config file's settings over the shipped ones."""
    return merge_settings(read_config_file(SHIPPED_CONFIG_FILE), settings)


def apply_settings_overrides(
    settings: dict[str, Any],
    *,
    select: Sequence[str] | None = None,
    extend_select: Sequence[str] | None = None,
    ignore: Sequence[str] | None = None,
    model: str | None = None,
    agent: Agent | None = None,
    max_concurrency: int | None = None,
    include_extensions: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Replace the settings the caller gave a value for, leaving the rest alone."""
    overrides = {
        "select": select,
        "extend-select": extend_select,
        "ignore": ignore,
        "model": model,
        "agent": agent,
        "max-concurrency": max_concurrency,
        "include-extensions": include_extensions,
    }

    return settings | {
        key: value for key, value in overrides.items() if value is not None
    }


class LinterConfig(BaseModel):
    """Linter configuration"""

    model_config = ConfigDict(extra="forbid")

    select: list[str]
    extend_select: list[str] = Field(alias="extend-select")
    ignore: list[str]

    agent: Agent
    model: str

    max_concurrency: PositiveInt = Field(alias="max-concurrency")
    include_extensions: list[str] = Field(alias="include-extensions")
    rules: RulesDefinitions


class Linter:
    """Run the enabled rules over documents."""

    def __init__(self, config: LinterConfig, model_judge: ModelJudge | None = None):
        self.config: LinterConfig = config
        self.rules: RuleBook = RuleBook(
            rules_definitions=self.config.rules,
            select=self.config.select,
            extend_select=self.config.extend_select,
            ignore=self.config.ignore,
        )

        if model_judge is not None:
            self.llm_judge = model_judge
        else:
            self.llm_judge = {
                Agent.CLAUDE: ClaudeModelJudge,
                Agent.CODEX: CodexModelJudge,
            }[self.config.agent](rules=self.rules.model_rules, model=self.config.model)

    @classmethod
    def from_config(
        cls,
        config_file: Path,
        /,
        *,
        select: Sequence[str] | None = None,
        extend_select: Sequence[str] | None = None,
        ignore: Sequence[str] | None = None,
        model: str | None = None,
        agent: Agent | None = None,
        max_concurrency: int | None = None,
        include_extensions: Sequence[str] | None = None,
    ) -> "Linter":
        """Read the config file and apply overrides."""
        settings = read_config_file(config_file)
        settings = merge_shipped_settings(settings)
        settings = apply_settings_overrides(
            settings,
            select=select,
            extend_select=extend_select,
            ignore=ignore,
            model=model,
            agent=agent,
            max_concurrency=max_concurrency,
            include_extensions=include_extensions,
        )

        if settings["model"] is None:
            settings["model"] = DEFAULT_AGENT_MODELS[settings["agent"]]

        try:
            configured = LinterConfig.model_validate(settings)
        except ValidationError as error:
            raise ValueError(f"Configuration error: {error}") from error

        for rule in configured.ignore:
            if rule in configured.select:
                raise ValueError(
                    f"rule {rule} is both in the ignore list and the selection list"
                )

            if rule in configured.extend_select:
                raise ValueError(
                    f"rule {rule} is both in the ignore list and the "
                    "extended selection list"
                )

        return cls(configured)

    async def lint(self, document: Document) -> Violations:
        """Lint a document."""
        # So, a Document has roughly an optional path as prop, the read content
        # its prose, initialized with the flag to ignore code

        violations = Violations()

        for rule in self.rules.code_rules:
            violations.extend(rule(document))

        if len(self.rules.model_rules) > 0:
            violations.extend(await self.llm_judge.judge(document))

        logger.info(
            "%s violations found%s",
            len(violations),
            f" in {document.path}" if document.path is not None else "",
        )

        return violations

    def lint_text(self, text: str) -> Violations:
        """Lint text."""
        document = Document(prose=text)
        return asyncio.run(self.lint(document))

    def _collect_matching_files(self, directory: Path) -> list[Path]:
        """List the files under a directory whose extension the config includes."""
        files: list[Path] = []

        for entry in sorted(directory.iterdir()):
            if entry.is_dir():
                if not entry.name.startswith("."):
                    files.extend(self._collect_matching_files(entry))
            elif entry.suffix.lower() in self.config.include_extensions:
                files.append(entry)

        return files

    def _collect_lintable_files(self, paths: Sequence[Path]) -> list[Path]:
        """List the named files and the matching files under the named directories."""
        files: list[Path] = []

        for path in paths:
            if path.is_file():
                files.append(path)
            elif path.is_dir():
                files.extend(self._collect_matching_files(path))
            else:
                raise RuntimeError(f"{path}: not a file or a directory")

        if len(files) == 0:
            raise RuntimeError("no files to lint in the given paths")

        return files

    async def _lint_file(self, path: Path, semaphore: asyncio.Semaphore) -> Violations:
        """Lint one file, holding a concurrency slot for the whole call."""
        async with semaphore:
            document = Document(path=path)

            return await self.lint(document)

    async def _lint_files_concurrently(self, files: Sequence[Path]) -> list[Violations]:
        """Lint files concurrently."""
        semaphore = asyncio.Semaphore(self.config.max_concurrency)

        async with asyncio.TaskGroup() as group:
            tasks = [
                group.create_task(self._lint_file(path, semaphore)) for path in files
            ]

        return [task.result() for task in tasks]

    def lint_paths(self, paths: Sequence[Path]) -> Violations:
        """Lint the named files and the matching files under the named directories."""
        files = self._collect_lintable_files(paths)
        logger.info(
            "Linting %d files, at most %d at a time",
            len(files),
            self.config.max_concurrency,
        )
        linted = asyncio.run(self._lint_files_concurrently(files))

        return Violations.collect(linted)
