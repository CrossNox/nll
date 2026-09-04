import json
import logging

from linnl.logconfig import build_handler, choose_level_for_verbosity


def test_choose_level_for_verbosity() -> None:
    assert choose_level_for_verbosity(0) == logging.ERROR
    assert choose_level_for_verbosity(1) == logging.INFO
    assert choose_level_for_verbosity(2) == logging.DEBUG
    assert choose_level_for_verbosity(5) == logging.DEBUG


def test_build_handler_uses_json_when_structured() -> None:
    handler = build_handler(structured=True, pretty=False, level=logging.INFO)

    record = logging.LogRecord(
        name="linnl.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )

    rendered = handler.format(record)

    assert json.loads(rendered)["message"] == "hello"
    assert handler.level == logging.INFO


def test_build_handler_uses_rich_for_pretty_output() -> None:
    handler = build_handler(structured=False, pretty=True, level=logging.DEBUG)

    assert handler.__class__.__name__ == "RichHandler"
    assert handler.level == logging.DEBUG
