import asyncio
from pathlib import Path

import pytest

from nll.agents import Agent
from nll.config import SHIPPED_CONFIG_FILE
from nll.document import Document
from nll.linter import Linter, apply_settings_overrides, merge_settings


def test_from_config_uses_shipped_defaults(default_linter: Linter) -> None:
    assert default_linter.config.agent is Agent.CLAUDE
    assert default_linter.config.model == "claude-opus-5"
    assert default_linter.config.max_concurrency == 4
    assert default_linter.config.include_extensions == [".md", ".txt", ".rst"]
    assert default_linter.config.select == [
        "SCH",
        "SLO",
        "ZIN",
        "CHR",
        "LEN",
        "RGX",
        "CLH",
        "WIK",
    ]
    assert default_linter.config.ignore == ["CHR000", "LEN001"]
    assert default_linter.config.ignore_code_blocks is True


def test_from_config_merges_a_file_over_shipped_settings(tmp_path: Path) -> None:
    path = tmp_path / "nll.toml"
    path.write_text(
        'ignore = ["CHR004"]\nmodel = "custom"\nignore-code-blocks = false\n',
        encoding="utf-8",
    )

    linter = Linter.from_config(path)

    assert linter.config.ignore == ["CHR004"]
    assert linter.config.model == "custom"
    assert linter.config.max_concurrency == 4
    assert linter.config.ignore_code_blocks is False
    assert "CHR004" not in linter.rules.rules_on
    assert "CHR001" in linter.rules.rules_on


def test_apply_settings_overrides_replaces_only_values_given_by_the_caller() -> None:
    settings = {"select": ["SCH"], "model": "old", "nested": {"keep": True}}

    updated = apply_settings_overrides(settings, model="new", select=["CHR"])

    assert updated == {
        "select": ["CHR"],
        "model": "new",
        "nested": {"keep": True},
    }
    assert settings["select"] == ["SCH"]


def test_merge_settings_descends_into_nested_tables() -> None:
    base = {"model": "old", "rules": {"CHR": {"001": "old"}}}

    merged = merge_settings(base, {"rules": {"CHR": {"002": "new"}}})

    assert merged == {
        "model": "old",
        "rules": {"CHR": {"001": "old", "002": "new"}},
    }
    assert base["rules"] == {"CHR": {"001": "old"}}


def test_lint_runs_code_rules_and_returns_sorted_violations() -> None:
    linter = Linter.from_config(SHIPPED_CONFIG_FILE, select=["CHR004"])

    violations = linter.lint_text("first; second")

    assert len(violations) == 1
    violation = next(iter(violations))
    assert violation.path is None
    assert violation.line == 1
    assert violation.offset == 6
    assert violation.rule.identifier == "CHR004"


def test_lint_omits_code_blocks_before_running_code_rules() -> None:
    linter = Linter.from_config(SHIPPED_CONFIG_FILE, select=["CHR004"])

    violations = asyncio.run(
        linter.lint(
            Document(
                path=Path("notes.md"),
                prose="```python\ninside;\n```\noutside;",
            )
        )
    )

    assert [(item.line, item.offset) for item in violations] == [(4, 8)]


def test_lint_runs_model_rules_and_passes_the_document_to_the_judge(
    fake_model,
) -> None:
    calls = fake_model({"violations": [{"identifier": "SLO001", "quote": "Ship less"}]})
    linter = Linter.from_config(SHIPPED_CONFIG_FILE, select=["SLO001"])

    violations = asyncio.run(
        linter.lint(Document(prose="Ship less, sleep more.", path=Path("x.md")))
    )

    assert [(item.rule.identifier, item.line, item.offset) for item in violations] == [
        ("SLO001", 1, 1)
    ]
    assert "Ship less, sleep more." in calls[0][0]


def test_lint_omits_code_blocks_from_model_prompts(fake_model) -> None:
    calls = fake_model({"violations": []})
    linter = Linter.from_config(SHIPPED_CONFIG_FILE, select=["SLO001"])

    asyncio.run(
        linter.lint(
            Document(
                prose="Before.\n```python\nShip less, sleep more.\n```\nAfter.",
                path=Path("x.md"),
            )
        )
    )

    assert "Ship less, sleep more." not in calls[0][0]
    assert "<text>\nBefore.\n\n\n\nAfter.\n</text>" in calls[0][0]


def test_lint_does_not_call_the_model_when_only_code_rules_are_enabled(
    fake_model,
) -> None:
    calls = fake_model({"violations": []})
    linter = Linter.from_config(SHIPPED_CONFIG_FILE, select=["CHR004"])

    asyncio.run(linter.lint(Document(prose="plain", path=Path("x.md"))))

    assert calls == []


def test_lint_paths_reads_files_and_reports_the_file_count(
    default_linter: Linter, tmp_path: Path
) -> None:
    (tmp_path / "a.md").write_text("a; b", encoding="utf-8")
    (tmp_path / "b.txt").write_text("c; d", encoding="utf-8")
    (tmp_path / "ignored.py").write_text("e; f", encoding="utf-8")
    linter = Linter.from_config(SHIPPED_CONFIG_FILE, select=["CHR004"])

    violations = linter.lint_paths([tmp_path])

    assert [item.path for item in violations] == [
        tmp_path / "a.md",
        tmp_path / "b.txt",
    ]


def test_lint_paths_lints_explicit_files_without_an_extension(tmp_path: Path) -> None:
    path = tmp_path / "LICENSE"
    path.write_text("A; B", encoding="utf-8")
    linter = Linter.from_config(SHIPPED_CONFIG_FILE, select=["CHR004"])

    violations = linter.lint_paths([path])

    assert [item.path for item in violations] == [path]


def test_lint_paths_lints_configured_unknown_extensions(tmp_path: Path) -> None:
    path = tmp_path / "notes.markdown"
    path.write_text("A; B", encoding="utf-8")
    linter = Linter.from_config(
        SHIPPED_CONFIG_FILE,
        select=["CHR004"],
        include_extensions=[".markdown"],
    )

    violations = linter.lint_paths([tmp_path])

    assert [item.path for item in violations] == [path]


def test_lint_paths_limits_concurrent_model_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    running = 0
    peak = 0

    async def slow_judge(self, document: Document):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.01)
        running -= 1
        return []

    monkeypatch.setattr("nll.judge.ClaudeModelJudge.judge", slow_judge)
    (tmp_path / "nll.toml").write_text("max-concurrency = 2\n", encoding="utf-8")
    for index in range(6):
        (tmp_path / f"doc{index}.md").write_text("text", encoding="utf-8")

    linter = Linter.from_config(tmp_path / "nll.toml", select=["SLO001"])
    linter.lint_paths([tmp_path])

    assert peak == 2


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("select = 'CHR'\n", "select"),
        ("agent = 'unknown'\n", "agent"),
        ("max-concurrency = 0\n", "max-concurrency"),
        ("include-extensions = 'md'\n", "include-extensions"),
        ("plugins = 'acme-rules'\n", "plugins"),
        ("unknown = true\n", "unknown"),
    ],
)
def test_invalid_configuration_raises_a_named_error(
    tmp_path: Path, content: str, message: str
) -> None:
    path = tmp_path / "nll.toml"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        Linter.from_config(path)


def test_ignore_and_select_conflicts_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "nll.toml"
    path.write_text('select = ["CHR004"]\nignore = ["CHR004"]\n', encoding="utf-8")

    with pytest.raises(ValueError, match="both in the ignore list"):
        Linter.from_config(path)
