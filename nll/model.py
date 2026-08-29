"""Judge rules with Claude."""

import logging
from importlib import resources
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
from pydantic import BaseModel

from nll.config import Config
from nll.document import Document
from nll.rules import TEMPLATES, Rule
from nll.violations import RuleViolation

logger = logging.getLogger(__name__)


class ModelFinding(BaseModel):
    code: str
    quote: str
    message: str
    suggestion: str | None = None


class ModelReport(BaseModel):
    findings: list[ModelFinding]


def render_rules_section(rules: list[Rule]) -> str:
    """List the rules under their group headings."""
    sections = []
    last_prefix = None

    for rule in rules:
        if rule.group_prefix != last_prefix:
            sections.append(f"\n## {rule.group_prefix}: {rule.group_description}")
            last_prefix = rule.group_prefix
        sections.append(f"- {rule.code}: {rule.render_description()}")

    return "\n".join(sections).strip()


def build_system_prompt(rules: list[Rule]) -> str:
    """Render the prompt template with the enabled rules."""
    template = resources.files("nll").joinpath("resources", "prompt.md.j2").read_text()

    return TEMPLATES.from_string(template).render(rules=render_rules_section(rules))


def build_output_schema(rules: list[Rule]) -> dict[str, Any]:
    """Build the JSON schema for the report, restricting codes to the enabled rules."""
    return {
        "type": "object",
        "properties": {
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "enum": [rule.code for rule in rules],
                        },
                        "quote": {"type": "string"},
                        "message": {"type": "string"},
                        "suggestion": {"type": "string"},
                    },
                    "required": ["code", "quote", "message"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["findings"],
        "additionalProperties": False,
    }


def convert_report_to_violations(
    document: Document, rules: list[Rule], report: ModelReport
) -> list[RuleViolation]:
    """Map the model's report onto violations, locating each quote in the document."""
    rules_by_code = {rule.code: rule for rule in rules}
    violations: list[RuleViolation] = []

    for finding in report.findings:
        position = document.locate(finding.quote)
        if position is None:
            logger.warning(
                "%s: could not locate the quoted span for %s: %r",
                document.path,
                finding.code,
                finding.quote,
            )

        violations.append(
            RuleViolation(
                rule=rules_by_code[finding.code],
                path=document.path,
                position=position,
                message=finding.message,
                quote=finding.quote,
                suggestion=finding.suggestion,
            )
        )

    return violations


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


async def judge_with_model(
    document: Document, rules: list[Rule], config: Config
) -> list[RuleViolation]:
    """Ask the model which of the given rules the document breaks."""
    if len(rules) == 0:
        return []

    text = document.extract_prose(config.ignore_code)
    logger.info(
        "%s: judging %d rules over %d characters (model=%s, effort=%s)",
        document.path,
        len(rules),
        len(text),
        config.model,
        config.effort,
    )

    options = ClaudeAgentOptions(
        system_prompt=build_system_prompt(rules),
        tools=[],
        model=config.model,
        effort=config.effort,
        setting_sources=None,
        output_format={"type": "json_schema", "schema": build_output_schema(rules)},
    )
    result = await run_query(
        f"Lint the following text.\n\n<text>\n{text}\n</text>", options, document.path
    )

    violations = convert_report_to_violations(
        document, rules, ModelReport.model_validate(result.structured_output)
    )
    logger.info("%s: model rules found %d violations", document.path, len(violations))

    return violations
