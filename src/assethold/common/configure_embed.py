# ABOUTME: Embeddable configuration for assethold's engine (workspace-hub#3308).
# ABOUTME: Mirrors assetutilities' configure_embed contract (#3297) for assethold's own engine.
"""Standalone ``configure_embed`` for assethold (workspace-hub#3308).

assethold has no local ``ApplicationManager`` (it imports the installed
``assetutilities`` package), so unlike #3297 this is a **module-level function**
(no ``self``, no ``library_name``) that mirrors the canonical #3297 signature
``configure_embed(cfg, basename, root_folder, log_to_file=False)``.

It makes the caller's in-memory cfg an ``AttributeDict`` and sets, **under the
injected root**:

- ``Analysis.analysis_root_folder`` -- honored by the ``stocks`` modules and by
  ``FileManagement.router``.
- ``Analysis.result_folder`` + ``Analysis.file_name`` -- so the engine's
  ``save_application_cfg`` cfg-dump lands under root instead of crashing
  (missing keys) or escaping the root.
- ``cfg["_config_dir_path"]`` -- per the locked #3297 contract, so any
  ``PathResolver``-routed / config-relative writes resolve under root and for
  cross-repo uniformity.

The ``workflow_io.output_path`` family is rebased separately via
``workflow_io.output_root(root_folder)`` (set by the engine embed branch); this
function only configures the cfg-driven write mechanisms.
"""

from __future__ import annotations

import datetime
import os

from assetutilities.common.update_deep import AttributeDict


def configure_embed(cfg, basename, root_folder, log_to_file=False):
    """Configure ``cfg`` for an embedded, root-sandboxed engine run.

    Parameters
    ----------
    cfg : dict | AttributeDict
        The caller's in-memory config. Returned as an ``AttributeDict``.
    basename : str
        The workflow basename (used for the cfg-dump file name).
    root_folder : str
        The injected root; every configured write lands under this dir.
    log_to_file : bool, default False
        Carried on ``Analysis`` for #3297 parity. assethold's engine writes no
        ``.log`` today, so this is informational unless a downstream consumer
        reads it.

    Raises
    ------
    ValueError
        If ``cfg`` or ``root_folder`` is None.
    """
    if cfg is None or root_folder is None:
        raise ValueError("configure_embed requires both cfg and root_folder")

    cfg = cfg if isinstance(cfg, AttributeDict) else AttributeDict(cfg)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%Hh%Mm")

    result_folder = os.path.join(root_folder, "results")
    os.makedirs(result_folder, exist_ok=True)

    # Preserve any caller-provided Analysis keys, then overlay the embed-root keys.
    analysis = dict(cfg.get("Analysis", {}))
    analysis.update(
        {
            "analysis_root_folder": root_folder,
            "result_folder": result_folder,
            "file_name": f"{basename}_{timestamp}",
            "log_folder": os.path.join(root_folder, "logs"),
            "log_to_file": log_to_file,
        }
    )
    cfg["Analysis"] = analysis
    cfg["_config_dir_path"] = root_folder
    return cfg
