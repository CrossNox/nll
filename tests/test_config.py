from pathlib import Path

import pytest

from nll.config import Config, find_config_file, load_config, locate_user_config_file


def test_shipped_defaults_apply_when_no_file_is_found(default_config: Config) -> None:
    assert default_config.source is None
    assert default_config.model == "opus"
    assert default_config.effort == "high"
    assert default_config.max_concurrency == 4
    assert default_config.include == ["*.md", "*.txt", "*.rst"]
    assert default_config.select == ["SCH", "SLO", "ZIN", "CHR", "LEN"]
    assert default_config.ignore == ["CHR000", "LEN001"]
    assert "CHR001" in default_config.rules


def test_user_file_overrides_defaults_key_by_key(no_user_config: Path) -> None:
    path = no_user_config / "nll.toml"
    path.write_text(
        'ignore = ["CHR004"]\nmodel = "sonnet"\nignore-code = false\n\n'
        "[rules.LEN.001]\nmax-sentences = 5\n"
    )

    config = load_config(path, no_user_config)

    assert config.ignore == ["CHR004"]
    assert config.model == "sonnet"
    assert config.ignore_code is False
    assert config.rules["LEN001"].options == {"max-sentences": 5}
    assert config.effort == "high"
    assert config.source == path


def test_user_rules_namespace_extends_the_rulebook(no_user_config: Path) -> None:
    path = no_user_config / "nll.toml"
    path.write_text('[rules.SEC]\ndescription = "Leaks"\n001 = "Names an IP"\n')

    config = load_config(path, no_user_config)

    assert config.rules["SEC001"].description == "Names an IP"
    assert "SCH001" in config.rules


def test_load_config_from_pyproject_section(no_user_config: Path) -> None:
    path = no_user_config / "pyproject.toml"
    path.write_text('[tool.nll]\nextend-select = ["LEN001"]\n')

    config = load_config(path, no_user_config)

    assert config.extend_select == ["LEN001"]


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("selekt = []\n", "selekt"),
        ("[SEC]\ndescription = 'x'\n", "SEC"),
        ("[LEN001]\nmax-sentences = 5\n", "LEN001"),
        ("select = 'CHR'\n", "select"),
        ("ignore-code = 'yes'\n", "ignore-code"),
        ("effort = 'extreme'\n", "effort"),
        ("max-concurrency = -1\n", "max-concurrency"),
        ("include = 'md'\n", "include"),
        ("[rules.LEN.001]\nmax-sentences = 0\n", "rule LEN001 options are invalid"),
        ("[rules.LEN.001]\nmax-words = 3\n", "rule LEN001 options are invalid"),
        ("[rules.SCH]\ndescription = 'again'\n999 = 'x'\n", "already defined"),
        (
            "[rules.SEC]\ndescription = 'x'\n001 = 'Over {{ limit }}.'\n",
            "cannot render",
        ),
    ],
)
def test_invalid_config_raises_naming_the_file_and_key(
    no_user_config: Path, content: str, message: str
) -> None:
    path = no_user_config / "nll.toml"
    path.write_text(content)

    with pytest.raises(ValueError, match=message) as raised:
        load_config(path, no_user_config)

    assert str(path) in str(raised.value)


def test_find_config_file_walks_upward(no_user_config: Path) -> None:
    (no_user_config / "nll.toml").write_text("")
    nested = no_user_config / "a" / "b"
    nested.mkdir(parents=True)

    assert find_config_file(nested) == no_user_config / "nll.toml"


def test_user_config_follows_xdg_config_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert locate_user_config_file() == tmp_path / "nll" / "config.toml"

    monkeypatch.setenv("XDG_CONFIG_HOME", "")
    assert locate_user_config_file() == Path.home() / ".config" / "nll" / "config.toml"

    monkeypatch.delenv("XDG_CONFIG_HOME")
    assert locate_user_config_file() == Path.home() / ".config" / "nll" / "config.toml"


def test_find_config_file_falls_back_to_user_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_home = tmp_path / "xdg"
    (config_home / "nll").mkdir(parents=True)
    (config_home / "nll" / "config.toml").write_text("")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))

    project = tmp_path / "project"
    project.mkdir()

    assert find_config_file(project) == config_home / "nll" / "config.toml"


def test_with_selection_without_select_appends_to_the_file_lists(
    default_config: Config,
) -> None:
    overridden = default_config.with_selection(None, ["CHR000"], ["SCH002"])

    assert overridden.select == default_config.select
    assert overridden.extend_select == ["CHR000"]
    assert overridden.ignore == ["CHR000", "LEN001", "SCH002"]


def test_with_selection_with_select_means_exactly_those_rules(
    default_config: Config,
) -> None:
    replaced = default_config.with_selection(["LEN001"], [], ["CHR"])

    assert replaced.select == ["LEN001"]
    assert replaced.extend_select == []
    assert replaced.ignore == ["CHR"]
    assert [rule.code for rule in replaced.enabled_rules()] == ["LEN001"]
