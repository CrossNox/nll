"""Parse the command line and run the linter."""

import pathlib as pl
import sys
from typing import Annotated

import typer

from nll.agents import Agent
from nll.agents import install_hook as install_agent_hook
from nll.config import SHIPPED_CONFIG_FILE, discover_config_file
from nll.linter import Linter
from nll.logconfig import (
    DEFAULT_PRETTY,
    DEFAULT_STRUCTURED,
    DEFAULT_VERBOSE,
    config_logging,
)

app = typer.Typer(
    add_completion=True,
    pretty_exceptions_show_locals=False,
    pretty_exceptions_short=True,
    pretty_exceptions_enable=False,
)


PathsArgument = Annotated[
    list[pl.Path] | None,
    typer.Argument(
        help="Files or directories to lint. Reads stdin when none are given."
    ),
]
ConfigOption = Annotated[
    pl.Path | None,
    typer.Option(
        help="Config file. Discovered from the working directory when not given."
    ),
]
SelectOption = Annotated[
    list[str] | None,
    typer.Option(
        help="Enable exactly these rules or prefixes, replacing the config's selection."
    ),
]
ExtendSelectOption = Annotated[
    list[str] | None,
    typer.Option(help="Enable these rules or prefixes on top of the selection."),
]
IgnoreOption = Annotated[
    list[str] | None,
    typer.Option(help="Disable these rules or prefixes."),
]
ModelOption = Annotated[
    str | None, typer.Option(help="Model alias or id the judge calls.")
]
AgentOption = Annotated[
    Agent | None, typer.Option(help="Model agent to use for model-judged rules.")
]
MaxConcurrencyOption = Annotated[
    int | None,
    typer.Option(min=1, help="How many documents are linted concurrently."),
]
IncludeExtensionOption = Annotated[
    list[str] | None,
    typer.Option(
        "--include-extension",
        help="Extensions linted when a directory is given, replacing the config's.",
    ),
]
IgnoreCodeBlocksOption = Annotated[
    bool | None,
    typer.Option(
        "--ignore-code-blocks/--lint-code-blocks",
        help="Ignore Markdown and reStructuredText code blocks.",
    ),
]


@app.callback()
def main(
    verbose: int = typer.Option(
        DEFAULT_VERBOSE,
        "--verbose",
        "-v",
        count=True,
        help="Verbosity level. Pass more than once for more logging.",
    ),
    pretty: bool = typer.Option(
        DEFAULT_PRETTY,
        "--pretty",
        help="Pretty-print logs with colors.",
    ),
    structured: bool = typer.Option(
        DEFAULT_STRUCTURED,
        "--structured/--unstructured",
        "-s/-u",
        help="Output structured (JSON) logs.",
    ),
) -> None:
    """nll, a prose linter."""
    config_logging(verbose=verbose, pretty=pretty, structured=structured)


@app.command()
def lint(
    paths: PathsArgument = None,
    config_file: ConfigOption = None,
    select: SelectOption = None,
    extend_select: ExtendSelectOption = None,
    ignore: IgnoreOption = None,
    model: ModelOption = None,
    agent: AgentOption = None,
    max_concurrency: MaxConcurrencyOption = None,
    include_extensions: IncludeExtensionOption = None,
    ignore_code_blocks: IgnoreCodeBlocksOption = None,
) -> None:
    """Lint files and print the violations. Exits with 1 when any is reported."""
    try:
        if config_file is None:
            config_file = discover_config_file(pl.Path.cwd())

        linter = Linter.from_config(
            config_file,
            select=select,
            extend_select=extend_select,
            ignore=ignore,
            model=model,
            agent=agent,
            max_concurrency=max_concurrency,
            include_extensions=include_extensions,
            ignore_code_blocks=ignore_code_blocks,
        )

        if paths is None:
            if sys.stdin.isatty():
                raise typer.BadParameter("no paths given and nothing piped to stdin")

            violations = linter.lint_text(sys.stdin.read())
        else:
            violations = linter.lint_paths(paths)
    except ExceptionGroup as error:
        typer.echo(f"Error: {error.exceptions[0]}", err=True)
        raise typer.Exit(code=2) from None
    except (OSError, RuntimeError, TypeError, ValueError, typer.BadParameter) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=2) from None

    if len(violations) == 0:
        print("No violations found.")
        return

    print(violations)

    file_count = len(set(v.path for v in violations))
    file_label = "file" if file_count == 1 else "files"
    print(f"Found {len(violations)} violations across {file_count} {file_label}.")

    raise typer.Exit(code=1)


@app.command(name="rules")
def list_rules(
    config_file: ConfigOption = None,
    select: SelectOption = None,
    extend_select: ExtendSelectOption = None,
    ignore: IgnoreOption = None,
) -> None:
    """Print the rule book with each rule's on/off state and who checks it."""
    if config_file is None:
        config_file = discover_config_file(pl.Path.cwd())

    linter = Linter.from_config(
        config_file,
        select=select,
        extend_select=extend_select,
        ignore=ignore,
    )

    print(linter.rules)


@app.command(name="config")
def print_shipped_config() -> None:
    """Print the shipped config, to copy and edit: nll config > nll.toml."""
    print(SHIPPED_CONFIG_FILE.read_text(encoding="utf-8"), end="")


@app.command()
def install_hook(
    agent: Agent,
    local: bool = typer.Option(
        False,
        "--local/--global",
        help="Install in the current project or in your home directory.",
    ),
) -> None:
    """Install nll as hook for your coding agent."""
    command_path = install_agent_hook(agent, local=local)
    typer.echo(f"Installed nll command at {command_path}")
