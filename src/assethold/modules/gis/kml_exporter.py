"""KML exporter: generate Google Earth KML/KMZ timeline overlays.

Creates a KMZ file containing:
- TimeSpan-tagged GroundOverlay elements for satellite imagery
- Placemark pins for development milestones
- Semi-transparent polygon overlays for future projections

The resulting KMZ can be opened in Google Earth Pro; the built-in timeline
slider animates through the overlays chronologically.

External dependency: simplekml (pure Python, no C libs required).
"""

from __future__ import annotations

import logging
import os
import zipfile
from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Tuple

from assethold.modules.gis.timeline_builder import DevelopmentMilestone, DevelopmentTimeline
from assethold.modules.gis.projector import ProjectedDevelopment

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Colour constants for KML overlays
# ---------------------------------------------------------------------------

# KML colours are AABBGGRR hex strings (alpha, blue, green, red)
_COLOUR_MILESTONE_HIGH = "ff0000ff"    # opaque red
_COLOUR_MILESTONE_MEDIUM = "ff00aaff"  # opaque orange
_COLOUR_MILESTONE_LOW = "ff00ffff"     # opaque yellow
_COLOUR_PROJECTION_FILL = "400000ff"   # semi-transparent red


# ---------------------------------------------------------------------------
# KML exporter
# ---------------------------------------------------------------------------


class KMLExporter:
    """Build a Google Earth KMZ animation for a property development timeline.

    Args:
        output_dir: Directory for the exported KMZ file.
    """

    def __init__(self, output_dir: str = "data/gis") -> None:
        self.output_dir = output_dir

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def export(
        self,
        timeline: DevelopmentTimeline,
        projections: Optional[List[ProjectedDevelopment]] = None,
        property_location: Optional[Tuple[float, float]] = None,
        filename: Optional[str] = None,
    ) -> Optional[str]:
        """Generate a KMZ file from a development timeline.

        Args:
            timeline: Assembled DevelopmentTimeline from TimelineBuilder.
            projections: Optional list of ProjectedDevelopment items.
            property_location: (lat, lon) of the subject property.
            filename: Override output filename (default: {property_id}.kmz).

        Returns:
            Absolute path to the exported KMZ file, or None on failure.
        """
        try:
            import simplekml  # type: ignore[import]
        except ImportError:
            logger.error(
                "simplekml not installed. Install with: pip install simplekml"
            )
            return None

        kml = simplekml.Kml(name=f"Development Timeline — {timeline.address}")
        doc_folder = kml.newfolder(name="Historical Milestones")
        self._add_milestones(doc_folder, timeline.milestones, simplekml)

        if projections:
            proj_folder = kml.newfolder(name="Future Projections")
            self._add_projections(
                proj_folder,
                projections,
                location=property_location,
                simplekml=simplekml,
            )

        if property_location:
            lat, lon = property_location
            pin = kml.newpoint(
                name="Subject Property",
                coords=[(lon, lat)],
            )
            pin.style.iconstyle.color = "ff0000ff"

        out_path = self._write_kmz(kml, timeline.property_id, filename)
        logger.info("KMZ exported to: %s", out_path)
        return out_path

    def export_milestones_kml_string(
        self,
        milestones: List[DevelopmentMilestone],
    ) -> str:
        """Return raw KML string for milestone placemarks (no simplekml dep).

        Useful for testing or embedding KML directly in reports without
        writing files.

        Args:
            milestones: List of DevelopmentMilestone objects.

        Returns:
            KML document as a string.
        """
        placemarks = "\n".join(
            self._milestone_placemark_xml(m) for m in milestones
        )
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<kml xmlns="http://www.opengis.net/kml/2.2">\n'
            "  <Document>\n"
            f"    <name>Development Timeline</name>\n"
            f"{placemarks}\n"
            "  </Document>\n"
            "</kml>"
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _add_milestones(
        self,
        folder: object,
        milestones: List[DevelopmentMilestone],
        simplekml: object,
    ) -> None:
        """Add milestone placemarks to a KML folder."""
        for m in milestones:
            lat, lon = m.metadata.get("centroid", (0.0, 0.0))
            point = folder.newpoint(  # type: ignore[attr-defined]
                name=m.title,
                description=m.description,
                coords=[(lon, lat)],
            )
            ts = point.timespan  # type: ignore[attr-defined]
            ts.begin = m.event_date.isoformat()
            colour = self._colour_for_confidence(m.confidence)
            point.style.iconstyle.color = colour  # type: ignore[attr-defined]

    def _add_projections(
        self,
        folder: object,
        projections: List[ProjectedDevelopment],
        location: Optional[Tuple[float, float]],
        simplekml: object,
    ) -> None:
        """Add future projection overlays to a KML folder."""
        if location is None:
            return
        lat, lon = location
        delta = 0.005  # ~0.5 km half-width

        for proj in projections:
            # Square polygon centred on property
            coords = [
                (lon - delta, lat - delta),
                (lon + delta, lat - delta),
                (lon + delta, lat + delta),
                (lon - delta, lat + delta),
                (lon - delta, lat - delta),
            ]
            poly = folder.newpolygon(  # type: ignore[attr-defined]
                name=f"{proj.horizon_year} Projection ({proj.confidence})",
                description=(
                    f"{proj.basis}\n"
                    f"Projected buildings: {proj.projected_building_count}\n"
                    f"Density: {proj.projected_density_bldgs_per_sqkm:.1f} bldgs/km²"
                ),
                outerboundaryis=coords,
            )
            poly.timespan.begin = proj.projection_date.isoformat()  # type: ignore[attr-defined]
            poly.style.polystyle.color = _COLOUR_PROJECTION_FILL  # type: ignore[attr-defined]
            poly.style.linestyle.color = "ff0000ff"  # type: ignore[attr-defined]

    def _write_kmz(
        self,
        kml: object,
        property_id: str,
        filename: Optional[str],
    ) -> str:
        """Save KML as a KMZ (zip) file and return the path."""
        os.makedirs(self.output_dir, exist_ok=True)
        out_filename = filename or f"{property_id}.kmz"
        out_path = os.path.join(self.output_dir, out_filename)

        kml_str = kml.kml()  # type: ignore[attr-defined]
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as kmz:
            kmz.writestr("doc.kml", kml_str)

        return out_path

    @staticmethod
    def _colour_for_confidence(confidence: str) -> str:
        """Map confidence label to a KML AABBGGRR colour string."""
        mapping = {
            "high": _COLOUR_MILESTONE_HIGH,
            "medium": _COLOUR_MILESTONE_MEDIUM,
            "low": _COLOUR_MILESTONE_LOW,
        }
        return mapping.get(confidence, _COLOUR_MILESTONE_MEDIUM)

    @staticmethod
    def _milestone_placemark_xml(m: DevelopmentMilestone) -> str:
        """Build a minimal KML Placemark XML string for a milestone."""
        lat, lon = m.metadata.get("centroid", (0.0, 0.0))
        return (
            "    <Placemark>\n"
            f"      <name>{m.title}</name>\n"
            f"      <description>{m.description}</description>\n"
            "      <TimeSpan>\n"
            f"        <begin>{m.event_date.isoformat()}</begin>\n"
            "      </TimeSpan>\n"
            "      <Point>\n"
            f"        <coordinates>{lon},{lat},0</coordinates>\n"
            "      </Point>\n"
            "    </Placemark>"
        )
