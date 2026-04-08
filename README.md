# CFO Silvia — X Content Factory

An automated content pipeline for [@CFOSilvia](https://x.com/CFOSilvia) on X. Scrapes financial data, generates a post in Silvia's voice via Claude, renders a branded image card, runs a QA review, and publishes to X.

One script. Three post types. No paid data APIs.

## What it does

You run one command. The pipeline:

1. **Scrapes** the data it needs (Yahoo Finance, TradingEconomics, Google News RSS).
2. **Writes** the post by calling the Claude API with a Silvia system prompt.
3. **Renders** a 1200x675 image card using a Playwright-driven HTML template.
4. **Reviews** the post against a banned-word, formatting, and hook checklist.
5. **Confirms** (or skips confirmation if `AUTO_POST=true`) and posts to X via Tweepy.
6. **Logs** the post text, card, review score, and final URL.

## Two pipelines

This repo ships two separate pipelines for two different trust levels:

| Pipeline | Use when | Entry point | Docs |
|---|---|---|---|
| **silvia_auto** | Experimentation, throwaway drafts, single-source scraping is good enough | `python silvia_auto.py ...` | This README |
| **TRIPLEX** | Every live post on @CFOSilvia — triple-source verification, adversarial red team, sentence-level traceability, mandatory human gate | `python silvia_triplex.py ...` | [TRIPLEX.md](TRIPLEX.md) |

Default to TRIPLEX for anything that ships publicly. silvia_auto is kept for experimentation and as a reference implementation.

## Post types

| Mode | Command | What it posts | Words |
|------|---------|---------------|-------|
| Earnings | `python silvia_auto.py earnings NVDA` | Beat/miss verdict, EPS, revenue, guidance, "If you own" line | 200-300 |
| Macro | `python silvia_auto.py macro CPI` | Headline number, verdict, market reaction, what to watch | 200-300 |
| Daily wrap | `python silvia_auto.py daily` | 5-8 story items covering the trading day, tomorrow's preview | 300-500 |
| Cron | `python silvia_auto.py cron` | Daemon. Fires the daily wrap at 4:30 PM EST on weekdays | — |

Macro indicators supported: `CPI`, `JOBS`, `GDP`, `PCE`, `FED`.

## Silvia voice (short version)

Silvia is a personal CFO. She writes like she's on a call with a client she respects:

- Lead with the number. No scene-setting.
- Short paragraphs (1-2 sentences). Varied rhythm.
- Has a take, never hedges into meaninglessness.
- No emojis, hashtags, em dashes, exclamation marks, corporate jargon.
- The first 280 characters must work as a standalone hook above X's "Show more" fold.
- Every post ends with a CTA to `cfosilvia.com`.

Full voice rules, banned word list, and format spec live in `CLAUDE.md`.

## Install

```bash
git clone https://github.com/AM1403x/silvia-x-content-factory.git
cd silvia-x-content-factory
bash setup.sh
```

`setup.sh` installs Python deps, grabs Chromium for Playwright, and copies `.env.example` to `.env`.

Manual install:

```bash
pip install anthropic tweepy requests beautifulsoup4 playwright lxml
playwright install chromium
cp .env.example .env
```

## Configure

Fill in `.env`:

```bash
# Claude API (required)
ANTHROPIC_API_KEY=sk-ant-...

# X/Twitter API (required for posting; set Read+Write perms)
TWITTER_API_KEY=
TWITTER_API_SECRET=
TWITTER_ACCESS_TOKEN=
TWITTER_ACCESS_SECRET=
TWITTER_BEARER_TOKEN=

# Optional
AUTO_POST=false            # true = skip human confirmation
LOG_DIR=./silvia_logs      # where logs, cards, and history go
```

## Run

```bash
# Earnings post (scrapes Yahoo Finance for the ticker)
python silvia_auto.py earnings NVDA

# Macro post (CPI, JOBS, GDP, PCE, FED)
python silvia_auto.py macro CPI

# Daily wrap (pulls indices, commodities, bitcoin, top stories)
python silvia_auto.py daily

# Daemon mode (fires daily wrap at 4:30 PM EST Mon-Fri)
python silvia_auto.py cron
```

## The review checklist

Every post is scored before it can publish. Errors block posting; warnings do not.

- Word count in target range
- No em dashes or en dashes
- No exclamation marks
- No emojis
- No banned words (`leverage`, `landscape`, `robust`, `navigate`, `moreover`, etc. — full list in `CLAUDE.md`)
- No banned transition openers (`Furthermore`, `In conclusion`, `In today's`, etc.)
- No hashtags
- CTA to `cfosilvia.com` present
- No hedging language (`it seems`, `only time will tell`, etc.)
- Hook (first 280 chars) contains a number
- Sentence-length variation above a minimum threshold
- Type-specific: earnings posts need `EPS` and an `If you own` line; daily wraps need 5+ content items

Set `AUTO_POST=false` (default) to see the review and type `POST` to publish. Set `AUTO_POST=true` to auto-publish any post that clears the review.

## Output

Every run lands in `silvia_logs/` (or whatever you set `LOG_DIR` to):

```
silvia_logs/
  pipeline.log                      # tail this to watch runs
  data_earnings_20260408_091200.json  # raw scraped data
  post_earnings_20260408_091200.txt   # the final post text
  card_earnings_20260408_091200.png   # 1200x675 image
  review_earnings_20260408_091200.json # QA checklist result
  post_history.json                   # append-only ledger of live posts
```

## Cron / scheduling

The built-in `cron` command runs a simple in-process scheduler that fires the daily wrap weekdays at 4:30 PM EST. For earnings and macro posts, trigger them manually the morning they land:

```bash
# Pre-market earnings (Delta, JPM, etc.)
python silvia_auto.py earnings DAL

# Macro print (CPI at 8:30 AM EST)
python silvia_auto.py macro CPI
```

If you want real production scheduling, wire the earnings and macro commands to your OS cron or a GitHub Actions schedule that matches the earnings calendar and BLS release dates.

## Project layout

```
silvia-x-content-factory/
  silvia_auto.py       # The entire pipeline: scrape -> write -> render -> review -> post
  setup.sh             # One-shot installer
  .env.example         # Template for your secrets
  .gitignore
  README.md            # You are here
  CLAUDE.md            # Voice rules, banned lists, Claude Code instructions
```

Everything the pipeline needs is in `silvia_auto.py`. Six sections, clearly marked:

1. Data scrapers (Yahoo, TradingEconomics, Google News)
2. Claude API calls with the three system prompts
3. Card image generation (HTML template + Playwright render)
4. Review engine (scores the post)
5. X posting (Tweepy v1.1 for media, v2 for tweets)
6. Orchestrator and CLI

## Extending

To add a new post type (say, `sector` for a sector-rotation snapshot):

1. Add a `scrape_sector()` in Part 1.
2. Add a `SYSTEM_SECTOR` prompt in Part 2 with hook rules, body structure, and the `IMAGE_CARD_BRIEF` fields the card template needs.
3. Add a `generate_sector_post()` that calls `call_claude(SYSTEM_SECTOR, ...)`.
4. Add a card branch in `generate_card_html()`.
5. Wire it into `run_pipeline()` and the CLI in `main()`.

To update the banned-word list, edit the `BANNED_WORDS` and `BANNED_OPENERS` arrays near the top of Part 4. `CLAUDE.md` has the reasoning behind each.

## License

Personal project. No warranty. Use at your own risk — especially `AUTO_POST=true`.
