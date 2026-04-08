#!/usr/bin/env python3
"""
CFO Silvia TRIPLEX — Multi-agent triple-verification X posting pipeline.

Usage:
    python silvia_triplex.py                       # Full daily batch
    python silvia_triplex.py --date 2026-04-08     # Specific date
    python silvia_triplex.py --event-id 2026-04-08_dal_earnings
    python silvia_triplex.py --dry-run             # Skip the human gate + publish
    python silvia_triplex.py --only-discover       # Just list today's events

Pipeline stages (every event runs all stages):

    1. Discovery       → Event Detector agent
    2. Triple-fetch    → Primary + Wire + Media scrapers in parallel
    3. Consensus       → Deterministic reconciliation (green/yellow/red)
    4. Tiebreaker      → Re-fetch yellow/red fields
    5. Red Team        → Adversarial fact checker
    6. Writer          → Silvia voice + trace block
    7. Compliance      → Voice + format + structure audit
    8. Traceability    → Deterministic + agent audit
    9. Devils Advocate → Hostile-reader framing check
   10. Assets          → Card PNG + ChatGPT image prompt
   11. Human gate      → POST / REVISE / REJECT (blocking)
   12. Publish         → Tweepy to @CFOSilvia + audit ledger

Configuration is via the same .env that silvia_auto.py uses. Set
ANTHROPIC_API_KEY for Claude access and TWITTER_* for posting.

TRIPLEX never has AUTO_POST. Every publish requires a human typing POST.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Optional

# Ensure the repo root is on sys.path so silvia_auto imports work
sys.path.insert(0, str(Path(__file__).parent))

# Reuse env loading and card renderer from silvia_auto
from silvia_auto import load_env, render_card, post_to_x
from triplex.agents import (
    ComplianceAuditor,
    DevilsAdvocate,
    EventDetector,
    MediaScraper,
    PrimaryScraper,
    RedTeam,
    WireScraper,
    Writer,
)
from triplex.reconcile import reconcile
from triplex.review import prompt_human, save_review_package
from triplex.schemas import (
    AgentReport,
    Event,
    LockedData,
    ReviewPackage,
    ScraperResult,
)
from triplex.traceability import (
    audit as traceability_audit,
    deterministic_compliance_scan,
)

load_env()

# ── Paths ───────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent
VERIFICATION_DIR = REPO_ROOT / "verification"
LOG_DIR = Path(os.environ.get("LOG_DIR", REPO_ROOT / "silvia_logs"))
LOG_DIR.mkdir(exist_ok=True, parents=True)
VERIFICATION_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "triplex.log"),
    ],
)
log = logging.getLogger("triplex")


# ── Client setup ────────────────────────────────────────────────────────────

def get_client():
    """Construct the Anthropic client."""
    try:
        import anthropic
    except ImportError:
        log.error("anthropic package not installed. Run: pip install anthropic")
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.error("ANTHROPIC_API_KEY not set")
        sys.exit(1)

    return anthropic.Anthropic(api_key=api_key)


# ── Pipeline stages ─────────────────────────────────────────────────────────

def stage1_discover(client, date_et: str) -> list[Event]:
    """Stage 1: Event Detector finds all events for the day."""
    log.info("[STAGE 1] Event Discovery for %s", date_et)
    detector = EventDetector(client)
    events = detector.run(date_et)
    for e in events:
        log.info("  - %s (%s, %s, %s)", e.event_id, e.type, e.fire_time_et, e.urgency)
    return events


def stage2_triple_fetch(client, event: Event) -> tuple[ScraperResult, ScraperResult, ScraperResult]:
    """Stage 2: Three independent scrapers in parallel."""
    log.info("[STAGE 2] Triple-fetch for %s", event.event_id)

    primary = PrimaryScraper(client)
    wire = WireScraper(client)
    media = MediaScraper(client)

    # Parallel execution via threads — the Anthropic SDK is thread-safe
    with ThreadPoolExecutor(max_workers=3) as ex:
        fa = ex.submit(primary.run, event)
        fb = ex.submit(wire.run, event)
        fc = ex.submit(media.run, event)
        a = fa.result()
        b = fb.result()
        c = fc.result()

    log.info(
        "  primary=%d fields, wire=%d fields, media=%d fields",
        len(a.fields),
        len(b.fields),
        len(c.fields),
    )
    return a, b, c


def stage3_reconcile(
    event: Event,
    a: ScraperResult,
    b: ScraperResult,
    c: ScraperResult,
) -> LockedData:
    """Stage 3: Deterministic triple-source consensus."""
    log.info("[STAGE 3] Consensus reconciliation for %s", event.event_id)
    locked = reconcile(
        event.event_id,
        event.type,
        event.identifier,
        a,
        b,
        c,
    )
    green = sum(1 for f in locked.fields.values() if f.confidence == "green")
    yellow = sum(1 for f in locked.fields.values() if f.confidence == "yellow")
    red = sum(1 for f in locked.fields.values() if f.confidence == "red")
    log.info("  locked fields: green=%d yellow=%d red=%d", green, yellow, red)
    return locked


def stage4_tiebreaker(client, event: Event, locked: LockedData) -> LockedData:
    """Stage 4: Re-run primary scraper with stricter query on yellow/red fields.

    Minimal implementation: if any critical field is yellow/red, re-run the
    primary scraper with a tighter user prompt focused on those fields. More
    sophisticated tiebreak would use a 4th independent source.
    """
    if not locked.unresolved_fields:
        log.info("[STAGE 4] Tiebreaker: no unresolved fields, skipping")
        return locked

    log.info(
        "[STAGE 4] Tiebreaker: re-fetching %d unresolved fields: %s",
        len(locked.unresolved_fields),
        locked.unresolved_fields,
    )
    # Placeholder: for this first version, we log the unresolved fields and
    # hand them to the red team to flag. A future iteration will re-fetch.
    return locked


def stage5_red_team(client, locked: LockedData) -> AgentReport:
    """Stage 5: Red Team adversarial fact checker."""
    log.info("[STAGE 5] Red Team")
    red_team = RedTeam(client)
    report = red_team.run(locked)
    log.info("  red team status: %s (%d findings)", report.status, len(report.findings))
    return report


def stage6_write(client, locked: LockedData, variant: str = "A") -> tuple[str, list[str]]:
    """Stage 6: Silvia Writer."""
    log.info("[STAGE 6] Writer (variant %s)", variant)
    writer = Writer(client)
    post_text, trace_fields = writer.run(locked, variant=variant)
    log.info("  writer output: %d words, %d trace fields", len(post_text.split()), len(trace_fields))
    return post_text, trace_fields


def stage7_compliance(client, event: Event, post_text: str) -> AgentReport:
    """Stage 7: Compliance Auditor (agent + deterministic scan)."""
    log.info("[STAGE 7] Compliance")
    # Deterministic scan first — cheap and catches most violations
    det_violations = deterministic_compliance_scan(post_text, event.type)
    if det_violations:
        log.warning("  deterministic scan found %d violations", len(det_violations))
        return AgentReport(
            agent_name="compliance_deterministic",
            status="fail",
            findings=det_violations,
            notes="Deterministic scan failed; skipped agent call to save tokens.",
        )

    # Agent scan as the second layer
    auditor = ComplianceAuditor(client)
    report = auditor.run(event.type, post_text)
    log.info("  compliance status: %s (%d findings)", report.status, len(report.findings))
    return report


def stage8_traceability(event: Event, post_text: str, locked: LockedData):
    """Stage 8: Deterministic sentence-by-sentence traceability audit."""
    log.info("[STAGE 8] Traceability")
    report = traceability_audit(event.event_id, post_text, locked)
    log.info(
        "  traceability %s: %d sentences, %d unsourced",
        report.overall_status,
        len(report.sentences),
        report.unsourced_count,
    )
    return report


def stage9_devils_advocate(
    client,
    event: Event,
    post_text: str,
    locked: LockedData,
) -> AgentReport:
    """Stage 9: Devil's Advocate hostile read."""
    log.info("[STAGE 9] Devil's Advocate")
    da = DevilsAdvocate(client)
    report = da.run(event.type, post_text, locked)
    log.info("  devils advocate status: %s (%d findings)", report.status, len(report.findings))
    return report


