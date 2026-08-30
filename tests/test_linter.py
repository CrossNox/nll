import asyncio
from pathlib import Path

import pytest

from nll.document import Document
from nll.judge import ModelJudge
from nll.linter import Linter
from nll.violations import Violation
from tests.conftest import FakeModel


def test_shipped_defaults_apply_without_a_file(default_linter: Linter) -> None:
    assert default_linter.model == "opus"
    assert default_linter.effort == "high"
    assert default_linter.max_concurrency == 4
    assert default_linter.include == ["*.md", "*.txt", "*.rst"]
    assert default_linter.select == ["SCH", "SLO", "ZIN", "CHR", "LEN"]
    assert default_linter.ignore == ["CHR000", "LEN001"]
    assert "CHR000" not in default_linter.rules.enabled_codes
    assert "CHR001" in default_linter.rules.enabled_codes


def test_from_config_reads_a_file_over_the_defaults(tmp_path: Path) -> None:
    path = tmp_path / "nll.toml"
    path.write_text('ignore = ["CHR004"]\nignore-code = false\n')

    linter = Linter.from_config(path)

    assert linter.ignore == ["CHR004"]
    assert linter.ignore_code is False
    assert "CHR004" not in linter.rules.enabled_codes
    assert "CHR000" in linter.rules.enabled_codes


def test_overrides_without_select_append_to_the_file_lists() -> None:
    linter = Linter.from_config(None, extend_select=["CHR000"], ignore=["SCH002"])

    assert linter.select == ["SCH", "SLO", "ZIN", "CHR", "LEN"]
    assert linter.extend_select == ["CHR000"]
    assert linter.ignore == ["CHR000", "LEN001", "SCH002"]
    assert "SCH002" not in linter.rules.enabled_codes
    assert "SCH001" in linter.rules.enabled_codes
    assert "CHR000" not in linter.rules.enabled_codes, "the file's ignore still applies"


def test_select_override_means_exactly_those_rules() -> None:
    linter = Linter.from_config(None, select=["LEN001", "CHR"], ignore=["CHR000"])

    assert linter.select == ["LEN001", "CHR"]
    assert linter.extend_select == []
    assert linter.ignore == ["CHR000"]
    assert [rule.code for rule in linter.rules.python_rules] == [
        "CHR001",
        "CHR002",
        "CHR003",
        "CHR004",
        "LEN001",
    ]
    assert linter.rules.model_rules == []
    assert linter.judge is None


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("selekt = []\n", "selekt"),
        ("[SEC]\ndescription = 'x'\n", "SEC"),
        ("[LEN001]\nmax-sentences = 5\n", "LEN001"),
        ("select = 'CHR'\n", "select"),
        ("ignore-code = 'yes'\n", "ignore-code"),
        ("effort = 'extreme'\n", "effort"),
        ("max-concurrency = -1\n", "max-concurrency"),
        ("include = 'md'\n", "include"),
    ],
)
def test_invalid_settings_raise_naming_the_file_and_key(
    tmp_path: Path, content: str, message: str
) -> None:
    path = tmp_path / "nll.toml"
    path.write_text(content)

    with pytest.raises(ValueError, match=message) as raised:
        Linter.from_config(path)

    assert str(path) in str(raised.value)


def test_judge_is_built_once_for_the_enabled_model_rules(
    fake_model: FakeModel,
) -> None:
    fake_model({"violations": []})
    linter = Linter.from_config(None, select=["SCH003", "CHR004"])

    assert isinstance(linter.judge, ModelJudge)
    assert linter.judge is linter.judge
    assert linter.judge.rule_count == 1


def test_lint_merges_python_and_model_violations_in_order(
    fake_model: FakeModel,
) -> None:
    calls = fake_model(
        {
            "violations": [
                {
                    "code": "SCH003",
                    "quote": "No a. No b.",
                    "message": "anaphora",
                    "suggestion": "",
                }
            ]
        }
    )
    document = Document("Intro; text.\nNo a. No b.\n", "x")
    linter = Linter.from_config(None, select=["SCH003", "CHR004"])

    violations = asyncio.run(linter.lint(document))

    assert [(item.code, item.render_text().split(":")[1]) for item in violations] == [
        ("CHR004", "1"),
        ("SCH003", "2"),
    ]
    assert len(calls) == 1


def test_lint_text_names_the_document() -> None:
    linter = Linter.from_config(None, select=["CHR004"])

    assert [item.path for item in linter.lint_text("a; b")] == ["<text>"]
    assert [item.path for item in linter.lint_text("a; b", "<stdin>")] == ["<stdin>"]


def test_ignore_code_masks_what_the_model_sees(
    tmp_path: Path, fake_model: FakeModel
) -> None:
    calls = fake_model({"violations": []})
    document = Document("Prose.\n```sh\nsecret-in-code\n```\n", "x")

    asyncio.run(Linter.from_config(None, select=["SLO001"]).lint(document))
    assert "secret-in-code" not in calls[0][0]

    (tmp_path / "nll.toml").write_text("ignore-code = false\n")
    unmasked = Linter.from_config(tmp_path / "nll.toml", select=["SLO001"])
    asyncio.run(unmasked.lint(document))
    assert "secret-in-code" in calls[1][0]


def test_lint_skips_the_model_when_no_model_rules_are_enabled(
    fake_model: FakeModel,
) -> None:
    calls = fake_model({"violations": []})

    asyncio.run(Linter.from_config(None, select=["CHR"]).lint(Document("x", "x")))

    assert calls == []


def test_lint_files_reads_files_and_directories(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("a; b\n")
    (tmp_path / "notes.py").write_text("c; d\n")
    linter = Linter.from_config(None, select=["CHR004"])

    violations = linter.lint_files([tmp_path / "notes.py", tmp_path / "docs"])

    assert [item.path for item in violations] == [
        str(tmp_path / "notes.py"),
        str(tmp_path / "docs" / "a.md"),
    ]


def test_lint_files_limits_concurrency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    running = 0
    peak = 0

    async def slow_judge(
        judge: ModelJudge, document: Document, prose: str
    ) -> list[Violation]:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.01)
        running -= 1
        return []

    monkeypatch.setattr("nll.judge.ModelJudge.judge", slow_judge)
    (tmp_path / "nll.toml").write_text("max-concurrency = 2\n")
    for index in range(6):
        (tmp_path / f"doc{index}.md").write_text("x")
    linter = Linter.from_config(tmp_path / "nll.toml", select=["SLO001"])

    linter.lint_files([tmp_path])

    assert peak == 2
