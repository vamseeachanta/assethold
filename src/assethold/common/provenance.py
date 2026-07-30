# ABOUTME: assethold's own code-version provenance (workspace-hub#3308 AC#3).
# ABOUTME: Stamps assethold's package version/git sha via assetutilities code_version("assethold").
"""Provenance helper for assethold (workspace-hub#3308).

AC#3 requires the embed path to stamp **assethold's own** ``{package_version,
git_sha}`` -- never the assetutilities default. The parameterized
``code_version(package_name)`` (workspace-hub#3282/#3297) lives in
``assetutilities.workflow_api``; this thin wrapper passes ``"assethold"``.

An import-guarded local fallback keeps the helper usable even if a stale
``assetutilities`` lacks ``workflow_api`` (it returns the same shape from
assethold's ``__version__`` + a local git sha probe).
"""

from __future__ import annotations

import os
import subprocess


def _git_sha_or_none() -> str | None:
    """Best-effort short git sha for the assethold checkout; None if unavailable."""
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        sha = subprocess.check_output(
            ["git", "-C", here, "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
        )
        return sha.decode().strip() or None
    except Exception:
        return None


def assethold_code_version() -> dict:
    """Return assethold's own ``{package_version, git_sha}``.

    Uses the parameterized ``code_version("assethold")`` from
    ``assetutilities.workflow_api`` when available (#3282/#3297); falls back to
    assethold's local ``__version__`` + git probe otherwise. NEVER returns the
    assetutilities default package version.
    """
    try:
        from assetutilities.workflow_api import code_version

        return code_version("assethold")
    except ImportError:
        from assethold import __version__

        return {"package_version": __version__, "git_sha": _git_sha_or_none()}
