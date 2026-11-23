# ABOUTME: assethold-local run_workflow() -> shared ResultEnvelope via the #3308 embed path.
"""Deterministic, in-process workflow runner for assethold (workspace-hub#3287).

``run_workflow(workflow_id, params=None, cfg=None, verify_reproducible=False)``
returns a shared :class:`~assetutilities.workflow_api.envelope.ResultEnvelope`.

Design (locked by the #3287 plan): assethold has its OWN engine, so this is an
assethold-LOCAL ``run_workflow`` that REUSES the shared envelope + determinism
helpers (workspace-hub#3282) and drives assethold's own engine through the embed
path (workspace-hub#3308):

``engine(cfg=<built cfg>, embed=True, root_folder=tempfile.mkdtemp(), log_to_file=False)``

Side-effect-freeness comes ENTIRELY from that embed path -- this module adds NO
cfg-level output redirection of its own. The injected root sandboxes every write
(the ``workflow_io.output_path`` CSV writers AND the ``save_application_cfg``
cfg-dump); the runner recursively content-hashes the emitted files and
``shutil.rmtree``s the root, leaving the repo/example tree byte-for-byte intact.

Unlike assetutilities' runner -- whose ``extract_result`` globs ``result_folder``
non-recursively -- assethold's portfolio router writes its CSVs at the rebased
``portfolio.outputs.*`` relative paths (e.g. ``<root>/examples/.../positions.csv``),
NOT under ``<root>/results``. So this runner globs the WHOLE injected root
recursively, excluding only the ``<file_name>.yml`` cfg-dump.
"""

from __future__ import annotations

import copy
import glob
import hashlib
import os
import shutil
import tempfile
from pathlib import Path

import yaml

from assetutilities.common.update_deep import update_deep_dictionary
from assetutilities.workflow_api import (
    ResultEnvelope,
    compute_reproducible,
    input_hash,
    make_provenance,
    result_hash,
)

from assethold.workflow_api.provenance import market_data_as_of

PACKAGE_NAME = "assethold"


def _repo_root() -> Path:
    # runner.py -> workflow_api -> assethold -> src -> <repo root>
    return Path(__file__).resolve().parents[3]


def registry_path() -> Path:
    return _repo_root() / "docs" / "registry" / "workflows.yaml"


def load_registry() -> dict:
    with open(registry_path()) as fh:
        return yaml.safe_load(fh)


def resolve_registry_row(workflow_id: str) -> dict:
    registry = load_registry()
    for row in registry.get("workflows", []):
        if row.get("id") == workflow_id:
            return row
    raise KeyError(
        f"unknown workflow_id '{workflow_id}' (not in {registry_path()})"
    )


def lookup_row_for_cfg(cfg: dict) -> dict | None:
    basename = cfg.get("basename")
    if not basename:
        return None
    for row in load_registry().get("workflows", []):
        if row.get("basename") == basename or row.get("id") == basename:
            return row
    return None


def resolve_example_path(rel_input: str) -> Path:
    """Resolve a registry ``input:`` path against the repo root."""
    return _repo_root() / rel_input


def build_cfg(row: dict, params: dict | None) -> dict:
    """Build the run cfg from a registry row + caller params.

    Starts from the row's ``basename`` + its loaded example ``input``, then
    deep-merges caller ``params`` (params win).
    """
    cfg: dict = {"basename": row["basename"]}
    input_rel = row.get("input")
    if input_rel:
        with open(resolve_example_path(input_rel)) as fh:
            example_cfg = yaml.safe_load(fh) or {}
        cfg = update_deep_dictionary(cfg, example_cfg)
    if params:
        cfg = update_deep_dictionary(cfg, copy.deepcopy(params))
    return cfg


def _result_kind(row: dict | None) -> str:
    if not row:
        return "files"
    return (row.get("result") or {}).get("kind", "files")


def extract_result(cfg_base: dict, root_folder: str, kind: str = "files"):
    """Return ``(payload, warnings)`` for an embed run.

    For ``kind == "files"`` the ACTUALLY emitted files are discovered by globbing
    the WHOLE injected ``root_folder`` recursively (assethold's portfolio writes
    its CSVs at rebased ``portfolio.outputs.*`` paths, not under ``result_folder``).
    The ``save_application_cfg`` cfg-dump ``<file_name>.yml`` is EXCLUDED -- it
    embeds the tempdir abspath + a ``start_time`` datetime that would poison the
    content hash and make ``reproducible`` spuriously False.
    """
    analysis = cfg_base.get("Analysis", {}) or {}
    file_name = analysis.get("file_name", "")
    cfg_dump_name = file_name + ".yml"

    emitted = sorted(
        p
        for p in glob.glob(os.path.join(root_folder, "**", "*"), recursive=True)
        if os.path.isfile(p) and os.path.basename(p) != cfg_dump_name
    )

    files = []
    for path in emitted:
        with open(path, "rb") as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
        files.append(
            {
                "basename": os.path.basename(path),
                "sha256": digest,
                "size": os.path.getsize(path),
            }
        )

    warns = []
    if not files:
        warns.append(
            f"declared kind:files workflow emitted no files under {root_folder}"
        )
    return {"kind": "files", "outputs": files}, warns


def _run_once(cfg: dict, kind: str = "files"):
    """One side-effect-free embed run. Returns ``(payload, warnings, result_hash)``."""
    # Imported here to keep the (~30s cold) engine import off module load.
    from assethold.engine import engine as assethold_engine

    root = tempfile.mkdtemp(prefix="ahwf_")
    try:
        cfg_base = assethold_engine(
            cfg=copy.deepcopy(cfg),
            embed=True,
            root_folder=root,
            log_to_file=False,
        )
        payload, warns = extract_result(cfg_base, root, kind)
        return payload, warns, result_hash(payload)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def run_workflow(
    workflow_id: str | None = None,
    params: dict | None = None,
    cfg: dict | None = None,
    verify_reproducible: bool = False,
) -> ResultEnvelope:
    """Run an assethold registry workflow in-process; return a ResultEnvelope.

    Fail-closed: an unknown id or a router exception is returned as a
    ``status="error"`` envelope, never raised. Provenance stamps assethold's OWN
    ``code_version("assethold")`` and the declared market ``data_as_of``.
    """
    wid = workflow_id or "(inline-cfg)"
    try:
        if cfg is None:
            row = resolve_registry_row(workflow_id)
            cfg = build_cfg(row, params)
        else:
            cfg = copy.deepcopy(cfg)
            row = lookup_row_for_cfg(cfg)

        kind = _result_kind(row)
        as_of, as_of_warns = market_data_as_of(cfg, row)
        ihash = input_hash(cfg)
        payload, warns, rhash = _run_once(cfg, kind)
        repro = compute_reproducible(
            lambda: _run_once(cfg, kind)[2], rhash, verify_reproducible
        )
        return ResultEnvelope(
            workflow_id=wid,
            status="ok",
            result=payload,
            provenance=make_provenance(
                ihash, package_name=PACKAGE_NAME, data_as_of=as_of
            ),
            determinism={"result_hash": rhash, "reproducible": repro},
            confidence=None,
            warnings=warns + as_of_warns,
        )
    except Exception as exc:  # fail-closed -> error envelope, never a raw traceback
        return ResultEnvelope(
            workflow_id=wid,
            status="error",
            result={},
            provenance=make_provenance(
                None, package_name=PACKAGE_NAME, data_as_of=None
            ),
            determinism={"result_hash": None, "reproducible": None},
            confidence=None,
            warnings=[str(exc)],
        )