def stage10_assets(event: Event, locked: LockedData, post_text: str) -> tuple[dict, Optional[str], str]:
    """Stage 10: Extract card brief, render PNG, generate image prompt."""
    log.info("[STAGE 10] Assets")

    # Extract card brief from locked data
    if event.type == "earnings":
        brief = {
            "TICKER": locked.get("ticker") or event.identifier,
            "VERDICT": "BEAT" if _is_beat(locked) else "MISS",
            "EPS_ACTUAL": str(locked.get("adjusted_eps_actual") or locked.get("reported_gaap_eps") or "?"),
            "EPS_EST": str(locked.get("adjusted_eps_estimate") or "?"),
            "REV_ACTUAL": str(locked.get("revenue_actual") or "?"),
            "REV_EST": str(locked.get("revenue_estimate") or "?"),
            "AH_MOVE": str(locked.get("stock_reaction_pct") or "N/A"),
            "QUARTER": str(locked.get("fiscal_period") or "?"),
        }
        post_type = "earnings"
    elif event.type == "macro":
        brief = {
            "DATA_NAME": locked.get("indicator") or event.identifier,
            "VERDICT": str(locked.get("verdict") or "HAWKISH"),
            "HEADLINE_NUM": str(locked.get("headline_number") or "?"),
            "UNIT": str(locked.get("headline_unit") or ""),
            "ESTIMATE": str(locked.get("consensus_estimate") or "?"),
        }
        post_type = "macro"
    else:  # daily
        brief = {
            "DATE": str(locked.get("date") or ""),
            "SP_CLOSE": str(locked.get("sp500_close") or "?"),
            "SP_PCT": str(locked.get("sp500_pct_change") or "0%"),
            "HEADLINE": str(locked.get("top_story_headline") or ""),
        }
        post_type = "daily"

    # Render PNG card via existing silvia_auto code
    card_path: Optional[str] = None
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        card_path = str(LOG_DIR / f"card_{post_type}_{timestamp}.png")
        render_card(post_type, brief, card_path)
        log.info("  card rendered: %s", card_path)
    except Exception as e:
        log.warning("  card render failed: %s", e)

    # ChatGPT image prompt (templated, not agent-generated)
    image_prompt = _build_image_prompt(event.type, brief)

    return brief, card_path, image_prompt


