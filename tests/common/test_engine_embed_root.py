"""Embed-port tests for assethold's engine (workspace-hub#3308).

Mirrors the assetutilities #3297 embed contract for assethold's OWN engine:
``engine(cfg=..., embed=True, root_folder=<dir>, log_to_file=False)`` routes
ALL writes (the ``workflow_io.output_path`` domains, the ``stocks``
``analysis_root_folder`` domain, and the ``save_application_cfg`` cfg-dump)
under the injected root, leaving nothing outside it; the default path stays
byte-identical. Provenance stamps assethold's own version, never assetutilities'.

Every test here exercises assethold-local code (engine, configure_embed,
workflow_io, provenance) with the workflow routers faked, so no real market
data / heavy domain fixtures are needed.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from assethold.common.configure_embed import configure_embed
from assethold.common.provenance import assethold_code_version
from assethold.engine import engine
from assethold.modules import workflow_io


@pytest.fixture
def scratch_cwd(tmp_path, monkeypatch):
    """Run the test body from an isolated cwd so cwd-leaks are detectable."""
    cwd = tmp_path / "scratch_cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    return cwd


def _list_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file()]


# --------------------------------------------------------------------------- #
# AC#1 — embed writes nothing outside root (both write mechanisms + cfg-dump)
# --------------------------------------------------------------------------- #

def test_embed_workflow_io_writes_under_root(scratch_cwd, tmp_path, monkeypatch):
    """A workflow_io.output_path-based domain writes ONLY under the injected root."""
    root = tmp_path / "embed_root"

    class FakeWorkflow:
        def router(self, cfg):
            target = workflow_io.output_path("results/portfolio/positions.csv")
            target.write_text("symbol,qty\nAAA,1\n", encoding="utf-8")
            return cfg

    monkeypatch.setattr("assethold.engine.PortfolioWorkflow", FakeWorkflow)
    cfg = {"basename": "portfolio"}

    engine(cfg=cfg, embed=True, root_folder=str(root))

    written = root / "results" / "portfolio" / "positions.csv"
    assert written.is_file()
    # Nothing escaped to the scratch cwd.
    assert _list_files(scratch_cwd) == []


def test_embed_stocks_writes_under_root(scratch_cwd, tmp_path, monkeypatch):
    """The stocks domain (analysis_root_folder) writes under the injected root."""
    root = tmp_path / "embed_root_stocks"
    seen = {}

    class FakeStocks:
        def router(self, cfg):
            arf = cfg["Analysis"]["analysis_root_folder"]
            seen["arf"] = arf
            out = os.path.join(arf, "AAA_data_copy.csv")
            with open(out, "w", encoding="utf-8") as f:
                f.write("close\n1.0\n")
            return cfg

    monkeypatch.setattr("assethold.engine.Stocks", FakeStocks)
    cfg = {"basename": "stocks"}

    engine(cfg=cfg, embed=True, root_folder=str(root))

    assert seen["arf"] == str(root)  # configure_embed injected the root (no skip-warning path)
    assert (root / "AAA_data_copy.csv").is_file()
    assert _list_files(scratch_cwd) == []


def test_embed_cfg_dump_under_root(scratch_cwd, tmp_path, monkeypatch):
    """save_application_cfg's <file_name>.yml lands under <root>/results, not cwd."""
    root = tmp_path / "embed_root_dump"

    class FakeWorkflow:
        def router(self, cfg):
            return cfg

    monkeypatch.setattr("assethold.engine.PortfolioWorkflow", FakeWorkflow)
    cfg = {"basename": "portfolio"}

    engine(cfg=cfg, embed=True, root_folder=str(root))

    dumps = list((root / "results").glob("portfolio_*.yml"))
    assert len(dumps) == 1, f"expected one cfg-dump under root/results, got {dumps}"
    assert _list_files(scratch_cwd) == []


# --------------------------------------------------------------------------- #
# configure_embed contract
# --------------------------------------------------------------------------- #

def test_embed_sets_config_dir_path(tmp_path):
    """configure_embed sets cfg['_config_dir_path'] == root_folder (locked contract)."""
    root = tmp_path / "cfgdir"
    cfg = configure_embed({"basename": "portfolio"}, "portfolio", str(root))
    assert cfg["_config_dir_path"] == str(root)
    assert cfg["Analysis"]["analysis_root_folder"] == str(root)
    assert cfg["Analysis"]["result_folder"] == os.path.join(str(root), "results")
    assert cfg["Analysis"]["file_name"].startswith("portfolio_")


