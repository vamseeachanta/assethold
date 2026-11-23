"""KML/KMZ exporter for the property_timeline module.

KMLExporter converts a PropertyTimeline into a KMZ file suitable for
opening in Google Earth Pro.  The built-in Google Earth timeline slider
will animate through the TimeSpan-tagged Placemark elements.

Two output modes:
1. to_kml_string()  — returns raw KML XML as a string (no file I/O,
                       no external dependency required)
2. export_kmz()     — packages the KML into a .kmz zip archive

KML is generated using stdlib xml.etree.ElementTree to avoid a
simplekml runtime dependency in environments where it is not installed.
"""

from __future__ import annotations

import logging
import os
import zipfile
import xml.etree.ElementTree as ET
from datetime import date
from typing import List, Optional

from assethold.modules.property_timeline.models import (
    DevelopmentChange,
    PropertyTimeline,
)

logger = logging.getLogger(__name__)

# KML namespace
_KML_NS = "http://www.opengis.net/kml/2.2"

# Colour map: confidence → KML AABBGGRR string
_CONFIDENCE_COLOURS = {
    "high": "ff0000ff",     # opaque red
    "medium": "ff00aaff",   # opaque orange
    "low": "ff00ffff",      # opaque yellow
}
_DEFAULT_COLOUR = _CONFIDENCE_COLOURS["medium"]


class KMLExporter:
    """Build a Google Earth KMZ animation from a PropertyTimeline.

    Each DevelopmentChange becomes a TimeSpan-tagged Placemark in the KML
    document.  Opening the resulting KMZ in Google Earth Pro and enabling
    the timeline slider produces a chronological flythrough.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def to_kml_string(self, timeline: PropertyTimeline) -> str:
        """Render the timeline as a KML XML string.

        No file I/O or external libraries required.

        Args:
            timeline: PropertyTimeline to serialise.

        Returns:
            KML document as a UTF-8 string.
        """
        root = ET.Element("kml")
        root.set("xmlns", _KML_NS)
        doc = ET.SubElement(root, "Document")
        name_el = ET.SubElement(doc, "name")
        name_el.text = f"Development Timeline — {timeline.address}"

        folder = ET.SubElement(doc, "Folder")
        folder_name = ET.SubElement(folder, "name")
        folder_name.text = "Development Changes"

        for change in timeline.changes:
            self._add_placemark(folder, change)

        ET.register_namespace("", _KML_NS)
        tree = ET.ElementTree(root)
        return ET.tostring(root, encoding="unicode", xml_declaration=False)

    def export_kmz(
        self,
        timeline: PropertyTimeline,
        output_dir: str = "data/gis",
        filename: Optional[str] = None,
    ) -> str:
        """Package the KML into a .kmz zip archive and write to disk.

        Args:
            timeline: PropertyTimeline to export.
            output_dir: Directory to write the KMZ file.
            filename: Override the default ``{property_id}.kmz`` name.

        Returns:
            Absolute path to the created KMZ file.
        """
        kml_str = self.to_kml_string(timeline)
        os.makedirs(output_dir, exist_ok=True)
        out_name = filename or f"{timeline.property_id}.kmz"
        out_path = os.path.join(output_dir, out_name)

        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as kmz:
            kml_content = '<?xml version="1.0" encoding="UTF-8"?>\n' + kml_str
            kmz.writestr("doc.kml", kml_content)

        logger.info("KMZ exported to: %s", out_path)
        return out_path

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _add_placemark(
        self,
        parent: ET.Element,
        change: DevelopmentChange,
    ) -> None:
        """Append a TimeSpan-tagged Placemark element to parent."""
        pm = ET.SubElement(parent, "Placemark")

        name_el = ET.SubElement(pm, "name")
        name_el.text = change.change_type.replace("_", " ").title()

        desc_el = ET.SubElement(pm, "description")
        desc_el.text = change.description

        ts = ET.SubElement(pm, "TimeSpan")
        begin = ET.SubElement(ts, "begin")
        begin.text = change.change_date.isoformat()

        style = ET.SubElement(pm, "Style")
        icon_style = ET.SubElement(style, "IconStyle")
        colour_el = ET.SubElement(icon_style, "color")
        colour_el.text = _CONFIDENCE_COLOURS.get(change.confidence, _DEFAULT_COLOUR)

        lat = change.metadata.get("centroid", (0.0, 0.0))[0]
        lon = change.metadata.get("centroid", (0.0, 0.0))[1]
        point = ET.SubElement(pm, "Point")
        coords = ET.SubElement(point, "coordinates")
        coords.text = f"{lon},{lat},0"
