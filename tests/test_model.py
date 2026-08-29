import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest

from nll.config import Config
from nll.document import Document
from nll.model import judge_with_model
from tests.conftest import FakeModel


def test_judge_fails_when_the_session_yields_no_result(
    default_config: Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def silent_query(
        *, prompt: str, options: Any = None, transport: Any = None
    ) -> AsyncIterator[Any]:
        return
        yield

    monkeypatch.setattr("nll.model.query", silent_query)

    with pytest.raises(RuntimeError, match="ended without a result message"):
        asyncio.run(
            judge_with_model(
                Document("x", "x.md"), [default_config.rules["SLO001"]], default_config
            )
        )


def test_judge_keeps_an_unlocated_quote_and_warns(
    default_config: Config, fake_model: FakeModel, caplog: pytest.LogCaptureFixture
) -> None:
    fake_model(
        {
            "findings": [
                {"code": "SLO001", "quote": "not in the text", "message": "slogan"}
            ]
        }
    )

    violations = asyncio.run(
        judge_with_model(
            Document("Plain words.", "x.md"),
            [default_config.rules["SLO001"]],
            default_config,
        )
    )

    assert len(violations) == 1
    assert violations[0].position is None
    assert violations[0].render_text().startswith("x.md:?:?: SLO001 slogan")
    assert "could not locate the quoted span for SLO001" in caplog.text


def test_judge_sends_the_prompt_with_grouped_rules_and_a_restricted_schema(
    default_config: Config, fake_model: FakeModel
) -> None:
    calls = fake_model({"findings": []})
    rules = default_config.rules.select(["SCH003", "SLO001"], [], [])

    asyncio.run(judge_with_model(Document("Some text.", "x.md"), rules, default_config))

    prompt, options = calls[0]
    assert "<text>\nSome text.\n</text>" in prompt
    assert "## SCH:" in options.system_prompt
    assert "## SLO:" in options.system_prompt
    schema = options.output_format["schema"]
    assert schema["properties"]["findings"]["items"]["properties"]["code"]["enum"] == [
        "SCH003",
        "SLO001",
    ]
    assert options.model == "opus"
    assert options.effort == "high"
