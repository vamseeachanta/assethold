"""Asserts .claude/settings.json is conflict-free and valid JSON.

Filed as durable enforcement against a recurring failure mode. The settings file
had a single ~143-line conflict block (3 markers) from a stash/rebase that
combined upstream hooks with stashed env/permissions/Claude-Flow integration;
resolution landed via issue #50.

Refs: assethold#50, workspace-hub#2411, workspace-hub#2719.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SETTINGS_FILE = REPO_ROOT / ".claude" / "settings.json"
CLAUDE_DIR = REPO_ROOT / ".claude"

CONFLICT_PATTERN = re.compile(r"^(<<<<<<<|=======|>>>>>>>)", re.MULTILINE)


def test_settings_file_exists():
    """The .claude/settings.json file must exist."""
    assert SETTINGS_FILE.exists(), f"{SETTINGS_FILE} missing"


def test_no_conflict_markers_in_settings():
    """No git merge-conflict markers may exist in .claude/settings.json."""
    body = SETTINGS_FILE.read_text(encoding="utf-8")
    markers = CONFLICT_PATTERN.findall(body)
    assert len(markers) == 0, (
        f"{SETTINGS_FILE.relative_to(REPO_ROOT)} contains {len(markers)} conflict marker(s); "
        f"unresolved merge conflict regression"
    )


def test_settings_parses_as_valid_json():
    """The .claude/settings.json must parse as valid JSON (was broken pre-resolution)."""
    body = SETTINGS_FILE.read_text(encoding="utf-8")
    try:
        json.loads(body)
    except json.JSONDecodeError as e:
        raise AssertionError(
            f"{SETTINGS_FILE.relative_to(REPO_ROOT)} is not valid JSON: {e}"
        ) from e


def test_settings_has_hooks_section():
    """Per resolution plan, post-merge file must retain `hooks` section."""
    config = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    assert isinstance(config, dict), "settings.json must be a JSON object"
    assert "hooks" in config, "missing `hooks` section post-merge"
    assert isinstance(config["hooks"], dict), "`hooks` must be a JSON object"


def test_no_conflict_markers_in_other_claude_configs():
    """Regression guard: no `.claude/*.json` file may contain conflict markers."""
    bad = []
    for f in CLAUDE_DIR.glob("*.json"):
        if CONFLICT_PATTERN.search(f.read_text(encoding="utf-8")):
            bad.append(f.name)
    assert not bad, f"Conflict markers in: {bad}"
