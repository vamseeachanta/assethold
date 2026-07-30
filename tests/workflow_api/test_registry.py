"""Registry v2-superset tests (workspace-hub#3287 AC#2).

Pure-unit: parses the committed registry; verifies the v2 superset (schema_version,
top-level invocation, per-row result descriptor + market_data_as_of) without
running any workflow. Also exercises the runner's registry resolution helpers.
"""

from __future__ import annotations

import pytest

from assethold.workflow_api import runner


def _registry():
    return runner.load_registry()


def test_schema_version_is_2():
    assert _registry()["schema_version"] == 2


def test_top_level_invocation_and_repo():
    reg = _registry()
    assert reg["invocation"] == "uv run python -m assethold {input}"
    assert reg["repo"] == "assethold"


def test_portfolio_row_has_result_descriptor_and_market_as_of():
    row = runner.resolve_registry_row("portfolio-offline")
    assert row["basename"] == "portfolio"
    assert (row.get("result") or {}).get("kind") == "files"
    assert row["market_data_as_of"] == "2026-06-27"


def test_all_seven_rows_valid_at_v2():
    rows = _registry()["workflows"]
    assert len(rows) == 7
    for row in rows:
        assert row.get("id")
        assert row.get("basename")
        assert row.get("input")
        # result descriptor optional; when present it must declare a kind
        if "result" in row:
            assert row["result"].get("kind") in {"files", "in_memory"}


def test_resolve_unknown_id_raises_keyerror():
    with pytest.raises(KeyError):
        runner.resolve_registry_row("does-not-exist")


def test_lookup_row_for_cfg_by_basename():
    row = runner.lookup_row_for_cfg({"basename": "portfolio"})
    assert row is not None and row["id"] == "portfolio-offline"
    assert runner.lookup_row_for_cfg({}) is None
