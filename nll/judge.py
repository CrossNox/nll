"""Judge model rules with Claude or Codex."""

import logging
from abc import ABC, abstractmethod
from collections.abc import Sequence
from enum import StrEnum
from functools import lru_cache

import jinja2
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
from openai_codex import AsyncCodex, Sandbox
from pydantic import BaseModel, ConfigDict, ValidationError

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


class ReportedViolation[IdentifierT: str](BaseModel):
    """Carry a violation as the model reports it, before its quote is located."""

    model_config = ConfigDict(extra="forbid")

    identifier: IdentifierT
    quote: str


class Report[IdentifierT: str](BaseModel):
    """Carry what the model returns for one document."""

    model_config = ConfigDict(extra="forbid")

    violations: list[ReportedViolation[IdentifierT]]


class ModelJudge(ABC):
    """Judge model rules for one document."""

    def __init__(self, rules: Sequence[ModelRule], model: str) -> None:
        self.rules = {rule.identifier: rule for rule in rules}
        self.model = model
        rule_names = {name: name for name in self.rules}
        rule_identifier = StrEnum("rule_identifier", rule_names)  # type: ignore[misc]
        self.report_model = Report[rule_identifier]

        jinja_env = _prepare_env()
        logger.debug("Rendering system prompt")
        self.system_prompt = (
            jinja_env.get_template("prompt.md.j2").render(rules=rules).strip()
        )

    @abstractmethod
    async def judge(self, document: Document) -> Violations:
        """Judge one document and return its violations."""

    def render_prompt_for_document(self, document: Document) -> str:
        """Render the document prompt for the model."""
        logger.info(
            "%s: judging %d rules over %d characters (model=%s)",
            document.path,
            len(self.rules),
            len(document.prose),
            self.model,
        )
        return f"Lint the following text.\n\n<text>\n{document.prose}\n</text>"

    def locate_violation_in_document[IdentifierT: str](
        self, reported: ReportedViolation[IdentifierT], document: Document
    ) -> Violation:
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
                    quote=reported.quote,
                )

        logger.error(
            "%s: could not find the span reported for %s: %r",
            document.path,
            reported.identifier,
            reported.quote,
        )
        raise RuntimeError("Could not find the quote in the document.")


class ClaudeModelJudge(ModelJudge):
    """Judge model rules with Claude."""

    def __init__(self, rules: Sequence[ModelRule], model: str):
        super().__init__(rules, model)
        self.options = ClaudeAgentOptions(
            system_prompt=self.system_prompt,
            tools=[],
            model=model,
            setting_sources=None,
            output_format={
                "type": "json_schema",
                "schema": self.report_model.model_json_schema(),
            },
        )

    async def judge(self, document: Document) -> Violations:
        """Judge one document with Claude and return its violations."""
        prompt = self.render_prompt_for_document(document)
        result: ResultMessage | None = None

        async for message in query(prompt=prompt, options=self.options):
            if isinstance(message, ResultMessage):
                result = message

        if result is None:
            raise RuntimeError(
                f"{document.path}: the Claude session ended without a result message"
            )

        if result.is_error or result.subtype != "success":
            raise RuntimeError(
                f"{document.path}: Claude run failed with subtype "
                f"{result.subtype!r}, errors {result.errors!r}"
            )

        if result.structured_output is None:
            raise RuntimeError(f"{document.path}: Claude returned no structured output")

        logger.info(
            "%s: Claude linted in %.1fs, cost %s",
            document.path,
            result.duration_ms / 1000,
            (
                "unknown"
                if result.total_cost_usd is None
                else f"{result.total_cost_usd:.4f} USD"
            ),
        )

        try:
            report = self.report_model.model_validate(result.structured_output)
        except ValidationError as error:
            raise RuntimeError(
                f"{document.path}: Claude returned invalid structured output: {error}"
            ) from error

        logger.info(
            "%s: Claude found %d violations", document.path, len(report.violations)
        )
        return Violations(
            self.locate_violation_in_document(reported, document)
            for reported in report.violations
        )


class CodexModelJudge(ModelJudge):
    """Judge model rules with Codex."""

    async def judge(self, document: Document) -> Violations:
        """Judge one document with Codex and return its violations."""
        prompt = self.render_prompt_for_document(document)

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
            raise RuntimeError(
                f"{document.path}: Codex turn failed: {error}"
            ) from error

        status = getattr(result.status, "value", result.status)
        if status != "completed" or result.error is not None:
            raise RuntimeError(
                f"{document.path}: Codex turn failed with status "
                f"{result.status!r}, error {result.error!r}"
            )

        if result.final_response is None:
            raise RuntimeError(
                f"{document.path}: Codex turn returned no final response"
            )

        try:
            report = self.report_model.model_validate_json(result.final_response)
        except (TypeError, ValidationError) as error:
            raise RuntimeError(
                f"{document.path}: Codex returned invalid structured output: {error}"
            ) from error

        logger.info(
            "%s: Codex found %d violations", document.path, len(report.violations)
        )
        return Violations(
            self.locate_violation_in_document(reported, document)
            for reported in report.violations
        )
