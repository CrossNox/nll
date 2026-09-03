# nll
`nll` is a text linter aimed to catch LLM tells and reduce the complexity of the text produced by them, so that the cognitive load on the reader is reduced and ideas are clearer.

Some built-in rules are checked in code, others (most) are judged by an LLM. Yes, full circle, but kinda works? The goal is to allow for python plugins to be added to check in code if you want to roll your own code rules in a future release. Meanwhile, you can set your own LLM rules in your config file.

## Install

```sh
uv tool install nll
```

### Claude as a judge
You will either need a working `claude` login or an `ANTHROPIC_API_KEY` set in your environment.

### Codex as a judge
Codex reuses the local Codex session. You can also set `OPENAI_API_KEY`.

## Use

```sh
nll lint notes.md
nll lint docs/
echo "text" | nll lint
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
nll lint --help
```

To see available quick configuration options.

### File configuration
The priority is:
- The closest `pyproject.toml` with a tool.nll section
- A `nll.toml` file next to the closest pyproject.toml
- `~/.config/nll/config.toml`
- The config file shipped with the tool

You can easily create a `nll.toml` with:
```sh
nll config > nll.toml
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

That defines `SEC001` and `SECabc`, judged by the model. `nll` shows the group description to the model above its rules, so make it say what the group is for.

If the rule requires configurable parameters:

```toml
extend-select = ["SEC"]

[rules.SEC]
description = "Wording that must not leak infrastructure details"
001 = "Names an internal host, IP or path"
abc = "Shows a credential or token in an example"

[rules.SEC.xyz]
description = "Do now show more {n_files} files in the current directory"
n-files: 3
```

A description can name the rule's options in braces. Write an option name with underscores, so `max-sentences` becomes `{max_sentences}` and `"More than {max_sentences} sentences."` renders with the configured value.

### Check configuration
`nll rules` prints every rule with its resolved on/off state and whether Python or the model checks it.

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
uv run ty check nll
uv run ruff check
uv run ruff format
uv tool install --editable .
```
