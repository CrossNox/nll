"""Define rules, group them, and select them from a rule book.

A rule is a code, a description, its options and how it is checked: a Python
check function bound by code, or the model when there is none. Groups come from
the `[rules.<PREFIX>]` tables of a config file.
"""

import logging
import re
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, replace
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from nll.document import Document
from nll.violations import Violation

logger = logging.getLogger(__name__)

GROUP_PREFIX = re.compile(r"^[A-Z]+$")
RULE_KEY = re.compile(r"^[A-Za-z0-9]+$")
DESCRIPTION_KEY = "description"

CheckFunction = Callable[["Rule", Document, str], list[Violation]]


class NoOptions(BaseModel):
    """Options of a rule that declares none. Any key is an error."""

    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class PythonCheck:
    """Pair a check function with the options model its rule accepts."""

    function: CheckFunction
    options: type[BaseModel] = NoOptions


def parse_rule_options(
    options_model: type[BaseModel], raw: dict[str, Any], code: str, source: str
) -> BaseModel:
    try:
        return options_model.model_validate(raw)
    except ValidationError as error:
        raise ValueError(
            f"{source}: rule {code} options are invalid: {error}"
        ) from error


@dataclass(frozen=True)
class Rule:
    code: str
    description_template: str
    options: BaseModel
    check: CheckFunction | None

    @classmethod
    def from_toml(
        cls, code: str, entry: Any, python_check: PythonCheck | None, source: str
    ) -> "Rule":
        """Build a rule from its entry: a description, or a table with options."""
        if isinstance(entry, str):
            template, raw_options = entry, {}
        elif isinstance(entry, dict) and isinstance(entry.get(DESCRIPTION_KEY), str):
            template = entry[DESCRIPTION_KEY]
            raw_options = {
                key: value for key, value in entry.items() if key != DESCRIPTION_KEY
            }
        else:
            raise ValueError(
                f"{source}: rule {code} must be a description or a table with one"
            )

        if python_check is None:
            options_model: type[BaseModel] = NoOptions
            check = None
        else:
            options_model = python_check.options
            check = python_check.function

        rule = cls(
            code=code,
            description_template=template,
            options=parse_rule_options(options_model, raw_options, code, source),
            check=check,
        )
        rule.validate_description_template(source)

        return rule

    @property
    def description(self) -> str:
        """Format the description template with the options as variables."""
        return self.description_template.format(**self.options.model_dump())

    def validate_description_template(self, source: str) -> None:
        """Fail now, naming the file, if the template uses an option the rule lacks."""
        try:
            self.description_template.format(**self.options.model_dump())
        except KeyError as error:
            raise ValueError(
                f"{source}: rule {self.code} description names "
                f"an unknown option {error}"
            ) from error

    @property
    def is_checked_in_python(self) -> bool:
        return self.check is not None

    def with_options(self, overrides: dict[str, Any], source: str) -> "Rule":
        """Copy the rule with the given options set over its current ones."""
        raw = {**self.options.model_dump(by_alias=True), **overrides}
        options = parse_rule_options(type(self.options), raw, self.code, source)

        return replace(self, options=options)

    def run_check(self, document: Document, prose: str) -> list[Violation]:
        """Run the Python check over the document's prose."""
        if self.check is None:
            raise TypeError(f"rule {self.code} is judged by the model, not Python")

        return self.check(self, document, prose)


@dataclass(frozen=True)
class RuleGroup:
    prefix: str
    description: str
    rules: tuple[Rule, ...]

    @classmethod
    def from_toml(
        cls,
        prefix: str,
        table: Any,
        python_checks: Mapping[str, PythonCheck],
        source: str,
    ) -> "RuleGroup":
        """Build a group from its `[rules.<PREFIX>]` table."""
        if GROUP_PREFIX.match(prefix) is None:
            raise ValueError(
                f"{source}: group {prefix!r} must be uppercase ASCII letters"
            )

        if not isinstance(table, dict) or not isinstance(
            table.get(DESCRIPTION_KEY), str
        ):
            raise ValueError(f"{source}: group {prefix} needs a description string")

        rules = []
        for key, entry in table.items():
            if key == DESCRIPTION_KEY:
                continue

            if RULE_KEY.match(key) is None:
                raise ValueError(
                    f"{source}: rule key {key!r} in {prefix} must be letters or digits"
                )

            code = prefix + key
            rules.append(Rule.from_toml(code, entry, python_checks.get(code), source))

        return cls(
            prefix=prefix, description=table[DESCRIPTION_KEY], rules=tuple(rules)
        )

    def override_options(self, table: Any, source: str) -> "RuleGroup":
        """Apply the options in `table` to this group's rules, nothing else."""
        refusal = (
            f"{source}: group {self.prefix} is already defined, "
            "only options of its rules may be set"
        )
        if not isinstance(table, dict):
            raise ValueError(refusal)

        rules = {rule.code: rule for rule in self.rules}
        for key, entry in table.items():
            code = self.prefix + key
            if (
                code not in rules
                or not isinstance(entry, dict)
                or DESCRIPTION_KEY in entry
            ):
                raise ValueError(refusal)

            rules[code] = rules[code].with_options(entry, source)

        return replace(self, rules=tuple(rules.values()))


