from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from nll.document import Document
from nll.linter import Linter
from nll.plugins import Plugin
from nll.rules import CodeRule, ModelRule
from nll.violations import Violation, Violations


class MarkerRule(CodeRule):
    def __call__(self, document: Document) -> Violations:
        if "marker" not in document.prose:
            return Violations([])

        return Violations([Violation(rule=self, path=document.path)])


class FakeEntryPoint:
    def __init__(self, name: str, factory: Callable[[], Plugin]) -> None:
        self.name = name
        self.factory = factory

    def load(self) -> Callable[[], Plugin]:
        return self.factory


def make_plugin() -> Plugin:
    return Plugin(
        name="acme-rules",
        rules={
            "ACM": {
                "description": "Rules from Acme",
                "001": "Contains a marker.",
                "002": "Needs a model judgment.",
            }
        },
        code_rules={"ACM001": MarkerRule},
    )


def install_fake_plugin(
    monkeypatch: pytest.MonkeyPatch, plugin: Plugin | None = None
) -> None:
    installed_plugin = make_plugin() if plugin is None else plugin

    def find_entry_points(*, group: str) -> list[FakeEntryPoint]:
        assert group == "nll.plugins"
        return [FakeEntryPoint("acme-rules", lambda: installed_plugin)]

    monkeypatch.setattr("nll.plugins.entry_points", find_entry_points)


def test_plugin_contributes_code_and_model_rules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_fake_plugin(monkeypatch)
    config = tmp_path / "nll.toml"
    config.write_text(
        'plugins = ["acme-rules"]\nselect = ["ACM001"]\n', encoding="utf-8"
    )

    linter = Linter.from_config(config)
    rules = {
        rule.identifier: rule for rule in linter.rules.rules_definitions.iter_rules()
    }

    assert isinstance(rules["ACM002"], ModelRule)
    assert [rule.identifier for rule in linter.rules.code_rules] == ["ACM001"]
    assert [violation.rule.identifier for violation in linter.lint_text("marker")] == [
        "ACM001"
    ]


def test_project_configuration_overrides_plugin_rule_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_fake_plugin(monkeypatch)
    config = tmp_path / "nll.toml"
    config.write_text(
        '\n'.join(
            [
                'plugins = ["acme-rules"]',
                'select = ["ACM"]',
                "",
                "[rules.ACM]",
                'description = "Project Acme rules"',
                '001 = "Project-specific marker rule."',
                "",
            ]
        ),
        encoding="utf-8",
    )

    linter = Linter.from_config(config)
    rules = {
        rule.identifier: rule for rule in linter.rules.rules_definitions.iter_rules()
    }

    assert rules["ACM001"].description == "Project-specific marker rule."
    assert rules["ACM002"].description == "Needs a model judgment."


def test_plugin_identifier_collision_names_both_providers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    colliding_plugin = Plugin(
        name="acme-rules",
        rules={
            "CHR": {
                "description": "Characters that must not appear in prose",
                "004": "Another semicolon rule.",
            }
        },
    )
    install_fake_plugin(monkeypatch, colliding_plugin)
    config = tmp_path / "nll.toml"
    config.write_text('plugins = ["acme-rules"]\n', encoding="utf-8")

    with pytest.raises(
        ValueError,
        match=r"rule CHR004 is provided by both nll and plugin acme-rules",
    ):
        Linter.from_config(config)


def test_plugin_identifier_collision_names_both_plugins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    other_plugin = Plugin(
        name="house-rules",
        rules={
            "ACM": {
                "description": "Rules from Acme",
                "001": "A conflicting rule.",
            }
        },
    )

    def find_entry_points(*, group: str) -> list[FakeEntryPoint]:
        assert group == "nll.plugins"
        return [
            FakeEntryPoint("acme-rules", make_plugin),
            FakeEntryPoint("house-rules", lambda: other_plugin),
        ]

    monkeypatch.setattr("nll.plugins.entry_points", find_entry_points)
    config = tmp_path / "nll.toml"
    config.write_text(
        'plugins = ["acme-rules", "house-rules"]\n', encoding="utf-8"
    )

    with pytest.raises(
        ValueError,
        match=(
            r"rule ACM001 is provided by both plugin acme-rules and "
            "plugin house-rules"
        ),
    ):
        Linter.from_config(config)


def test_missing_enabled_plugin_fails_before_linting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("nll.plugins.entry_points", lambda *, group: [])
    config = tmp_path / "nll.toml"
    config.write_text('plugins = ["missing"]\n', encoding="utf-8")

    with pytest.raises(ValueError, match="plugin missing is enabled but not installed"):
        Linter.from_config(config)


def test_disabled_plugin_is_not_loaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse_to_discover_plugins(*, group: str) -> list[FakeEntryPoint]:
        raise AssertionError("nll must not discover disabled plugins")

    monkeypatch.setattr("nll.plugins.entry_points", refuse_to_discover_plugins)
    config = tmp_path / "nll.toml"
    config.write_text('select = ["CHR004"]\n', encoding="utf-8")

    linter = Linter.from_config(config)

    assert [rule.identifier for rule in linter.rules.code_rules] == ["CHR004"]


def test_plugin_factory_must_return_a_plugin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def build_wrong_value() -> Any:
        return object()

    def find_entry_points(*, group: str) -> list[FakeEntryPoint]:
        return [FakeEntryPoint("acme-rules", build_wrong_value)]  # type: ignore[arg-type]

    monkeypatch.setattr("nll.plugins.entry_points", find_entry_points)
    config = tmp_path / "nll.toml"
    config.write_text('plugins = ["acme-rules"]\n', encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="plugin acme-rules did not return an nll Plugin",
    ):
        Linter.from_config(config)
