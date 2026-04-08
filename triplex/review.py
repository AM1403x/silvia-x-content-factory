"""
Human sign-off gate.

Builds a review package from all pipeline outputs and presents it to a human
via stdin/stdout. The human must type POST (publish) or REJECT (kill) or
REVISE (send back to the writer). There is no auto-publish mode in TRIPLEX.
"""

from __future__ import annotations

import json
import logging
import textwrap
from pathlib import Path
from typing import Literal

from .schemas import ReviewPackage

log = logging.getLogger("triplex.review")


def print_review_package(pkg: ReviewPackage) -> None:
    """Pretty-print the review package to stdout."""
    bar = "=" * 72
    print(f"\n{bar}")
    print(f"  TRIPLEX REVIEW  |  {pkg.event_id}  |  {pkg.event_type.upper()}  |  {pkg.identifier}")
    print(bar)

    # 1. The post text
    print("\n[1] POST TEXT")
    print("-" * 72)
    print(textwrap.indent(pkg.post_text, "    "))

    # 2. Card brief
    print("\n[2] CARD BRIEF")
    print("-" * 72)
    for k, v in pkg.card_brief.items():
        print(f"    {k}: {v}")

    if pkg.card_image_path:
        print(f"\n    Rendered image: {pkg.card_image_path}")

    # 3. Traceability summary
    print("\n[3] TRACEABILITY AUDIT")
    print("-" * 72)
    tr = pkg.traceability
    print(f"    Overall: {tr.overall_status.upper()}")
    print(f"    Sentences: {len(tr.sentences)}")
    print(f"    Unsourced: {tr.unsourced_count}")
    if tr.overall_status == "fail":
        for s in tr.sentences:
            if s.status != "sourced":
                print(f"    [FAIL] #{s.sentence_number}: {s.notes}")
                print(f"           {s.sentence_text[:100]}")

    # 4. Red team report
    print("\n[4] RED TEAM REPORT")
    print("-" * 72)
    rt = pkg.red_team_report
    print(f"    Status: {rt.status.upper()}")
    for f in rt.findings[:10]:
        print(f"    - {f}")
    if rt.notes:
        print(f"    Notes: {rt.notes}")

    # 5. Compliance report
    print("\n[5] COMPLIANCE REPORT")
    print("-" * 72)
    cc = pkg.compliance_report
    print(f"    Status: {cc.status.upper()}")
    for f in cc.findings[:10]:
        print(f"    - {f}")

    # 6. Devil's advocate
    print("\n[6] DEVIL'S ADVOCATE")
    print("-" * 72)
    da = pkg.devils_advocate_report
    print(f"    Status: {da.status.upper()}")
    for f in da.findings[:10]:
        print(f"    - {f}")

    # 7. All source URLs
    print("\n[7] ALL SOURCE URLS")
    print("-" * 72)
    for url in pkg.all_source_urls:
        print(f"    {url}")

    # 8. Locked data field confidence summary
    print("\n[8] LOCKED DATA CONFIDENCE")
    print("-" * 72)
    ld = pkg.locked_data
    green = [k for k, f in ld.fields.items() if f.confidence == "green"]
    yellow = [k for k, f in ld.fields.items() if f.confidence == "yellow"]
    red = [k for k, f in ld.fields.items() if f.confidence == "red"]
    print(f"    Green: {len(green)}  Yellow: {len(yellow)}  Red: {len(red)}")
    if yellow:
        print(f"    Yellow fields: {yellow}")
    if red:
        print(f"    Red fields: {red}")

    print(f"\n{bar}")


def prompt_human(pkg: ReviewPackage) -> Literal["POST", "REJECT", "REVISE"]:
    """Block on stdin until the human types a decision."""
    print_review_package(pkg)

    # Hard preconditions before offering POST
    blocked_reasons = []
    if pkg.traceability.overall_status == "fail":
        blocked_reasons.append("Traceability audit FAILED — unsourced claims detected")
    if pkg.compliance_report.status == "fail":
        blocked_reasons.append("Compliance audit FAILED")
    if pkg.red_team_report.status == "fail":
        blocked_reasons.append("Red team audit FAILED")
    if pkg.locked_data.unresolved_fields:
        red_fields = [
            f
            for f in pkg.locked_data.unresolved_fields
            if pkg.locked_data.fields[f].confidence == "red"
        ]
        if red_fields:
            blocked_reasons.append(f"Locked data has RED fields: {red_fields}")

    if blocked_reasons:
        print("\n  POST is BLOCKED. Reasons:")
        for r in blocked_reasons:
            print(f"    - {r}")
        print("\n  You can type REJECT or REVISE, but not POST.")

    print("\n  Actions:")
    print("    POST    — publish to @CFOSilvia now")
    print("    REVISE  — send back to writer with notes (type notes after the word)")
    print("    REJECT  — kill this post")
    print()

    while True:
        ans = input("  Decision: ").strip().upper()
        if ans == "POST":
            if blocked_reasons:
                print("  POST is blocked. Pick REVISE or REJECT.")
                continue
            return "POST"
        if ans == "REJECT":
            return "REJECT"
        if ans.startswith("REVISE"):
            return "REVISE"
        print("  Invalid. Type POST, REVISE, or REJECT.")


def save_review_package(pkg: ReviewPackage, path: Path) -> None:
    """Persist the review package as JSON for the audit trail."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pkg.to_dict(), indent=2, default=str))
    log.info("Review package saved to %s", path)
