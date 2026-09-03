"""Discover and load rule plugins installed with Python packages."""

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from importlib.metadata import EntryPoint, entry_points
from typing import Any

from nll.rules import CodeRule

logger = logging.getLogger(__name__)

PLUGIN_ENTRY_POINT_GROUP = "nll.plugins"

RuleDefinitions = Mapping[str, Mapping[str, Any]]


@dataclass(frozen=True)
class Plugin:
    """Define the rules a package contributes to nll."""

    name: str
    rules: RuleDefinitions
    code_rules: Mapping[str, type[CodeRule]] = field(default_factory=dict)


@dataclass(frozen=True)
class LoadedPlugins:
    """Carry the definitions and code checkers contributed by plugins."""

    rules: dict[str, dict[str, Any]]
    code_rule_types: dict[str, type[CodeRule]]


def collect_rule_identifiers(rules: RuleDefinitions) -> set[str]:
    """Return the identifiers defined by a rules mapping."""
    identifiers = set()

    for section_name, section in rules.items():
        if not isinstance(section_name, str) or not isinstance(section, Mapping):
            raise ValueError("rules must map section names to rule definitions")

        for code in section:
            if code != "description":
                if not isinstance(code, str):
                    raise ValueError(
                        f"rule code in section {section_name} must be a string"
                    )

                identifiers.add(f"{section_name}{code}")

    return identifiers


def read_enabled_plugin_names(settings: Mapping[str, Any]) -> list[str]:
    """Read and validate the plugin names from settings."""
    plugin_names = settings.get("plugins", [])

    if not isinstance(plugin_names, list) or not all(
        isinstance(name, str) and name != "" for name in plugin_names
    ):
        raise ValueError("Configuration error: plugins must be a list of names")

    if len(plugin_names) != len(set(plugin_names)):
        raise ValueError("Configuration error: a plugin is enabled more than once")

    return plugin_names


def find_installed_plugin_entry_points() -> dict[str, EntryPoint]:
    """Find the entry points exposed by installed nll plugin packages."""
    installed: dict[str, EntryPoint] = {}

    for entry_point in sorted(
        entry_points(group=PLUGIN_ENTRY_POINT_GROUP), key=lambda item: item.name
    ):
        if entry_point.name in installed:
            raise ValueError(
                f"plugin {entry_point.name} is provided by more than one "
                "installed package"
            )

        installed[entry_point.name] = entry_point

    return installed


def load_enabled_plugins(
    plugin_names: Sequence[str],
    builtin_rules: RuleDefinitions,
    builtin_code_rules: Mapping[str, type[CodeRule]],
) -> LoadedPlugins:
    """Load configured plugins and validate their rule contributions."""
    if len(plugin_names) == 0:
        return LoadedPlugins(rules={}, code_rule_types=dict(builtin_code_rules))

    entry_points_by_name = find_installed_plugin_entry_points()
    rules = copy_rule_definitions(builtin_rules)
    rule_owners = {identifier: "nll" for identifier in collect_rule_identifiers(rules)}
    section_descriptions = {
        section_name: section["description"]
        for section_name, section in rules.items()
        if "description" in section
    }
    code_rule_types = dict(builtin_code_rules)

    for plugin_name in plugin_names:
        try:
            entry_point = entry_points_by_name[plugin_name]
        except KeyError as error:
            raise ValueError(
                f"plugin {plugin_name} is enabled but not installed"
            ) from error

        plugin = load_plugin(entry_point)
        validate_plugin(plugin, entry_point.name)

        plugin_identifiers = collect_rule_identifiers(plugin.rules)

        for identifier in sorted(plugin_identifiers):
            if identifier in rule_owners:
                raise ValueError(
                    f"rule {identifier} is provided by both {rule_owners[identifier]} "
                    f"and plugin {plugin.name}"
                )

            rule_owners[identifier] = f"plugin {plugin.name}"

        merge_plugin_rule_definitions(
            rules,
            plugin.rules,
            plugin.name,
            section_descriptions,
        )
        code_rule_types.update(plugin.code_rules)
        logger.info("Loaded plugin %s", plugin.name)

    builtin_identifiers = collect_rule_identifiers(builtin_rules)
    plugin_rules = {
        section_name: section
        for section_name, section in rules.items()
        if section_name not in builtin_rules
        or any(
            f"{section_name}{code}" not in builtin_identifiers
            for code in section
            if code != "description"
        )
    }

    return LoadedPlugins(rules=plugin_rules, code_rule_types=code_rule_types)


def load_plugin(entry_point: EntryPoint) -> Plugin:
    """Load one plugin factory and return its plugin definition."""
    try:
        factory = entry_point.load()
    except Exception as error:
        logger.error("Could not import plugin %s: %s", entry_point.name, error)
        raise ValueError(
            f"Could not import plugin {entry_point.name}: {error}"
        ) from error

    if not callable(factory):
        raise ValueError(f"plugin {entry_point.name} must expose a callable factory")

    try:
        plugin = factory()
    except Exception as error:
        logger.error("Could not initialize plugin %s: %s", entry_point.name, error)
        raise ValueError(
            f"Could not initialize plugin {entry_point.name}: {error}"
        ) from error

    if not isinstance(plugin, Plugin):
        raise ValueError(f"plugin {entry_point.name} did not return an nll Plugin")

    return plugin


def validate_plugin(plugin: Plugin, entry_point_name: str) -> None:
    """Validate a plugin against the public nll plugin contract."""
    if plugin.name != entry_point_name:
        raise ValueError(
            f"plugin {entry_point_name} returned the mismatched name {plugin.name}"
        )

    plugin_identifiers = collect_rule_identifiers(plugin.rules)

    for identifier, rule_type in plugin.code_rules.items():
        if identifier not in plugin_identifiers:
            raise ValueError(
                f"plugin {plugin.name} defines code rule {identifier} without "
                "a rule definition"
            )

        if not isinstance(rule_type, type) or not issubclass(rule_type, CodeRule):
            raise ValueError(
                f"plugin {plugin.name} code rule {identifier} must subclass CodeRule"
            )


def copy_rule_definitions(rules: RuleDefinitions) -> dict[str, dict[str, Any]]:
    """Copy rule definitions into mutable mappings."""
    copied: dict[str, dict[str, Any]] = {}

    for section_name, section in rules.items():
        if not isinstance(section_name, str) or not isinstance(section, Mapping):
            raise ValueError("rules must map section names to rule definitions")

        copied[section_name] = dict(section)

    return copied


def merge_plugin_rule_definitions(
    target: dict[str, dict[str, Any]],
    additions: RuleDefinitions,
    plugin_name: str,
    section_descriptions: dict[str, Any],
) -> None:
    """Merge plugin defaults after confirming their section descriptions agree."""
    for section_name, section in copy_rule_definitions(additions).items():
        try:
            description = section["description"]
        except KeyError as error:
            raise ValueError(
                f"plugin {plugin_name} section {section_name} has no description"
            ) from error

        if section_name in section_descriptions:
            if section_descriptions[section_name] != description:
                raise ValueError(
                    f"plugin {plugin_name} section {section_name} has a description "
                    "that conflicts with its existing section"
                )
        else:
            section_descriptions[section_name] = description

        target.setdefault(section_name, {}).update(section)
