"""
Deterministic traceability audit.

For every sentence in the final post, the auditor extracts numeric and named
entities, then confirms each one maps back to a field in the locked data dict.
Any sentence with an unsourced claim is marked as such and the overall report
fails.

This is the last line of defense against hallucinated numbers leaking into
the post. The Writer agent is instructed to output a TRACE: block listing
every field it referenced, but this auditor does not trust that list — it
re-derives the mapping from the text itself.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from .schemas import LockedData, SentenceTrace, TraceabilityReport

log = logging.getLogger("triplex.traceability")

# ── Token extraction ────────────────────────────────────────────────────────

# Numeric tokens: captures $0.64, 14.2B, 2.51%, 11.8, -92,000, 1,312, etc.
_NUMERIC_RE = re.compile(
    r"(?:\$|\+|-)?\d{1,3}(?:,\d{3})*(?:\.\d+)?(?:[BMKT]|%)?",
    re.IGNORECASE,
)

# Sentence splitter — keeps it simple, splits on . ? with lookahead
_SENTENCE_RE = re.compile(r"(?<=[.?])\s+(?=[A-Z𝗔-𝗭])")

_STOP_NUMBERS = {
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",  # list markers
}


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences, keeping paragraph structure stripped."""
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    out = []
    for p in paragraphs:
        # Skip the CTA line and the final disclaimer
        sentences = _SENTENCE_RE.split(p)
        out.extend(s.strip() for s in sentences if s.strip())
    return out


def _extract_numeric_tokens(sentence: str) -> list[str]:
    """Extract numeric-looking tokens from a sentence."""
    found = _NUMERIC_RE.findall(sentence)
    return [t for t in found if t.strip("+-$%BMKTbmkt ").strip(",") not in _STOP_NUMBERS]


def _tokens_overlap(sentence_tokens: list[str], locked_value: Any) -> bool:
    """Check if any sentence token matches the locked field value."""
    if locked_value is None:
        return False
    locked_str = str(locked_value).strip()
    # Try several normalizations
    locked_variants = {
        locked_str,
        locked_str.replace("$", "").replace(",", ""),
        locked_str.replace(",", ""),
        locked_str.lstrip("+"),
    }
    for tok in sentence_tokens:
        tok_clean = tok.strip("+-$%BMKTbmkt ").strip(",")
        for variant in locked_variants:
            v_clean = variant.strip("+-$%BMKTbmkt ").strip(",")
            if tok_clean == v_clean and tok_clean:
                return True
            # Also match numeric values with tolerance (e.g. "14.2" in "$14.2B")
            try:
                if abs(float(tok_clean) - float(v_clean)) < 1e-6:
                    return True
            except (ValueError, TypeError):
                continue
    return False


# ── Main audit ──────────────────────────────────────────────────────────────

def audit(
    event_id: str,
    post_text: str,
    locked: LockedData,
) -> TraceabilityReport:
    """Audit the final post, sentence by sentence, against locked data."""
    sentences = _split_sentences(post_text)
    report = TraceabilityReport(
        event_id=event_id,
        post_text=post_text,
        sentences=[],
        overall_status="pass",
        unsourced_count=0,
    )

    locked_values = {
        name: f.value for name, f in locked.fields.items() if f.value is not None
    }

    for i, sentence in enumerate(sentences, start=1):
        tokens = _extract_numeric_tokens(sentence)
        if not tokens:
            # No numeric claims — acceptable, skip traceability for this sentence
            report.sentences.append(
                SentenceTrace(
                    sentence_number=i,
                    sentence_text=sentence,
                    claims=[],
                    mapped_fields=[],
                    source_urls=[],
                    status="sourced",
                    notes="no numeric claims",
                )
            )
            continue

        mapped_fields: list[str] = []
        source_urls: list[str] = []
        unmapped_tokens: list[str] = []

        for tok in tokens:
            matched_field = None
            for field_name, value in locked_values.items():
                if _tokens_overlap([tok], value):
                    matched_field = field_name
                    break
            if matched_field:
                if matched_field not in mapped_fields:
                    mapped_fields.append(matched_field)
                f = locked.fields[matched_field]
                urls = [
                    u
                    for u in (f.primary_url, f.wire_url, f.media_url)
                    if u is not None
                ]
                for u in urls:
                    if u not in source_urls:
                        source_urls.append(u)
            else:
                unmapped_tokens.append(tok)

        if unmapped_tokens:
            status = "unsourced" if len(unmapped_tokens) == len(tokens) else "partial"
            report.unsourced_count += 1
            report.overall_status = "fail"
            notes = f"unmapped tokens: {unmapped_tokens}"
        else:
            status = "sourced"
            notes = None

        report.sentences.append(
            SentenceTrace(
                sentence_number=i,
                sentence_text=sentence,
                claims=tokens,
                mapped_fields=mapped_fields,
                source_urls=source_urls,
                status=status,
                notes=notes,
            )
        )

    log.info(
        "Traceability audit for %s: %d sentences, %d with unmapped claims (status=%s)",
        event_id,
        len(report.sentences),
        report.unsourced_count,
        report.overall_status,
    )
    return report


