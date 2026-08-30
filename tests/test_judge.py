import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest
from pydantic import ValidationError

from nll.document import Document
from nll.judge import ModelJudge, ReportedViolation, build_report_model
from nll.linter import Linter
from tests.conftest import FakeModel


def judge_for(select: list[str]) -> ModelJudge:
    linter = Linter.from_config(None, select=select)

    return ModelJudge(linter.rules, model=linter.model, effort=linter.effort)


def judge_text(judge: ModelJudge, text: str) -> list[Any]:
    document = Document(text, "x.md")

    return asyncio.run(judge.judge(document, document.text))


def test_judge_needs_at_least_one_model_rule() -> None:
    with pytest.raises(ValueError, match="no enabled rule is judged by the model"):
        judge_for(["CHR004"])


def test_judge_fails_when_the_session_yields_no_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def silent_query(
        *, prompt: str, options: Any = None, transport: Any = None
    ) -> AsyncIterator[Any]:
        return
        yield

    monkeypatch.setattr("nll.judge.query", silent_query)

    with pytest.raises(RuntimeError, match="ended without a result message"):
        judge_text(judge_for(["SLO001"]), "x")


def test_judge_sends_the_prompt_with_grouped_rules_and_a_restricted_schema(
    fake_model: FakeModel,
) -> None:
    calls = fake_model({"violations": []})
    judge = judge_for(["SCH003", "SLO001", "CHR004"])

    judge_text(judge, "Some text.")

    prompt, options = calls[0]
    assert "<text>\nSome text.\n</text>" in prompt
    assert "## SCH:" in options.system_prompt
    assert "## SLO:" in options.system_prompt
    assert "CHR004" not in options.system_prompt
    schema = options.output_format["schema"]
    assert schema["$defs"]["RuleCode"]["enum"] == ["SCH003", "SLO001"]
    assert options.model == "opus"
    assert options.effort == "high"


def test_judge_rejects_a_code_outside_its_rules(fake_model: FakeModel) -> None:
    fake_model({"violations": [{"code": "CHR004", "quote": "x", "message": "m"}]})

    with pytest.raises(ValidationError, match="SLO001"):
        judge_text(judge_for(["SLO001"]), "x")


def test_judge_locates_every_reported_violation(
    fake_model: FakeModel, caplog: pytest.LogCaptureFixture
) -> None:
    fake_model(
        {
            "violations": [
                {"code": "SLO001", "quote": "Ship less", "message": "slogan"},
                {"code": "SLO001", "quote": "absent", "message": "lost"},
            ]
        }
    )

    violations = judge_text(judge_for(["SLO001"]), "Ship less, sleep more.")

    assert [(item.code, item.path) for item in violations] == [
        ("SLO001", "x.md"),
        ("SLO001", "x.md"),
    ]
    assert violations[0].position is not None
    assert violations[1].position is None
    assert "could not locate the quoted span for SLO001" in caplog.text


def test_reported_violation_turns_an_empty_suggestion_into_a_deletion() -> None:
    document = Document("First.\nNo a. No b.\n", "x.md")

    kept = ReportedViolation(code="SCH003", quote="No a. No b.", message="m")
    deleted = ReportedViolation(
        code="SCH003", quote="No a.", message="m", suggestion=""
    )

    assert kept.locate_in(document).suggestion is None
    assert kept.locate_in(document).position is not None
    assert deleted.locate_in(document).suggestion == "Delete the span"


def test_report_model_restricts_codes_in_schema_and_validation() -> None:
    report_model = build_report_model(["SCH003", "SLO001"])

    schema = report_model.model_json_schema()
    reported = schema["$defs"]["ReportedViolation"]
    assert reported["properties"]["code"] == {"$ref": "#/$defs/RuleCode"}
    assert schema["$defs"]["RuleCode"]["enum"] == ["SCH003", "SLO001"]
    assert reported["required"] == ["code", "quote", "message"]
    assert schema["required"] == ["violations"]

    report = report_model.model_validate(
        {"violations": [{"code": "SLO001", "quote": "q", "message": "m"}]}
    )
    assert report.violations[0].code == "SLO001"
    assert type(report.violations[0].code) is str

    with pytest.raises(ValidationError):
        report_model.model_validate(
            {"violations": [{"code": "CHR004", "quote": "q", "message": "m"}]}
        )
