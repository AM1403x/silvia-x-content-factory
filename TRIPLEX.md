# TRIPLEX — Multi-Agent Triple-Verification Pipeline

TRIPLEX is the strict data-accuracy pipeline for @CFOSilvia. It runs 8 specialized AI agents plus 2 deterministic reconciliation stages plus 1 mandatory human sign-off gate before any post ships.

Use TRIPLEX when data accuracy is critical (which is every live post on @CFOSilvia). Use the lighter `silvia_auto.py` pipeline for experimentation or throwaway drafts.

## Why TRIPLEX exists

The single-source `silvia_auto.py` pipeline scrapes Yahoo Finance, writes with Claude, and publishes. It works 95% of the time. The 5% when it does not includes: sign errors (+92K vs -92K), direction errors (BEAT vs MISS), vote-count errors (11-1 vs 11-2), stale consensus numbers, and paraphrased quotes presented as verbatim. Any of those on a live CFO account is a reputation-damaging mistake.

TRIPLEX fixes the 5% by requiring **three independent paths to the same truth** and a traceability audit that ties every sentence back to a verified source.

## Pipeline stages

```
1. Discovery         Event Detector agent identifies every event today
2. Triple-fetch      3 parallel scrapers (primary / wire / media)
3. Consensus         Deterministic reconciliation (green/yellow/red)
4. Tiebreaker        Re-fetch yellow/red fields
5. Red Team          Adversarial fact checker (sign, direction, timing, identity)
6. Writer            Silvia voice, using only locked fields via traceable refs
7. Compliance        Voice + format + structure audit (agent + deterministic)
8. Traceability      Sentence-by-sentence audit against locked data
9. Devils Advocate   Hostile-reader framing check
10. Assets           Card PNG render + ChatGPT image prompt
11. Human gate       POST / REVISE / REJECT (blocking, never auto-post)
12. Publish          Tweepy to @CFOSilvia + append to post_history.json
```

Every stage writes its output to `verification/<event_id>/` so the full audit trail is preserved. A run you published yesterday can be fully reviewed six months later.

## Agents and their roles

