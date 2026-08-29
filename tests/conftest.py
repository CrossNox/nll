from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import pytest
from claude_agent_sdk import ResultMessage

from nll.config import Config
from nll.linter import Linter
from nll.rules import RuleBook

FakeModel = Callable[[dict[str, Any]], list[tuple[str, Any]]]


@pytest.fixture
def no_user_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point XDG at an empty directory so the shipped defaults apply."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    return tmp_path


@pytest.fixture
def default_linter(no_user_config: Path) -> Linter:
    return Linter.load(None, no_user_config, None, [], [])


@pytest.fixture
def default_config(default_linter: Linter) -> Config:
    return default_linter.config


@pytest.fixture
def rulebook(default_config: Config) -> RuleBook:
    return default_config.rules


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

        monkeypatch.setattr("nll.model.query", fake_query)
        return calls

    return install