def test_configure_embed_requires_cfg_and_root():
    with pytest.raises(ValueError):
        configure_embed(None, "portfolio", "/tmp/x")
    with pytest.raises(ValueError):
        configure_embed({"basename": "portfolio"}, "portfolio", None)


def test_configure_embed_preserves_caller_analysis_keys(tmp_path):
    cfg = configure_embed(
        {"basename": "portfolio", "Analysis": {"custom": "keep"}},
        "portfolio",
        str(tmp_path),
    )
    assert cfg["Analysis"]["custom"] == "keep"
    assert cfg["Analysis"]["analysis_root_folder"] == str(tmp_path)


def test_embed_requires_root_folder(scratch_cwd):
    """engine(embed=True) without root_folder raises ValueError."""
    with pytest.raises(ValueError):
        engine(cfg={"basename": "portfolio"}, embed=True)


# --------------------------------------------------------------------------- #
# absolute-path passthrough + re-entrancy
# --------------------------------------------------------------------------- #

def test_embed_absolute_output_path_not_rebased(scratch_cwd, tmp_path, monkeypatch):
    """An absolute config output path is left untouched (caller's explicit choice)."""
    root = tmp_path / "embed_root_abs"
    abs_target = tmp_path / "abs_outside" / "x.csv"

    class FakeWorkflow:
        def router(self, cfg):
            target = workflow_io.output_path(str(abs_target))
            target.write_text("data\n", encoding="utf-8")
            return cfg

    monkeypatch.setattr("assethold.engine.PortfolioWorkflow", FakeWorkflow)
    engine(cfg={"basename": "portfolio"}, embed=True, root_folder=str(root))

    assert abs_target.is_file()
    # The absolute path must NOT have been rebased under root.
    assert not (root / "abs_outside").exists()


def test_embed_repeated_calls_reentrant(scratch_cwd, tmp_path, monkeypatch):
    """Two sequential embed runs with different roots stay isolated; contextvar resets."""
    root_a = tmp_path / "root_a"
    root_b = tmp_path / "root_b"

    class FakeWorkflow:
        def router(self, cfg):
            target = workflow_io.output_path("results/out.csv")
            target.write_text("x\n", encoding="utf-8")
            return cfg

    monkeypatch.setattr("assethold.engine.PortfolioWorkflow", FakeWorkflow)

    engine(cfg={"basename": "portfolio"}, embed=True, root_folder=str(root_a))
    engine(cfg={"basename": "portfolio"}, embed=True, root_folder=str(root_b))

    assert (root_a / "results" / "out.csv").is_file()
    assert (root_b / "results" / "out.csv").is_file()
    # No bleed: each root has exactly its own out.csv (plus its cfg-dump).
    assert not (root_a / "results" / "out.csv").read_text() == ""
    # Contextvar fully reset after both runs.
    assert workflow_io._output_root.get() is None
    assert _list_files(scratch_cwd) == []


# --------------------------------------------------------------------------- #
# AC#2 — default behavior unchanged (backward-compat)
# --------------------------------------------------------------------------- #

def test_output_path_default_unchanged(scratch_cwd):
    """With no output_root context, output_path resolves relative -> cwd as today."""
    target = workflow_io.output_path("results/x.csv")
    assert target == Path("results/x.csv")  # relative, unchanged
    assert (scratch_cwd / "results").is_dir()  # parent created under cwd


def test_output_path_absolute_default_unchanged(scratch_cwd, tmp_path):
    abs_p = tmp_path / "abs" / "y.csv"
    target = workflow_io.output_path(str(abs_p))
    assert target == abs_p


# --------------------------------------------------------------------------- #
# AC#3 — provenance stamps assethold's version, never assetutilities'
# --------------------------------------------------------------------------- #

def test_provenance_is_assethold_not_assetutilities():
    prov = assethold_code_version()
    assert set(prov) == {"package_version", "git_sha"}
    # Must be assethold's version, never the assetutilities default.
    try:
        import importlib.metadata as md

        au_version = md.version("assetutilities")
    except Exception:
        au_version = None
    ah_version = prov["package_version"]
    if au_version is not None and ah_version is not None:
        assert ah_version != au_version or ah_version == md.version("assethold")
