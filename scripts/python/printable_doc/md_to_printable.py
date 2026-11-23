#!/usr/bin/env python3
"""
md_to_printable.py — turn a Markdown checklist into a PDF somebody can carry
onto a site and tick with a pen.

Why this exists rather than pandoc: the field documents that come out of this
repo are checklists, and a checklist needs three things a generic converter
does not give you.

  * ``- [ ]`` has to render as an actual empty box, big enough to tick, not as
    a literal ``[ ]`` or a disabled HTML checkbox that prints as a grey smudge.
  * Blank table cells have to keep their height, or a tally sheet prints as a
    row of hairlines with nowhere to write.
  * Wide numeric tables have to shrink to the page rather than clip at the
    margin.  A quantity table that loses its last column in print is worse than
    no table.

So this is a small Markdown subset renderer plus a print stylesheet, driven
through headless Chrome.  The subset is deliberate: headings, tables, task and
plain lists, block quotes, fenced code, and inline bold/italic/code/links.  If a
document needs more than that it has stopped being a checklist.

Two things to know before using it:

  * **Box-drawing characters do not survive.**  Diagrams drawn with U+2500 and
    friends silently lose their rules in print, because the mono webfont has no
    glyph for them and the fallback is blank.  Draw sequence diagrams in plain
    ASCII (``-`` ``|`` ``+`` ``>`` ``v``) and they render everywhere, including
    in a terminal and in a chat message.
  * **Images must be embedded.**  Chrome will not load ``file://`` subresources
    into a page it is printing, so ``--image`` inlines the file as a data URI.

Usage::

    python md_to_printable.py CHECKLIST.md -o checklist.pdf
    python md_to_printable.py CHECKLIST.md -o checklist.pdf \
        --image site_plan.png --image-before "Part A" \
        --caption "The layout as measured. Print and carry."
    python md_to_printable.py CHECKLIST.md -o checklist.html   # skip Chrome

Chrome is located from CHROME_PATH, else the usual macOS/Linux install paths.
"""

from __future__ import annotations

import argparse
import base64
import html as H
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

# --------------------------------------------------------------------------
# Markdown subset -> HTML
# --------------------------------------------------------------------------

_BLOCK_START = re.compile(r"^(#|\||>|[-*] |\d+\. |```|---\s*$)")


def _inline(text: str) -> str:
    t = H.escape(text)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\*\w])\*([^*]+)\*(?!\*)", r"<em>\1</em>", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)
    return t


def _cell(text: str) -> str:
    t = text.strip()
    if t == "[ ]":
        return '<span class="cb"></span>'
    if t in ("[x]", "[X]"):
        return '<span class="cb on"></span>'
    return _inline(t)


def _split_row(row: str) -> List[str]:
    return row.strip().strip("|").split("|")


def markdown_to_html(md: str) -> str:
    """Render the supported subset. Unsupported syntax degrades to a paragraph."""
    lines = md.split("\n")
    out: List[str] = []
    i, n = 0, len(lines)

    while i < n:
        line = lines[i]

        if line.startswith("```"):
            i += 1
            buf = []
            while i < n and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append("<pre>" + H.escape("\n".join(buf)) + "</pre>")
            continue

        if re.match(r"^\s*---\s*$", line):
            out.append("<hr>")
            i += 1
            continue

        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{_inline(m.group(2))}</h{lvl}>")
            i += 1
            continue

        if line.startswith("|"):
            rows = []
            while i < n and lines[i].startswith("|"):
                rows.append(lines[i])
                i += 1
            header = _split_row(rows[0])
            is_rule = len(rows) > 1 and set(
                rows[1].replace("|", "").replace(" ", "")
            ) <= set("-:")
            body = rows[2:] if is_rule else rows[1:]
            thead = ""
            if any(c.strip() for c in header) and is_rule:
                thead = (
                    "<thead><tr>"
                    + "".join(f"<th>{_cell(c)}</th>" for c in header)
                    + "</tr></thead>"
                )
            elif not is_rule:
                body = rows
            tbody = "".join(
                "<tr>" + "".join(f"<td>{_cell(c)}</td>" for c in _split_row(r)) + "</tr>"
                for r in body
            )
            out.append(f'<div class="tw"><table>{thead}<tbody>{tbody}</tbody></table></div>')
            continue

        if line.startswith("> "):
            buf = []
            while i < n and lines[i].startswith(">"):
                buf.append(lines[i][1:].strip())
                i += 1
            out.append("<blockquote>" + _inline(" ".join(buf)) + "</blockquote>")
            continue

        if re.match(r"^[-*] ", line) or re.match(r"^\d+\. ", line):
            ordered = bool(re.match(r"^\d+\. ", line))
            items: List[str] = []
            while i < n:
                s = lines[i]
                if re.match(r"^[-*] ", s) or re.match(r"^\d+\. ", s):
                    items.append(re.sub(r"^([-*]|\d+\.) ", "", s))
                elif items and s.startswith("  ") and s.strip():
                    items[-1] += " " + s.strip()
                else:
                    break
                i += 1
            checked = any(x.startswith(("[ ] ", "[x] ", "[X] ")) for x in items)
            li = ""
            for it in items:
                if it.startswith("[ ] "):
                    li += f'<li class="ck"><span class="cb"></span><span>{_inline(it[4:])}</span></li>'
                elif it.startswith(("[x] ", "[X] ")):
                    li += f'<li class="ck"><span class="cb on"></span><span>{_inline(it[4:])}</span></li>'
                else:
                    li += f"<li>{_inline(it)}</li>"
            tag = "ol" if ordered else "ul"
            cls = ' class="cks"' if checked else ""
            out.append(f"<{tag}{cls}>{li}</{tag}>")
            continue

        if not line.strip():
            i += 1
            continue

        buf = [line]
        i += 1
        while i < n and lines[i].strip() and not _BLOCK_START.match(lines[i]):
            buf.append(lines[i])
            i += 1
        out.append("<p>" + _inline(" ".join(buf)) + "</p>")

    return "\n".join(out)


