"""run_workflow() tests for assethold's workflow API (workspace-hub#3287).

These drive assethold's OWN engine through the #3308 embed path and assert the
shared ResultEnvelope contract, side-effect-freeness, determinism, and
assethold-stamped provenance. The golden test pins the portfolio result_hash.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from assetutilities.workflow_api import ResultEnvelope

from assethold.workflow_api import build_cfg, run_workflow
from assethold.workflow_api import runner as runner_mod

# Pinned golden result_hash for the committed portfolio example (workspace-hub#3287).
# Captured 2026-06-28 via a verify_reproducible double-run.
GOLDEN_PORTFOLIO_RESULT_HASH = (
    "97eff355c696a518f3d474dbf81ade5317f913dd617144945bd11ff982a84b99"
)

PORTFOLIO_OUTPUTS_DIR = Path("examples/workflows/portfolio/outputs")


def _snapshot(d: Path) -> dict:
    snap = {}
    if d.is_dir():
        for root, _, files in os.walk(d):
            for f in files:
                p = Path(root) / f
                snap[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    return snap


@pytest.fixture(scope="module")
def portfolio_env() -> ResultEnvelope:
    return run_workflow("portfolio-offline")


# --------------------------------------------------------------------------- #
# envelope shape + provenance
# --------------------------------------------------------------------------- #

def test_returns_shared_result_envelope(portfolio_env):
    assert isinstance(portfolio_env, ResultEnvelope)
    assert portfolio_env.status == "ok"
    assert portfolio_env.result["kind"] == "files"
    names = {o["basename"] for o in portfolio_env.result["outputs"]}
    assert names == {"positions.csv", "allocation.csv"}
    for o in portfolio_env.result["outputs"]:
        assert len(o["sha256"]) == 64


def test_provenance_data_as_of_populated(portfolio_env):
    assert portfolio_env.provenance["data_as_of"] == "2026-06-27"


def test_provenance_code_version_is_assethold(portfolio_env):
    cv = portfolio_env.provenance["code_version"]
    assert set(cv) == {"package_version", "git_sha"}
    import importlib.metadata as md

    ah = md.version("assethold")
    au = md.version("assetutilities")
    assert cv["package_version"] == ah
    assert cv["package_version"] != au  # never the assetutilities default


def test_determinism_fields_present(portfolio_env):
    assert portfolio_env.determinism["result_hash"] == GOLDEN_PORTFOLIO_RESULT_HASH
    # default run: reproducible not checked -> honest None (never fabricated True)
    assert portfolio_env.determinism["reproducible"] is None
    assert portfolio_env.provenance["input_hash"] is not None


def test_data_as_of_missing_warns(monkeypatch):
    # Inline cfg with market prices but NO declared as-of date anywhere, AND no
    # registry-row hint (monkeypatched to None) -> fail-soft warn into the envelope.
    monkeypatch.setattr("assethold.workflow_api.runner.lookup_row_for_cfg", lambda c: None)
    cfg = {
        "basename": "portfolio",
        "Analysis": {"file_name": "portfolio-run"},
        "portfolio": {
            "data_dir": "examples/workflows/portfolio/data",
            "targets": "examples/workflows/portfolio/targets.yml",
            "prices": {"VOO": 500.0, "BRKB": 400.0},
            "outputs": {
                "positions_csv": "examples/workflows/portfolio/outputs/positions.csv",
                "allocation_csv": "examples/workflows/portfolio/outputs/allocation.csv",
            },
        },
    }
    env = run_workflow(cfg=cfg)
    assert env.status == "ok"
    assert env.provenance["data_as_of"] is None
    assert any("data_as_of" in w for w in env.warnings)


# --------------------------------------------------------------------------- #
# embed-path consumption + isolation (#3308 consumer gate)
# --------------------------------------------------------------------------- #

def test_run_drives_embed_path(monkeypatch):
    captured = {}

    def spy(cfg=None, embed=False, root_folder=None, log_to_file=True, **kw):
        captured["embed"] = embed
        captured["root_folder"] = root_folder
        captured["log_to_file"] = log_to_file
        return {"Analysis": {"file_name": "portfolio-run"}}

    monkeypatch.setattr("assethold.engine.engine", spy)
    env = run_workflow("portfolio-offline")
    assert captured["embed"] is True
    assert captured["root_folder"] and os.path.isabs(captured["root_folder"])
    assert captured["log_to_file"] is False
    # spy wrote nothing -> empty payload + a warning (proves we read from the root)
    assert env.result["outputs"] == []


def test_writes_nothing_outside_tempdir():
    before = _snapshot(PORTFOLIO_OUTPUTS_DIR)
    env = run_workflow("portfolio-offline")
    after = _snapshot(PORTFOLIO_OUTPUTS_DIR)
    assert env.status == "ok"
    assert before == after  # repo example tree byte-for-byte unchanged


def test_extract_result_excludes_cfg_dump(portfolio_env):
    for o in portfolio_env.result["outputs"]:
        assert not o["basename"].endswith(".yml")


# --------------------------------------------------------------------------- #
# determinism: content-sensitivity + golden + reproducible
# --------------------------------------------------------------------------- #

def test_result_hash_content_sensitive():
    base = run_workflow("portfolio-offline").determinism["result_hash"]
    same = run_workflow("portfolio-offline").determinism["result_hash"]
    perturbed = run_workflow(
        "portfolio-offline", params={"portfolio": {"prices": {"VOO": 999.0}}}
    ).determinism["result_hash"]
    assert base == same
    assert perturbed != base


def test_golden_portfolio_result_hash():
    env = run_workflow("portfolio-offline")
    assert env.determinism["result_hash"] == GOLDEN_PORTFOLIO_RESULT_HASH


def test_reproducible_true_on_double_run():
    env = run_workflow("portfolio-offline", verify_reproducible=True)
    assert env.determinism["reproducible"] is True
    assert env.determinism["result_hash"] == GOLDEN_PORTFOLIO_RESULT_HASH


# --------------------------------------------------------------------------- #
# build_cfg + fail-closed error envelopes
# --------------------------------------------------------------------------- #

def test_build_cfg_merges_params_over_example():
    row = runner_mod.resolve_registry_row("portfolio-offline")
    cfg = build_cfg(row, {"portfolio": {"prices": {"VOO": 123.0}}})
    assert cfg["basename"] == "portfolio"
    assert cfg["portfolio"]["prices"]["VOO"] == 123.0  # param wins
    assert cfg["portfolio"]["data_dir"]  # example keys preserved


def test_unknown_id_returns_error_envelope():
    env = run_workflow("nope-not-real")
    assert env.status == "error"
    assert env.result == {}
    assert env.warnings and "nope-not-real" in env.warnings[0]
    assert env.determinism["result_hash"] is None


def test_engine_exception_returns_error_envelope(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("router blew up")

    monkeypatch.setattr("assethold.engine.engine", boom)
    env = run_workflow("portfolio-offline")
    assert env.status == "error"
    assert any("router blew up" in w for w in env.warnings)
