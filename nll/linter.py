"""Lint documents against the enabled rules."""

import asyncio
import logging
from collections.abc import Sequence
from functools import cached_property
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, ValidationError

from nll.config import SHIPPED_CONFIG_FILE, read_config_layers
from nll.document import Document
from nll.judge import Effort, ModelJudge
from nll.rules import RuleBook
from nll.sources import find_files_to_lint
from nll.violations import Violation, sort_violations_by_position

logger = logging.getLogger(__name__)


class Linter(BaseModel):
    """Run the enabled rules over documents: Python checks first, then the model.

    The fields are the settings of a run as the config files state them, and
    the rule book with the enabled rules marked.
    """

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

    @classmethod
    def from_config(
        cls,
        config_file: Path | None,
        /,
        *,
        select: Sequence[str] | None = None,
        extend_select: Sequence[str] = (),
        ignore: Sequence[str] = (),
    ) -> "Linter":
        """Read `config_file` over the shipped config and select the rules.

        A `select` override means exactly those rules: it replaces the file's
        select, extend-select and ignore, and only the `ignore` override applies
        on top. Without it, the other two append to the file's lists.
        """
        try:
            configured = cls.model_validate(read_config_layers(config_file))
        except ValidationError as error:
            raise ValueError(
                f"{config_file or SHIPPED_CONFIG_FILE}: {error}"
            ) from error

        if select is None:
            select = configured.select
            extend_select = [*configured.extend_select, *extend_select]
            ignore = [*configured.ignore, *ignore]

        return configured.model_copy(
            update={
                "select": list(select),
                "extend_select": list(extend_select),
                "ignore": list(ignore),
                "rules": configured.rules.select(
                    list(select), list(extend_select), list(ignore)
                ),
            }
        )

    @cached_property
    def judge(self) -> ModelJudge | None:
        """Build the model judge for the enabled model rules, or None without any."""
        if len(self.rules.model_rules) == 0:
            return None

        return ModelJudge(self.rules, model=self.model, effort=self.effort)

    async def lint(self, document: Document) -> list[Violation]:
        """Lint one document and sort the violations by position."""
        prose = document.extract_prose(self.ignore_code)

        violations: list[Violation] = []
        for rule in self.rules.python_rules:
            violations.extend(rule.run_check(document, prose))
        logger.info(
            "%s: python checks found %d violations", document.path, len(violations)
        )

        if self.judge is not None:
            violations.extend(await self.judge.judge(document, prose))

        return sort_violations_by_position(violations)

    def lint_text(self, text: str, path: str = "<text>") -> list[Violation]:
        """Lint a text the caller already holds, reported under `path`."""
        return asyncio.run(self.lint(Document(text, path)))

    def lint_files(self, paths: Sequence[Path]) -> list[Violation]:
        """Lint the named files and the matching files under the named directories."""
        documents = [
            Document.read(path) for path in find_files_to_lint(paths, self.include)
        ]

        async def lint_everything() -> list[list[Violation]]:
            semaphore = asyncio.Semaphore(self.max_concurrency)

            async def lint_with_limit(document: Document) -> list[Violation]:
                async with semaphore:
                    return await self.lint(document)

            return await asyncio.gather(
                *(lint_with_limit(document) for document in documents)
            )

        per_document = asyncio.run(lint_everything())

        return [violation for violations in per_document for violation in violations]