# --------------------------------------------------------------------------
# Print stylesheet
# --------------------------------------------------------------------------

PRINT_CSS = """
@page { size: A4 portrait; margin: 14mm 14mm 16mm; }
*{box-sizing:border-box}
html,body{background:#fff;color:#141413}
body{margin:0;font-family:"Source Serif 4",Georgia,serif;font-size:11.4px;
  line-height:1.5;-webkit-print-color-adjust:exact;print-color-adjust:exact}
h1{font-family:Archivo,Helvetica,Arial,sans-serif;font-size:25px;line-height:1.12;
  font-weight:700;letter-spacing:-.02em;margin:0 0 12px;max-width:30ch}
h2{font-family:Archivo,Helvetica,Arial,sans-serif;font-size:16px;font-weight:700;
  margin:22px 0 8px;padding-bottom:5px;border-bottom:2px solid #141413;break-after:avoid}
h3{font-family:Archivo,Helvetica,Arial,sans-serif;font-size:12.5px;font-weight:600;
  margin:15px 0 6px;color:#8E3D16;break-after:avoid}
h4{font-size:11.4px;font-weight:600;margin:12px 0 5px;break-after:avoid}
p{margin:0 0 8px}
hr{border:0;border-top:1px solid #CDD5DB;margin:14px 0}
code{font-family:"IBM Plex Mono",Menlo,monospace;font-size:10.2px;background:#F2F4F6;padding:1px 3px}
a{color:#8E3D16;text-decoration:none}
blockquote{margin:10px 0;padding:9px 14px;border-left:3px solid #B54E1D;
  background:#FBF3EE;font-size:12px;break-inside:avoid}
pre{font-family:"IBM Plex Mono",Menlo,monospace;font-size:9.2px;line-height:1.45;
  background:#F7F8F9;border:1px solid #E1E6E9;padding:10px 12px;white-space:pre;
  break-inside:avoid;margin:0 0 10px}
.tw{margin:0 0 11px}
table{border-collapse:collapse;width:100%;font-size:10.2px}
th{font-family:"IBM Plex Mono",monospace;font-size:8.4px;letter-spacing:.08em;
  text-transform:uppercase;text-align:left;color:#5A646E;padding:6px 8px;
  border-bottom:1.4px solid #A9B4BC;background:#F2F4F6}
td{padding:5px 8px;border-bottom:1px solid #E1E6E9;vertical-align:top}
tr{break-inside:avoid}
table tr:nth-child(even) td{background:#FAFBFC}
/* a blank cell is somewhere to write, so it keeps its height and a rule */
td:empty::after{content:"\\00a0";display:block;height:15px}
td:empty{border-bottom:1px solid #A9B4BC}
ul,ol{margin:0 0 10px;padding-left:1.15em}
li{margin:0 0 4px}
ul.cks,ol.cks{list-style:none;padding-left:0;margin:0 0 11px}
li.ck{display:flex;gap:8px;align-items:flex-start;margin:0 0 5px;break-inside:avoid}
.cb{flex:0 0 auto;width:10px;height:10px;border:1.3px solid #5A646E;border-radius:1.5px;
  display:inline-block;margin-top:2.5px;background:#fff}
.cb.on{background:#5A646E}
td .cb{margin-top:1px}
figure.plan{margin:14px 0 4px;break-inside:avoid}
figure.plan img{width:100%;display:block;border:1px solid #E1E6E9}
figcaption{font-family:"IBM Plex Mono",monospace;font-size:8.6px;color:#5A646E;margin-top:6px}
"""

