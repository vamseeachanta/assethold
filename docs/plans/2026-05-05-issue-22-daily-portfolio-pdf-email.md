# Issue #22 Plan — Daily portfolio report as PDF emailed to inbox

**Issue:** [vamseeachanta/assethold#22](https://github.com/vamseeachanta/assethold/issues/22)
**Tier:** T2 (bug-fix-sized integration)
**Date:** 2026-05-05

## Context

Issue #22 wants the #21-Phase-5 daily report (terminal/HTML output) rendered as a styled PDF and emailed at 6:00 AM CST Mon-Fri. Body is concrete: weasyprint preferred (HTML→PDF), Gmail SMTP or API for delivery, Jinja2 template, systemd timer or cron, optional CSV attachment, no email on weekends/market-holidays. This depends on #21 Phase 5 (daily report generator) producing an HTML output that PDF rendering can consume.

`assethold.portfolio.daily_report` is scoped in the #21 plan to emit HTML via Jinja2 — that becomes the PDF source. Holiday calendar already exists in `src/assethold/utils/market_hours.py` (per issue #40 reference).

## Plan

1. **PDF renderer** at `src/assethold/portfolio/pdf_export.py`: `render_pdf(html_path, output_pdf)` using `weasyprint`. Add `weasyprint` to `pyproject.toml` deps.
2. **Email sender** at `src/assethold/portfolio/email_dispatch.py`: `send_email(recipient, subject, body, attachments: list[Path])` via `smtplib.SMTP_SSL` to Gmail with app-password auth. Credentials from env vars (`ASSETHOLD_SMTP_USER`, `ASSETHOLD_SMTP_PASS`, `ASSETHOLD_REPORT_RECIPIENT`).
3. **Config block** in `config/targets.yaml`:
   ```yaml
   email:
     recipient: vamsee@example.com
     subject_prefix: "[Portfolio Daily]"
     smtp_host: smtp.gmail.com
     smtp_port: 465
     attach_csv: true
   ```
4. **Holiday gate** in CLI entry: query `assethold.utils.market_hours.is_trading_day(date)` — skip dispatch on weekends and NYSE holidays.
5. **CLI extension** in `src/assethold/portfolio/daily_report.py`: add `--output pdf` (writes `data/reports/YYYY-MM-DD.pdf`) and `--email` flags. `--output pdf --email` is the cron-driven path.
6. **Systemd timer skeleton** at `scripts/systemd/assethold-daily-report.{service,timer}` (template only; user installs to `~/.config/systemd/user/`) — `OnCalendar=Mon..Fri 06:00 America/Chicago`.
7. **Tests** at `tests/portfolio/test_pdf_export.py` (renders a fixture HTML, asserts PDF file >0 bytes and `%PDF` magic-number prefix) and `tests/portfolio/test_email_dispatch.py` (mocks `smtplib.SMTP_SSL`, asserts MIME structure with attachment).

Smoke: `uv run python -m assethold.portfolio.daily_report --output pdf --no-email`, then visually inspect `data/reports/<today>.pdf`.

## Acceptance Criteria

- `weasyprint` renders the daily-report HTML to a valid PDF (≥1 page, contains expected position table cells via `pdfplumber` text-extraction in tests).
- Email dispatch sends via SMTP_SSL with the PDF + optional CSV as MIME attachments; tested with mocked SMTP.
- Cron/timer skeleton runs `--output pdf --email` only on Mon-Fri at 06:00 America/Chicago.
- Holiday gate skips email on a hand-checked NYSE holiday (e.g., 2026-07-03 observed Independence Day).
- Credentials never appear in the config file or command line — only via env vars; tests assert this via lint check.
- E2E smoke produces a PDF in `data/reports/` and exits 0.

## Open questions

- Gmail OAuth (cleaner) vs app-password (simpler) — default to app-password for v1 to ship faster; OAuth is a follow-up if security review demands it.
- Should the cron skeleton be systemd-only, or also include a cron-format file? Provide both — `scripts/cron/assethold-daily-report.cron` as a one-liner alternative.
