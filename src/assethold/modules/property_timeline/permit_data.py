"""Permit and zoning data loader for the property_timeline module.

PermitDataLoader parses permit record dicts (from local open data APIs
or CSV exports) and converts them into DevelopmentChange objects that
can be added to a PropertyTimeline.

Supported open municipal data sources (no API key required):
- NYC Department of Buildings: data.cityofnewyork.us
- Chicago Data Portal: data.cityofchicago.org
- San Francisco Open Data: data.sfgov.org

All three use the Socrata Open Data API which returns JSON natively.
Live API calls are not made here — the caller supplies pre-fetched
record lists so the module remains testable without network access.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from assethold.modules.property_timeline.models import DevelopmentChange

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Permit type → DevelopmentChange type mapping
# ---------------------------------------------------------------------------

_PERMIT_TYPE_MAP: Dict[str, str] = {
    "new_construction": "construction",
    "new construction": "construction",
    "newconstruction": "construction",
    "demolition": "demolition",
    "demo": "demolition",
    "alteration": "renovation",
    "renovation": "renovation",
    "addition": "construction",
    "road": "road_expansion",
    "grading": "vegetation_loss",
}


class PermitDataLoader:
    """Convert permit record dicts into DevelopmentChange objects.

    Permit records are expected as plain dicts with at minimum:
      - ``issue_date``: ISO-8601 date string (YYYY-MM-DD) or date object
      - ``permit_type``: string label (see _PERMIT_TYPE_MAP above)
      - ``description``: free-text description

    Records missing ``issue_date`` are silently skipped.

    Args:
        confidence: Default confidence level for permit-sourced changes.
            Permits are authoritative official records so defaults to
            "high".
    """

    def __init__(self, confidence: str = "high") -> None:
        self.confidence = confidence

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_from_records(
        self,
        records: List[Dict[str, Any]],
    ) -> List[DevelopmentChange]:
        """Parse a list of permit record dicts into DevelopmentChange objects.

        Args:
            records: List of permit record dicts.

        Returns:
            List of DevelopmentChange objects (records without a date are
            skipped).
        """
        changes: List[DevelopmentChange] = []
        for record in records:
            change = self._parse_record(record)
            if change is not None:
                changes.append(change)
        logger.debug("Loaded %d permit changes from %d records", len(changes), len(records))
        return changes

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_record(
        self, record: Dict[str, Any]
    ) -> Optional[DevelopmentChange]:
        """Parse a single permit record dict.  Returns None on failure."""
        raw_date = record.get("issue_date")
        if raw_date is None:
            return None

        try:
            change_date = (
                date.fromisoformat(raw_date)
                if isinstance(raw_date, str)
                else raw_date
            )
        except (ValueError, TypeError):
            logger.warning("Could not parse permit date: %r", raw_date)
            return None

        permit_type = str(record.get("permit_type", "unknown")).lower().strip()
        change_type = _PERMIT_TYPE_MAP.get(permit_type, "unknown")

        description = record.get("description", "")
        if not description:
            description = f"Permit filed: {permit_type.replace('_', ' ').title()}"

        return DevelopmentChange(
            change_date=change_date,
            change_type=change_type,
            description=description,
            confidence=self.confidence,
            source="permit",
            metadata={k: v for k, v in record.items() if k != "description"},
        )
