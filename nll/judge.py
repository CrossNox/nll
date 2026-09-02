"""Judge the model rules with Claude."""

import logging
from collections.abc import Sequence
from enum import StrEnum
from functools import lru_cache

import jinja2
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
from pydantic import BaseModel

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


class Effort(StrEnum):
    """Effort level the judge runs the model at."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"
    MAX = "max"


class ReportedViolation[IdentifierT](BaseModel):
    """Carry a violation as the model reports it, before its quote is located."""

    identifier: IdentifierT
    quote: str


class Report[IdentifierT](BaseModel):
    """Carry what the model returns for one document."""

    violations: list[ReportedViolation[IdentifierT]]


class ModelJudge:
    """Ask the model which of the rules it is given a document breaks."""

    def __init__(self, rules: Sequence[ModelRule], model: str, model_effort: Effort):
        self.rules = {rule.identifier: rule for rule in rules}
        self.model = model
        self.model_effort = model_effort
        rule_names = {name: name for name in self.rules}
        rule_identifier = StrEnum("rule_identifier", rule_names)
        self.report_model = Report[rule_identifier]

        jinja_env = _prepare_env()
        logger.debug("Rendering system prompt")
        self.system_prompt = (
            jinja_env.get_template("prompt.md.j2").render(rules=rules).strip()
        )

        self.claude_options = ClaudeAgentOptions(
            system_prompt=self.system_prompt,
            tools=[],
            model=model,
            effort=model_effort.value,
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
            "%s: judging %d rules over %d characters (model=%s, effort=%s)",
            path,
            len(self.rules),
            len(document.prose),
            self.model,
            self.model_effort,
        )

        prompt = f"Lint the following text.\n\n<text>\n{document.prose}\n</text>"

        result: ResultMessage | None = None

        async for message in query(prompt=prompt, options=self.claude_options):
            if isinstance(message, ResultMessage):
                result = message

        if result is None:
            raise RuntimeError(
                f"{path}: the model session ended without a result message"
            )

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
            "%s: linted in %.1fs, cost %s",
            path,
            result.duration_ms / 1000,
            (
                "unknown"
                if result.total_cost_usd is None
                else f"{result.total_cost_usd:.4f} USD"
            ),
        )

        report = self.report_model.model_validate(result.structured_output)

        logger.info("%s: the model found %d violations", path, len(report.violations))

        return Violations(
            self.locate(reported, document) for reported in report.violations
        )

    def locate(self, reported: ReportedViolation, document: Document) -> Violation:
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
