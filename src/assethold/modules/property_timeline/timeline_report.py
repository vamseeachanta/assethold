"""HTML timeline report generator for the property_timeline module.

TimelineReport renders a self-contained HTML report that includes:
- Property summary table
- Chronological development changes table
- Future projection section (when projections are supplied)
- Data sources and methodology note

Jinja2 is used for templating (already in the assethold dependency tree).
A fallback plain-HTML generator is used if Jinja2 is unavailable.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from assethold.modules.property_timeline.models import PropertyTimeline

if TYPE_CHECKING:
    from assethold.modules.property_timeline.projection import DevelopmentProjection

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Jinja2 template
# ---------------------------------------------------------------------------

_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Property Development Timeline — {{ address }}</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 2rem; color: #333; }
    h1 { color: #1a3a5c; }
    h2 { color: #2c5f8a; border-bottom: 1px solid #ccc; padding-bottom: 0.3rem; }
    table { border-collapse: collapse; width: 100%; margin-bottom: 1.5rem; }
    th { background: #1a3a5c; color: #fff; padding: 0.5rem 0.75rem; text-align: left; }
    td { padding: 0.4rem 0.75rem; border-bottom: 1px solid #e0e0e0; }
    tr:hover td { background: #f5f9ff; }
    .high   { color: #1a7f1a; font-weight: bold; }
    .medium { color: #b36800; font-weight: bold; }
    .low    { color: #a00000; }
    .meta   { color: #666; font-size: 0.85rem; }
    .note   { background: #f8f8f8; border-left: 4px solid #2c5f8a;
              padding: 0.75rem 1rem; font-size: 0.9rem; }
  </style>
</head>
<body>
<h1>Property Development Timeline</h1>
<p class="meta">Generated: {{ generated_at }} | Property: {{ address }}</p>

<h2>Property Summary</h2>
<table>
  <tr><th>Field</th><th>Value</th></tr>
  <tr><td>Address</td><td>{{ address }}</td></tr>
  <tr><td>Property ID</td><td>{{ property_id }}</td></tr>
  <tr><td>Total Changes</td><td>{{ changes | length }}</td></tr>
</table>

{% if changes %}
<h2>Historical Development Changes</h2>
<table>
  <tr>
    <th>Date</th><th>Type</th><th>Description</th>
    <th>Source</th><th>Confidence</th>
  </tr>
  {% for c in changes %}
  <tr>
    <td>{{ c.change_date }}</td>
    <td>{{ c.change_type | replace("_", " ") | title }}</td>
    <td>{{ c.description }}</td>
    <td>{{ c.source }}</td>
    <td class="{{ c.confidence }}">{{ c.confidence | upper }}</td>
  </tr>
  {% endfor %}
</table>
{% endif %}

{% if projections %}
<h2>Future Development Projections</h2>
<table>
  <tr>
    <th>Horizon Year</th><th>Projected Buildings</th>
    <th>Confidence</th><th>Basis</th>
  </tr>
  {% for p in projections %}
  <tr>
    <td>{{ p.horizon_year }}</td>
    <td>{{ p.projected_building_count }}</td>
    <td class="{{ p.confidence }}">{{ p.confidence | upper }}</td>
    <td>{{ p.basis }}</td>
  </tr>
  {% endfor %}
</table>
<p class="meta">
  <strong>HIGH</strong> = approved permits;
  <strong>MEDIUM</strong> = zoning analysis;
  <strong>LOW</strong> = historical trajectory extrapolation.
</p>
{% endif %}

<h2>Data Sources &amp; Methodology</h2>
<div class="note">
  <p><strong>Satellite imagery</strong>: Landsat Collection 2 (1984–present,
  30 m) via USGS; Sentinel-2 (2015–present, 10 m) via Copernicus.
  Cloud cover threshold 20 %; NDVI differencing for change detection.</p>
  <p><strong>Building counts</strong>: Historical OSM footprints via ohsome API
  (HeiGIT), 2007–present.</p>
  <p><strong>Permits</strong>: Municipal open data APIs (NYC, Chicago, SF — no
  API key required).</p>
  <p><strong>Disclaimer</strong>: Projections are estimates and should not be
  used as the sole basis for investment decisions.</p>
</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Report generator
# ---------------------------------------------------------------------------


class TimelineReport:
    """Generate an HTML development timeline report for a property.

    Args:
        output_dir: Default root directory for saved reports.
    """

    def __init__(self, output_dir: str = "data/gis") -> None:
        self.output_dir = output_dir

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(
        self,
        timeline: PropertyTimeline,
        projections: Optional[List["DevelopmentProjection"]] = None,
    ) -> str:
        """Render the HTML report string.

        Args:
            timeline: PropertyTimeline to summarise.
            projections: Optional list of DevelopmentProjection objects.

        Returns:
            Rendered HTML as a string.
        """
        try:
            from jinja2 import Environment  # type: ignore[import]
        except ImportError:
            logger.warning("jinja2 unavailable — using plain-HTML fallback")
            return self._fallback_html(timeline, projections)

        env = Environment(autoescape=True)
        template = env.from_string(_TEMPLATE)

        changes_data = [c.to_dict() for c in timeline.changes]
        projections_data = (
            [p.to_dict() for p in projections] if projections else []
        )

        return template.render(
            address=timeline.address,
            property_id=timeline.property_id,
            changes=changes_data,
            projections=projections_data,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )

    def save(
        self,
        timeline: PropertyTimeline,
        projections: Optional[List["DevelopmentProjection"]] = None,
        output_dir: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> str:
        """Render and save the HTML report to disk.

        Args:
            timeline: PropertyTimeline to summarise.
            projections: Optional list of DevelopmentProjection objects.
            output_dir: Override the default output directory.
            filename: Override the default ``{property_id}_timeline.html``.

        Returns:
            Absolute path to the saved HTML file.
        """
        html = self.render(timeline, projections)
        out_dir = output_dir or os.path.join(
            self.output_dir, timeline.property_id, "reports"
        )
        os.makedirs(out_dir, exist_ok=True)
        out_file = filename or f"{timeline.property_id}_timeline.html"
        out_path = os.path.join(out_dir, out_file)
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(html)
        logger.info("Timeline report saved to: %s", out_path)
        return out_path

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _fallback_html(
        timeline: PropertyTimeline,
        projections: Optional[List["DevelopmentProjection"]],
    ) -> str:
        """Minimal HTML when Jinja2 is unavailable."""
        rows = "".join(
            f"<tr><td>{c.change_date}</td><td>{c.change_type}</td>"
            f"<td>{c.description}</td><td>{c.confidence}</td></tr>"
            for c in timeline.changes
        )
        return (
            f"<html><body><h1>Development Timeline — {timeline.address}</h1>"
            f"<table><tr><th>Date</th><th>Type</th>"
            f"<th>Description</th><th>Confidence</th></tr>"
            f"{rows}</table></body></html>"
        )
