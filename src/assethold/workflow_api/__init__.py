# ABOUTME: Public surface for assethold's deterministic workflow API (workspace-hub#3287).
"""Deterministic, in-process workflow API for assethold.

assethold has its OWN engine (it does not use assetutilities' ``run_workflow``).
This package ships an assethold-local ``run_workflow`` that REUSES the shared
:class:`~assetutilities.workflow_api.envelope.ResultEnvelope` + determinism
helpers (workspace-hub#3282) and drives assethold's own engine through the
embed path delivered by workspace-hub#3308
(``engine(cfg=..., embed=True, root_folder=..., log_to_file=False)``).

The shared ``ResultEnvelope`` is re-exported here so adopters import it from one
place; it is NOT redefined.
"""

from assetutilities.workflow_api import ResultEnvelope

from assethold.workflow_api.runner import (
    build_cfg,
    extract_result,
    run_workflow,
)

__all__ = [
    "ResultEnvelope",
    "run_workflow",
    "build_cfg",
    "extract_result",
]
