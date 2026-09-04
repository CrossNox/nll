import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from claude_agent_sdk import ResultMessage

from linnl.config import SHIPPED_CONFIG_FILE
from linnl.document import Document
from linnl.judge import ClaudeModelJudge, CodexModelJudge, ModelJudge
from linnl.linter import Linter


def get_model_judge(select: list[str]) -> ModelJudge:
    linter = Linter.from_config(SHIPPED_CONFIG_FILE, select=select)
    return ClaudeModelJudge(linter.rules.model_rules, linter.config.model)


def test_model_judge_rejects_an_empty_rule_set() -> None:
    judge = get_model_judge(["CHR004"])

    assert judge.rules == {}
    schema = judge.report_model.model_json_schema()
    assert (
        schema["$defs"]["ReportedViolation_rule_identifier_"]["properties"][
            "identifier"
        ]["enum"]
        == []
    )


def test_claude_judge_renders_rules_and_restricts_reported_codes(fake_model) -> None:
    calls = fake_model({"violations": []})
    judge = get_model_judge(["SCH003", "SLO001", "CHR004"])

    asyncio.run(judge.judge(Document(prose="Some text.", path=Path("x.md"))))

    prompt, options = calls[0]
    assert "<text>\nSome text.\n</text>" in prompt
    assert "SCH003" in options.system_prompt
    assert "SLO001" in options.system_prompt
    assert "CHR004" not in options.system_prompt
    schema = options.output_format["schema"]
    assert schema["$defs"]["rule_identifier"]["enum"] == ["SCH003", "SLO001"]


def test_claude_judge_locates_reported_quotes() -> None:
    judge = get_model_judge(["SLO001"])
    reported = judge.report_model.model_validate(
        {"violations": [{"identifier": "SLO001", "quote": "Ship less"}]}
    ).violations[0]

    violation = judge.locate_violation_in_document(
        reported, Document(prose="Ship less, sleep more.", path=Path("x.md"))
    )

    assert violation.path == Path("x.md")
    assert violation.line == 1
    assert violation.offset == 1
    assert violation.quote == "Ship less"


def test_claude_judge_surfaces_a_quote_that_is_not_in_the_document(
    fake_model,
) -> None:
    fake_model({"violations": [{"identifier": "SLO001", "quote": "absent"}]})

    with pytest.raises(RuntimeError, match="Could not find the quote"):
        asyncio.run(
            get_model_judge(["SLO001"]).judge(Document(prose="text", path=Path("x.md")))
        )


def test_claude_judge_fails_when_the_session_has_no_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def silent_query(*, prompt: str, options: Any) -> Any:
        if False:
            yield prompt

    monkeypatch.setattr("linnl.judge.query", silent_query)

    with pytest.raises(RuntimeError, match="ended without a result message"):
        asyncio.run(
            get_model_judge(["SLO001"]).judge(Document(prose="text", path=Path("x.md")))
        )


def test_claude_judge_fails_on_an_error_result(monkeypatch: pytest.MonkeyPatch) -> None:
    async def failed_query(*, prompt: str, options: Any):
        yield ResultMessage(
            subtype="error",
            duration_ms=10,
            duration_api_ms=5,
            is_error=True,
            num_turns=1,
            session_id="test",
            errors=["service failed"],
        )

    monkeypatch.setattr("linnl.judge.query", failed_query)

    with pytest.raises(RuntimeError, match="Claude run failed"):
        asyncio.run(
            get_model_judge(["SLO001"]).judge(Document(prose="text", path=Path("x.md")))
        )


def test_claude_judge_fails_on_invalid_structured_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def invalid_query(*, prompt: str, options: Any):
        yield ResultMessage(
            subtype="success",
            duration_ms=10,
            duration_api_ms=5,
            is_error=False,
            num_turns=1,
            session_id="test",
            structured_output={"violations": [{"identifier": "CHR004", "quote": "x"}]},
        )

    monkeypatch.setattr("linnl.judge.query", invalid_query)

    with pytest.raises(RuntimeError, match="invalid structured output"):
        asyncio.run(
            get_model_judge(["SLO001"]).judge(Document(prose="text", path=Path("x.md")))
        )


def test_codex_judge_sends_read_only_request_and_parses_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[dict[str, Any]] = []

    class FakeThread:
        async def run(self, prompt: str, *, output_schema: dict[str, Any]) -> Any:
            requests.append({"prompt": prompt, "schema": output_schema})
            return SimpleNamespace(
                status="completed",
                error=None,
                final_response=json.dumps(
                    {"violations": [{"identifier": "SLO001", "quote": "Ship less"}]}
                ),
            )

    class FakeCodex:
        async def __aenter__(self) -> "FakeCodex":
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        async def thread_start(self, **kwargs: Any) -> FakeThread:
            requests.append(kwargs)
            return FakeThread()

    linter = Linter.from_config(SHIPPED_CONFIG_FILE, select=["SLO001"])
    monkeypatch.setattr("linnl.judge.AsyncCodex", FakeCodex)
    judge = CodexModelJudge(linter.rules.model_rules, linter.config.model)

    violations = asyncio.run(
        judge.judge(Document(prose="Ship less, sleep more.", path=Path("x.md")))
    )

    assert len(violations) == 1
    assert requests[0]["sandbox"].value == "read-only"
    assert "Ship less, sleep more." in requests[1]["prompt"]