| # | Agent | Model | Purpose |
|---|---|---|---|
| 1 | EventDetector | Sonnet 4.5 | Finds every event that warrants a post today |
| 2A | PrimaryScraper | Sonnet 4.5 | Official sources only (SEC, Fed.gov, BLS, BEA, company IR) |
| 2B | WireScraper | Sonnet 4.5 | Wire services only (Reuters, Bloomberg, AP) |
| 2C | MediaScraper | Sonnet 4.5 | Financial media only (CNBC, WSJ, Barron's, Benzinga) |
| 3 | ConsensusReconciler | deterministic Python | Compares A/B/C field-by-field |
| 3b | Tiebreaker | Sonnet 4.5 | Resolves yellow/red fields with a 4th source |
| 4 | RedTeam | **Opus 4.6** | Adversarial fact checker |
| 5 | Writer | **Opus 4.6** | Silvia voice generator |
| 6 | ComplianceAuditor | Sonnet 4.5 + deterministic Python | Voice + format + structure |
| 7 | TraceabilityAuditor | deterministic Python | Sentence-to-field mapping |
| 8 | DevilsAdvocate | **Opus 4.6** | Hostile-reader framing check |

Opus 4.6 runs on the three highest-stakes agents: red team, writer, devil's advocate. Sonnet 4.5 handles everything else. All agent prompts live in `triplex/prompts/*.txt` and can be edited independently of the Python code.

## Triple-source consensus rules

For every data field in the event schema:

- **Green** → all three scrapers agree within tolerance (1% for numeric, exact match for text). Ship it.
- **Yellow** → two of three scrapers agree. Tiebreaker runs with a fourth independent source.
- **Red** → all three disagree, or only one scraper returned a value. Pipeline halts for human review.

Numeric tolerance is 1% relative. Text fields (names, quotes, directions) require exact match after normalization. Sign fields (positive vs negative, beat vs miss, hawkish vs dovish) require zero-tolerance exact agreement.

## Field schemas per event type

See `triplex/schemas.py` for the full schemas. Summary:

**Earnings required:** ticker, company_name, fiscal_period, report_timing, adjusted_eps_actual, adjusted_eps_estimate, revenue_actual, revenue_estimate, stock_reaction_pct

**Earnings optional:** reported_gaap_eps, revenue_yoy_growth, segment_breakdown, q2_eps_guidance, q2_revenue_guidance, fy_guidance, ceo_quote_verbatim, conference_call_time, premium_revenue_actual, capacity_change

**Macro required:** indicator, release_time_et, headline_number, headline_unit, consensus_estimate, prior_value

**Macro optional:** sub_components, revisions, market_reaction_yield, market_reaction_equities, fomc_vote_count, fomc_dissenters, fomc_dissent_reasoning, fed_funds_target, powell_quote_verbatim

**Daily required:** date, sp500_close, sp500_pct_change, nasdaq_pct_change, dow_pct_change, dow_close, wti_close, wti_pct_change, top_story_headline

**Daily optional:** brent_close, brent_pct_change, gold_pct_change, bitcoin_pct_change, ten_year_yield_close, ten_year_yield_bps_change, vix_close, russell_pct_change, after_hours_earnings, tomorrow_calendar

## Running TRIPLEX

```bash
# Full daily batch (discovers all events, runs each through the full pipeline)
python silvia_triplex.py

# Specific date
python silvia_triplex.py --date 2026-04-08

# Single event by id
python silvia_triplex.py --event-id 2026-04-08_dal_earnings

# Just list today's events without running the pipeline
python silvia_triplex.py --only-discover

# Full pipeline but skip the human gate and publish (for testing)
python silvia_triplex.py --dry-run

# Print the Claude Code runbook without calling any APIs
python silvia_triplex.py --claude-code
```

**All API keys are optional.** TRIPLEX auto-detects what is available:

```
ANTHROPIC_API_KEY=sk-ant-...   # optional; if missing → Claude Code mode
TWITTER_API_KEY=...            # optional; if missing → manual posting mode
TWITTER_API_SECRET=...
TWITTER_ACCESS_TOKEN=...
TWITTER_ACCESS_SECRET=...
TWITTER_BEARER_TOKEN=...
```

There is no `AUTO_POST` in TRIPLEX. Every publish requires a human typing POST at the gate.

## Running without API keys (Claude Code mode)

If you do not want to pay for an Anthropic API key (or Twitter API access), TRIPLEX still works. You run each agent by hand in Claude Code (claude.ai/code) using the prompt files in `triplex/prompts/*.txt`, then use the deterministic Python stages locally for consensus, traceability, and compliance regex.

### Step-by-step for one event

1. **Discover events** — Open Claude Code in the repo folder and run:

   ```
   Read triplex/prompts/01_event_detector.txt
   Using WebSearch, find every CFO Silvia-caliber event for 2026-04-08
   Save the JSON result to verification/2026-04-08/events.json
   ```

2. **Triple-scrape one event** — For each event, run three separate Claude Code sessions (or three sequential prompts) so each scraper forms an independent view:

   ```
   Read triplex/prompts/02a_primary_scraper.txt
   The event is: {event JSON from step 1}
   Use WebSearch + WebFetch on company IR, SEC, Fed.gov, BLS only
   Save to verification/<event_id>/primary.json
   ```

   Then repeat with `02b_wire_scraper.txt` (Reuters/Bloomberg/AP only) and `02c_media_scraper.txt` (CNBC/WSJ/Barron's/Benzinga only). Each run should only touch its allowed sources.

3. **Run deterministic consensus locally** — This is pure Python, no LLM needed:

   ```bash
   python -c "
   import json
   from triplex.reconcile import reconcile
   from triplex.schemas import ScraperResult, ScrapedField

   def load(name):
       data = json.load(open(f'verification/2026-04-08_dal_earnings/{name}.json'))
       fields = {k: ScrapedField(**v) for k, v in data['fields'].items()}
       return ScraperResult(event_id=data['event_id'], scraper_label=data['scraper_label'], fields=fields)

   locked = reconcile('2026-04-08_dal_earnings', 'earnings', 'DAL',
                      load('primary'), load('wire'), load('media'))
   open('verification/2026-04-08_dal_earnings/locked_data.json', 'w').write(
       json.dumps(locked.to_dict(), indent=2, default=str))
   print('Locked. Green:', sum(1 for f in locked.fields.values() if f.confidence == 'green'))
   "
   ```

4. **Red team, writer, compliance, devil's advocate** — Back to Claude Code, one prompt at a time:

   ```
   Read triplex/prompts/04_red_team.txt
   The locked data is: {paste contents of verification/<event_id>/locked_data.json}
   Use WebSearch to independently verify the critical claims
   Return the JSON report per the prompt spec
   Save to verification/<event_id>/red_team.json
   ```

   Same pattern for `05_writer.txt`, `06_compliance.txt`, `08_devils_advocate.txt`.

5. **Deterministic traceability scan** — local Python again:

   ```bash
   python -c "
   import json
   from triplex.traceability import audit, deterministic_compliance_scan
   from triplex.schemas import LockedData, LockedField

   ld_json = json.load(open('verification/2026-04-08_dal_earnings/locked_data.json'))
   fields = {k: LockedField(**v) for k, v in ld_json['fields'].items()}
   locked = LockedData(event_id=ld_json['event_id'], event_type=ld_json['event_type'],
                       identifier=ld_json['identifier'], fields=fields,
                       unresolved_fields=ld_json['unresolved_fields'])
   post = open('verification/2026-04-08_dal_earnings/post.txt').read()
   print('Compliance:', deterministic_compliance_scan(post, 'earnings'))
   print('Traceability:', audit('2026-04-08_dal_earnings', post, locked).overall_status)
   "
   ```

6. **Render the card PNG** — use the existing Playwright helper:

   ```bash
   python -c "
   from silvia_auto import render_card
   brief = {'TICKER': 'DAL', 'VERDICT': 'BEAT', 'EPS_ACTUAL': '\$0.64',
            'EPS_EST': '\$0.61', 'REV_ACTUAL': '\$14.2B', 'REV_EST': '\$13.94B',
            'AH_MOVE': '+11.8%', 'QUARTER': 'Q1 FY2026'}
   render_card('earnings', brief, 'silvia_logs/card_dal.png')
   "
   ```

7. **Generate the Calvin & Hobbes illustration** — copy the prompt from `output/<date>/<event>/<event>-ch-image-prompt.md` into ChatGPT-4o image generation or DALL-E 3. Save the result.

8. **Post manually** — open https://x.com/compose/post, paste the post text from `verification/<event_id>/post.txt`, attach the Calvin & Hobbes image (or the Playwright card, whichever you prefer), and click Post.

### Shortcut: TRIPLEX runbook auto-print

Running `python silvia_triplex.py --claude-code` or running it with no `ANTHROPIC_API_KEY` prints a condensed version of this runbook for the current date. Use it as a prompt for Claude Code.

## Image generation modes

Each post supports two image styles:

1. **Institutional Bloomberg-style card** (`<event>-image-prompt.md`) — rendered automatically by Playwright from the card brief, or manually via ChatGPT from the prompt. 1200x675 PNG, jet black background, gold accent bar.

2. **Calvin & Hobbes illustration** (`<event>-ch-image-prompt.md`) — generated manually via ChatGPT-4o image / DALL-E 3 / Midjourney. Hand-drawn watercolor style, recurring character, scene-specific props and mood. See `triplex/prompts/ch_image_style_guide.md` for the shared style spec.

The Calvin & Hobbes illustrations are the default @CFOSilvia voice for posts. The institutional card is a fallback for days when the illustration cannot be generated in time.

## What the human sees at the gate

The review package shown at the human sign-off gate contains:

1. The full post text
2. The rendered card PNG path
3. The traceability report (every sentence → locked fields → source URLs)
4. Red team findings and status
5. Compliance audit findings and status
6. Devil's advocate framing notes
7. All source URLs used anywhere in the pipeline
8. Locked data confidence summary (green/yellow/red field counts)

Hard preconditions block the POST option:
- Traceability status = fail (any sentence has an unsourced numeric claim)
- Compliance status = fail (any banned word, em dash, exclamation, etc.)
- Red team status = fail (any sign/direction/timing/identity error)
- Any locked field still marked red after tiebreaker

If any of those are true, the human can type REJECT or REVISE, but not POST.

## Directory layout

```
silvia-x-content-factory/
  silvia_triplex.py              # CLI + orchestrator
  triplex/
    __init__.py
    schemas.py                   # dataclasses for events, locked data, reports
    agents.py                    # 8 agent wrapper classes
    reconcile.py                 # deterministic consensus + numeric tolerance
    traceability.py              # sentence-level audit + deterministic scan
    review.py                    # human gate and review package
    prompts/
      01_event_detector.txt
      02a_primary_scraper.txt
      02b_wire_scraper.txt
      02c_media_scraper.txt
      04_red_team.txt
      05_writer.txt
      06_compliance.txt
      08_devils_advocate.txt
  verification/                  # runtime output, audit trails
    2026-04-08/
      events.json
      2026-04-08_dal_earnings/
        primary.json
        wire.json
        media.json
        locked_data.json
        red_team.json
        post.txt
        writer_trace.json
        compliance.json
        traceability.json
        devils_advocate.json
        review_package.json
        human_decision.json
        published.json
```

## Cost

Rough per-post estimate at Opus 4.6 / Sonnet 4.5 pricing:

| Agent | Input | Output | Model | Cost |
|---|---|---|---|---|
| EventDetector | 3k | 1k | Sonnet | $0.02 |
| PrimaryScraper | 8k | 2k | Sonnet | $0.05 |
| WireScraper | 8k | 2k | Sonnet | $0.05 |
| MediaScraper | 8k | 2k | Sonnet | $0.05 |
| RedTeam | 5k | 2k | Opus | $0.23 |
| Writer | 4k | 1.5k | Opus | $0.17 |
| Compliance | 3k | 0.5k | Sonnet | $0.02 |
| DevilsAdvocate | 3k | 1k | Opus | $0.13 |

**Per post: ~$0.70. Per four-post daily batch: ~$3.** Roughly $75-90/month if run every trading day.

## Extending

To add a new event type (e.g., `sector` for sector rotation):

1. Add a new event type to `EventType` literal in `schemas.py`
2. Add field lists to `schemas.py` (`SECTOR_FIELDS_REQUIRED`, `SECTOR_FIELDS_OPTIONAL`)
3. Update `fields_for()` in `schemas.py`
4. Add card brief extraction in `silvia_triplex.py` `stage10_assets()`
5. Add image prompt template in `_build_image_prompt()`
6. Update `SYSTEM_*` prompt in the writer agent (`triplex/prompts/05_writer.txt`)
7. Test with `--event-id` on a specific date

To change the banned word list, update both:
- `triplex/prompts/05_writer.txt` (informs the writer)
- `triplex/traceability.py` `BANNED_WORDS` (enforced by deterministic scan)

## Audit trail

Every run writes to `verification/<event_id>/`. These files are gitignored by default but can be committed if the team wants a shared audit trail. The minimum retention is 30 days; longer is recommended for compliance review.