FONTS = (
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    "family=Archivo:wght@600;700&family=IBM+Plex+Mono:wght@400;500&"
    'family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap">'
)


def _data_uri(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "gif": "image/gif", "webp": "image/webp", "svg": "image/svg+xml"}.get(ext)
    if mime is None:
        raise ValueError(f"unsupported image type: {path.suffix}")
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def build_html(
    md_path: Path,
    image: Optional[Path] = None,
    image_before: Optional[str] = None,
    caption: str = "",
    extra_css: str = "",
) -> str:
    body = markdown_to_html(md_path.read_text(encoding="utf-8"))
    if image is not None:
        cap = f"<figcaption>{H.escape(caption)}</figcaption>" if caption else ""
        fig = (
            f'<figure class="plan"><img src="{_data_uri(image)}" alt="">{cap}</figure>'
        )
        anchor = None
        if image_before:
            for pat in (f"<hr>\n<h2>{image_before}", f"<h2>{image_before}"):
                if pat in body:
                    anchor = pat
                    break
        if anchor:
            body = body.replace(anchor, fig + "\n" + anchor, 1)
        else:
            if image_before:
                print(
                    f"warning: no heading starting {image_before!r}; "
                    "image placed at the top",
                    file=sys.stderr,
                )
            body = fig + "\n" + body
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        + FONTS
        + "<style>"
        + PRINT_CSS
        + extra_css
        + "</style></head><body>"
        + body
        + "</body></html>"
    )


# --------------------------------------------------------------------------
# Chrome
# --------------------------------------------------------------------------

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome",
    "chromium",
    "chromium-browser",
]


def find_chrome() -> str:
    env = os.environ.get("CHROME_PATH")
    if env and (Path(env).exists() or shutil.which(env)):
        return env
    for c in CHROME_CANDIDATES:
        if Path(c).exists() or shutil.which(c):
            return c
    raise RuntimeError(
        "Chrome not found. Set CHROME_PATH to a Chrome or Chromium binary."
    )


def html_to_pdf(html: str, out_pdf: Path, wait_ms: int = 9000) -> None:
    """Print HTML to PDF. ``wait_ms`` lets webfonts and any script settle."""
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "doc.html"
        src.write_text(html, encoding="utf-8")
        subprocess.run(
            [
                find_chrome(),
                "--headless",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--virtual-time-budget={wait_ms}",
                f"--print-to-pdf={out_pdf}",
                str(src),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    if not out_pdf.exists():
        raise RuntimeError("Chrome produced no PDF")


def page_count(pdf: Path) -> int:
    """Rough page count without a PDF library."""
    d = pdf.read_bytes()
    return d.count(b"/Type /Page") - d.count(b"/Type /Pages")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    ap.add_argument("markdown", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True,
                    help="output .pdf, or .html to stop before Chrome")
    ap.add_argument("--image", type=Path, help="drawing to embed as a data URI")
    ap.add_argument("--image-before", metavar="HEADING",
                    help="place the image before the h2 starting with this text")
    ap.add_argument("--caption", default="")
    ap.add_argument("--css", default="", help="extra CSS appended to the stylesheet")
    ap.add_argument("--check-currency", action="store_true",
                    help="fail if the document contains a currency symbol - use on "
                         "field documents that must not carry prices")
    a = ap.parse_args(argv)

    if a.check_currency:
        text = a.markdown.read_text(encoding="utf-8")
        hits = [s for s in ("₹", "$", "€", "£", "INR ", "USD ") if s in text]
        if hits:
            print(f"currency found in {a.markdown}: {hits}", file=sys.stderr)
            return 2

    html = build_html(a.markdown, a.image, a.image_before, a.caption, a.css)
    if a.out.suffix.lower() == ".html":
        a.out.write_text(html, encoding="utf-8")
        print(f"wrote {a.out}")
        return 0
    html_to_pdf(html, a.out)
    print(f"wrote {a.out} ({page_count(a.out)} pages)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
