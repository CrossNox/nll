"""Load rule plugins installed with Python packages."""

from dataclasses import dataclass
from importlib.metadata import entry_points
from typing import Any

from nll.logconfig import get_logger

logger = get_logger(__name__)

PLUGIN_ENTRY_POINT_GROUP = "nll.plugins"


@dataclass(frozen=True)
class Plugin:
    """Define the rules a package contributes to nll."""

    name: str
    rules: dict[str, dict[str, Any]]


def load_plugins(plugin_names: object) -> tuple[Plugin, ...]:
    """Load the plugins named by a configuration file."""
    if not isinstance(plugin_names, list) or not all(
        isinstance(name, str) and name != "" for name in plugin_names
    ):
        raise ValueError("Configuration error: plugins must be a list of names")

    installed = {
        entry_point.name: entry_point
        for entry_point in entry_points(group=PLUGIN_ENTRY_POINT_GROUP)
    }
    plugins = []

    for name in plugin_names:
        try:
            factory = installed[name].load()
        except KeyError as error:
            raise ValueError(f"plugin {name} is enabled but not installed") from error

        plugin = factory()

        if not isinstance(plugin, Plugin):
            raise ValueError(f"plugin {name} did not return an nll Plugin")

        plugins.append(plugin)
        logger.info("Loaded plugin %s", plugin.name)

    return tuple(plugins)
