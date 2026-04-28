"""Unit tests for the Python Tests workflow verifier."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

MODULE_PATH = (
    Path(__file__).parents[3] / "scripts" / "ci" / "verify_python_tests_workflow.py"
)
SPEC = importlib.util.spec_from_file_location(
    "verify_python_tests_workflow", MODULE_PATH
)
assert SPEC is not None
assert SPEC.loader is not None
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


def _lint_step(*commands: str) -> dict[str, str]:
    return {"name": "Lint with flake8", "run": "\n".join(commands)}


def test_flake8_contract_rejects_root_target_after_scoped_targets():
    """Root lint targets are rejected even when appended after scoped targets."""
    steps = [
        _lint_step(
            "flake8 src/assethold tests/ . "
            "--count --select=E9,F63,F7,F82 --show-source --statistics",
            "flake8 src/assethold tests/ --count --exit-zero "
            "--max-complexity=10 --max-line-length=88 --statistics",
        )
    ]

    with pytest.raises(AssertionError, match="repository root"):
        verifier._assert_flake8_contract(steps)
