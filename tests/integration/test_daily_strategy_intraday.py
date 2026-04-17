"""ABOUTME: Integration tests for the --intraday flag in daily_strategy CLI.
ABOUTME: Covers fail-loud-on-Sunday and the no-flag legacy path."""

import subprocess
import sys


REPO = "/mnt/local-analysis/workspace-hub/assethold-worktrees/35-market-hours"


def test_intraday_on_sunday_fails_loud():
    """--intraday on a Sunday must exit 1 with 'next open' in stderr."""
    result = subprocess.run(
        [
            sys.executable, "-m", "assethold.analysis.daily_strategy",
            "--intraday",
            "--date", "2026-04-19",  # Sunday
            "--no-write",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 1, f"Expected exit 1, got {result.returncode}. stderr={result.stderr}"
    assert "next open" in result.stderr.lower(), f"stderr missing 'next open': {result.stderr}"


def test_no_intraday_flag_does_not_fail_on_sunday():
    """Without --intraday, a Sunday invocation runs to completion (legacy behavior)."""
    result = subprocess.run(
        [
            sys.executable, "-m", "assethold.analysis.daily_strategy",
            "--date", "2026-04-19",  # Sunday
            "--no-write",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=300,  # legacy path may do real fetches
    )
    # Exit 0 (success) or 0/1 if there's a real network failure — but NOT a market-hours
    # rejection. Specifically, "next open" should NOT appear in stderr.
    assert "next open" not in result.stderr.lower(), (
        f"Legacy path should not check market hours: {result.stderr}"
    )
