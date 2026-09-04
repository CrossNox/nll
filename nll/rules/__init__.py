"""Rules, the rule book, and the code rules the library owns."""

from nll.rules import (  # noqa: F401  fills CodeRule.registry
    cliche_rules,
    code_rules,
    wikipedia_rules,
)
from nll.rules.rules import (
    CodeRule,
    ModelRule,
    RegexRule,
    Rule,
    RuleBook,
    RulesDefinitions,
)

__all__ = [
    "CodeRule",
    "ModelRule",
    "RegexRule",
    "Rule",
    "RuleBook",
    "RulesDefinitions",
]
