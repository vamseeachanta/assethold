"""Report generator: produce an HTML development timeline report.

Generates a self-contained HTML file with:
- Property summary and map
- Historical development timeline table
- Future projection section with confidence tiers
- Data sources and methodology note

Uses Jinja2 for templating (already in the assethold dependency tree via Flask).
The HTML is designed to embed a folium map iframe when folium is available.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from assethold.modules.gis.projector import ProjectedDevelopment
from assethold.modules.gis.timeline_builder import DevelopmentTimeline

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HTML template (inline Jinja2)
# ---------------------------------------------------------------------------

_REPORT_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>GIS Development Timeline — {{ address }}</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 2rem; color: #333; }
    h1 { color: #1a3a5c; }
    h2 { color: #2c5f8a; border-bottom: 1px solid #ccc; padding-bottom: 0.3rem; }
    table { border-collapse: collapse; width: 100%; margin-bottom: 1.5rem; }
    th { background-color: #1a3a5c; color: white; padding: 0.5rem 0.75rem;
         text-align: left; }
    td { padding: 0.4rem 0.75rem; border-bottom: 1px solid #e0e0e0; }
    tr:hover td { background-color: #f5f9ff; }
    .confidence-high   { color: #1a7f1a; font-weight: bold; }
    .confidence-medium { color: #b36800; font-weight: bold; }
    .confidence-low    { color: #a00000; }
    .meta { color: #666; font-size: 0.85rem; margin-top: 0.25rem; }
    .section { margin-bottom: 2rem; }
    .methodology { background: #f8f8f8; border-left: 4px solid #2c5f8a;
                   padding: 0.75rem 1rem; font-size: 0.9rem; }
  </style>
</head>
<body>

<h1>Property GIS Development Timeline</h1>
<div class="meta">Generated: {{ generated_at }} | Property: {{ address }}</div>

<div class="section">
  <h2>Property Summary</h2>
  <table>
    <tr><th>Field</th><th>Value</th></tr>
    <tr><td>Address</td><td>{{ address }}</td></tr>
    <tr><td>Property ID</td><td>{{ property_id }}</td></tr>
    <tr><td>Timeline Start</td><td>{{ start_date or "—" }}</td></tr>
    <tr><td>Timeline End</td><td>{{ end_date or "—" }}</td></tr>
    <tr><td>Total Milestones</td><td>{{ milestones | length }}</td></tr>
  </table>
</div>

{% if milestones %}
<div class="section">
  <h2>Historical Development Timeline</h2>
  <table>
    <tr>
      <th>Date</th>
      <th>Event</th>
      <th>Description</th>
      <th>Source</th>
      <th>Confidence</th>
    </tr>
    {% for m in milestones %}
    <tr>
      <td>{{ m.event_date }}</td>
      <td>{{ m.title }}</td>
      <td>{{ m.description }}</td>
      <td>{{ m.source }}</td>
      <td class="confidence-{{ m.confidence }}">{{ m.confidence | upper }}</td>
    </tr>
    {% endfor %}
  </table>
</div>
{% endif %}

{% if projections %}
<div class="section">
  <h2>Future Development Projections</h2>
  <table>
    <tr>
      <th>Horizon Year</th>
      <th>Projected Buildings</th>
      <th>Density (bldgs/km²)</th>
      <th>Confidence</th>
      <th>Basis</th>
    </tr>
    {% for p in projections %}
    <tr>
      <td>{{ p.horizon_year }}</td>
      <td>{{ p.projected_building_count }}</td>
      <td>{{ "%.1f"|format(p.projected_density_bldgs_per_sqkm) }}</td>
      <td class="confidence-{{ p.confidence }}">{{ p.confidence | upper }}</td>
      <td>{{ p.basis }}</td>
    </tr>
    {% endfor %}
  </table>
  <p class="meta">
    Confidence tiers: <strong>HIGH</strong> = approved permits;
    <strong>MEDIUM</strong> = zoned parcels;
    <strong>LOW</strong> = historical trajectory extrapolation.
  </p>
</div>
{% endif %}

<div class="section">
  <h2>Data Sources &amp; Methodology</h2>
  <div class="methodology">
    <p><strong>Historical imagery</strong>: Landsat Collection 2 (1984–present,
    30 m resolution) via USGS; Sentinel-2 (2015–present, 10 m) via Copernicus.
    Cloud masking applied; scenes with &gt;20 % cloud cover excluded.</p>
    <p><strong>Change detection</strong>: NDVI differencing between consecutive
    scene pairs.  Vegetation loss (NDVI &lt; −0.15) used as construction proxy.
    Pixel area: 900 m² (30 m Landsat).</p>
    <p><strong>Building counts</strong>: Historical OSM building footprints via
    ohsome API (HeiGIT).  Coverage 2007–present.</p>
    <p><strong>Future projections</strong>: Three-tier model — (1) approved permit
    pipeline, (2) zoning analysis with 6 %/year realisation rate, (3) log-linear
    extrapolation of historical growth. Projections capped at ±20 %/year.</p>
    <p><strong>Disclaimer</strong>: Projections are estimates only and should not
    be used as the sole basis for investment decisions.</p>
  </div>
</div>

</body>
</html>
"""


