"""Define rules and select them from a rule book."""

import logging
import re
from collections.abc import Iterator
from typing import Any

from jinja2 import Environment, StrictUndefined, TemplateError
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, ValidationError

logger = logging.getLogger(__name__)

GROUP_PREFIX = re.compile(r"^[A-Z]+$")
RULE_KEY = re.compile(r"^[A-Za-z0-9]+$")
DESCRIPTION_KEY = "description"

TEMPLATES = Environment(undefined=StrictUndefined, autoescape=False)


class NoOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SentenceCountOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, strict=True)

    max_sentences: PositiveInt = Field(alias="max-sentences")


OPTION_MODELS: dict[str, type[BaseModel]] = {
    "LEN001": SentenceCountOptions,
}


def validate_options(code: str, options: dict[str, Any], source: str) -> dict[str, Any]:
    """Check a rule's options against the model it declares and normalize them."""
    option_model = OPTION_MODELS.get(code, NoOptions)
    try:
        return option_model.model_validate(options).model_dump(by_alias=True)
    except ValidationError as error:
        raise ValueError(
            f"{source}: rule {code} options are invalid: {error}"
        ) from error


class Rule(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    group_prefix: str
    group_description: str
    description: str
    options: dict[str, Any] = Field(default_factory=dict)

    def render_description(self) -> str:
        """Render the description template with the options as variables."""
        variables = {
            key.replace("-", "_"): value for key, value in self.options.items()
        }
        try:
            return TEMPLATES.from_string(self.description).render(variables)
        except TemplateError as error:
            raise ValueError(
                f"rule {self.code}: cannot render its description: {error}"
            ) from error


def build_rule(
    prefix: str, key: str, group_description: str, entry: Any, source: str
) -> Rule:
    """Build one rule from its entry: a description, or a table with options."""
    if RULE_KEY.match(key) is None:
        raise ValueError(
            f"{source}: rule key {key!r} in {prefix} must be letters or digits"
        )

    if isinstance(entry, str):
        description, raw_options = entry, {}
    elif isinstance(entry, dict) and isinstance(entry.get(DESCRIPTION_KEY), str):
        description = entry[DESCRIPTION_KEY]
        raw_options = {
            option: value
            for option, value in entry.items()
            if option != DESCRIPTION_KEY
        }
    else:
        raise ValueError(
            f"{source}: rule {prefix}{key} must be a description or a table with one"
        )

    rule = Rule(
        code=prefix + key,
        group_prefix=prefix,
        group_description=group_description,
        description=description,
        options=validate_options(prefix + key, raw_options, source),
    )
    check_renders(rule, source)

    return rule


def check_renders(rule: Rule, source: str) -> None:
    try:
        rule.render_description()
    except ValueError as error:
        raise ValueError(f"{source}: {error}") from error


def parse_rule_group(prefix: str, group: Any, source: str) -> list[Rule]:
    """Turn one group table into rules."""
    if GROUP_PREFIX.match(prefix) is None:
        raise ValueError(f"{source}: group {prefix!r} must be uppercase ASCII letters")

    if not isinstance(group, dict) or not isinstance(group.get(DESCRIPTION_KEY), str):
        raise ValueError(f"{source}: group {prefix} needs a description string")

    return [
        build_rule(prefix, key, group[DESCRIPTION_KEY], entry, source)
        for key, entry in group.items()
        if key != DESCRIPTION_KEY
    ]


class RuleBook(BaseModel):
    """Every defined rule, by code, in definition order."""

    model_config = ConfigDict(frozen=True)

    rules: dict[str, Rule]

    @classmethod
    def parse(cls, groups: Any, source: str) -> "RuleBook":
        """Build a rule book from the groups of a config file."""
        return cls(rules={}).merge(groups, source)

    def __iter__(self) -> Iterator[Rule]:  # type: ignore[override]
        return iter(self.rules.values())

    def __len__(self) -> int:
        return len(self.rules)

    def __contains__(self, code: str) -> bool:
        return code in self.rules

    def __getitem__(self, code: str) -> Rule:
        return self.rules[code]

    def prefixes(self) -> set[str]:
        return {rule.group_prefix for rule in self}

    def merge(self, groups: Any, source: str) -> "RuleBook":
        """Add new groups and apply option overrides to existing ones."""
        if not isinstance(groups, dict):
            raise ValueError(f"{source}: rules must be a table of groups")

        rules = dict(self.rules)
        for prefix, group in groups.items():
            if prefix in self.prefixes():
                rules.update(self.override_options(prefix, group, source))
            else:
                rules.update(
                    {
                        rule.code: rule
                        for rule in parse_rule_group(prefix, group, source)
                    }
                )
                logger.info("Rule group %s loaded from %s", prefix, source)

        return RuleBook(rules=rules)

    def override_options(self, prefix: str, group: Any, source: str) -> dict[str, Rule]:
        """Apply the options in `group` to the rules of `prefix`, nothing else."""
        refusal = (
            f"{source}: group {prefix} is already defined, "
            "only options of its rules may be set"
        )
        if not isinstance(group, dict):
            raise ValueError(refusal)

        overridden = {}
        for key, entry in group.items():
            code = prefix + key
            if (
                code not in self.rules
                or not isinstance(entry, dict)
                or DESCRIPTION_KEY in entry
            ):
                raise ValueError(refusal)

            options = validate_options(
                code, {**self.rules[code].options, **entry}, source
            )
            rule = self.rules[code].model_copy(update={"options": options})
            check_renders(rule, source)
            overridden[code] = rule

        return overridden

    def expand(self, selector: str) -> set[str]:
        """Expand a selector such as SCH, SCH00 or SCH001 into rule codes."""
        matches = {code for code in self.rules if code.startswith(selector)}
        if len(matches) == 0:
            raise ValueError(f"rule selector {selector!r} matches no rule")

        return matches

    def select(
        self, select: list[str], extend_select: list[str], ignore: list[str]
    ) -> list[Rule]:
        """Select rules, then add extend_select, then remove ignore."""
        enabled: set[str] = set()
        for selector in select:
            enabled |= self.expand(selector)

        for selector in extend_select:
            enabled |= self.expand(selector)

        for selector in ignore:
            enabled -= self.expand(selector)

        rules = [rule for rule in self if rule.code in enabled]
        logger.info("Enabled rules: %s", " ".join(rule.code for rule in rules))

        return rules
