# CFO Silvia Content Universe

This folder defines **who we cover** on @CFOSilvia. It exists so the event detector stops making subjective judgment calls on every ticker.

## Files

- `silvia_universe.json` — the canonical tiered universe with coverage rules per event type
- `tier_1_mega_caps.txt` — plain-text list of the 100 Tier 1 tickers for quick grep and visual inspection

## The three tiers

### Tier 1 — Auto-cover (100 tickers)

The top 100 US companies by market capitalization as of the last refresh. Every earnings print from these names becomes a Silvia post. No judgment call, no selective filtering. If they report, we write.

This tier is anchored to market cap, not index inclusion, because some mega caps (like Berkshire Hathaway historically) flip in and out of the top 500 for mechanical reasons that don't affect how Silvia's audience perceives them.

**Rule for editing:** Add a ticker only if it crosses $100B market cap AND has the kind of retail recognition that warrants always-cover. Remove a ticker only if it falls out of the top 150 and the removal doesn't create a household-name gap.

### Tier 2 — Conditional S&P 500 (~400 tickers)

All S&P 500 members not in Tier 1. Covered only if at least one of these fires:

- EPS beat/miss ≥ 5% vs consensus
- Revenue beat/miss ≥ 3% vs consensus
- Post-release stock move ≥ 3% (pre-market or after-hours, 8-hour window)
- Narrative trigger from the list in `silvia_universe.json` (CEO change, guidance shock, dividend cut, $1B+ buyback, $5B+ M&A, activist 13D, SEC/DOJ action, multi-notch credit downgrade, Tier 1 sector read-through)

This keeps us from drowning in 500 posts per earnings season while catching anything that matters.

### Tier 3 — Non-S&P conditional

Default is **skip**. Silvia is not a meme-stock account. Non-S&P names are covered only when they meet both a size threshold and a concrete catalyst:

- Stock move ≥ 8% intraday on a concrete catalyst (not momentum)
- Qualifying catalyst: recent IPO first/second print, major M&A $5B+, viral retail story, crypto-adjacent breaking news, Musk-style public endorsement, SEC/DOJ enforcement, needle-moving biotech FDA event, notable ADR (TSM, ASML, SE, MELI style), or Russell 1000 with Tier 1 sector read-through

There is also a small **Tier 3 allowlist** of 23 high-profile non-S&P names (COIN, HOOD, MSTR, RBLX, RDDT, TSM, ASML, SE, SHOP, BABA, JD, PDD, MELI, NIO, RIVN, LCID, SMCI, ARM, CRWD, SNOW, NET, DDOG, DJT) that we treat like Tier 2 even though they're outside the index — they're household enough to Silvia's audience that missing their earnings would be a gap.

## Non-earnings event rules

Macro releases, Fed events, and geopolitical surprises follow their own always-cover / conditional logic in `silvia_universe.json` under `event_type_rules`. Summary:

- **Always cover**: CPI, PPI, NFP, PCE, GDP, FOMC meetings and minutes, JOLTS, Retail Sales, Powell speeches, FOMC voter market-moving quotes
- **Conditional**: ISM, Consumer Confidence, housing data, regional Fed presidents — only if they move the tape or dissent meaningfully
- **Geopolitical**: any event that moves a major index >1% or oil/gold/DXY >3% intraday, or that names a Tier 1 sector specifically

## Daily cadence

One post always fires per trading day regardless of what else happens: **the 4:30 PM ET daily wrap** — session summary, indices, commodities, top earnings, key stories, tomorrow's preview.

## Refresh cadence

This universe should be refreshed:
- Quarterly (or after any major S&P 500 index rebalance)
- When a mega-cap is spun off (e.g., GE Vernova from GE in 2024, SanDisk from Western Digital in 2025)
- When a new name crosses $100B and stays there for two quarters
- When a current Tier 1 name falls below $50B for two quarters

Track the `updated` and `last_review` fields in `silvia_universe.json`.

## How the detector uses this

`triplex/prompts/01_event_detector.txt` instructs the event detector agent to classify every earnings / macro / surprise event against this file. The detector outputs a JSON list of events with tier classifications. Tier 1 always becomes a post; Tier 2 and Tier 3 become posts only when their specific coverage triggers fire.

## Why this matters

The prior approach was "Silvia-caliber names (large-cap, household, market-moving)" which required judgment on every ticker and led to inconsistent coverage. This file kills the judgment, makes "why wasn't X covered" answerable by grep, and makes the entire universe editable from one place.
