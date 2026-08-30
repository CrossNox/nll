from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import pytest
from claude_agent_sdk import ResultMessage

from nll.linter import Linter
from nll.rules import RuleBook

FakeModel = Callable[[dict[str, Any]], list[tuple[str, Any]]]


@pytest.fixture
def no_user_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point XDG at an empty directory so the shipped defaults apply."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    return tmp_path


@pytest.fixture
def default_linter() -> Linter:
    return Linter.from_config(None)


@pytest.fixture
def rulebook(default_linter: Linter) -> RuleBook:
    return default_linter.rules


@pytest.fixture
def fake_model(monkeypatch: pytest.MonkeyPatch) -> FakeModel:
    """Fake the Claude query: return the given report and record every call."""

    def install(structured_output: dict[str, Any]) -> list[tuple[str, Any]]:
        calls: list[tuple[str, Any]] = []

        async def fake_query(
            *, prompt: str, options: Any = None, transport: Any = None
        ) -> AsyncIterator[ResultMessage]:
            calls.append((prompt, options))
            yield ResultMessage(
                subtype="success",
                duration_ms=10,
                duration_api_ms=5,
                is_error=False,
                num_turns=1,
                session_id="test",
                structured_output=structured_output,
            )

        monkeypatch.setattr("nll.judge.query", fake_query)
        return calls

    return install
