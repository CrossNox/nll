# linnl
`linnl` is a text linter aimed to catch LLM tells and reduce the complexity of the text produced by them, so that the cognitive load on the reader is reduced and ideas are clearer.

Some built-in rules are checked in code, others (most) are judged by an LLM. You can also install `linnl` plugins to provide your own set of rules.

## Install

```sh
uv tool install linnl
```

### Claude as a judge
You will either need a working `claude` login or an `ANTHROPIC_API_KEY` set in your environment.

### Codex as a judge
Codex reuses the local Codex session. You can also set `OPENAI_API_KEY`.

## Use

```sh
linnl lint notes.md
linnl lint docs/
echo "text" | linnl lint
```

Example output:

```
notes.md
=========
line 3:
    > No config. No cron. No surprises.
SCH003 Three successive fragments open with the same word for emphasis, which is anaphora.

line 5:
    > Set it up once; forget about it.
CHR004 Semicolon.

Found 2 violations across 1 file.
```

## Configure
### CLI

Check
```sh
linnl lint --help
```

To see available quick configuration options.

### File configuration
The priority is:
- The closest `pyproject.toml` with a tool.linnl section
- A `linnl.toml` file next to the closest pyproject.toml
- `~/.config/linnl/config.toml`
- The config file shipped with the tool

You can easily create a `linnl.toml` with:
```sh
linnl config > linnl.toml
```

#### Adding your own rules

Add groups under `[rules.<PREFIX>]` in your config file. `description` is the only reserved key. Every other key is a rule:

```toml
extend-select = ["SEC"]

[rules.SEC]
description = "Wording that must not leak infrastructure details"
001 = "Names an internal host, IP or path"
abc = "Shows a credential or token in an example"
```

That defines `SEC001` and `SECabc`, judged by the model. `linnl` shows the group description to the model above its rules, so make it say what the group is for.

The reserved `RGX` group defines regular expression rules. Every value under
`[rules.RGX]` is compiled as a Python regular expression and is enabled by
default:

```toml
[rules.RGX]
description = "Patterns to avoid"
001 = "X is not (.*), it's (.*)"
```

Each non-overlapping match is reported separately, with the full match as the
quoted text. Invalid regular expressions fail configuration.

If the rule requires configurable parameters:

```toml
extend-select = ["SEC"]

[rules.SEC]
description = "Wording that must not leak infrastructure details"
001 = "Names an internal host, IP or path"
abc = "Shows a credential or token in an example"

[rules.SEC.xyz]
description = "Do now show more {n_files} files in the current directory"
n-files = 3
```

A description can name the rule's options in braces. Write an option name with underscores, so `max-sentences` becomes `{max_sentences}` and `"More than {max_sentences} sentences."` renders with the configured value. Options work on Python and model rules. linnl renders their values before sending model rules to the judge.

#### Installing rules plugins

Install them alongside `linnl`:

```sh
uv tool install linnl --with linnl-acme-rules
```

Then enable their `linnl.plugins` entry-point names.

```toml
plugins = ["acme-rules"]
extend-select = ["ACM"]
```

The package contributes default sections under `[rules]`. Your configuration can select, ignore, and override those rules in the same way as built-in rules.

`linnl plugins` lists the rule packages enabled by the active configuration.

To author a package, declare an entry point that names a `linnl.plugins.Plugin` subclass:

```toml
[project.entry-points."linnl.plugins"]
acme-rules = "linnl_acme_rules:AcmePlugin"
```

```python
from typing import ClassVar

from linnl.document import Document
from linnl.plugins import Plugin
from linnl.rules import CodeRule
from linnl.rules.pattern_rules import TextPatternRule
from linnl.violations import Violation, Violations


class Acme001(TextPatternRule, identifier="ACM001"):
    """Flag obviously.

    Example: "This is obviously correct."
    """

    pattern = r"\bobviously\b"


class Acme002(CodeRule, identifier="ACM002"):
    """Flag lines longer than 80 characters.

    Example: "This line has more than eighty characters and should be shortened before it is committed."
    """

    def __call__(self, document: Document) -> Violations:
        violations = []

        for line_number, line in enumerate(document.lines, start=1):
            if len(line) > 80:
                violations.append(
                    Violation(
                        rule=self,
                        path=document.path,
                        line=line_number,
                        offset=81,
                        quote=line,
                    )
                )

        return Violations(violations)


class AcmePlugin(Plugin):
    """Define Acme's writing rules."""

    name = "acme-rules"
    rules: ClassVar = {
        "ACM": {
            "description": "Acme writing rules",
            "001": "Avoid obviously.",
            "002": "Keep lines at 80 characters or fewer.",
        }
    }
```

The class's `name` must match the entry point name. `Acme001` registers itself when the package imports it. Each code rule needs a definition in `rules`.

### Check configuration
`linnl rules` prints every rule with its resolved on/off state and whether Python or the model checks it.

## Built-in rules

