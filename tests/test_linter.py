import asyncio
from pathlib import Path

import pytest

from nll.config import Config
from nll.document import Document
from nll.linter import Linter
from nll.rules import Rule
from nll.violations import RuleViolation
from tests.conftest import FakeModel


def load(no_user_config: Path, select: list[str]) -> Linter:
    return Linter.load(None, no_user_config, select, [], [])


def test_load_resolves_the_enabled_rules(no_user_config: Path) -> None:
    linter = load(no_user_config, ["SCH003", "CHR004"])

    assert [rule.code for rule in linter.rules] == ["SCH003", "CHR004"]


def test_lint_merges_python_and_model_violations_in_order(
    no_user_config: Path, fake_model: FakeModel
) -> None:
    calls = fake_model(
        {
            "findings": [
                {
                    "code": "SCH003",
                    "quote": "No a. No b.",
                    "message": "anaphora",
                    "suggestion": "",
                }
            ]
        }
    )
    linter = load(no_user_config, ["SCH003", "CHR004"])
    document = Document("Intro; text.\nNo a. No b.\n", "x")

    violations = asyncio.run(linter.lint(document))

    assert [
        (item.rule.code, item.render_text().split(":")[1]) for item in violations
    ] == [
        ("CHR004", "1"),
        ("SCH003", "2"),
    ]
    assert len(calls) == 1


def test_ignore_code_masks_what_the_model_sees(
    no_user_config: Path, fake_model: FakeModel
) -> None:
    calls = fake_model({"findings": []})
    linter = load(no_user_config, ["SLO001"])
    document = Document("Prose.\n```sh\nsecret-in-code\n```\n", "x")

    asyncio.run(linter.lint(document))
    assert "secret-in-code" not in calls[0][0]

    unmasked = linter.model_copy(
        update={"config": linter.config.model_copy(update={"ignore_code": False})}
    )
    asyncio.run(unmasked.lint(document))
    assert "secret-in-code" in calls[1][0]


def test_lint_skips_the_model_when_no_model_rules_are_enabled(
    no_user_config: Path, fake_model: FakeModel
) -> None:
    calls = fake_model({"findings": []})

    asyncio.run(load(no_user_config, ["CHR"]).lint(Document("x", "x")))

    assert calls == []


def test_lint_all_limits_concurrency(
    no_user_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    running = 0
    peak = 0

    async def slow_judge(
        document: Document, rules: list[Rule], config: Config
    ) -> list[RuleViolation]:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.01)
        running -= 1
        return []

    monkeypatch.setattr("nll.linter.judge_with_model", slow_judge)
    linter = load(no_user_config, ["SLO001"])
    limited = linter.model_copy(
        update={"config": linter.config.model_copy(update={"max_concurrency": 2})}
    )
    documents = [Document("x", f"doc{index}") for index in range(6)]

    limited.lint_all(documents)

    assert peak == 2


def test_render_rules_groups_rules_and_marks_state_and_checker(
    no_user_config: Path,
) -> None:
    rendered = load(no_user_config, ["CHR001"]).render_rules()

    assert "CHR  Characters that must not appear in prose" in rendered
    assert "  CHR001   on   python  Em dash (U+2014)." in rendered
    assert "  SCH001   off  model   Tricolon." in rendered
    assert "  LEN001   off  python  The text has more than 3 sentences." in rendered
