"""Judge rules with Claude."""

import logging
from collections.abc import Sequence
from enum import StrEnum
from importlib import resources
from typing import Literal

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
from jinja2 import Environment, StrictUndefined
from pydantic import BaseModel, ConfigDict, create_model

from nll.document import Document
from nll.rules import RuleBook
from nll.violations import Violation

logger = logging.getLogger(__name__)

TEMPLATES = Environment(undefined=StrictUndefined, autoescape=False)
PROMPT_TEMPLATE = resources.files("nll").joinpath("resources", "prompt.md.j2")

Effort = Literal["low", "medium", "high", "xhigh", "max"]


class ReportedViolation(BaseModel):
    """Carry a violation as the model reports it, before its quote is located."""

    model_config = ConfigDict(use_enum_values=True)

    code: str
    quote: str
    message: str
    suggestion: str | None = None

    def locate_in(self, document: Document) -> Violation:
        """Turn the report into a violation positioned at its quote."""
        position = document.locate(self.quote)
        if position is None:
            logger.warning(
                "%s: could not locate the quoted span for %s: %r",
                document.path,
                self.code,
                self.quote,
            )

        # The prompt tells the model an empty suggestion means the span goes.
        suggestion = "Delete the span" if self.suggestion == "" else self.suggestion

        return Violation(
            code=self.code,
            path=document.path,
            position=position,
            message=self.message,
            quote=self.quote,
            suggestion=suggestion,
        )


class Report(BaseModel):
    """Carry what the model returns for one document."""

    violations: list[ReportedViolation]


def build_report_model(codes: Sequence[str]) -> type[Report]:
    """Derive a Report whose violations may only carry the given rule codes.

    An enum, rather than a Literal, so the JSON schema says `enum` even for a
    single code. The value is stored as a plain string.
    """
    rule_code = StrEnum("RuleCode", {code: code for code in codes})  # type: ignore[misc]
    reported = create_model(
        "ReportedViolation", __base__=ReportedViolation, code=(rule_code, ...)
    )

    return create_model("Report", __base__=Report, violations=(list[reported], ...))


async def run_query(
    prompt: str, options: ClaudeAgentOptions, path: str
) -> ResultMessage:
    """Run one query and return its result message."""
    result: ResultMessage | None = None
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            result = message

    if result is None:
        raise RuntimeError(f"{path}: the model session ended without a result message")

    if (
        result.is_error
        or result.subtype != "success"
        or result.structured_output is None
    ):
        raise RuntimeError(
            f"{path}: model run failed with subtype {result.subtype!r}, "
            f"errors {result.errors!r}"
        )

    logger.info(
        "%s: %s answered in %.1fs, %d turns, cost %s USD",
        path,
        "unknown model"
        if result.model_usage is None
        else ", ".join(result.model_usage),
        result.duration_ms / 1000,
        result.num_turns,
        "unknown" if result.total_cost_usd is None else f"{result.total_cost_usd:.4f}",
    )

    return result


class ModelJudge:
    """Ask the model which of the enabled model rules a document breaks.

    The prompt and the output schema depend only on the rules, so they are built
    once here and reused for every document.
    """

    def __init__(self, rules: RuleBook, model: str, effort: Effort):
        codes = [rule.code for rule in rules.model_rules]
        if len(codes) == 0:
            raise ValueError("no enabled rule is judged by the model")

        self.model = model
        self.effort = effort
        self.rule_count = len(codes)
        self.report_model = build_report_model(codes)
        self.system_prompt = TEMPLATES.from_string(PROMPT_TEMPLATE.read_text()).render(
            rules=rules.render_model_rules_as_markdown()
        )
        self.options = ClaudeAgentOptions(
            system_prompt=self.system_prompt,
            tools=[],
            model=model,
            effort=effort,
            setting_sources=None,
            output_format={
                "type": "json_schema",
                "schema": self.report_model.model_json_schema(),
            },
        )

    async def judge(self, document: Document, prose: str) -> list[Violation]:
        """Run one model call over the prose and locate what it reports."""
        logger.info(
            "%s: judging %d rules over %d characters (model=%s, effort=%s)",
            document.path,
            self.rule_count,
            len(prose),
            self.model,
            self.effort,
        )

        prompt = f"Lint the following text.\n\n<text>\n{prose}\n</text>"
        result = await run_query(prompt, self.options, document.path)

        report = self.report_model.model_validate(result.structured_output)
        logger.info(
            "%s: model rules found %d violations", document.path, len(report.violations)
        )

        return [reported.locate_in(document) for reported in report.violations]
