from pathlib import Path
from typing import ClassVar

import pytest

from nll.config import SHIPPED_CONFIG_FILE
from nll.document import Document
from nll.linter import Linter
from nll.plugins import Plugin
from nll.rules import CodeRule, ModelRule
from nll.violations import Violation, Violations


class MarkerRule(CodeRule, identifier="ACM001"):
    def __call__(self, document: Document) -> Violations:
        if "marker" not in document.prose:
            return Violations([])

        return Violations([Violation(rule=self, path=document.path)])


class FakeEntryPoint:
    def __init__(self, name: str, plugin_class: type[object]) -> None:
        self.name = name
        self.plugin_class = plugin_class

    def load(self) -> type[object]:
        return self.plugin_class


class AcmePlugin(Plugin):
    name = "acme-rules"
    rules: ClassVar = {
        "ACM": {
            "description": "Rules from Acme",
            "001": "Contains a marker.",
            "002": "Needs a model judgment.",
        }
    }


def install_fake_plugin(monkeypatch: pytest.MonkeyPatch) -> None:
    def find_entry_points(*, group: str) -> list[FakeEntryPoint]:
        assert group == "nll.plugins"
        return [FakeEntryPoint("acme-rules", AcmePlugin)]

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
        "\n".join(
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


def test_shipped_configuration_enables_its_plugin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_fake_plugin(monkeypatch)
    shipped_config = tmp_path / "shipped.toml"
    shipped_config.write_text(
        SHIPPED_CONFIG_FILE.read_text(encoding="utf-8").replace(
            "plugins = []", 'plugins = ["acme-rules"]'
        ),
        encoding="utf-8",
    )
    project_config = tmp_path / "nll.toml"
    project_config.write_text('select = ["ACM001"]\n', encoding="utf-8")
    monkeypatch.setattr("nll.linter.SHIPPED_CONFIG_FILE", shipped_config)

    linter = Linter.from_config(project_config)

    assert linter.config.plugins == ["acme-rules"]
    assert [rule.identifier for rule in linter.rules.code_rules] == ["ACM001"]


def test_plugin_definitions_override_shipped_definitions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class AcmePluginWithChrRule(Plugin):
        name = "acme-rules"
        rules: ClassVar = {
            "CHR": {
                "description": "Characters that must not appear in prose",
                "004": "Another semicolon rule.",
            }
        }

    monkeypatch.setattr(
        "nll.plugins.entry_points",
        lambda *, group: [FakeEntryPoint("acme-rules", AcmePluginWithChrRule)],
    )
    config = tmp_path / "nll.toml"
    config.write_text(
        'plugins = ["acme-rules"]\nselect = ["CHR004"]\n', encoding="utf-8"
    )

    linter = Linter.from_config(config)

    assert [
        rule.description
        for rule in linter.rules.rules_definitions.iter_rules()
        if rule.identifier == "CHR004"
    ] == ["Another semicolon rule."]


def test_later_plugins_override_earlier_plugin_definitions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class HousePlugin(Plugin):
        name = "house-rules"
        rules: ClassVar = {
            "ACM": {
                "description": "Rules from Acme",
                "001": "A conflicting rule.",
            }
        }

    def find_entry_points(*, group: str) -> list[FakeEntryPoint]:
        assert group == "nll.plugins"
        return [
            FakeEntryPoint("acme-rules", AcmePlugin),
            FakeEntryPoint("house-rules", HousePlugin),
        ]

    monkeypatch.setattr("nll.plugins.entry_points", find_entry_points)
    config = tmp_path / "nll.toml"
    config.write_text('plugins = ["acme-rules", "house-rules"]\n', encoding="utf-8")

    linter = Linter.from_config(config)

    assert [
        rule.description
        for rule in linter.rules.rules_definitions.iter_rules()
        if rule.identifier == "ACM001"
    ] == ["A conflicting rule."]


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
    class UnusedPlugin(Plugin):
        name = "unused-rules"
        rules: ClassVar = {}

    class UnusedEntryPoint(FakeEntryPoint):
        def load(self) -> type[object]:
            raise AssertionError("nll loaded a disabled plugin")

    monkeypatch.setattr(
        "nll.plugins.entry_points",
        lambda *, group: [UnusedEntryPoint("unused-rules", UnusedPlugin)],
    )
    config = tmp_path / "nll.toml"
    config.write_text('select = ["CHR004"]\n', encoding="utf-8")

    linter = Linter.from_config(config)

    assert [rule.identifier for rule in linter.rules.code_rules] == ["CHR004"]


def test_plugin_entry_point_must_define_a_plugin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class NotAPlugin:
        pass

    def find_entry_points(*, group: str) -> list[FakeEntryPoint]:
        return [FakeEntryPoint("acme-rules", NotAPlugin)]

    monkeypatch.setattr("nll.plugins.entry_points", find_entry_points)
    config = tmp_path / "nll.toml"
    config.write_text('plugins = ["acme-rules"]\n', encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="plugin acme-rules does not define an nll Plugin",
    ):
        Linter.from_config(config)