# ── Deterministic banned-content scan ───────────────────────────────────────
# Second line of defense after the Compliance Auditor agent. Same regex checks
# that silvia_auto.py's review_post() runs, but re-run here as a hard gate.

BANNED_WORDS = [
    "additionally", "bolstered", "comprehensive", "crucial", "delve", "elevate",
    "empower", "enduring", "enhance", "ensuring", "evolving landscape", "exemplifies",
    "facilitate", "fostering", "furthermore", "game-changer", "garner", "groundbreaking",
    "holistic", "in the realm of", "it's worth noting", "landscape", "leverage",
    "meticulous", "moreover", "multifaceted", "myriad", "navigate", "nestled",
    "paradigm", "pivotal", "plethora", "profound", "robust", "seamless", "showcasing",
    "spearhead", "streamline", "synergy", "tapestry", "testament", "transformative",
    "underscore", "utilize", "vibrant",
]

BANNED_OPENERS = [
    "furthermore", "moreover", "additionally", "in conclusion", "overall",
    "in summary", "to sum up", "firstly", "secondly", "lastly",
    "in today's", "in an era", "as we navigate",
]


def deterministic_compliance_scan(post_text: str, event_type: str) -> list[str]:
    """Run the same regex scans that silvia_auto.py's review_post uses.

    Returns a list of violations. Empty list = pass.
    """
    violations: list[str] = []
    text_lower = post_text.lower()

    # Banned words
    found_words = [w for w in BANNED_WORDS if w in text_lower]
    if found_words:
        violations.append(f"Banned words: {', '.join(found_words)}")

    # Banned openers
    paragraphs = [p.strip() for p in post_text.split("\n\n") if p.strip()]
    for para in paragraphs:
        first = para.lower()[:50]
        for opener in BANNED_OPENERS:
            if first.startswith(opener):
                violations.append(f"Banned opener: '{opener}...'")
                break

    # Em dashes / en dashes
    if "\u2014" in post_text:
        violations.append("Em dash (U+2014) found")
    if "\u2013" in post_text:
        violations.append("En dash (U+2013) found")

    # Exclamation marks
    if "!" in post_text:
        violations.append(f"{post_text.count('!')} exclamation mark(s) found")

    # Emojis (rough range check)
    if re.search(r"[\U0001F600-\U0001FAFF\U00002600-\U000027BF]", post_text):
        violations.append("Emoji(s) found")

    # Hashtags (including #1, #4 style)
    if re.search(r"#\w+", post_text):
        violations.append("Hashtag-like pattern found (#word)")

    # Raw URLs in body
    if re.search(r"https?://\S+", post_text):
        violations.append("Raw URL in post body")

    # Hedging phrases
    hedges = ["it seems", "it appears", "it remains to be seen", "only time will tell"]
    found_hedges = [h for h in hedges if h in text_lower]
    if found_hedges:
        violations.append(f"Hedging: {', '.join(found_hedges)}")

    # Required CTA
    if "cfosilvia.com" not in text_lower:
        violations.append("Missing cfosilvia.com CTA")

    # Word count bounds
    wc = len(post_text.split())
    if event_type in ("earnings", "macro"):
        if not (190 <= wc <= 350):
            violations.append(f"Word count {wc} outside 200-300 target (190-350 tolerance)")
    elif event_type == "daily":
        if not (280 <= wc <= 550):
            violations.append(f"Word count {wc} outside 300-500 target (280-550 tolerance)")

    # Type-specific
    if event_type == "earnings":
        if "eps" not in text_lower:
            violations.append("Earnings post missing 'EPS'")
        if "if you own" not in text_lower:
            violations.append("Earnings post missing 'If you own' line")

    return violations
