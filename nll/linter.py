"""Lint documents against the enabled rules."""

import asyncio
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from nll.checks import is_checked_in_python, run_python_checks
from nll.config import Config, load_config
from nll.document import Document
from nll.model import judge_with_model
from nll.rules import Rule
from nll.violations import RuleViolations


class Linter(BaseModel):
    """A config with its selection resolved, ready to lint."""

    model_config = ConfigDict(frozen=True)

    config: Config
    rules: list[Rule]

    @classmethod
    def load(
        cls,
        config_path: Path | None,
        start: Path,
        select: list[str] | None,
        extend_select: list[str],
        ignore: list[str],
    ) -> "Linter":
        """Load the config for `start`, apply the selectors and resolve the rules."""
        config = load_config(config_path, start).with_selection(
            select, extend_select, ignore
        )

        return cls(config=config, rules=config.enabled_rules())

    async def lint(self, document: Document) -> RuleViolations:
        """Lint one document and sort the violations by position."""
        python_rules = [rule for rule in self.rules if is_checked_in_python(rule)]
        model_rules = [rule for rule in self.rules if not is_checked_in_python(rule)]

        violations = run_python_checks(document, python_rules, self.config.ignore_code)
        violations.extend(await judge_with_model(document, model_rules, self.config))

        return RuleViolations.collect(violations)

    def lint_all(self, documents: list[Document]) -> RuleViolations:
        """Lint every document, max-concurrency at a time, in document order."""

        async def lint_everything() -> list[RuleViolations]:
            semaphore = asyncio.Semaphore(self.config.max_concurrency)

            async def lint_with_limit(document: Document) -> RuleViolations:
                async with semaphore:
                    return await self.lint(document)

            return await asyncio.gather(
                *(lint_with_limit(document) for document in documents)
            )

        return RuleViolations.concatenate(asyncio.run(lint_everything()))

    def render_rules(self) -> str:
        """List every rule under its group with its on/off state and who checks it."""
        enabled_codes = {rule.code for rule in self.rules}
        lines = []
        last_prefix = None

        for rule in self.config.rules:
            if rule.group_prefix != last_prefix:
                lines.append(f"{rule.group_prefix}  {rule.group_description}")
                last_prefix = rule.group_prefix

            state = "on " if rule.code in enabled_codes else "off"
            checker = "python" if is_checked_in_python(rule) else "model "
            lines.append(
                f"  {rule.code:8} {state}  {checker}  {rule.render_description()}"
            )

        return "\n".join(lines)
