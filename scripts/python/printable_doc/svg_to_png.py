#!/usr/bin/env python3
"""
svg_to_png.py — render an inline SVG out of an HTML page at print resolution.

For getting a drawing out of a report: a diagram drawn as inline SVG has no
raster to extract (``pdfimages`` on the printed PDF returns nothing), and
cropping pixels out of the PDF throws away the resolution the vector had.  This
re-renders the SVG from source at whatever scale is asked for instead.

It also solves the sizing problem.  Headless Chrome screenshots the window, so a
window taller than the drawing leaves a band of white and a shorter one crops
it.  ``--width`` plus the SVG's own ``viewBox`` aspect ratio gives the exact
height, so the output is the drawing and nothing else.

``--strip`` removes elements matching a regex before rendering, which is how a
commercial drawing becomes a field drawing: the same geometry with the prices
and the sale ordering taken out.  Keeping one source and two renders beats
maintaining two drawings that will drift.

Usage::

    python svg_to_png.py report.html -o plan.png --scale 3
    python svg_to_png.py report.html -o plan_field.png --index 1 \
        --strip '<g[^>]*class="money".*?</g>' --replace 'RESERVED - SELL LAST=RESERVED'
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent))
from md_to_printable import find_chrome  # noqa: E402

VIEWBOX = re.compile(
    r'viewBox\s*=\s*["\']\s*([-\d.]+)\s+([-\d.]+)\s+([\d.]+)\s+([\d.]+)\s*["\']'
)


def extract_svg(html: str, index: int = 0) -> str:
    spans = [(m.start(), html.index("</svg>", m.start()) + 6)
             for m in re.finditer(r"<svg\b", html)]
    if not spans:
        raise ValueError("no <svg> in the document")
    if index >= len(spans):
        raise ValueError(f"only {len(spans)} svg element(s); asked for index {index}")
    a, b = spans[index]
    return html[a:b]


def extract_style(html: str) -> str:
    """Carry the page's <style> blocks so CSS custom properties resolve."""
    return "".join(m.group(0) for m in re.finditer(r"<style\b.*?</style>", html, re.S))


def render(
    html_path: Path,
    out_png: Path,
    index: int = 0,
    width: int = 1200,
    scale: int = 3,
    pad: int = 24,
    background: str = "#ffffff",
    strip: Optional[List[str]] = None,
    replace: Optional[List[str]] = None,
) -> None:
    html = html_path.read_text(encoding="utf-8")
    svg = extract_svg(html, index)

    for pattern in strip or []:
        svg = re.sub(pattern, "", svg, flags=re.S)
    for pair in replace or []:
        if "=" not in pair:
            raise ValueError(f"--replace needs OLD=NEW, got {pair!r}")
        old, new = pair.split("=", 1)
        svg = svg.replace(old, new)

    m = VIEWBOX.search(svg)
    if not m:
        raise ValueError("svg has no viewBox, so its aspect ratio is unknown")
    vb_w, vb_h = float(m.group(3)), float(m.group(4))

    # min-width on the element would fight the requested render width
    svg = re.sub(r"min-width\s*:\s*[^;\"']+;?", "", svg)

    inner = width - 2 * pad
    height = round(inner * vb_h / vb_w) + 2 * pad

    page = (
        '<!doctype html><html><head><meta charset="utf-8">'
        f"<style>html,body{{margin:0;background:{background}}}</style>"
        + extract_style(html)
        + "</head><body>"
        f'<div style="width:{width}px;padding:{pad}px;background:{background}">'
        + svg
        + "</div></body></html>"
    )

    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "svg.html"
        src.write_text(page, encoding="utf-8")
        subprocess.run(
            [
                find_chrome(),
                "--headless",
                "--disable-gpu",
                "--hide-scrollbars",
                f"--default-background-color={background.lstrip('#').upper()}FF",
                f"--force-device-scale-factor={scale}",
                f"--window-size={width},{height}",
                f"--screenshot={out_png}",
                str(src),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    if not out_png.exists():
        raise RuntimeError("Chrome produced no PNG")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Render an inline SVG to PNG.")
    ap.add_argument("html", type=Path)
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--index", type=int, default=0, help="which <svg>, in document order")
    ap.add_argument("--width", type=int, default=1200, help="CSS px before scaling")
    ap.add_argument("--scale", type=int, default=3, help="device pixel ratio")
    ap.add_argument("--pad", type=int, default=24)
    ap.add_argument("--background", default="#ffffff")
    ap.add_argument("--strip", action="append", help="regex of markup to remove (repeatable)")
    ap.add_argument("--replace", action="append", metavar="OLD=NEW", help="repeatable")
    a = ap.parse_args(argv)
    render(a.html, a.out, a.index, a.width, a.scale, a.pad, a.background,
           a.strip, a.replace)
    size = a.out.stat().st_size
    print(f"wrote {a.out} ({size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