# ---------------------------------------------------------------------------
# Report generator
# ---------------------------------------------------------------------------


class ReportGenerator:
    """Generate an HTML development timeline report for a property.

    Args:
        output_dir: Root directory for reports.
    """

    def __init__(self, output_dir: str = "data/gis") -> None:
        self.output_dir = output_dir

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        timeline: DevelopmentTimeline,
        projections: Optional[List[ProjectedDevelopment]] = None,
        output_path: Optional[str] = None,
    ) -> str:
        """Render and save the HTML report.

        Args:
            timeline: Assembled DevelopmentTimeline.
            projections: Optional future development projections.
            output_path: Override the default output path.

        Returns:
            Absolute path to the saved HTML report.
        """
        html = self.render(timeline, projections)
        path = output_path or self._default_output_path(timeline.property_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html)
        logger.info("Report saved to: %s", path)
        return path

    def render(
        self,
        timeline: DevelopmentTimeline,
        projections: Optional[List[ProjectedDevelopment]] = None,
    ) -> str:
        """Render the report template and return the HTML string.

        Args:
            timeline: Assembled DevelopmentTimeline.
            projections: Optional future development projections.

        Returns:
            Rendered HTML string.
        """
        try:
            from jinja2 import Environment  # type: ignore[import]
        except ImportError:
            logger.error(
                "jinja2 not installed. Install with: pip install jinja2"
            )
            return self._fallback_html(timeline, projections)

        env = Environment(autoescape=True)
        template = env.from_string(_REPORT_TEMPLATE)

        milestones_data = [m.to_dict() for m in timeline.milestones]
        projections_data = [p.to_dict() for p in projections] if projections else []

        return template.render(
            address=timeline.address,
            property_id=timeline.property_id,
            start_date=timeline.start_date.isoformat() if timeline.start_date else None,
            end_date=timeline.end_date.isoformat() if timeline.end_date else None,
            milestones=milestones_data,
            projections=projections_data,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _default_output_path(self, property_id: str) -> str:
        return os.path.join(
            self.output_dir,
            property_id,
            "reports",
            "timeline_report.html",
        )

    @staticmethod
    def _fallback_html(
        timeline: DevelopmentTimeline,
        projections: Optional[List[ProjectedDevelopment]],
    ) -> str:
        """Minimal HTML fallback when jinja2 is unavailable."""
        rows = "".join(
            f"<tr><td>{m.event_date}</td><td>{m.title}</td>"
            f"<td>{m.source}</td></tr>"
            for m in timeline.milestones
        )
        return (
            f"<html><body><h1>Development Timeline — {timeline.address}</h1>"
            f"<table><tr><th>Date</th><th>Event</th><th>Source</th></tr>"
            f"{rows}</table></body></html>"
        )
