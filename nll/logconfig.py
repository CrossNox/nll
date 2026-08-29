"""Configure logging for the CLI."""

import logging

from pythonjsonlogger import json as jsonlogger
from rich.logging import RichHandler

DEFAULT_VERBOSE = 0
DEFAULT_STRUCTURED = False
DEFAULT_PRETTY = False


def choose_level_for_verbosity(verbose: int) -> int:
    if verbose >= 2:
        return logging.DEBUG

    if verbose == 1:
        return logging.INFO

    return logging.ERROR


def build_handler(structured: bool, pretty: bool, level: int) -> logging.Handler:
    if pretty:
        handler: logging.Handler = RichHandler(
            level=level,
            rich_tracebacks=True,
            tracebacks_show_locals=False,
            show_time=True,
            show_path=True,
        )
    else:
        handler = logging.StreamHandler()

    if structured:
        handler.setFormatter(
            jsonlogger.JsonFormatter("%(asctime)s %(name)s %(levelname)s %(message)s")
        )
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)-7s %(name)s: %(message)s", datefmt="%H:%M:%S"
            )
        )

    handler.setLevel(level)
    return handler


def config_logging(
    verbose: int = DEFAULT_VERBOSE,
    structured: bool = DEFAULT_STRUCTURED,
    pretty: bool = DEFAULT_PRETTY,
) -> None:
    """Configure the root logger, unless something already did."""
    level = choose_level_for_verbosity(verbose)
    handler = build_handler(structured, pretty, level)
    logging.basicConfig(level=level, handlers=[handler])
