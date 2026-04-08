"""
Agent wrappers for the TRIPLEX pipeline.

Each agent is a thin class that:
1. Loads its system prompt from triplex/prompts/*.txt
2. Wraps a single Claude API call with appropriate model and tools
3. Parses the JSON response into a typed result

The Anthropic web_search tool is used for agents that need live sources
(event detector, three scrapers, red team). Writer and compliance agents
are pure LLM calls with no tool use.

Claude Code fallback mode:
  If the anthropic package is not installed OR ANTHROPIC_API_KEY is not
  configured, these classes can still be imported and instantiated. Any
  .run() call will raise ClaudeCodeModeRequired with instructions for
  running the agent manually in Claude Code.

  This lets the deterministic parts of the pipeline (consensus, traceability,
  compliance regex) still work even without Anthropic API access.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .schemas import (
    AgentReport,
    Event,
    EventType,
    LockedData,
    ScrapedField,
    ScraperResult,
    fields_for,
)

log = logging.getLogger("triplex.agents")


class ClaudeCodeModeRequired(RuntimeError):
    """Raised when an agent is invoked but no Anthropic API access is configured.

    When this is raised, the caller should either:
      1. Install anthropic (`pip install anthropic`) and set ANTHROPIC_API_KEY
      2. Run the agent's prompt manually in Claude Code (claude.ai/code)
         using the matching file in triplex/prompts/*.txt

    The pipeline's deterministic stages (consensus, traceability, regex
    compliance) still work without this.
    """

# ── Model selection ─────────────────────────────────────────────────────────
# The user's stated preference: accuracy over cost. Opus 4.6 on the
# high-stakes agents, Sonnet 4.5 on the scrapers and deterministic steps.

MODEL_OPUS = "claude-opus-4-6"
MODEL_SONNET = "claude-sonnet-4-5"

# Web search tool config — adjust if Anthropic updates the tool type name
WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": 10,
}


# ── Prompt loading ──────────────────────────────────────────────────────────

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(filename: str) -> str:
    """Load a prompt file from triplex/prompts/."""
    path = _PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


# ── Low-level Claude call ───────────────────────────────────────────────────

def _call_claude(
    client,
    system_prompt: str,
    user_prompt: str,
    model: str = MODEL_SONNET,
    max_tokens: int = 4000,
    use_web_search: bool = False,
) -> str:
    """Single Claude API call with optional web search tool.

    If `client` is None, raises ClaudeCodeModeRequired. The orchestrator
    catches this and falls back to printing a manual-mode instruction
    sheet for Claude Code users.
    """
    if client is None:
        raise ClaudeCodeModeRequired(
            "No Anthropic client available. Run this agent's prompt manually "
            "in Claude Code. The system prompt is in triplex/prompts/ and the "
            "user prompt should be the JSON payload this stage would have sent."
        )

    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    if use_web_search:
        kwargs["tools"] = [WEB_SEARCH_TOOL]

    log.info(
        "Calling %s (web_search=%s, system=%d chars, user=%d chars)",
        model,
        use_web_search,
        len(system_prompt),
        len(user_prompt),
    )
    response = client.messages.create(**kwargs)

    # Extract text from the response, ignoring tool_use and tool_result blocks
    text_parts = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            text_parts.append(block.text)
    text = "\n".join(text_parts).strip()

    if not text:
        raise RuntimeError(
            f"Claude returned no text (model={model}, blocks={[b.type for b in response.content]})"
        )
    return text


def get_anthropic_client():
    """Construct an Anthropic client, or return None if not configured.

    Returns None (not raises) when:
      - anthropic package is not installed
      - ANTHROPIC_API_KEY is not set

    Callers should treat None as "Claude Code mode — run agent prompts manually".
    """
    try:
        import anthropic
    except ImportError:
        log.info("anthropic package not installed — Claude Code mode")
        return None
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.info("ANTHROPIC_API_KEY not set — Claude Code mode")
        return None
    return anthropic.Anthropic(api_key=api_key)


def _parse_json(text: str) -> Any:
    """Parse JSON from an LLM response, handling optional markdown fences."""
    stripped = text.strip()
    if stripped.startswith("```"):
        # strip code fence
        stripped = stripped.split("```", 2)[1]
        if stripped.startswith("json"):
            stripped = stripped[4:]
        stripped = stripped.rsplit("```", 1)[0].strip()
    return json.loads(stripped)


# ── Agent 1: EVENT DETECTOR ────────────────────────────────────────────────

class EventDetector:
    """Finds all newsworthy events for a given trading day."""

    def __init__(self, client):
        self.client = client
        self.system = load_prompt("01_event_detector.txt")

    def run(self, date_et: str) -> list[Event]:
        user = f"Detect all CFO Silvia-caliber events for {date_et} (US Eastern time)."
        text = _call_claude(
            self.client,
            self.system,
            user,
            model=MODEL_SONNET,
            max_tokens=4000,
            use_web_search=True,
        )
        raw = _parse_json(text)
        if not isinstance(raw, list):
            raise ValueError(f"Event Detector returned non-list: {text[:200]}")
        events = [
            Event(
                event_id=e["event_id"],
                type=e["type"],
                identifier=e["identifier"],
                fire_time_et=e["fire_time_et"],
                urgency=e.get("urgency", "normal"),
                rationale=e.get("rationale", ""),
                discovery_sources=e.get("discovery_sources", []),
            )
            for e in raw
        ]
        log.info("Event Detector found %d events", len(events))
        return events


# ── Agents 2A / 2B / 2C: SCRAPERS ──────────────────────────────────────────

class _BaseScraper:
    """Base class for the three scrapers. Subclasses set prompt filename and label."""

    PROMPT_FILE: str = ""
    LABEL: str = ""

    def __init__(self, client):
        self.client = client
        self.system = load_prompt(self.PROMPT_FILE)

    def run(self, event: Event) -> ScraperResult:
        required, optional = fields_for(event.type)
        user_payload = {
            "event_id": event.event_id,
            "type": event.type,
            "identifier": event.identifier,
            "required_fields": required,
            "optional_fields": optional,
        }
        user = json.dumps(user_payload, indent=2)
        text = _call_claude(
            self.client,
            self.system,
            user,
            model=MODEL_SONNET,
            max_tokens=6000,
            use_web_search=True,
        )
        raw = _parse_json(text)
        fields = {}
        for name, f in raw.get("fields", {}).items():
            if f is None:
                continue
            fields[name] = ScrapedField(
                value=f.get("value"),
                source_url=f.get("source_url"),
                source_label=self.LABEL,
                verbatim=f.get("verbatim"),
                timestamp=f.get("timestamp"),
            )
        return ScraperResult(
            event_id=event.event_id,
            scraper_label=self.LABEL,
            fields=fields,
            errors=raw.get("errors", []),
        )


class PrimaryScraper(_BaseScraper):
    PROMPT_FILE = "02a_primary_scraper.txt"
    LABEL = "primary"


class WireScraper(_BaseScraper):
    PROMPT_FILE = "02b_wire_scraper.txt"
    LABEL = "wire"


class MediaScraper(_BaseScraper):
    PROMPT_FILE = "02c_media_scraper.txt"
    LABEL = "media"


# ── Agent 4: RED TEAM ──────────────────────────────────────────────────────

class RedTeam:
    """Adversarial fact checker — tries to prove every claim wrong."""

    def __init__(self, client):
        self.client = client
        self.system = load_prompt("04_red_team.txt")

    def run(self, locked: LockedData) -> AgentReport:
        user = json.dumps(locked.to_dict(), indent=2, default=str)
        text = _call_claude(
            self.client,
            self.system,
            user,
            model=MODEL_OPUS,
            max_tokens=6000,
            use_web_search=True,
        )
        raw = _parse_json(text)
        return AgentReport(
            agent_name="red_team",
            status=raw.get("status", "fail"),
            findings=raw.get("findings", []),
            notes=raw.get("notes"),
            raw=raw,
        )


# ── Agent 5: WRITER ────────────────────────────────────────────────────────

class Writer:
    """Silvia writer — uses only locked data, outputs post + trace."""

    def __init__(self, client):
        self.client = client
        self.system = load_prompt("05_writer.txt")

    def run(self, locked: LockedData, variant: str = "A") -> tuple[str, list[str]]:
        payload = {
            "event_id": locked.event_id,
            "event_type": locked.event_type,
            "identifier": locked.identifier,
            "writer_variant": variant,
            "locked_data": {
                k: {"value": v.value, "verbatim": v.verbatim}
                for k, v in locked.fields.items()
            },
        }
        user = json.dumps(payload, indent=2, default=str)
        text = _call_claude(
            self.client,
            self.system,
            user,
            model=MODEL_OPUS,
            max_tokens=4000,
            use_web_search=False,
        )
        # Split post text from the trailing TRACE: block
        if "TRACE:" in text:
            post_part, trace_part = text.split("TRACE:", 1)
            post_text = post_part.strip()
            trace_fields = [
                line.strip("- ").strip()
                for line in trace_part.strip().splitlines()
                if line.strip()
            ]
        else:
            post_text = text.strip()
            trace_fields = []
        return post_text, trace_fields


# ── Agent 6: COMPLIANCE AUDITOR ────────────────────────────────────────────

class ComplianceAuditor:
    """Voice, format, structure audit."""

    def __init__(self, client):
        self.client = client
        self.system = load_prompt("06_compliance.txt")

    def run(self, event_type: EventType, post_text: str) -> AgentReport:
        payload = {"event_type": event_type, "post_text": post_text}
        user = json.dumps(payload, indent=2)
        text = _call_claude(
            self.client,
            self.system,
            user,
            model=MODEL_SONNET,
            max_tokens=3000,
            use_web_search=False,
        )
        raw = _parse_json(text)
        return AgentReport(
            agent_name="compliance",
            status=raw.get("status", "fail"),
            findings=raw.get("findings", []) + raw.get("violations", []),
            notes=raw.get("notes"),
            raw=raw,
        )


# ── Agent 8: DEVIL'S ADVOCATE ──────────────────────────────────────────────

class DevilsAdvocate:
    """Hostile reader — looks for framing, tone, and legal risks."""

    def __init__(self, client):
        self.client = client
        self.system = load_prompt("08_devils_advocate.txt")

    def run(
        self,
        event_type: EventType,
        post_text: str,
        locked: LockedData,
    ) -> AgentReport:
        payload = {
            "event_type": event_type,
            "post_text": post_text,
            "locked_data_summary": {
                k: v.value for k, v in locked.fields.items() if v.value is not None
            },
        }
        user = json.dumps(payload, indent=2, default=str)
        text = _call_claude(
            self.client,
            self.system,
            user,
            model=MODEL_OPUS,
            max_tokens=4000,
            use_web_search=False,
        )
        raw = _parse_json(text)
        status = raw.get("status", "rework")
        # Map "rework" to "warn" in the standard AgentReport schema
        report_status = "pass" if status == "pass" else "warn"
        return AgentReport(
            agent_name="devils_advocate",
            status=report_status,
            findings=raw.get("findings", []) + raw.get("rework_notes", []),
            notes=raw.get("notes"),
            raw=raw,
        )
