# Batch: Wednesday, April 8, 2026

Market day. Four X posts, firing in chronological order: two pre-market earnings, the FOMC March minutes at 2 PM ET, and the after-close daily wrap.

## The posts (in order of when they fire)

| # | Time ET | Type | Scope | Words | File |
|---|---------|------|-------|-------|------|
| 1 | 8:15 AM | Earnings | DAL (Delta Air Lines, Q1 FY2026 BEAT) | 260 | [dal-earnings/dal-earnings.md](dal-earnings/dal-earnings.md) |
| 2 | 8:30 AM | Earnings | STZ (Constellation Brands, Q4 FY2026 BEAT) | 245 | [stz-earnings/stz-earnings.md](stz-earnings/stz-earnings.md) |
| 3 | 2:05 PM | Macro | FOMC March meeting minutes (HAWKISH) | 290 | [fomc-minutes-macro/fomc-minutes-macro.md](fomc-minutes-macro/fomc-minutes-macro.md) |
| 4 | 4:30 PM | Daily wrap | Market close | 320 | [daily-wrap/daily-wrap.md](daily-wrap/daily-wrap.md) |

## Why four posts today

The factory's triggers are event-driven, not a fixed daily count. April 8, 2026 happens to stack up:

- **Two pre-market earnings** — Delta kicks off Q1 airline season, Constellation reports full-year FY2026
- **FOMC March minutes at 2 PM ET** — released exactly three weeks after the March 17-18 FOMC meeting, on a pre-announced calendar. This is the biggest macro print of the week until Thursday's CPI
- **Daily wrap** — always fires at 4:30 PM ET after the close

Run the pipeline as:

```bash
python silvia_auto.py earnings DAL      # ~8:00 AM ET
python silvia_auto.py earnings STZ      # ~8:15 AM ET
python silvia_auto.py macro FED         # ~2:05 PM ET (after minutes release)
python silvia_auto.py daily             # ~4:30 PM ET (or let cron fire it)
```

## Image prompts (for ChatGPT-4o / DALL-E 3)

Each post has a matching image prompt that reproduces the branded `@CFOSilvia` card style (1200x675, jet black, gold footer bar, institutional typography):

- [DAL card prompt](dal-earnings/dal-earnings-image-prompt.md)
- [STZ card prompt](stz-earnings/stz-earnings-image-prompt.md)
- [FOMC minutes card prompt](fomc-minutes-macro/fomc-minutes-macro-image-prompt.md)
- [Daily wrap card prompt](daily-wrap/daily-wrap-image-prompt.md)

## Publishing checklist

Before you hit post on @CFOSilvia:

1. Copy the post body from each `.md` file (between the `## The post` header and the next `---`).
2. Generate the card image by pasting the matching image prompt into ChatGPT-4o (or run `python silvia_auto.py earnings DAL` to render locally via Playwright).
3. Attach the card as a single image.
4. Post pre-market earnings around 8:15-8:45 AM ET when traders are scanning the tape.
5. Post the daily wrap at 4:30 PM ET after all the close prints have settled.

## Voice self-check (all four posts)

- [x] Zero em dashes in post bodies
- [x] Zero exclamation marks
- [x] Zero emojis
- [x] Zero hashtags
- [x] Zero banned words (`leverage`, `landscape`, `robust`, `navigate`, `moreover`, `utilize`, etc.)
- [x] Zero banned transition openers (`Furthermore`, `In conclusion`, `In today's`, etc.)
- [x] Zero hedging language
- [x] Every hook has a number in the first 280 chars
- [x] Every earnings post contains "EPS" and an "If you own" line
- [x] Macro post has verdict, headline number, portfolio impact, and "what to watch next" with a date
- [x] Daily wrap has 8 content items (spec requires 5+)
- [x] Every post ends with a cfosilvia.com CTA

## Context used for these posts

Plausible Q1 earnings-season data for April 8, 2026. Live run would swap in real scraped numbers from:

- Yahoo Finance JSON (`query1.finance.yahoo.com/v10/finance/quoteSummary/DAL`)
- Delta Q1 2026 press release and earnings call transcript
- Constellation Brands FY2026 Q4 press release and management commentary
- March FOMC meeting minutes PDF released by the Fed at 2:00 PM ET
- Fed funds futures curve from the CME FedWatch tool (June cut probabilities before and after the release)
- Market close data for S&P, Nasdaq, Dow, 10Y, oil, gold, bitcoin
- Google News RSS for the day's top stories
