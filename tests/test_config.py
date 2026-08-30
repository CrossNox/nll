from pathlib import Path

import pytest

from nll.checks import SentenceCountOptions
from nll.config import (
    discover_config_file,
    locate_user_config_file,
    read_config_file,
    read_config_layers,
)
from nll.rules import RuleBook


def test_layers_start_from_the_shipped_config() -> None:
    settings = read_config_layers(None)

    assert settings["model"] == "opus"
    assert settings["select"] == ["SCH", "SLO", "ZIN", "CHR", "LEN"]
    assert isinstance(settings["rules"], RuleBook)
    assert settings["rules"]["CHR001"].is_checked_in_python
    assert not settings["rules"]["SCH001"].is_checked_in_python


def test_user_file_overrides_defaults_key_by_key(tmp_path: Path) -> None:
    path = tmp_path / "nll.toml"
    path.write_text(
        'ignore = ["CHR004"]\nmodel = "sonnet"\n\n[rules.LEN.001]\nmax-sentences = 5\n'
    )

    settings = read_config_layers(path)

    assert settings["ignore"] == ["CHR004"]
    assert settings["model"] == "sonnet"
    assert settings["effort"] == "high"
    assert settings["rules"]["LEN001"].options == SentenceCountOptions(max_sentences=5)


def test_user_rules_namespace_extends_the_rulebook(tmp_path: Path) -> None:
    path = tmp_path / "nll.toml"
    path.write_text('[rules.SEC]\ndescription = "Leaks"\n001 = "Names an IP"\n')

    rules = read_config_layers(path)["rules"]

    assert rules["SEC001"].description == "Names an IP"
    assert rules["SCH001"].code == "SCH001"


def test_read_config_file_unwraps_the_pyproject_section(tmp_path: Path) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text('[project]\nname = "x"\n\n[tool.nll]\nextend-select = ["LEN001"]\n')

    assert read_config_file(path) == {"extend-select": ["LEN001"]}


def test_read_config_file_refuses_a_pyproject_without_the_section(
    tmp_path: Path,
) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text("[project]\nname = 'x'\n")

    with pytest.raises(ValueError, match=r"no \[tool.nll\] table"):
        read_config_file(path)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("[rules.LEN.001]\nmax-sentences = 0\n", "rule LEN001 options are invalid"),
        ("[rules.LEN.001]\nmax-words = 3\n", "rule LEN001 options are invalid"),
        ("[rules.SCH]\ndescription = 'again'\n999 = 'x'\n", "already defined"),
        (
            "[rules.SEC]\ndescription = 'x'\n001 = 'Over {limit}.'\n",
            "names an unknown option",
        ),
    ],
)
def test_invalid_rules_raise_naming_the_file_and_rule(
    tmp_path: Path, content: str, message: str
) -> None:
    path = tmp_path / "nll.toml"
    path.write_text(content)

    with pytest.raises(ValueError, match=message) as raised:
        read_config_layers(path)

    assert str(path) in str(raised.value)


def test_discover_walks_upward(no_user_config: Path) -> None:
    (no_user_config / "nll.toml").write_text("")
    nested = no_user_config / "a" / "b"
    nested.mkdir(parents=True)

    assert discover_config_file(nested) == no_user_config / "nll.toml"


def test_discover_prefers_pyproject_with_nll_section_and_warns(
    no_user_config: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (no_user_config / "nll.toml").write_text("")
    (no_user_config / "pyproject.toml").write_text("[tool.nll]\n")

    assert discover_config_file(no_user_config) == no_user_config / "pyproject.toml"
    assert "both pyproject.toml and nll.toml configure nll" in caplog.text


def test_discover_skips_pyproject_without_nll_section(no_user_config: Path) -> None:
    (no_user_config / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    (no_user_config / "nll.toml").write_text("")

    assert discover_config_file(no_user_config) == no_user_config / "nll.toml"


def test_discover_falls_back_to_user_config_then_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_home = tmp_path / "xdg"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    project = tmp_path / "project"
    project.mkdir()

    assert discover_config_file(project) is None

    (config_home / "nll").mkdir(parents=True)
    (config_home / "nll" / "config.toml").write_text("")

    assert discover_config_file(project) == config_home / "nll" / "config.toml"


def test_user_config_follows_xdg_config_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert locate_user_config_file() == tmp_path / "nll" / "config.toml"

    monkeypatch.setenv("XDG_CONFIG_HOME", "")
    assert locate_user_config_file() == Path.home() / ".config" / "nll" / "config.toml"

    monkeypatch.delenv("XDG_CONFIG_HOME")
    assert locate_user_config_file() == Path.home() / ".config" / "nll" / "config.toml"