@dataclass(frozen=True)
class RuleBook:
    """Hold every rule group in definition order and mark the enabled rules."""

    groups: tuple[RuleGroup, ...]
    enabled_codes: frozenset[str] = frozenset()

    @classmethod
    def from_toml(
        cls, groups: Any, python_checks: Mapping[str, PythonCheck], source: str
    ) -> "RuleBook":
        """Build a book from the `rules` table of a config file."""
        if not isinstance(groups, dict):
            raise ValueError(f"{source}: rules must be a table of groups")

        return cls(
            groups=tuple(
                RuleGroup.from_toml(prefix, table, python_checks, source)
                for prefix, table in groups.items()
            )
        )

    def __iter__(self) -> Iterator[Rule]:
        return (rule for group in self.groups for rule in group.rules)

    def __len__(self) -> int:
        return sum(len(group.rules) for group in self.groups)

    def __getitem__(self, code: str) -> Rule:
        for rule in self:
            if rule.code == code:
                return rule

        raise KeyError(code)

    def __str__(self) -> str:
        lines = []
        for group in self.groups:
            lines.append(f"{group.prefix}  {group.description}")
            for rule in group.rules:
                state = "on " if rule.code in self.enabled_codes else "off"
                checker = "python" if rule.is_checked_in_python else "model "
                lines.append(f"  {rule.code:8} {state}  {checker}  {rule.description}")

        return "\n".join(lines)
        return self.render_listing()

    @property
    def python_rules(self) -> list[Rule]:
        """List the enabled rules Python checks."""
        return [
            rule
            for rule in self
            if rule.code in self.enabled_codes and rule.is_checked_in_python
        ]

    @property
    def model_rules(self) -> list[Rule]:
        """List the enabled rules the model judges."""
        return [
            rule
            for rule in self
            if rule.code in self.enabled_codes and not rule.is_checked_in_python
        ]

    def merge(self, groups: Any, source: str) -> "RuleBook":
        """Add the new groups of a config file and apply its option overrides.

        New groups are judged by the model. An existing group may only have
        the options of its rules set.
        """
        if not isinstance(groups, dict):
            raise ValueError(f"{source}: rules must be a table of groups")

        merged = {group.prefix: group for group in self.groups}
        for prefix, table in groups.items():
            if prefix in merged:
                merged[prefix] = merged[prefix].override_options(table, source)
            else:
                merged[prefix] = RuleGroup.from_toml(prefix, table, {}, source)
                logger.info("Rule group %s loaded from %s", prefix, source)

        return replace(self, groups=tuple(merged.values()))

    def expand(self, selector: str) -> set[str]:
        """Expand a selector such as SCH, SCH00 or SCH001 into rule codes."""
        matches = {rule.code for rule in self if rule.code.startswith(selector)}
        if len(matches) == 0:
            raise ValueError(f"rule selector {selector!r} matches no rule")

        return matches

    def select(
        self, select: list[str], extend_select: list[str], ignore: list[str]
    ) -> "RuleBook":
        """Mark as enabled the selected rules plus extend_select, minus ignore."""
        enabled: set[str] = set()
        for selector in [*select, *extend_select]:
            enabled |= self.expand(selector)

        for selector in ignore:
            enabled -= self.expand(selector)

        book = replace(self, enabled_codes=frozenset(enabled))
        logger.info(
            "Enabled rules: %s",
            " ".join(rule.code for rule in book if rule.code in enabled),
        )

        return book

    def render_model_rules_as_markdown(self) -> str:
        """List the enabled model rules under a markdown heading per group."""
        model_codes = {rule.code for rule in self.model_rules}
        lines = []
        for group in self.groups:
            rules = [rule for rule in group.rules if rule.code in model_codes]
            if len(rules) == 0:
                continue

            lines.append(f"\n## {group.prefix}: {group.description}")
            lines.extend(f"- {rule.code}: {rule.description}" for rule in rules)

        return "\n".join(lines).strip()
