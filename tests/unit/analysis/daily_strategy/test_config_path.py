"""Default daily-strategy config resolution: private file first, example last."""

from __future__ import annotations

from pathlib import Path

from assethold.analysis.daily_strategy import loader


def test_env_var_wins(monkeypatch, tmp_path):
    cfg = tmp_path / "private.yaml"
    monkeypatch.setenv(loader.CONFIG_ENV_VAR, str(cfg))
    assert loader._default_config_path() == cfg


def test_falls_back_to_committed_example(monkeypatch):
    monkeypatch.delenv(loader.CONFIG_ENV_VAR, raising=False)
    path = loader._default_config_path()
    assert path.name in {"daily_strategy.yaml", "daily_strategy.example.yaml"}
    assert path.is_file()


def test_example_config_loads_with_fictional_targets():
    example = Path(loader.__file__).parents[4] / "config" / "daily_strategy.example.yaml"
    cfg = loader._load_yaml(example)
    assert "loader" in cfg and "targets" in cfg
    assert cfg["loader"]["employee_account_patterns"] == ["EXAMPLE EMPLOYER", "EMPLOYEE INV"]
