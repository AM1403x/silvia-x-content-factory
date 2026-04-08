"""
Data schemas shared across all TRIPLEX agents.

Every agent input and output is typed. Every field in the locked data dict
carries its source URLs and confidence marker. Every traceability report
rows back to a specific data field.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Literal, Optional
import json


# ── Events ──────────────────────────────────────────────────────────────────

EventType = Literal["earnings", "macro", "daily", "speech"]
Urgency = Literal["critical", "high", "normal"]


@dataclass
class Event:
    """A single newsworthy event that warrants a post today."""

    event_id: str                    # e.g. "2026-04-08_dal_earnings"
    type: EventType
    identifier: str                  # ticker (DAL) or indicator (FOMC, CPI)
    fire_time_et: str                # "07:00 ET", "14:00 ET", "16:30 ET"
    urgency: Urgency
    rationale: str                   # one-sentence reason for including it
    discovery_sources: list[str]     # URLs that led to the discovery

    def to_dict(self) -> dict:
        return asdict(self)


# ── Scraper outputs ─────────────────────────────────────────────────────────

@dataclass
class ScrapedField:
    """A single data field as seen by one scraper."""

    value: Any                      # the actual value (number, string, list)
    source_url: Optional[str]       # the URL this came from
    source_label: str               # "primary", "wire", "media"
    verbatim: Optional[str] = None  # the verbatim text snippet (for quotes)
    timestamp: Optional[str] = None # ISO timestamp of the fetch


@dataclass
class ScraperResult:
    """Complete output of one scraper agent for one event."""

    event_id: str
    scraper_label: Literal["primary", "wire", "media"]
    fields: dict[str, ScrapedField] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "scraper_label": self.scraper_label,
            "fields": {k: asdict(v) for k, v in self.fields.items()},
            "errors": self.errors,
        }


# ── Consensus / locked data ────────────────────────────────────────────────

Confidence = Literal["green", "yellow", "red"]


@dataclass
class LockedField:
    """A data field after triple-consensus reconciliation."""

    value: Any
    confidence: Confidence          # green=all 3 agree, yellow=2 of 3, red=conflict
    primary_url: Optional[str]
    wire_url: Optional[str]
    media_url: Optional[str]
    tiebreaker_url: Optional[str] = None
    conflict_notes: Optional[str] = None
    verbatim: Optional[str] = None


@dataclass
class LockedData:
    """The full locked data dict for one event."""

    event_id: str
    event_type: EventType
    identifier: str
    fields: dict[str, LockedField] = field(default_factory=dict)
    unresolved_fields: list[str] = field(default_factory=list)

    def get(self, field_name: str) -> Any:
        """Shortcut to read a locked value."""
        f = self.fields.get(field_name)
        return f.value if f else None

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "identifier": self.identifier,
            "fields": {k: asdict(v) for k, v in self.fields.items()},
            "unresolved_fields": self.unresolved_fields,
        }


# ── Audit reports ──────────────────────────────────────────────────────────

@dataclass
class SentenceTrace:
    """Traceability record for a single sentence in the final post."""

    sentence_number: int
    sentence_text: str
    claims: list[str]               # the extracted claims (numbers, names, quotes)
    mapped_fields: list[str]        # locked data field names
    source_urls: list[str]          # the URLs backing those fields
    status: Literal["sourced", "unsourced", "partial"]
    notes: Optional[str] = None


@dataclass
class TraceabilityReport:
    event_id: str
    post_text: str
    sentences: list[SentenceTrace] = field(default_factory=list)
    overall_status: Literal["pass", "fail"] = "pass"
    unsourced_count: int = 0

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "overall_status": self.overall_status,
            "unsourced_count": self.unsourced_count,
            "sentences": [asdict(s) for s in self.sentences],
        }


@dataclass
class AgentReport:
    """Generic agent output: pass/fail + findings + free-form notes."""

    agent_name: str
    status: Literal["pass", "fail", "warn"]
    findings: list[str] = field(default_factory=list)
    notes: Optional[str] = None
    raw: Optional[dict] = None

    def to_dict(self) -> dict:
        return asdict(self)


# ── Review package ────────────────────────────────────────────────────────

@dataclass
class ReviewPackage:
    """What the human sees before typing POST or REJECT."""

    event_id: str
    event_type: EventType
    identifier: str
    post_text: str
    card_brief: dict
    card_image_path: Optional[str]
    image_prompt: str
    locked_data: LockedData
    traceability: TraceabilityReport
    red_team_report: AgentReport
    compliance_report: AgentReport
    devils_advocate_report: AgentReport
    all_source_urls: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "identifier": self.identifier,
            "post_text": self.post_text,
            "card_brief": self.card_brief,
            "card_image_path": self.card_image_path,
            "image_prompt": self.image_prompt,
            "locked_data": self.locked_data.to_dict(),
            "traceability": self.traceability.to_dict(),
            "red_team_report": self.red_team_report.to_dict(),
            "compliance_report": self.compliance_report.to_dict(),
            "devils_advocate_report": self.devils_advocate_report.to_dict(),
            "all_source_urls": self.all_source_urls,
        }


# ── Field schemas per event type ─────────────────────────────────────────
# These define the mandatory and optional fields the scrapers must populate
# for each event type. The consensus agent uses these to know what to check.

EARNINGS_FIELDS_REQUIRED = [
    "ticker",
    "company_name",
    "fiscal_period",              # e.g., "Q1 FY2026"
    "report_timing",              # "BMO" or "AMC"
    "adjusted_eps_actual",
    "adjusted_eps_estimate",
    "revenue_actual",
    "revenue_estimate",
    "stock_reaction_pct",         # post-earnings % move
]
EARNINGS_FIELDS_OPTIONAL = [
    "reported_gaap_eps",
    "revenue_yoy_growth",
    "segment_breakdown",
    "q2_eps_guidance",
    "q2_revenue_guidance",
    "fy_guidance",
    "ceo_quote_verbatim",
    "conference_call_time",
    "premium_revenue_actual",     # for airlines etc
    "capacity_change",
]

MACRO_FIELDS_REQUIRED = [
    "indicator",                  # e.g., "FOMC Minutes", "CPI", "NFP"
    "release_time_et",
    "headline_number",
    "headline_unit",              # "YoY", "MoM", "basis points", "jobs"
    "consensus_estimate",
    "prior_value",
]
MACRO_FIELDS_OPTIONAL = [
    "sub_components",
    "revisions",
    "market_reaction_yield",
    "market_reaction_equities",
    "fomc_vote_count",            # "11-1", "10-2"
    "fomc_dissenters",
    "fomc_dissent_reasoning",
    "fed_funds_target",
    "powell_quote_verbatim",
]

DAILY_FIELDS_REQUIRED = [
    "date",
    "sp500_close",
    "sp500_pct_change",
    "nasdaq_pct_change",
    "dow_pct_change",
    "dow_close",
    "wti_close",
    "wti_pct_change",
    "top_story_headline",
]
DAILY_FIELDS_OPTIONAL = [
    "brent_close",
    "brent_pct_change",
    "gold_pct_change",
    "bitcoin_pct_change",
    "ten_year_yield_close",
    "ten_year_yield_bps_change",
    "vix_close",
    "russell_pct_change",
    "after_hours_earnings",
    "tomorrow_calendar",
]


def fields_for(event_type: EventType) -> tuple[list[str], list[str]]:
    """Return (required, optional) field lists for an event type."""
    if event_type == "earnings":
        return EARNINGS_FIELDS_REQUIRED, EARNINGS_FIELDS_OPTIONAL
    if event_type == "macro":
        return MACRO_FIELDS_REQUIRED, MACRO_FIELDS_OPTIONAL
    if event_type == "daily":
        return DAILY_FIELDS_REQUIRED, DAILY_FIELDS_OPTIONAL
    return [], []
