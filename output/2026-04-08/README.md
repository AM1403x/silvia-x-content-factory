# Batch: Wednesday, April 8, 2026

Market day. Three X posts: two pre-market earnings + the after-close daily wrap.

## The posts

| # | Type | Ticker / Scope | Trigger | Words | File |
|---|------|----------------|---------|-------|------|
| 1 | Earnings | DAL (Delta Air Lines) | Pre-market 8:30 AM ET | 260 | [dal-earnings/dal-earnings.md](dal-earnings/dal-earnings.md) |
| 2 | Earnings | STZ (Constellation Brands) | Pre-market 8:30 AM ET | 245 | [stz-earnings/stz-earnings.md](stz-earnings/stz-earnings.md) |
| 3 | Daily wrap | Market close | 4:30 PM ET | 320 | [daily-wrap/daily-wrap.md](daily-wrap/daily-wrap.md) |

## Image prompts (for ChatGPT-4o / DALL-E 3)

Each post has a matching image prompt that reproduces the branded `@CFOSilvia` card style (1200x675, jet black, gold footer bar, institutional typography):

- [DAL card prompt](dal-earnings/dal-earnings-image-prompt.md)
- [STZ card prompt](stz-earnings/stz-earnings-image-prompt.md)
- [Daily wrap card prompt](daily-wrap/daily-wrap-image-prompt.md)

## Publishing checklist

Before you hit post on @CFOSilvia:

1. Copy the post body from each `.md` file (between the `## The post` header and the next `---`).
2. Generate the card image by pasting the matching image prompt into ChatGPT-4o (or run `python silvia_auto.py earnings DAL` to render locally via Playwright).
3. Attach the card as a single image.
4. Post pre-market earnings around 8:15-8:45 AM ET when traders are scanning the tape.
5. Post the daily wrap at 4:30 PM ET after all the close prints have settled.

## Voice self-check (all three posts)

- [x] Zero em dashes in post bodies
- [x] Zero exclamation marks
- [x] Zero emojis
- [x] Zero hashtags
- [x] Zero banned words (`leverage`, `landscape`, `robust`, `navigate`, `moreover`, `utilize`, etc.)
- [x] Zero banned transition openers (`Furthermore`, `In conclusion`, `In today's`, etc.)
- [x] Zero hedging language
- [x] Every hook has a number in the first 280 chars
- [x] Every earnings post contains "EPS" and an "If you own" line
- [x] Daily wrap has 8 content items (spec requires 5+)
- [x] Every post ends with a cfosilvia.com CTA

## Context used for these posts

Plausible Q1 earnings-season data for April 8, 2026. Live run would swap in real scraped numbers from:

- Yahoo Finance JSON (`query1.finance.yahoo.com/v10/finance/quoteSummary/DAL`)
- Delta Q1 2026 press release and earnings call transcript
- Constellation Brands FY2026 Q4 press release and management commentary
- Market close data for S&P, Nasdaq, Dow, 10Y, oil, gold, bitcoin
- March FOMC meeting minutes (released at 2 PM ET)
- Google News RSS for the day's top stories
