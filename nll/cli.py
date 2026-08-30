"""Parse the command line and run the linter."""

import pathlib as pl
import sys
from typing import Annotated

import typer

from nll.config import discover_config_file
from nll.linter import Linter
from nll.logconfig import (
    DEFAULT_PRETTY,
    DEFAULT_STRUCTURED,
    DEFAULT_VERBOSE,
    config_logging,
)
from nll.violations import OutputFormat, render_violations

app = typer.Typer(
    add_completion=False,
    pretty_exceptions_show_locals=False,
    pretty_exceptions_short=True,
    pretty_exceptions_enable=False,
)

ConfigOption = Annotated[
    pl.Path | None, typer.Option(help="Config file, instead of the discovered one.")
]
SelectOption = Annotated[
    list[str] | None,
    typer.Option(
        help="Enable exactly these rules or prefixes, ignoring the config's selection."
    ),
]
ExtendSelectOption = Annotated[
    list[str],
    typer.Option(
        default_factory=list,
        show_default=False,
        help="Enable these rules or prefixes on top.",
    ),
]
IgnoreOption = Annotated[
    list[str],
    typer.Option(
        default_factory=list,
        show_default=False,
        help="Disable these rules or prefixes.",
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
    extend_select: ExtendSelectOption,
    ignore: IgnoreOption,
    paths: Annotated[
        list[pl.Path] | None,
        typer.Argument(
            help="Files or directories to lint. Reads stdin when none are given."
        ),
    ] = None,
    config_file: ConfigOption = None,
    select: SelectOption = None,
    output_format: Annotated[
        OutputFormat, typer.Option(help="How to print violations.")
    ] = OutputFormat.TEXT,
) -> None:
    """Lint files and print the violations. Exits with 1 when any is reported."""
    if config_file is None:
        config_file = discover_config_file(pl.Path.cwd())

    linter = Linter.from_config(
        config_file,
        select=select,
        extend_select=extend_select,
        ignore=ignore,
    )

    if paths is None:
        if sys.stdin.isatty():
            raise typer.BadParameter("no paths given and nothing piped to stdin")
        violations = linter.lint_text(sys.stdin.read(), path="<stdin>")
    else:
        violations = linter.lint_files(paths)

    print(violations.render_as(output_format))

    if len(violations) > 0:
        raise typer.Exit(code=1)


@app.command(name="rules")
def list_rules(
    extend_select: ExtendSelectOption,
    ignore: IgnoreOption,
    config_file: ConfigOption = None,
    select: SelectOption = None,
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
