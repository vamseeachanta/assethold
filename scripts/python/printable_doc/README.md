# printable_doc

Turning a Markdown checklist into something somebody can carry onto a site and tick with a pen, and
getting a vector drawing out of a report at print resolution.

| Script | Does |
|---|---|
| `md_to_printable.py` | Markdown → printable A4 PDF. Real tick boxes for `- [ ]`, blank table cells that stay tall enough to write in, wide tables shrunk to the page rather than clipped. `--check-currency` refuses to build a document that contains a price. |
| `svg_to_png.py` | Re-renders an inline `<svg>` from an HTML report to PNG at any scale, sized from its own `viewBox`. `--strip` / `--replace` produce a field variant of the same drawing from the same source. |

```bash
python md_to_printable.py CHECKLIST.md -o checklist.pdf \
    --image site_plan.png --image-before "Part A" \
    --caption "The layout as measured." --check-currency

python svg_to_png.py report.html -o plan.png --index 1 --scale 3
```

Both drive headless Chrome and take no third-party dependencies. Set `CHROME_PATH` if Chrome is not
in a standard location.

**Why these exist, the field-vs-commercial document rule, and the three things that fail silently in
print** — see [Print Report Generation Standard §
Field documents](../../../docs/standards/print-report-generation.md#field-documents-and-the-tooling-for-them).
