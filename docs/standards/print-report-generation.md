# Print Report Generation Standard

> **Version:** 1.0.0
> **Last updated:** 2026-09-04
> **Scope:** Formal, circulated PDF reports produced from `assethold` analysis

## Relationship to the HTML Reporting Standard

[`HTML_REPORTING_STANDARDS.md`](../HTML_REPORTING_STANDARDS.md) governs **interactive
analysis reports and dashboards** — Plotly, hover tooltips, zoom, CSV-driven.

This standard governs a different artifact: a **formal report that a person will read,
print, attach to an email, or hand to counsel, a lender or a broker**. Those are
print-first documents. Interactivity is meaningless in them, and the requirements
conflict, so they are separated deliberately.

Choose by asking who consumes it:

| | Interactive HTML report | Print report |
|---|---|---|
| Reader | Us, exploring | A third party, deciding |
| Plots | Interactive, mandatory | Static — a printed page has no hover |
| Data | Loaded from CSV at view time | Frozen at publication |
| Lifetime | Regenerated on demand | A dated record of what was known |

## Requirements

### 1. Author in HTML, render with headless Chrome

```
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless --disable-gpu --no-pdf-header-footer \
  --print-to-pdf=report.pdf --virtual-time-budget=20000 \
  --user-data-dir=<scratch> "file://$PWD/report.html"
```

- **Do not use LibreOffice/`soffice`.** The Writer/Web filter mangles list markup and
  ignores `@page` rules.
- Pass a scratch `--user-data-dir`; Chrome will otherwise contend with a running profile.
- **Chrome frequently writes a valid PDF and then does not exit.** A non-zero exit code
  from a timeout is not evidence of failure. Verify the artifact, not the exit status.

### 2. Verify the output, always

Never ship a PDF without checking it programmatically:

```python
import pypdf
r = pypdf.PdfReader("report.pdf")
assert len(r.pages) > 0
assert abs(r.pages[0].mediabox.width - 595) < 2      # A4
text = " ".join(p.extract_text() or "" for p in r.pages)
assert "<expected heading>" in text                   # content actually rendered
assert "<superseded figure>" not in text              # corrections actually landed
```

Checking for a string that **should be gone** catches a failed edit, which is the more
dangerous case: a silently un-applied correction ships wrong numbers under a corrected
date.

### 3. Self-contained HTML

Inline every image as a `data:` URI. The HTML must render correctly when emailed on its
own, with no sibling files. Expect ~4/3 size inflation from base64 and compress
accordingly — `sips -Z <px> -s formatOptions <q>` for photographs, PNG for line work.

### 4. Print CSS

- `@page { size: A4; margin: 18mm 16mm 16mm 16mm; }`
- `-webkit-print-color-adjust: exact` — otherwise Chrome strips background fills
- `page-break-inside: avoid` on figures and callouts; `page-break-after: avoid` on headings
- `tr { page-break-inside: avoid }` so table rows do not split across pages

### 5. Third-party imagery must carry attribution

Any map, aerial or licensed image reproduced in a report **must** carry a visible
attribution line in its caption, naming the copyright holders.

- When screenshotting a mapping service, **crop the UI chrome but keep the service's own
  on-image attribution strip.** Crop losslessly (`jpegtran -crop WxH+X+Y`) so the imagery
  is not re-encoded.
- Record the licence position in the report's **limitations section**, not only in the
  caption — including whether the document may be redistributed publicly. A future reader
  must not have to reconstruct why the imagery is there or assume it is unencumbered.

### 6. State limitations in their own section

Every report carries a **Limitations** section covering, at minimum:

- which figures are measured versus estimated, and the tolerance on each;
- any cost figure that is an order-of-magnitude range rather than a quotation;
- source material that was illegible, unavailable or unread;
- questions of jurisdiction or applicability left unresolved;
- that the report is not legal, tax or engineering advice.

A report that reads as more certain than its evidence is worse than no report, because it
will be relied on. **Estimates presented without their tolerance are the most common way
this goes wrong.**

