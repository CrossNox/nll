# nll

Lint prose against a rule set and get the violations in the `path:line:col: CODE message` layout linters use.

Character and length rules are checked in Python. Rhetorical schemes, slogans, Zinsser's principles and concision are judged by Claude through the [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk), which reuses the `claude` CLI login on the machine.

## Install

```sh
uv tool install nll
```

The model-judged rules need a working `claude` login (run `claude` once, interactively) or an `ANTHROPIC_API_KEY` in the environment.

## Use

```sh
nll lint notes.md
nll lint docs/
nll lint --select CHR --extend-select LEN001 notes.md
echo "text" | nll lint
nll lint --output-format json notes.md
nll rules
nll -v lint notes.md
```

Given a directory, nll walks it for files matching the `include` patterns (`*.md`, `*.txt`, `*.rst` by default) and skips hidden directories. It lints any file you name on the command line, whatever its extension. With no paths, it reads stdin.

A command line `--select` means exactly those rules: the config's `select`, `extend-select` and `ignore` are set aside, and only a command line `--ignore` applies on top. `--extend-select` and `--ignore` without `--select` add to the config's lists.

Exit status is 1 when the linter reports a violation. nll writes violations to stdout and logs to stderr. Logs are off unless you pass `-v` (info) or `-vv` (debug), with `--pretty` for colors and `--structured` for JSON lines.

Example output:

```
notes.md:3:61: SCH003 Three successive fragments open with the same word for emphasis, which is anaphora.
    > No config. No cron. No surprises.
    Fix: It needs no config file and no cron entry.
notes.md:5:96: CHR004 Semicolon.
    > Set it up once; forget about it.
    Fix: Split into two sentences or join with a comma
Found 2 violations.
```

## Configure

nll walks up from the working directory looking for a `pyproject.toml` with a `[tool.nll]` table or an `nll.toml`. When a directory has both, the `pyproject.toml` wins and nll logs a warning. If neither is found, it reads `$XDG_CONFIG_HOME/nll/config.toml` (`~/.config/nll/config.toml` when the variable is unset). Each key in that file overrides the matching shipped default. The defaults are [`nll/resources/config.toml`](nll/resources/config.toml):

```toml
# Prefixes expand: SCH means every SCH rule.
# `select` replaces this list, `extend-select` adds, `ignore` removes.
select = ["SCH", "SLO", "ZIN", "CHR", "LEN"]
extend-select = []
ignore = ["CHR000", "LEN001"]

# Model alias or id passed to the claude CLI, and its effort level.
model = "opus"
effort = "high"

# Skip fenced code blocks and inline code for every rule, the model included.
ignore-code = true

# How many documents are linted concurrently. Each document is one model call.
max-concurrency = 4

# Files linted when a directory is given. Hidden directories are skipped.
include = ["*.md", "*.txt", "*.rst"]

# The built-in rules follow, under [rules.<PREFIX>].
```

A rule with options is a table under its group. To change an option of a built-in rule, set it under the same path in your file:

```toml
[rules.LEN.001]
max-sentences = 5
```

`nll rules` prints every rule with its resolved on/off state and whether Python or the model checks it.

## Add your own rules

Add groups under `[rules.<PREFIX>]` in your config file, the same way the shipped [`config.toml`](nll/resources/config.toml) defines the built-ins. `description` is the one reserved key. Every other key is a rule:

```toml
extend-select = ["SEC"]

[rules.SEC]
description = "Wording that must not leak infrastructure details"
001 = "Names an internal host, IP or path"
abc = "Shows a credential or token in an example"
```

That defines `SEC001` and `SECabc`, judged by the model. nll shows the group description to the model above its rules, so make it say what the group is for. Group prefixes are uppercase letters and cannot repeat a built-in group.

A description can name the rule's options in braces. Write an option name with underscores, so `max-sentences` becomes `{max_sentences}` and `"More than {max_sentences} sentences."` renders with the configured value. nll accepts options only on rules that declare them (`PYTHON_CHECKS` in `nll/checks.py`).

## Built-in rules

| Code | Rule |
| --- | --- |
| SCH001 | tricolon |
| SCH002 | isocolon |
| SCH003 | anaphora |
| SCH004 | antithesis |
| SCH005 | chiasmus |
| SCH006 | asyndeton |
| SCH007 | alliterative pairing |
| SCH008 | epigrammatic closer |
| SCH000 | other scheme |
| SLO001 | slogan |
| ZIN001 | simplicity |
| ZIN002 | brevity |
| ZIN003 | clarity |
| ZIN004 | humanity |
| CHR001 | em dash |
| CHR002 | en dash |
| CHR003 | middle dot |
| CHR004 | semicolon |
| CHR000 | other non-ASCII character (off by default) |
| LEN001 | more than `max-sentences` sentences (off by default) |
| LEN002 | not concise |

## Develop

```sh
uv sync --group dev
uv run pytest
uv run mypy
uv run ruff check
uv run ruff format
uv tool install --editable .
```
