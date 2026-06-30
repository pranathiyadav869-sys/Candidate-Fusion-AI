"""
engine/provenance.py
--------------------
Provenance records track exactly where each field value came from,
how it was extracted, and with what confidence.

Design Decisions:
- Provenance is stored per-field, not per-source, because the merge engine
  selects one value per field from possibly many sources.
- We record ALL candidates (not just the winner) so a reviewer can audit
  conflict resolution decisions.
- The ProvenanceTracker acts as a mutable accumulator during the pipeline;
  it is sealed into the final schema object at the end.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from engine.schema import FieldProvenance, ProvenanceEntry, SourceName

logger = logging.getLogger(__name__)


class ProvenanceTracker:
    """
    Mutable accumulator for provenance data during the pipeline run.

    Usage
    -----
    tracker = ProvenanceTracker()
    tracker.record("full_name", SourceName.RESUME, "regex", "Alice Smith", 0.95)
    tracker.record("full_name", SourceName.CSV, "direct_field", "ALICE SMITH", 0.82)
    tracker.select("full_name", SourceName.RESUME, 0.95)
    provenance_dict = tracker.finalize()
    """

    def __init__(self):
        self._data: Dict[str, Dict[str, Any]] = {}

    def record(
        self,
        field_name: str,
        source: SourceName,
        method: str,
        raw_value: Any,
        confidence: float,
    ) -> None:
        """Record a candidate value for a field from a source."""
        if field_name not in self._data:
            self._data[field_name] = {"selected": None, "entries": []}

        entry = ProvenanceEntry(
            source=source,
            method=method,
            raw_value=str(raw_value) if raw_value is not None else None,
            confidence=round(confidence, 4),
        )
        self._data[field_name]["entries"].append(entry)
        logger.debug(
            "Provenance recorded: field=%s source=%s method=%s conf=%.3f",
            field_name, source.value, method, confidence,
        )

    def select(
        self,
        field_name: str,
        selected_source: SourceName,
        final_confidence: float,
    ) -> None:
        """Mark which source was selected as the winner for this field."""
        if field_name not in self._data:
            self._data[field_name] = {"selected": None, "entries": []}
        self._data[field_name]["selected"] = (selected_source, final_confidence)

    def finalize(self) -> Dict[str, FieldProvenance]:
        """Convert accumulated data into immutable FieldProvenance objects."""
        result: Dict[str, FieldProvenance] = {}
        for field_name, data in self._data.items():
            entries = data.get("entries", [])
            selected = data.get("selected")
            if selected:
                sel_source, sel_conf = selected
            else:
                # If no explicit selection, use highest-confidence entry
                if entries:
                    best = max(entries, key=lambda e: e.confidence)
                    sel_source = best.source
                    sel_conf = best.confidence
                else:
                    sel_source = None
                    sel_conf = 0.0

            result[field_name] = FieldProvenance(
                selected_source=sel_source,
                entries=entries,
                confidence=round(sel_conf, 4),
            )
        return result

    def get_agreeing_sources(self, field_name: str, normalized_value: str) -> int:
        """
        Count how many sources provided a value that normalizes to the same string.
        Used by confidence engine for cross-source agreement bonus.
        """
        if field_name not in self._data:
            return 1
        count = sum(
            1 for e in self._data[field_name]["entries"]
            if e.raw_value and e.raw_value.lower().strip() == normalized_value.lower().strip()
        )
        return max(1, count)
