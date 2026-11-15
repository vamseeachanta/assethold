#!/usr/bin/env python3
"""Leak scan for this public repository.

Fails (exit 1) when a tracked file:

* holds the repository owner's email address (any address whose local part
  contains the owner's surname; GitHub noreply addresses are allowed), or
* sits under a path that was moved to private storage on 2026-11-15
  (raw broker emails, data-room files, personal brokerage reports and config,
  personal statements, personal business and property documents, chat
  exports), or
* contains any literal listed in the ``LEAK_SCAN_EXTRA_PATTERNS`` environment
  variable (one per line, case-insensitive). CI fills it from a repository
  secret so that private names and numbers (for example the names of private
  repositories and account numbers) never have to be written into this public
  tree.

The scanner scans its own source too: its email pattern is assembled at run
time, so the file does not match itself.

Standard library only. Usage: ``python scripts/ci/leak_scan.py [repo_root]``.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

# Built by concatenation so this file never matches its own pattern.
_SURNAME = "ach" + "anta"
OWNER_EMAIL_RE = re.compile(
    rb"[A-Za-z0-9._%+-]*" + _SURNAME.encode() + rb"[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})",
    re.IGNORECASE,
)
ALLOWED_EMAIL_DOMAINS = {b"users.noreply.github.com"}

# Paths moved to private storage. A tracked file under any of these fails.
FORBIDDEN_PATH_PREFIXES = (
    "data/sandsig-cre-listings/email/",
    "data/cre/net_lease/nola-",
    "reports/daily-strategy/",
    "config/daily_strategy.yaml",
    "tests/modules/stocks/data/clients/",
    "docs/business/",
    "docs/domain/realestate/re_multifamily/walzel_properties/",
    "docs/domain/realestate/re_cre/kkd/",
    "data/private/",
)
FORBIDDEN_PATH_SUFFIXES = ("_conversations.md",)
FORBIDDEN_PATH_SUBSTRINGS = ("whatsapp chat with",)
# Single files removed on 2026-11-15 that no folder rule above covers.
FORBIDDEN_PATHS = frozenset(
    {
        "docs/domain/realestate/re_farmland/farmfolio/Las Lomas Property Service Agreement v3 for LOT #65_encrypted_.pdf",
        "docs/domain/realestate/re_cre/202-08-Stryker CRE News & Insights.pdf",
        "docs/domain/realestate/re_cre/2023-08-10 STRYKER- AquaSonic Car wash Development - Florida.pdf",
        "docs/plans/reviews/2026-09-22-plan-90-adversarial-review.md",
        "docs/session-handoffs/2026-09-22-issue-90-dual-basis-valuation-exit.md",
    }
)

EXTRA_PATTERNS_ENV = "LEAK_SCAN_EXTRA_PATTERNS"


def tracked_files(root: Path) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True
    ).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def path_findings(paths: list[str]) -> list[str]:
    findings = []
    for p in paths:
        if (
            p in FORBIDDEN_PATHS
            or p.startswith(FORBIDDEN_PATH_PREFIXES)
            or p.endswith(FORBIDDEN_PATH_SUFFIXES)
            or any(s in p.lower() for s in FORBIDDEN_PATH_SUBSTRINGS)
        ):
            findings.append(f"{p}: path is reserved for private storage")
    return findings


def content_findings(path: str, data: bytes, extra: list[bytes]) -> list[str]:
    findings = []
    for m in OWNER_EMAIL_RE.finditer(data):
        if m.group(1).lower() not in ALLOWED_EMAIL_DOMAINS:
            findings.append(f"{path}: owner email address")
            break
    lowered = data.lower()
    for i, pat in enumerate(extra, start=1):
        if pat in lowered:
            findings.append(f"{path}: matches private pattern #{i}")
    return findings


def load_extra_patterns() -> list[bytes]:
    raw = os.environ.get(EXTRA_PATTERNS_ENV, "")
    return [line.strip().lower().encode("utf-8") for line in raw.splitlines() if line.strip()]


def scan(root: Path) -> list[str]:
    paths = tracked_files(root)
    extra = load_extra_patterns()
    findings = path_findings(paths)
    for p in paths:
        full = root / p
        if not full.is_file():
            continue
        findings.extend(content_findings(p, full.read_bytes(), extra))
    return findings


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path.cwd()
    findings = scan(root)
    extra_count = len(load_extra_patterns())
    if findings:
        print(f"Leak scan FAILED: {len(findings)} finding(s)")
        for f in findings:
            print(f"  {f}")
        return 1
    print(f"Leak scan passed ({extra_count} private pattern(s) loaded).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
