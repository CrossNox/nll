"""Install nll commands for supported coding agents."""

import logging
from enum import StrEnum
from pathlib import Path

logger = logging.getLogger(__name__)


class Agent(StrEnum):
    """Select the model backend for model-judged rules."""

    CLAUDE = "claude"
    CODEX = "codex"


DEFAULT_AGENT_MODELS: dict[Agent, str] = {
    Agent.CLAUDE: "claude-opus-5",
    Agent.CODEX: "gpt-5.6-luna",
}


NLL_COMMAND = """---
description: Check your most recent response with nll.
---

Check your most recent assistant response with nll.

Extract only the user-facing text from your immediately preceding response.
Do not include tool calls, this command, or your current reasoning. Pipe that
text to `nll lint` through standard input and report the result.

If nll reports violations, explain them and provide a corrected version. If it
reports no violations, say that the response is clean.
"""

AGENT_COMMAND_DIRECTORIES: dict[Agent, tuple[str, str]] = {
    Agent.CLAUDE: (".claude", "commands"),
    Agent.CODEX: (".codex", "prompts"),
}


def install_hook(agent: Agent, *, local: bool) -> Path:
    """Install the nll command for an agent and return its path."""
    agent = Agent(agent)
    agent_directory, command_directory = AGENT_COMMAND_DIRECTORIES[agent]
    base_directory = Path.cwd() if local else Path.home()
    command_path = base_directory / agent_directory / command_directory / "nll.md"
    command_path.parent.mkdir(parents=True, exist_ok=True)

    if command_path.exists():
        existing_command = command_path.read_text(encoding="utf-8")
        if existing_command != NLL_COMMAND:
            logger.info("nll command out of date, will update at %s", command_path)
        else:
            logger.info("nll command already installed at %s", command_path)
            return command_path

    command_path.write_text(NLL_COMMAND, encoding="utf-8")
    logger.info("Installed nll command at %s", command_path)
    return command_path