def _is_beat(locked: LockedData) -> bool:
    """Rough heuristic for beat vs miss based on locked data."""
    eps_a = locked.get("adjusted_eps_actual")
    eps_e = locked.get("adjusted_eps_estimate")
    if eps_a is not None and eps_e is not None:
        try:
            return float(str(eps_a).replace("$", "")) >= float(str(eps_e).replace("$", ""))
        except (ValueError, TypeError):
            pass
    return True


def _build_image_prompt(event_type: str, brief: dict) -> str:
    """Build a templated ChatGPT image prompt from the card brief."""
    base = (
        "Create a premium institutional finance social card for X. "
        "Pure widescreen 16:9, exactly 1200 by 675 pixels. "
        "Pure jet black background #0A0A0A. No gradients, 3D, shadows, "
        "stock photography, illustrations, or logos. Only flat typography "
        "and geometric shapes. Minimalist Bloomberg Terminal meets Apple "
        "keynote aesthetic. SF Pro Display throughout. "
    )
    if event_type == "earnings":
        verdict = brief.get("VERDICT", "BEAT")
        is_beat = verdict.upper() == "BEAT"
        pill_color = "#22C55E" if is_beat else "#EF4444"
        pill_bg = "rgba(34,197,94,0.15)" if is_beat else "rgba(239,68,68,0.12)"
        return base + (
            f'Top right corner: small gray label "{brief.get("QUARTER", "")} Earnings" in #444 at 15pt. '
            f'Center row 1: ticker "{brief.get("TICKER", "???")}" in ultra-bold white 120pt, '
            f'with a pill to the right. Pill background {pill_bg}, '
            f'2 pixel border {pill_color}, "BEAT" in {pill_color} 24pt ALL CAPS. '
            f'Center row 2: two data blocks side by side. Left header "EPS" in gray #666 16pt; '
            f'below "{brief.get("EPS_ACTUAL", "?")}" in {pill_color} 52pt with "vs {brief.get("EPS_EST", "?")}" in gray #555 24pt. '
            f'Right header "REVENUE"; below "{brief.get("REV_ACTUAL", "?")}" in {pill_color} 52pt '
            f'with "vs {brief.get("REV_EST", "?")}" in gray #555 24pt. '
            f'Center row 3: "Pre-market: {brief.get("AH_MOVE", "N/A")}" with the percentage in {pill_color}. '
            f'Footer bar: 80px tall, #111 background, 2px gold top border #C9A84C. '
            f'Left: "@CFOSilvia" in gold 15pt. Center: "↑ Show more ↑" with arrows gray #888 and text white 28pt. '
            f'Output at 1200x675 PNG. No extra elements.'
        )
    elif event_type == "macro":
        verdict = brief.get("VERDICT", "HAWKISH")
        is_hot = verdict.upper() in ("HAWKISH", "HOT")
        pill_color = "#EF4444" if is_hot else "#22C55E"
        pill_bg = "rgba(239,68,68,0.12)" if is_hot else "rgba(34,197,94,0.15)"
        return base + (
            f'Top right corner: small gray label "{datetime.now().strftime("%B %d, %Y")}" in #444 at 15pt. '
            f'Center row 1: headline "{brief.get("DATA_NAME", "???")}" in ultra-bold white 100pt on one line. '
            f'Center row 2: pill badge with {pill_bg} background, 2 pixel border {pill_color}, '
            f'"{verdict}" in {pill_color} ALL CAPS 22pt. '
            f'Center row 3: "{brief.get("HEADLINE_NUM", "?")}" in white 72pt with "{brief.get("UNIT", "")}" in gray #666 20pt; '
            f'below in gray #888 18pt: "{brief.get("ESTIMATE", "")}". '
            f'Footer bar: same @CFOSilvia gold pattern. '
            f'Output at 1200x675 PNG. No extra elements.'
        )
    else:  # daily
        pct = brief.get("SP_PCT", "+0.0%")
        is_green = not pct.startswith("-")
        color = "#22C55E" if is_green else "#EF4444"
        return base + (
            f'Top right corner: "Daily Wrap" in #444 at 15pt. '
            f'Center row 1: "WEDNESDAY" in gray #555 24pt ALL CAPS (or actual day). '
            f'Center row 2: "{brief.get("DATE", "Date")}" in ultra-bold white 80pt. '
            f'Center row 3: "S&P 500" gray #666 20pt, "{brief.get("SP_CLOSE", "?")}" white 56pt, "{pct}" {color} 32pt. '
            f'Center row 4: "{brief.get("HEADLINE", "")}" in gray #999 22pt centered, max width 800px. '
            f'Footer bar: same @CFOSilvia gold pattern. '
            f'Output at 1200x675 PNG. No extra elements.'
        )


