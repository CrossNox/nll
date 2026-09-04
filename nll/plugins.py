"""Load rule plugins installed with Python packages."""

from importlib.metadata import entry_points
from typing import Any, ClassVar

from nll.logconfig import get_logger

logger = get_logger(__name__)

PLUGIN_ENTRY_POINT_GROUP = "nll.plugins"


class Plugin:
    """Define the rules a package contributes to nll."""

    name: ClassVar[str]
    rules: ClassVar[dict[str, dict[str, Any]]]


def load_plugins(plugin_names: list[str]) -> tuple[Plugin, ...]:
    """Load the plugins named by a configuration file."""
    installed = {
        entry_point.name: entry_point
        for entry_point in entry_points(group=PLUGIN_ENTRY_POINT_GROUP)
    }
    plugins = []

    for name in plugin_names:
        try:
            plugin_class = installed[name].load()
        except KeyError as error:
            raise ValueError(f"plugin {name} is enabled but not installed") from error

        plugin = plugin_class()

        if not isinstance(plugin, Plugin):
            raise ValueError(f"plugin {name} does not define an nll Plugin")

        if plugin.name != name:
            raise ValueError(f"plugin {name} defines the name {plugin.name}")

        plugins.append(plugin)
        logger.info("Loaded plugin %s", plugin.name)

    return tuple(plugins)
