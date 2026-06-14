from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any


def section(cfg: dict, name: str) -> dict:
    if name not in cfg:
        raise KeyError(f"Missing workflow section: {name}")
    value = cfg[name]
    if not isinstance(value, dict):
        raise TypeError(f"Workflow section {name!r} must be a mapping")
    return value


def output_path(path: str) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def write_json(path: str, data: Any) -> Path:
    target = output_path(path)
    target.write_text(
        json.dumps(to_plain_data(data), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


def write_text(path: str, text: str) -> Path:
    target = output_path(path)
    target.write_text(text, encoding="utf-8")
    return target


def to_plain_data(value: Any) -> Any:
    if is_dataclass(value):
        return to_plain_data(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): to_plain_data(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain_data(v) for v in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except ValueError:
            pass
    return value


def record_outputs(cfg: dict, basename: str, paths: list[Path]) -> dict:
    cfg.setdefault("outputs", {})
    cfg["outputs"][basename] = [str(path) for path in paths]
    return cfg