| Code | Default | Rule |
| --- | --- | --- |
| SCH001 | on | Tricolon. Three parallel words, phrases or clauses arranged as a series for rhythm or emphasis. Example: 'It is fast, small and simple.' A list of three things that happen to be three is fine, the arrangement for effect is not. |
| SCH002 | on | Isocolon. Two or more clauses of matching length and grammatical structure, set side by side for balance. Example: 'Simple to learn, hard to master.' |
| SCH003 | on | Anaphora. The same word or phrase opening successive clauses or sentences. Example: 'No config. No setup. No surprises.' |
| SCH004 | on | Antithesis. Contrasting ideas placed in parallel structure. Example: 'Not because it is easy, but because it is hard.' |
| SCH005 | on | Chiasmus. Words or structure repeated in reverse order across two clauses. Example: 'Ask not what your country can do for you, ask what you can do for your country.' |
| SCH006 | on | Asyndeton. Conjunctions dropped from a series of clauses or phrases to quicken the pace. Example: 'I came, I saw, I conquered.' |
| SCH007 | on | Alliterative pairing. Two or more nearby words chosen for a shared initial sound. Example: 'fast and fluid', 'bold and brave'. |
| SCH008 | on | Epigrammatic closer. A short, pithy, quotable sentence used to close a paragraph or the whole text. Example: ending a paragraph with 'Simple tools, simple problems.' |
| SCH000 | on | Other scheme. Any scheme not covered above: epistrophe, polysyndeton, climax, symploce, and the like. |
| SLO001 | on | Slogan. A sentence written to be quoted rather than to inform. Example: 'Ship less, sleep more.' |
| ZIN001 | on | Simplicity. The sentence is more complex than the idea it carries, through long-winded construction or jargon where a plain word exists. |
| ZIN002 | on | Brevity. Words that do no work: padding, redundant pairs, throat-clearing openers and restating what was already said. |
| ZIN003 | on | Clarity. The reader cannot tell what is meant: ambiguous pronouns, vague references, undefined terms, sentences that need a second reading. |
| ZIN004 | on | Humanity. The writing does not sound like one person talking to another: stiff, bureaucratic, impersonal, over-hedged, or passive voice hiding who did what. |
| CHR001 | on | Em dash (U+2014). |
| CHR002 | on | En dash (U+2013). |
| CHR003 | on | Middle dot (U+00B7). |
| CHR004 | on | Semicolon. |
| CHR000 | off | Any non-ASCII character not covered by another CHR rule. |
| LEN001 | off | The text has more than 3 sentences. |
| LEN002 | on | Not concise. The text includes material the reader did not ask for: justification, background, alternatives or caveats. |
| CLH001 | on | No X, no Y chains. |
| CLH002 | on | That's the whole point, game, or thing. |
| CLH003 | on | Did not X, did not Y chains. |
| CLH004 | on | Don't VERB it, VERB it. |
| CLH005 | on | Sit with that. |
| CLH006 | on | You already know. |
| CLH007 | on | Is the entire point, game, or business model. |
| CLH008 | on | The entire point, game, or business model is. |
| CLH009 | on | Is real and or not. |
| CLH010 | on | The punchline is. |
| CLH011 | on | Worth naming. |
| CLH012 | on | That's not nothing. |
| CLH013 | on | Is the whole point, trick, pitch, or idea. |
| CLH014 | on | Echoing sentence runs. |
| CLH015 | on | Performative honesty. |
| CLH016 | on | That's the part. |
| CLH017 | on | The only X I trust. |
| CLH018 | on | Don't take my word for it. |
| CLH019 | on | Turns out. |
| CLH020 | on | Fits in your head. |
| CLH021 | on | Stacked rhetorical questions. |
| CLH022 | on | Repeated sentence openers. |
| CLH023 | on | Colon into a triple. |
| CLH024 | on | Here's the twist. |
| CLH025 | on | X is dead. |
| CLH026 | on | That's why X mattered. |
| CLH027 | on | Stranded auxiliary contrast. |
| WIK001 | on | AI vocabulary words. |
| WIK002 | on | Not just X, but Y. |
| WIK003 | on | It's important to note. |
| WIK004 | on | Stands as a testament. |
| WIK005 | on | Plays a crucial role. |
| WIK006 | on | Ever-evolving landscape. |
| WIK007 | on | Experts argue. |
| WIK008 | on | Despite these challenges. |
| WIK009 | on | Participle sentence tails. |
| WIK010 | on | Promotional boilerplate. |
| WIK011 | on | Chatbot leftovers. |

## Develop

```sh
uv sync --group dev
uv run pytest
uv run ty check linnl
uv run ruff check
uv run ruff format
uv tool install --editable .
```

## Acknowledgments

The CLH and WIK rules are adapted from [Simon Willison's LLM cliche highlighter](https://github.com/simonw/tools/blob/main/llm-cliche-highlighter.html).

For a broader collection of deterministic prose checks, see [Proselint](https://github.com/amperser/proselint).
