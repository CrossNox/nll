from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence
from copy import copy
from itertools import chain
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, model_validator

from nll.document import Document
from nll.logconfig import get_logger
from nll.violations import Violations

logger = get_logger(__name__)


class Rule:
    def __init__(
        self,
        section: str,
        code: str,
        description: str,
        **arguments: Any,
    ) -> None:
        self.section = section
        self.code = code
        self._description = description
        self.arguments = arguments

    def __str__(self) -> str:
        return f"{self.identifier}: {self.description}"

    @property
    def description(self) -> str:
        return self._description.format(**self.arguments)

    @property
    def identifier(self) -> str:
        return f"{self.section}{self.code}"


class ModelRule(Rule):
    pass


class CodeRule(Rule, ABC):
    """A rule that can be defined in code."""

    registry: ClassVar[dict[str, type["CodeRule"]]] = {}

    def __init_subclass__(cls, identifier: str | None = None, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

        if identifier is None:
            return

        if identifier in CodeRule.registry:
            raise ValueError(f"code rule {identifier} is defined twice")

        CodeRule.registry[identifier] = cls

    @abstractmethod
    def __call__(self, document: Document) -> Violations:
        raise NotImplementedError


class RulesSection(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    rules: list[Rule]


class RulesDefinitions(BaseModel):
    sections: list[RulesSection]

    def iter_rules(self) -> Iterator[Rule]:
        return chain.from_iterable(section.rules for section in self.sections)

    @model_validator(mode="before")
    @classmethod
    def build_rules(cls, sections: dict[str, Any]) -> dict[str, Any]:
        """Build one rule per code in every section."""
        rules_sections: list[dict[str, Any]] = []

        for section_name, section in sections.items():
            definitions = copy(section)

            try:
                section_description = definitions.pop("description")
            except KeyError as e:
                logger.error("Bad config for section %s", section_name)
                raise ValueError(
                    f"Bad config for section {section_name}: no description"
                ) from e

            rules: list[Rule] = []

            for code, definition in definitions.items():
                description: str
                arguments: dict[str, Any]

                match definition:
                    case {"description": description, **rest}:
                        arguments = {
                            str(key).replace("-", "_"): value
                            for key, value in rest.items()
                        }
                    case {}:
                        logger.error("Bad config for %s%s", section_name, code)
                        raise ValueError(
                            f"Bad config for {section_name}{code}: no description"
                        )
                    case str():
                        description, arguments = definition, {}
                    case _:
                        logger.error("Bad config for %s%s", section_name, code)
                        raise ValueError(
                            f"Bad config for {section_name}{code}: "
                            "must be a description, or a description with arguments"
                        )

                rule_class = CodeRule.registry.get(f"{section_name}{code}", ModelRule)
                rules.append(
                    rule_class(
                        section=section_name,
                        code=code,
                        description=description,
                        **arguments,
                    )
                )

            rules_sections.append(
                {
                    "name": section_name,
                    "description": section_description,
                    "rules": rules,
                }
            )

        return {"sections": rules_sections}


class RuleBook:
    def __init__(
        self,
        rules_definitions: RulesDefinitions,
        select: Sequence[str],
        extend_select: Sequence[str],
        ignore: Sequence[str],
    ):
        self.rules_definitions = rules_definitions
        self.select = select
        self.extend_select = extend_select
        self.ignore = ignore

        self.rules_on = set(
            rule.identifier
            for rule in self.rules_definitions.iter_rules()
            if any(
                rule.identifier.startswith(selector)
                for selector in (*self.select, *self.extend_select)
            )
            and not any(
                rule.identifier.startswith(selector) for selector in self.ignore
            )
        )

        self.code_rules: list[CodeRule] = [
            rule
            for rule in self.rules_definitions.iter_rules()
            if isinstance(rule, CodeRule) and rule.identifier in self.rules_on
        ]
        self.model_rules: list[ModelRule] = [
            rule
            for rule in self.rules_definitions.iter_rules()
            if isinstance(rule, ModelRule) and rule.identifier in self.rules_on
        ]
        self.all_rules = rules_definitions

    def __str__(self) -> str:
        lines = []

        for section in self.all_rules.sections:
            lines.append(f"{section.name} - {section.description}")

            for rule in section.rules:
                rule_status = "ON" if rule.identifier in self.rules_on else "OFF"
                lines.append(f"[{rule_status}] {rule}")

        return "\n".join(lines)
