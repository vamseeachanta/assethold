"""Verify the Python Tests workflow contract for the bounded CI tranche."""

from __future__ import annotations

import shlex
import sys
from pathlib import Path
from typing import Any

import yaml

WORKFLOW_PATH = Path(".github/workflows/python-tests.yml")
VERIFIER_COMMAND = "python scripts/ci/verify_python_tests_workflow.py"
TYPES_PYYAML_PIN = "types-PyYAML==6.0.12.20240917"
LINT_TARGETS = ("src/assethold", "tests/")
MYPY_TARGETS = (
    "src/assethold/signals/watchlist.py",
    "src/assethold/modules/reporting/utils/path_utils.py",
)


def _load_workflow() -> dict[str, Any]:
    if not WORKFLOW_PATH.exists():
        raise AssertionError(f"workflow file does not exist: {WORKFLOW_PATH}")
    loaded = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError("workflow YAML did not parse to a mapping")
    return loaded


def _step_by_name(steps: list[dict[str, Any]], name: str) -> dict[str, Any]:
    for step in steps:
        if step.get("name") == name:
            return step
    raise AssertionError(f"missing workflow step: {name}")


def _step_index(steps: list[dict[str, Any]], name: str) -> int:
    for index, step in enumerate(steps):
        if step.get("name") == name:
            return index
    raise AssertionError(f"missing workflow step: {name}")


def _run_lines(step: dict[str, Any]) -> list[str]:
    run = step.get("run")
    if not isinstance(run, str):
        raise AssertionError(f"step {step.get('name')} has no run command")
    return [
        line.strip()
        for line in run.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _test_steps(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict) or "test" not in jobs:
        raise AssertionError("workflow must define jobs.test")

    test_job = jobs["test"]
    steps = test_job.get("steps")
    if not isinstance(steps, list):
        raise AssertionError("jobs.test.steps must be a list")
    return steps


def _assert_dependency_contract(steps: list[dict[str, Any]]) -> None:
    install_step = _step_by_name(steps, "Install dependencies with uv")
    install_run = "\n".join(_run_lines(install_step))
    if TYPES_PYYAML_PIN not in install_run:
        raise AssertionError(f"test job must install {TYPES_PYYAML_PIN}")


def _assert_verifier_contract(steps: list[dict[str, Any]]) -> None:
    verifier_step = _step_by_name(steps, "Verify Python Tests workflow contract")
    verifier_lines = _run_lines(verifier_step)
    if verifier_lines != [VERIFIER_COMMAND]:
        raise AssertionError(
            "workflow verifier step must run exactly "
            f"{VERIFIER_COMMAND!r} for shell-neutral self-enforcement"
        )


def _assert_step_order(steps: list[dict[str, Any]]) -> None:
    ordered_steps = [
        "Install project in development mode",
        "Verify Python Tests workflow contract",
        "Run smoke tests first",
        "Lint with flake8",
        "Type checking with mypy",
        "Run unit tests with coverage",
    ]
    indexes = [_step_index(steps, name) for name in ordered_steps]
    if indexes != sorted(indexes):
        raise AssertionError(
            "test job step order must keep verifier and smoke before lint/mypy"
        )


def _assert_smoke_contract(steps: list[dict[str, Any]]) -> None:
    smoke_lines = _run_lines(_step_by_name(steps, "Run smoke tests first"))
    if smoke_lines != ["pytest tests/test_smoke.py --verbose --tb=short"]:
        raise AssertionError("smoke command must remain single-line and shell-neutral")


def _assert_flake8_contract(steps: list[dict[str, Any]]) -> None:
    lint_lines = _run_lines(_step_by_name(steps, "Lint with flake8"))
    flake8_lines = [line for line in lint_lines if line.startswith("flake8 ")]
    if len(flake8_lines) != 2:
        raise AssertionError("lint step must contain exactly two flake8 commands")
    for line in flake8_lines:
        if "flake8 ." in line:
            raise AssertionError("flake8 must not target the repository root")
        for target in LINT_TARGETS:
            if target not in line:
                raise AssertionError(
                    f"flake8 command missing target {target!r}: {line}"
                )


def _assert_mypy_contract(steps: list[dict[str, Any]]) -> None:
    mypy_lines = _run_lines(_step_by_name(steps, "Type checking with mypy"))
    if len(mypy_lines) != 1:
        raise AssertionError("mypy step must be a single shell-neutral command")
    mypy_line = mypy_lines[0]
    mypy_tokens = shlex.split(mypy_line)
    if len(mypy_tokens) > 1 and mypy_tokens[1] == "src/":
        raise AssertionError(
            "mypy must not target the entire src/ tree in this tranche"
        )
    for target in MYPY_TARGETS:
        if target not in mypy_line:
            raise AssertionError(f"mypy command missing target {target!r}")
    if "--follow-imports=silent" not in mypy_line:
        raise AssertionError("mypy command must include --follow-imports=silent")
    if "--ignore-missing-imports" not in mypy_line:
        raise AssertionError("mypy command must preserve --ignore-missing-imports")


def _assert_test_job_contract(workflow: dict[str, Any]) -> None:
    steps = _test_steps(workflow)
    _assert_dependency_contract(steps)
    _assert_verifier_contract(steps)
    _assert_step_order(steps)
    _assert_smoke_contract(steps)
    _assert_flake8_contract(steps)
    _assert_mypy_contract(steps)


def main() -> int:
    errors: list[str] = []
    try:
        _assert_test_job_contract(_load_workflow())
    except AssertionError as exc:
        errors.append(str(exc))

    if errors:
        print("Python Tests workflow contract check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Python Tests workflow contract check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
