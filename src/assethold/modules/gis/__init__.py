"""GIS-based property development timeline and future projection module.

Provides tools for:
- Geocoding property addresses to coordinates
- Fetching historical satellite imagery (Landsat, Sentinel-2)
- Detecting development changes between time periods
- Building historical development timelines
- Projecting future development patterns
- Exporting Google Earth KML/KMZ animations
- Generating HTML timeline reports

See docs/gis-tool-research.md for tool selection rationale and Phase 0 findings.
"""

__version__ = "0.1.0"

from assethold.modules.gis.geocoder import Geocoder, PropertyLocation
from assethold.modules.gis.change_detector import ChangeDetector, ChangeEvent
from assethold.modules.gis.timeline_builder import TimelineBuilder, DevelopmentMilestone
from assethold.modules.gis.projector import DevelopmentProjector, ProjectedDevelopment
from assethold.modules.gis.kml_exporter import KMLExporter
from assethold.modules.gis.report_generator import ReportGenerator

__all__ = [
    "Geocoder",
    "PropertyLocation",
    "ChangeDetector",
    "ChangeEvent",
    "TimelineBuilder",
    "DevelopmentMilestone",
    "DevelopmentProjector",
    "ProjectedDevelopment",
    "KMLExporter",
    "ReportGenerator",
]