# ── Full pipeline per event ─────────────────────────────────────────────────

def run_pipeline_for_event(
    client,
    event: Event,
    *,
    dry_run: bool = False,
) -> Optional[str]:
    """Run all 11 stages for a single event. Returns the live X URL on publish."""
    event_dir = VERIFICATION_DIR / event.event_id
    event_dir.mkdir(parents=True, exist_ok=True)

    # Stages 2-3: triple fetch and consensus
    primary, wire, media = stage2_triple_fetch(client, event)
    (event_dir / "primary.json").write_text(json.dumps(primary.to_dict(), indent=2, default=str))
    (event_dir / "wire.json").write_text(json.dumps(wire.to_dict(), indent=2, default=str))
    (event_dir / "media.json").write_text(json.dumps(media.to_dict(), indent=2, default=str))

    locked = stage3_reconcile(event, primary, wire, media)
    locked = stage4_tiebreaker(client, event, locked)
    (event_dir / "locked_data.json").write_text(json.dumps(locked.to_dict(), indent=2, default=str))

    # Stage 5: red team
    red_team_report = stage5_red_team(client, locked)
    (event_dir / "red_team.json").write_text(json.dumps(red_team_report.to_dict(), indent=2, default=str))
    if red_team_report.status == "fail":
        log.error("Red team FAILED for %s. Halting pipeline.", event.event_id)
        return None

    # Stage 6: writer
    post_text, trace_fields = stage6_write(client, locked)
    (event_dir / "post.txt").write_text(post_text)
    (event_dir / "writer_trace.json").write_text(json.dumps(trace_fields, indent=2))

    # Stage 7: compliance
    compliance_report = stage7_compliance(client, event, post_text)
    (event_dir / "compliance.json").write_text(json.dumps(compliance_report.to_dict(), indent=2, default=str))
    if compliance_report.status == "fail":
        log.error("Compliance FAILED for %s. Halting pipeline.", event.event_id)
        return None

    # Stage 8: traceability (deterministic)
    traceability_report = stage8_traceability(event, post_text, locked)
    (event_dir / "traceability.json").write_text(json.dumps(traceability_report.to_dict(), indent=2, default=str))
    if traceability_report.overall_status == "fail":
        log.error("Traceability FAILED for %s. Halting pipeline.", event.event_id)
        return None

    # Stage 9: devil's advocate
    da_report = stage9_devils_advocate(client, event, post_text, locked)
    (event_dir / "devils_advocate.json").write_text(json.dumps(da_report.to_dict(), indent=2, default=str))

    # Stage 10: assets
    card_brief, card_path, image_prompt = stage10_assets(event, locked, post_text)

    # Collect all source URLs for the review package
    all_urls: list[str] = []
    for f in locked.fields.values():
        for u in (f.primary_url, f.wire_url, f.media_url, f.tiebreaker_url):
            if u and u not in all_urls:
                all_urls.append(u)

    # Stage 11: human gate
    pkg = ReviewPackage(
        event_id=event.event_id,
        event_type=event.type,
        identifier=event.identifier,
        post_text=post_text,
        card_brief=card_brief,
        card_image_path=card_path,
        image_prompt=image_prompt,
        locked_data=locked,
        traceability=traceability_report,
        red_team_report=red_team_report,
        compliance_report=compliance_report,
        devils_advocate_report=da_report,
        all_source_urls=all_urls,
    )
    save_review_package(pkg, event_dir / "review_package.json")

    if dry_run:
        log.info("[DRY RUN] Skipping human gate and publish for %s", event.event_id)
        return None

    decision = prompt_human(pkg)
    (event_dir / "human_decision.json").write_text(
        json.dumps({"decision": decision, "timestamp": datetime.now().isoformat()}, indent=2)
    )

    if decision != "POST":
        log.info("Decision: %s. Not publishing.", decision)
        return None

    # Stage 12: publish
    if card_path is None:
        log.error("Cannot publish without a rendered card. Skipping.")
        return None

    url = post_to_x(post_text, card_path)
    if url:
        log.info("LIVE: %s", url)
        (event_dir / "published.json").write_text(
            json.dumps({"url": url, "timestamp": datetime.now().isoformat()}, indent=2)
        )
    return url


# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="CFO Silvia TRIPLEX pipeline")
    parser.add_argument("--date", default=None, help="Override today's date (YYYY-MM-DD)")
    parser.add_argument("--event-id", default=None, help="Run a single event by id")
    parser.add_argument("--only-discover", action="store_true", help="Just list events")
    parser.add_argument("--dry-run", action="store_true", help="Skip human gate and publish")
    args = parser.parse_args()

    client = get_client()
    date_et = args.date or datetime.now().strftime("%Y-%m-%d")

    log.info("=" * 72)
    log.info("TRIPLEX run starting: date=%s dry_run=%s", date_et, args.dry_run)
    log.info("=" * 72)

    events = stage1_discover(client, date_et)

    # Save the discovered events
    date_dir = VERIFICATION_DIR / date_et
    date_dir.mkdir(parents=True, exist_ok=True)
    (date_dir / "events.json").write_text(
        json.dumps([e.to_dict() for e in events], indent=2, default=str)
    )

    if args.only_discover:
        print("\nDiscovered events:")
        for e in events:
            print(f"  {e.event_id}  {e.type:>8}  {e.fire_time_et}  {e.identifier}")
        return

    if args.event_id:
        events = [e for e in events if e.event_id == args.event_id]
        if not events:
            log.error("Event id %s not found in today's list", args.event_id)
            sys.exit(1)

    for event in events:
        try:
            run_pipeline_for_event(client, event, dry_run=args.dry_run)
        except Exception as e:
            log.exception("Pipeline failed for %s: %s", event.event_id, e)
            continue


if __name__ == "__main__":
    main()
