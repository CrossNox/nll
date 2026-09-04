from pathlib import Path

import pytest

from nll.config import (
    SHIPPED_CONFIG_FILE,
    discover_config_file,
    has_nll_section,
    locate_user_config_file,
    read_config_file,
)


def test_locate_user_config_follows_xdg_config_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    assert locate_user_config_file() == tmp_path / "nll" / "config.toml"


def test_locate_user_config_uses_the_default_when_xdg_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

    assert locate_user_config_file() == Path.home() / ".config" / "nll" / "config.toml"


def test_read_config_file_parses_a_regular_toml_file(tmp_path: Path) -> None:
    path = tmp_path / "nll.toml"
    path.write_text('select = ["CHR"]\n', encoding="utf-8")

    assert read_config_file(path) == {"select": ["CHR"]}


def test_read_config_file_extracts_the_nll_tool_table(tmp_path: Path) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text('[project]\nname = "demo"\n\n[tool.nll]\nselect = ["CHR"]\n')

    assert read_config_file(path) == {"select": ["CHR"]}


def test_read_config_file_rejects_a_pyproject_without_nll(tmp_path: Path) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text('[project]\nname = "demo"\n')

    with pytest.raises(ValueError, match=r"no \[tool.nll\] table"):
        read_config_file(path)


def test_has_nll_section_only_accepts_the_tool_table(tmp_path: Path) -> None:
    path = tmp_path / "pyproject.toml"
    path.write_text('[tool.nll]\nselect = ["CHR"]\n')
    assert has_nll_section(path)

    path.write_text("[tool.ruff]\nline-length = 88\n")
    assert not has_nll_section(path)


def test_discover_prefers_a_local_nll_file_over_the_user_file(
    no_user_config: Path,
) -> None:
    local = no_user_config / "project" / "nested"
    local.mkdir(parents=True)
    nll_file = no_user_config / "project" / "nll.toml"
    nll_file.write_text("", encoding="utf-8")

    assert discover_config_file(local) == nll_file


def test_discover_prefers_pyproject_over_nll_in_the_same_directory(
    no_user_config: Path, caplog: pytest.LogCaptureFixture
) -> None:
    pyproject = no_user_config / "pyproject.toml"
    pyproject.write_text("[tool.nll]\n", encoding="utf-8")
    nll_file = no_user_config / "nll.toml"
    nll_file.write_text("", encoding="utf-8")

    assert discover_config_file(no_user_config) == pyproject
    assert "both pyproject.toml and nll.toml configure nll" in caplog.text


def test_discover_falls_back_to_user_then_shipped_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    user_file = tmp_path / "xdg" / "nll" / "config.toml"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    assert discover_config_file(project) == SHIPPED_CONFIG_FILE

    user_file.parent.mkdir(parents=True)
    user_file.write_text("", encoding="utf-8")
    assert discover_config_file(project) == user_file