### 7. Dates and figures that are computed, not quoted

Any date or figure **derived** rather than read directly from a source must say so, and
must name what it depends on.

This is not pedantry. A renewal notice date computed as "90 days before expiry" depends on
the lease's own notice-computation and delivery provisions, and on whether a deadline
falling at a weekend rolls. Presenting the computed day as though it were quoted invites
someone to diary it and stop thinking.

### 8. Corrections are visible, not silent

When a superseded conclusion is corrected, **say so in the document**. Strike or annotate
the earlier statement and record what changed and why. Do not delete it.

Analysis documents are read by people deciding whether to trust the analysis. A file that
silently changes its mind offers no way to judge that.

## Field documents, and the tooling for them

A development or analysis document usually needs to exist twice.

The **commercial** version carries rates, budgets, tax position and negotiating strategy. The
**field** version — the one that reaches a contractor, a surveyor, a vendor — carries quantities
and sequence and **no prices at all**. A rupee or dollar figure on the field copy is negotiating
information handed to the other side, and a sale strategy on it is nobody's business.

Two scripts in [`scripts/python/printable_doc/`](https://github.com/vamseeachanta/assethold/tree/main/scripts/python/printable_doc)
build that second version. Both drive headless Chrome per §1 and take no third-party dependencies.

### `md_to_printable.py` — Markdown checklist to A4 PDF

```bash
python md_to_printable.py CHECKLIST.md -o checklist.pdf \
    --image site_plan.png --image-before "Part A" \
    --caption "The layout as measured." --check-currency
```

A deliberately small Markdown subset — headings, tables, task and plain lists, block quotes, fenced
code, inline emphasis. A document needing more than that has stopped being a checklist. What it
adds over a general converter is the three things a checklist actually needs in print:

- `- [ ]` renders as a real empty box big enough to tick, not a literal `[ ]` and not a disabled
  HTML checkbox that prints as a grey smudge;
- **blank table cells keep their height and a rule**, so a tally sheet prints as somewhere to write
  rather than a row of hairlines;
- wide numeric tables shrink to the page instead of clipping at the margin. A quantity table that
  loses its last column in print is worse than no table.

**`--check-currency` refuses to build a document containing a currency symbol.** It is the cheapest
possible guard on the rule above, and it belongs in whatever produces the field copy.

### `svg_to_png.py` — a vector drawing out of a report, at print resolution

```bash
python svg_to_png.py report.html -o plan.png --index 1 --scale 3
```

A diagram authored as inline SVG has no raster to extract — `pdfimages` on the printed PDF returns
nothing — and cropping pixels out of the PDF discards the resolution the vector had. This
re-renders from source at any scale, sizing the window from the SVG's own `viewBox` so the output
is the drawing and nothing else.

`--strip` and `--replace` produce a **field variant of the same drawing**: the same geometry with
the money figures and the sale ordering removed. One source feeding two renders beats two drawings
that will drift apart.

### Three things that fail silently in print

- **Box-drawing characters do not survive.** A sequence diagram drawn with `─ ├ └ ►` loses its
  rules, because the mono webfont has no glyph and the fallback is blank — the diagram still
  renders, just wrong. **Draw it in plain ASCII** (`-` `|` `+` `>` `v`) and it works in print, in a
  terminal and in a chat message.
- **Chrome will not load `file://` subresources into a page it is printing.** Images must be
  inlined as data URIs; `--image` does that. This is the same constraint as §3.
- **Webfonts need time.** `--virtual-time-budget` has to outlast the font fetch or the PDF renders
  in a fallback face at different metrics, which reflows every table.

## Client data

Reports about specific holdings — with addresses, tenants, rents, or recorded
instruments — belong in the relevant **private** repository, not here. `assethold` holds
the method and the abstracted models. See the convention in
[`modules/net_lease`](../api/net_lease.md): *"Abstracted tenant profile — no
client-identifying data."*
