"""Parse the command line, gather the documents and run the linter."""

import pathlib as pl
import sys
from fnmatch import fnmatch
from typing import Annotated

import typer

from nll.document import Document
from nll.linter import Linter
from nll.logconfig import (
    DEFAULT_PRETTY,
    DEFAULT_STRUCTURED,
    DEFAULT_VERBOSE,
    config_logging,
)
from nll.violations import OutputFormat, RuleViolations

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


def find_files(directory: pl.Path, include: list[str]) -> list[pl.Path]:
    """Walk a directory for files matching the patterns, skipping hidden directories."""
    files: list[pl.Path] = []

    for child in sorted(directory.iterdir()):
        if child.name.startswith("."):
            continue

        if child.is_dir():
            files.extend(find_files(child, include))
        elif any(fnmatch(child.name, pattern) for pattern in include):
            files.append(child)

    return files


def read_document(path: pl.Path) -> Document:
    return Document(path.read_text(encoding="utf-8"), str(path))


def read_stdin_document() -> Document:
    """Read the text piped to stdin, refusing to wait on a terminal."""
    if sys.stdin.isatty():
        raise typer.BadParameter("no paths given and nothing piped to stdin")

    return Document(sys.stdin.read(), "<stdin>")


def collect_documents(paths: list[pl.Path], include: list[str]) -> list[Document]:
    """Read the named files and directories, or stdin when nothing is named."""
    if len(paths) == 0:
        return [read_stdin_document()]

    documents: list[Document] = []
    for path in paths:
        if path.is_dir():
            files = find_files(path, include)
            if len(files) == 0:
                typer.echo(f"{path}: no files match {' '.join(include)}", err=True)
            documents.extend(read_document(file) for file in files)
        else:
            documents.append(read_document(path))

    return documents


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
    config: ConfigOption = None,
    select: SelectOption = None,
    output_format: Annotated[
        OutputFormat, typer.Option(help="How to print violations.")
    ] = OutputFormat.TEXT,
) -> None:
    """Lint files and print the violations. Exits with 1 when any is reported."""
    linter: Linter = Linter.load(config, pl.Path.cwd(), select, extend_select, ignore)
    documents: list[Document] = collect_documents(
        [] if paths is None else paths, linter.config.include
    )
    violations: RuleViolations = linter.lint_all(documents)

    print(violations.render(output_format))

    if len(violations) > 0:
        raise typer.Exit(code=1)


@app.command(name="rules")
def list_rules(
    extend_select: ExtendSelectOption,
    ignore: IgnoreOption,
    config: ConfigOption = None,
    select: SelectOption = None,
) -> None:
    """Print the rule book with each rule's on/off state and who checks it."""
    linter: Linter = Linter.load(config, pl.Path.cwd(), select, extend_select, ignore)

    print(linter.render_rules())
