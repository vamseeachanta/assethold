"""Tests for scripts/ci/leak_scan.py (fictional inputs only)."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ci" / "leak_scan.py"
_spec = importlib.util.spec_from_file_location("leak_scan", _SCRIPT)
leak_scan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(leak_scan)

SURNAME = "ach" + "anta"


def test_owner_email_is_flagged():
    data = ("contact: someone." + SURNAME + "@example.com\n").encode()
    assert leak_scan.content_findings("a.md", data, []) == ["a.md: owner email address"]


def test_noreply_address_is_allowed():
    data = ("12345+someone" + SURNAME + "@users.noreply.github.com").encode()
    assert leak_scan.content_findings("a.md", data, []) == []


def test_unrelated_email_is_allowed():
    assert leak_scan.content_findings("a.md", b"info@example.com", []) == []


def test_extra_pattern_is_flagged_case_insensitively():
    findings = leak_scan.content_findings("b.py", b"repo = 'Fictional-Private-Repo'", [b"fictional-private-repo"])
    assert findings == ["b.py: matches private pattern #1"]


def test_extra_patterns_come_from_environment(monkeypatch):
    monkeypatch.setenv(leak_scan.EXTRA_PATTERNS_ENV, "AlphaRepo\n\n  BETA-123  \n")
    assert leak_scan.load_extra_patterns() == [b"alpharepo", b"beta-123"]


@pytest.mark.parametrize(
    "path",
    [
        "data/sandsig-cre-listings/email/x.md",
        "reports/daily-strategy/2030-01-01.md",
        "config/daily_strategy.yaml",
        "tests/modules/stocks/data/clients/client9/2030.csv",
        "docs/business/x.pdf",
        "docs/domain/realestate/x/someone_conversations.md",
        "docs/x/WhatsApp Chat with Someone.txt",
        "data/private/fidelity/2030.csv",
    ],
)
def test_private_paths_are_flagged(path):
    assert leak_scan.path_findings([path]) == [f"{path}: path is reserved for private storage"]


def test_example_config_path_is_allowed():
    assert leak_scan.path_findings(["config/daily_strategy.example.yaml"]) == []


def test_scan_end_to_end_on_a_temporary_repo(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "ok.md").write_text("nothing private here\n")
    (tmp_path / "bad.md").write_text("mail someone." + SURNAME + "@example.com\n")
    subprocess.run(["git", "add", "ok.md", "bad.md"], cwd=tmp_path, check=True)
    assert leak_scan.scan(tmp_path) == ["bad.md: owner email address"]


# Last main commit before the 2026-11-15 clean-up. Every file deleted since then
# must stay blocked by the path rules, so restoring any of them fails the scan.
CLEANUP_BASE = "0e734cc7f406bd8b72a9a68672d027277437eaf9"


def _removed_since_cleanup_base() -> list[str]:
    root = Path(__file__).resolve().parents[2]
    proc = subprocess.run(
        ["git", "diff", "--name-only", "--no-renames", "--diff-filter=D", "-z", CLEANUP_BASE, "HEAD"],
        cwd=root,
        capture_output=True,
    )
    if proc.returncode != 0:
        pytest.skip("clean-up base commit not in this clone (shallow checkout)")
    return [p for p in proc.stdout.decode("utf-8").split("\0") if p]


def test_every_removed_path_is_blocked_by_path_rules():
    removed = _removed_since_cleanup_base()
    assert len(removed) >= 525
    unprotected = [p for p in removed if not leak_scan.path_findings([p])]
    assert unprotected == []


def test_scanner_source_is_scanned_and_clean():
    data = _SCRIPT.read_bytes()
    assert leak_scan.content_findings("scripts/ci/leak_scan.py", data, []) == []
