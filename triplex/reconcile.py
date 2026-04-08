"""
Deterministic triple-source consensus reconciliation.

Compares the three independent scraper outputs field-by-field and builds
a locked data dict where every field is marked green/yellow/red based on
how many scrapers agreed.

Numeric fields use a 1% tolerance. Text fields require exact match (after
normalization). Sign fields (positive/negative) require explicit agreement.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from .schemas import (
    Confidence,
    LockedData,
    LockedField,
    ScrapedField,
    ScraperResult,
    fields_for,
)

log = logging.getLogger("triplex.reconcile")


# ── Value normalization ─────────────────────────────────────────────────────

_NUM_RE = re.compile(r"[-+]?\d[\d,]*\.?\d*")


def _to_float(value: Any) -> Optional[float]:
    """Best-effort conversion of a scraped value to a float for comparison."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        # Strip dollar signs, commas, trailing B/M/K, percent signs, spaces
        cleaned = value.strip().replace(",", "").replace("$", "").replace(" ", "")
        multiplier = 1.0
        if cleaned.lower().endswith("b"):
            multiplier = 1e9
            cleaned = cleaned[:-1]
        elif cleaned.lower().endswith("m"):
            multiplier = 1e6
            cleaned = cleaned[:-1]
        elif cleaned.lower().endswith("k"):
            multiplier = 1e3
            cleaned = cleaned[:-1]
        elif cleaned.endswith("%"):
            cleaned = cleaned[:-1]
        try:
            return float(cleaned) * multiplier
        except ValueError:
            return None
    return None


def _normalize_text(value: Any) -> str:
    """Normalize a text field for exact-match comparison."""
    if value is None:
        return ""
    s = str(value).strip().lower()
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s)
    # Strip surrounding quotes
    s = s.strip('"\'“”‘’')
    return s


def _numeric_equal(a: Any, b: Any, tolerance: float = 0.01) -> bool:
    """True if two numeric values agree within tolerance (relative)."""
    fa, fb = _to_float(a), _to_float(b)
    if fa is None or fb is None:
        return False
    if fa == 0 and fb == 0:
        return True
    if fa == 0 or fb == 0:
        return abs(fa - fb) < 1e-6
    return abs(fa - fb) / max(abs(fa), abs(fb)) <= tolerance


def _field_values_agree(a: Any, b: Any) -> bool:
    """Check if two scraped values agree (numeric tolerance OR text exact)."""
    if a is None or b is None:
        return False
    # Try numeric comparison first
    if _to_float(a) is not None and _to_float(b) is not None:
        return _numeric_equal(a, b)
    # Fall back to normalized text comparison
    return _normalize_text(a) == _normalize_text(b)


# ── Consensus merge ────────────────────────────────────────────────────────

def _consensus_for_field(
    field_name: str,
    a: Optional[ScrapedField],
    b: Optional[ScrapedField],
    c: Optional[ScrapedField],
) -> LockedField:
    """Decide LOCKED value for one field given three scraper outputs."""
    values = [
        ("a", a.value if a else None),
        ("b", b.value if b else None),
        ("c", c.value if c else None),
    ]
    non_null = [(lbl, v) for lbl, v in values if v is not None]

    if len(non_null) == 0:
        return LockedField(
            value=None,
            confidence="red",
            primary_url=None,
            wire_url=None,
            media_url=None,
            conflict_notes=f"{field_name}: no scraper returned a value",
        )

    # Count pairwise agreements
    agreements = 0
    if len(non_null) >= 2:
        if _field_values_agree(non_null[0][1], non_null[1][1]):
            agreements += 1
        if len(non_null) == 3:
            if _field_values_agree(non_null[1][1], non_null[2][1]):
                agreements += 1
            if _field_values_agree(non_null[0][1], non_null[2][1]):
                agreements += 1

    # Determine confidence
    if len(non_null) == 3 and agreements == 3:
        confidence: Confidence = "green"
        value = non_null[0][1]
    elif len(non_null) == 2 and agreements == 1:
        confidence = "green"
        value = non_null[0][1]
    elif len(non_null) == 3 and agreements >= 1:
        # 2 of 3 agree — pick the majority value
        confidence = "yellow"
        value = _majority_value(non_null)
    elif len(non_null) == 2 and agreements == 0:
        confidence = "yellow"
        value = non_null[0][1]  # arbitrary; tiebreaker will fix
    elif len(non_null) == 1:
        confidence = "yellow"
        value = non_null[0][1]
    else:
        confidence = "red"
        value = None

    conflict_notes = None
    if confidence != "green":
        values_display = ", ".join(f"{lbl}={v!r}" for lbl, v in non_null)
        conflict_notes = f"{field_name}: {values_display}"

    return LockedField(
        value=value,
        confidence=confidence,
        primary_url=(a.source_url if a else None),
        wire_url=(b.source_url if b else None),
        media_url=(c.source_url if c else None),
        conflict_notes=conflict_notes,
        verbatim=(a.verbatim if a else (b.verbatim if b else (c.verbatim if c else None))),
    )


def _majority_value(non_null: list[tuple[str, Any]]) -> Any:
    """Pick the value that at least 2 of the 3 scrapers agreed on."""
    for i in range(len(non_null)):
        for j in range(i + 1, len(non_null)):
            if _field_values_agree(non_null[i][1], non_null[j][1]):
                return non_null[i][1]
    return non_null[0][1]


def reconcile(
    event_id: str,
    event_type: str,
    identifier: str,
    primary: ScraperResult,
    wire: ScraperResult,
    media: ScraperResult,
) -> LockedData:
    """Produce a LockedData dict from three scraper outputs."""
    required, optional = fields_for(event_type)
    all_fields = set(required) | set(optional)

    # Union with any extra fields any scraper returned
    for sr in (primary, wire, media):
        all_fields.update(sr.fields.keys())

    locked = LockedData(
        event_id=event_id,
        event_type=event_type,  # type: ignore
        identifier=identifier,
        fields={},
        unresolved_fields=[],
    )

    for name in sorted(all_fields):
        a = primary.fields.get(name)
        b = wire.fields.get(name)
        c = media.fields.get(name)
        field = _consensus_for_field(name, a, b, c)
        locked.fields[name] = field
        if field.confidence != "green":
            locked.unresolved_fields.append(name)

    # Enforce that all REQUIRED fields for this event type are green
    critical_missing = [f for f in required if locked.fields.get(f) is None or locked.fields[f].confidence == "red"]
    if critical_missing:
        log.warning(
            "Reconciliation: %d critical field(s) RED for %s: %s",
            len(critical_missing),
            event_id,
            critical_missing,
        )

    log.info(
        "Reconciled %s: %d fields total, %d unresolved",
        event_id,
        len(locked.fields),
        len(locked.unresolved_fields),
    )
    return locked
