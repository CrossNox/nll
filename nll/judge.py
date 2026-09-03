"""Judge model rules with a supported model agent."""

import logging
from collections.abc import Sequence
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any

import jinja2
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
from openai_codex import AsyncCodex, Sandbox
from pydantic import BaseModel, ValidationError

from nll.agents import Agent, find_default_model_for_agent
from nll.document import Document
from nll.rules import ModelRule
from nll.violations import Violation, Violations

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _prepare_env() -> jinja2.Environment:
    jinja_logging_undef = jinja2.make_logging_undefined(
        logger=logger, base=jinja2.Undefined
    )
    env = jinja2.Environment(
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=jinja_logging_undef,
        autoescape=jinja2.select_autoescape(
            disabled_extensions=(".md.j2"), default_for_string=False, default=False
        ),
        loader=jinja2.PackageLoader("nll", package_path="resources/templates/"),
    )
    return env


class ReportedViolation[IdentifierT](BaseModel):
    """Carry a violation as the model reports it, before its quote is located."""

    identifier: IdentifierT
    quote: str


class Report[IdentifierT](BaseModel):
    """Carry what the model returns for one document."""

    violations: list[ReportedViolation[IdentifierT]]


class ModelJudge:
    """Ask the model which of the rules it is given a document breaks."""

    def __init__(
        self,
        rules: Sequence[ModelRule],
        *,
        agent: Agent = "claude",
        model: str | None = None,
    ):
        self.rules = {rule.identifier: rule for rule in rules}
        self.agent = agent
        self.model = model if model is not None else find_default_model_for_agent(agent)
        rule_names = {name: name for name in self.rules}
        rule_identifier = StrEnum("rule_identifier", rule_names)  # type: ignore[misc]
        self.report_model = Report[rule_identifier]

        jinja_env = _prepare_env()
        logger.debug("Rendering system prompt")
        self.system_prompt = (
            jinja_env.get_template("prompt.md.j2").render(rules=rules).strip()
        )

        self.claude_options: ClaudeAgentOptions | None = None

        if agent == "claude":
            self.claude_options = ClaudeAgentOptions(
                system_prompt=self.system_prompt,
                tools=[],
                model=model,
                setting_sources=None,
                output_format={
                    "type": "json_schema",
                    "schema": self.report_model.model_json_schema(),
                },
            )

    async def __call__(self, document: Document) -> Violations:
        """Run one model call over the document and locate what it reports."""
        path = document.path

        logger.info(
            "%s: judging %d rules over %d characters (agent=%s, model=%s)",
            path,
            len(self.rules),
            len(document.prose),
            self.agent,
            self.model,
        )

        prompt = f"Lint the following text.\n\n<text>\n{document.prose}\n</text>"

        if self.agent == "claude":
            report = await self._judge_with_claude(prompt, path)
        elif self.agent == "codex":
            report = await self._judge_with_codex(prompt, path)
        else:
            raise ValueError(f"Unsupported model agent: {self.agent!r}")

        logger.info("%s: the model found %d violations", path, len(report.violations))

        return Violations(
            self.locate(reported, document) for reported in report.violations
        )

    async def _judge_with_claude(self, prompt: str, path: Path | None) -> Report[Any]:
        """Run the prompt through Claude and parse its report."""
        result: ResultMessage | None = None

        if self.claude_options is None:
            raise RuntimeError("Claude options are unavailable for this model agent")

        async for message in query(prompt=prompt, options=self.claude_options):
            if isinstance(message, ResultMessage):
                result = message

        if result is None:
            raise RuntimeError(
                f"{path}: the model session ended without a result message"
            )

        if result.is_error or result.subtype != "success":
            raise RuntimeError(
                f"{path}: Claude run failed with subtype {result.subtype!r}, "
                f"errors {result.errors!r}"
            )

        if result.structured_output is None:
            raise RuntimeError(f"{path}: Claude returned no structured output")

        logger.info(
            "%s: Claude linted in %.1fs, cost %s",
            path,
            result.duration_ms / 1000,
            (
                "unknown"
                if result.total_cost_usd is None
                else f"{result.total_cost_usd:.4f} USD"
            ),
        )

        try:
            return self.report_model.model_validate(result.structured_output)
        except ValidationError as error:
            raise RuntimeError(
                f"{path}: Claude returned invalid structured output: {error}"
            ) from error

    async def _judge_with_codex(self, prompt: str, path: Path | None) -> Report[Any]:
        """Run the prompt through Codex and parse its final response."""
        try:
            async with AsyncCodex() as codex:
                thread = await codex.thread_start(
                    developer_instructions=self.system_prompt,
                    ephemeral=True,
                    model=self.model,
                    sandbox=Sandbox.read_only,
                )
                result = await thread.run(
                    prompt,
                    output_schema=self.report_model.model_json_schema(),
                )
        except Exception as error:
            raise RuntimeError(f"{path}: Codex turn failed: {error}") from error

        status = getattr(result.status, "value", result.status)
        if status != "completed" or result.error is not None:
            raise RuntimeError(
                f"{path}: Codex turn failed with status {result.status!r}, "
                f"error {result.error!r}"
            )

        if result.final_response is None:
            raise RuntimeError(f"{path}: Codex turn returned no final response")

        try:
            return self.report_model.model_validate_json(result.final_response)
        except (TypeError, ValidationError) as error:
            raise RuntimeError(
                f"{path}: Codex returned invalid structured output: {error}"
            ) from error

    def locate(self, reported: ReportedViolation[Any], document: Document) -> Violation:
        """Place a reported violation at the line its quote sits on."""
        rule = self.rules[reported.identifier]

        for line_number, line in enumerate(document.lines, start=1):
            index = line.find(reported.quote)

            if index != -1:
                return Violation(
                    rule=rule,
                    path=document.path,
                    line=line_number,
                    offset=index + 1,
                    quote=reported.quote,  # should it be line?
                )

        logger.error(
            "%s: could not find the span reported for %s: %r",
            document.path,
            reported.identifier,
            reported.quote,
        )
        raise RuntimeError("Could not find the quote in the document.")
