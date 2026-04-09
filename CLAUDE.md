# CLAUDE.md — CFO Silvia X Content Factory

Instructions for Claude Code (and any LLM collaborator) working on this repo.

## API keys are optional

Both ANTHROPIC_API_KEY and TWITTER_* keys are OPTIONAL. The pipeline detects
what is available:

- **No ANTHROPIC_API_KEY**: use Claude Code manual mode. Run each agent
  prompt from `triplex/prompts/*.txt` by hand in Claude Code, save the
  outputs to `verification/<event_id>/`, then run the deterministic
  Python stages (consensus, traceability, compliance regex) locally.
- **No TWITTER_\***: the pipeline still renders the card PNG and writes
  the post text to a file. Post manually by copying the text into
  https://x.com/compose/post and attaching the PNG.

See `TRIPLEX.md` section "Running without API keys" for the full step-by-step.

## What this repo is

A single-file Python pipeline (`silvia_auto.py`) that produces X posts for [@CFOSilvia](https://x.com/CFOSilvia). Three post types: earnings, macro, daily wrap. Every run scrapes its own data, writes with Claude, renders an image card, QA-reviews the post, and publishes to X.

This is not the long-form article factory. That one lives in a separate repo and produces blog posts with SVG visualizations. This repo only produces X posts with PNG cards.

## How to run

```bash
# Setup once
bash setup.sh
# Fill .env with ANTHROPIC_API_KEY + TWITTER_* keys

# Daily operations
python silvia_auto.py earnings NVDA    # Earnings post
python silvia_auto.py macro CPI        # Macro data post
python silvia_auto.py daily            # Daily wrap
python silvia_auto.py cron             # Daemon: daily wrap at 4:30 PM EST

# Auto-publish without confirmation
AUTO_POST=true python silvia_auto.py daily
```

## Pipeline order (never skip, never reorder)

1. **Scrape** — pulls public data. Yahoo Finance JSON for tickers/indices, TradingEconomics for macro estimates, Google News RSS for context. Failures fall back to `[MANUAL]` placeholders.
2. **Generate** — Claude writes the post from one of three system prompts (`SYSTEM_EARNINGS`, `SYSTEM_MACRO`, `SYSTEM_DAILY`) plus a scraped-data user prompt. Returns post text plus an `IMAGE_CARD_BRIEF` block for the card.
3. **Render card** — builds an HTML card from `CARD_HTML_TEMPLATE`, loads it in headless Chromium via Playwright, screenshots the `.card` div at 1200x675.
4. **Review** — runs `review_post()` against the banned-word list, word count, em dashes, exclamation marks, emojis, hashtags, hedging, CTA presence, hook-has-number, sentence variation, and type-specific checks.
5. **Confirm + post** — prints a preview, asks the user to type `POST` unless `AUTO_POST=true`, then publishes via Tweepy (v1.1 for media upload, v2 for the tweet).
6. **Log** — writes raw data, post text, card image, review JSON, and appends to `post_history.json`.

## Silvia voice

Silvia is a personal CFO. She writes like she's on a call with a client she respects. The whole voice fits in five rules:

1. **Lead with the number.** No scene-setting, no throat-clearing. First sentence has a dollar sign or percentage.
2. **Have a take.** Every post makes a judgment. Never hedge into meaninglessness.
3. **Short paragraphs, varied rhythm.** 1-2 sentence paragraphs. Follow a long explanatory sentence with a short punchy one.
4. **Talk to the reader.** Use "you" and "your." Every post ends with "Ask Silvia. cfosilvia.com" or a type-specific CTA.
5. **No corporate jargon.** See the banned lists below.

The first 280 characters of every post must work as a standalone hook above X's "Show more" fold. That means ticker in Unicode bold (earnings), data name in Unicode bold (macro), or date in Unicode bold (daily), followed by the number and the verdict.

## ZERO trade action language (absolute rule)

Silvia is a commentator and CFO voice, not a licensed broker. She NEVER tells the reader what to do with a position. She tells them what to WATCH, what the RISK is, and what the KEY TELL is. Prescriptive trade actions are illegal for unlicensed finance accounts and damage the brand.

**Banned verbs and phrases (case-insensitive, any match = hard fail):**

Direct instructions: `you should buy`, `you should sell`, `buy this stock`, `sell this stock`, `we recommend`, `I recommend`, `must buy`, `must sell`

Trim / add: `trim into strength`, `trim on strength`, `trim the position`, `add on weakness`, `add into weakness`, `add to the position`

Chase: `do not chase`, `don't chase`, `chase this`

Take profits / cut losses: `take profits`, `take profit here`, `lock in profits`, `book the gain`, `cut losses`, `cut your losses`

Scale in/out, load, dump, exit, enter: `scale in`, `scale out`, `load up`, `dump this`, `exit now`, `get out of`, `get into`, `time to buy`, `time to sell`, `time to exit`

Dip / rip: `buy the dip`, `sell the rip`

Size / allocation: `size up`, `size down`, `size positions accordingly`, `size your position`, `position size`

Wait / avoid: `wait for entry`, `wait to buy`, `better to wait`, `avoid this stock`, `avoid the name`, `skip this one`

Rotate: `rotate into`, `rotate out of`

Short/long as verbs: `short it`, `long it`, `short the name`, `long the name`

Position actions: `initiate a position`, `close the position`, `open a position`

**The "If you own TICKER:" line is allowed**, but its job is to direct ATTENTION, never to direct ACTION.

- Good: *"If you own DAL: premium is doing its job. Watch main cabin yield in the Q2 report."*
- Good: *"If you own INTC: the real test is whether management puts dollar numbers on the Google deal on the next earnings call."*
- **Bad (hard fail):** *"Trim into strength if you're sitting on a multi-bagger. Do not chase."*

**No specific price targets** unless quoting a named analyst verbatim with attribution.

**No allocation advice.** Never say "put 5% of your portfolio in X" or any variation.

The full banned phrase list lives in `triplex/traceability.py` `BANNED_TRADE_ACTION_PHRASES`. The deterministic compliance scan hard-blocks any post containing any of these phrases before it can reach the human gate. The writer system prompt (`triplex/prompts/05_writer.txt`) and the compliance auditor prompt (`triplex/prompts/06_compliance.txt`) enforce the same rule at the LLM layer.

If you ever need to add a new banned phrase, update all three locations: `CLAUDE.md` (this section), `05_writer.txt` (writer guidance), `06_compliance.txt` (auditor scan), and `traceability.py::BANNED_TRADE_ACTION_PHRASES` (deterministic regex enforcement).

## Bolding convention — Unicode only, never markdown

X does NOT render markdown `**bold**`. Asterisks get stripped on paste. The only kind of bold that survives copy-paste into the X composer is **Unicode Mathematical Bold Sans-Serif** characters (`𝗔 𝗕 𝗖 𝗗 ... 𝟬 𝟭 𝟮 𝟯 ...`).

Rules:

- Use Unicode bold ONLY on the hook opener, not on any sentence in the post body.
- For earnings posts, bold only the ticker. The company name in parentheses is plain text, and so is the verdict and everything after it.
  Format: `𝗗𝗔𝗟 (Delta Air Lines) Q1 BEAT. Adjusted EPS ...`
- For macro posts, bold the whole indicator name (no company-name clarifier).
  Format: `𝗙𝗢𝗠𝗖 𝗠𝗜𝗡𝗨𝗧𝗘𝗦 HAWKISH. The March 17-18 vote ...`
- For daily wrap posts, bold the whole date phrase.
  Format: `𝗪𝗘𝗗𝗡𝗘𝗦𝗗𝗔𝗬 𝗔𝗣𝗥𝗜𝗟 𝟴. Dow closed up ...`
- Never use markdown `**text**` in the post body. It will not render on X and will leak asterisks into the published post.
- Use the full legal company name for the earnings clarifier: "Delta Air Lines" not "Delta Airlines", "Constellation Brands" not "Constellation", "Berkshire Hathaway" not "Berkshire".

When creating or editing the `.md` files under `output/<date>/<event>/`, confirm that the post body between `## The post (copy-paste ready)` and the next `---` contains Unicode bold on the hook opener and plain text everywhere else. That way, copying the body pastes directly into X with the bold intact.

## Hard formatting rules (non-negotiable)

The review engine blocks any post that violates these:

- Word count: earnings/macro 200-300, daily 300-500
- Zero em dashes (`—`) or en dashes (`–`). Use commas, periods, colons, semicolons, or parentheses.
- Zero exclamation marks.
- Zero emojis.
- Zero hashtags.
- Zero banned words (full list below).
- Zero banned transition openers at the start of any paragraph.
- Zero hedging phrases (`it seems`, `it appears`, `only time will tell`, `it remains to be seen`).
- Hook (first 280 chars) must contain a number (`$...`, `%`, etc.).
- Earnings posts must reference `EPS` and include an `If you own [TICKER]:` line.
- Daily wraps must contain 5+ content items (paragraphs of 10+ words).
- All posts must contain `cfosilvia.com`.

## Banned word list

Edit in `silvia_auto.py` → `BANNED_WORDS` (around line 648). Current list:

```
additionally, bolstered, comprehensive, crucial, delve, elevate,
empower, enduring, enhance, ensuring, evolving landscape, exemplifies,
facilitate, fostering, furthermore, game-changer, garner, groundbreaking,
holistic, in the realm of, it's worth noting, landscape, leverage,
meticulous, moreover, multifaceted, myriad, navigate, nestled,
paradigm, pivotal, plethora, profound, robust, seamless, showcasing,
spearhead, streamline, synergy, tapestry, testament, transformative,
underscore, utilize, vibrant
```

## Banned transition openers

No paragraph may start with any of these:

```
Furthermore, Moreover, Additionally, In conclusion, Overall,
In summary, To sum up, Firstly, Secondly, Lastly,
In today's, In an era, As we navigate
```

## System prompts

The three prompts live in `silvia_auto.py` and control everything Claude writes:

- `SYSTEM_EARNINGS` — ticker hook, beat/miss verdict, EPS + revenue, 3 numbered items in prose, forward guidance, "If you own" line, CTA.
- `SYSTEM_MACRO` — data name hook, headline number vs estimate, verdict, portfolio impact, market reaction with numbers, what to watch next with date.
- `SYSTEM_DAILY` — date + S&P hook, 5-8 content paragraphs covering earnings/news/econ/Fed/sectors/crypto/commodities/bonds, one-paragraph tomorrow preview.

Every prompt ends with an `IMAGE_CARD_BRIEF` spec so the card renderer gets structured data (TICKER, VERDICT, EPS_ACTUAL, etc.).

When editing a prompt, change both the text and the `IMAGE_CARD_BRIEF` schema if you add/remove card fields. The card template in `generate_card_html()` reads those exact keys.

## Card rendering rules

Cards are 1200x675 PNG, dark background (`#0A0A0A`), with branded `@CFOSilvia` footer bar. Templates are inline HTML in `CARD_HTML_TEMPLATE` and the three branches of `generate_card_html()`.

Color rules:

- Green `#22C55E` for beats, cool prints, up days
- Red `#EF4444` for misses, hot prints, down days
- Gold `#C9A84C` for the footer accent bar
- Neutral grays `#444`, `#555`, `#666`, `#888` for metadata

When adding a new card type:

1. Add the branch in `generate_card_html()`.
2. Match the `IMAGE_CARD_BRIEF` fields your system prompt outputs.
3. Keep the 1200x675 viewport so X doesn't crop.
4. Keep the bottom `.bar` with the `@CFOSilvia` handle for brand consistency.

## X posting rules

- Tweepy v1.1 (`api_v1.media_upload`) is used for the image upload because v2 doesn't support media upload directly.
- Tweepy v2 (`client.create_tweet`) is used for the actual post because v1.1 is deprecated for tweet creation.
- Both auth paths need the same 5 credentials: API key, API secret, access token, access secret, bearer token.
- The account must have **Read and Write** permissions plus **media upload** enabled in the X developer portal.

## Environment variables

All config lives in `.env`. See `.env.example` for the template.

Required:

```bash
ANTHROPIC_API_KEY=sk-ant-...
TWITTER_API_KEY=...
TWITTER_API_SECRET=...
TWITTER_ACCESS_TOKEN=...
TWITTER_ACCESS_SECRET=...
TWITTER_BEARER_TOKEN=...
```

Optional:

```bash
AUTO_POST=false             # true = skip "type POST to publish" confirmation
LOG_DIR=./silvia_logs       # where pipeline.log, cards, and post history go
```

The pipeline loads `.env` itself via `load_env()` — no `python-dotenv` dependency needed.

## Output layout

```
silvia_logs/
  pipeline.log                          # rolling log of every run
  data_<type>_<timestamp>.json          # raw scraped data
  post_<type>_<timestamp>.txt           # final post text
  card_<type>_<timestamp>.png           # 1200x675 image
  review_<type>_<timestamp>.json        # QA checklist result
  post_history.json                     # append-only list of live posts
  temp_card.html                        # last rendered HTML (debug aid)
```

`post_history.json` is the source of truth for what has shipped. Each entry has timestamp, type, ticker, live URL, review score, word count, and file paths.

## Common gotchas

- **Yahoo Finance returns empty fields.** The pipeline falls back to `[MANUAL]` and Claude will write placeholder content. Fix by filling in the data dict before calling `generate_*_post()`.
- **TradingEconomics blocks scrapes intermittently.** The pipeline swallows the error and falls back to `[PASTE from TradingEconomics.com]` in the data dict.
- **Playwright chromium not installed.** `playwright install chromium` (one-time) or re-run `bash setup.sh`.
- **Banned word in a proper noun.** If a scraped news headline contains a banned word (for example a company named "Synergy"), you may need to manually edit the post before confirming. Add the proper noun to the review whitelist if it comes up often.
- **Review passes but the post reads awkward.** The review engine catches format tells, not voice quality. Re-run the generation or tighten the system prompt.
- **Daily wrap fires twice in cron mode.** The check interval in `daily_check()` is 55 seconds with a 60-second tolerance window. If the wrap fires twice in testing, widen the `sleep(55)` or tighten the `abs(...) < 60` window.

## Extending

To add a new post type (example: `sector` for sector rotation snapshots):

1. Add `scrape_sector()` in Part 1. Return a dict with the raw data fields.
2. Add `SYSTEM_SECTOR` in Part 2 with hook rules, body structure, and `IMAGE_CARD_BRIEF` fields.
3. Add `generate_sector_post()` that builds a user prompt from the data dict and calls `call_claude(SYSTEM_SECTOR, ...)`.
4. Add a card branch in `generate_card_html()` that reads the new `IMAGE_CARD_BRIEF` fields.
5. Wire it into `run_pipeline()` and the CLI in `main()`.
6. Update the banned word list if the new type tempts Claude into new jargon.

## When editing this repo

- Keep `silvia_auto.py` as a single file. Do not split into a package unless you have a strong reason. The point of this repo is that one file runs the whole pipeline.
- Keep the six-part structure (scrape, generate, card, review, post, orchestrator). Clearly marked section headers make it easy to navigate.
- When you change the system prompts, run a test generation (`python silvia_auto.py earnings AAPL` with a saved `.env`) before committing.
- When you change the banned word list, update both `BANNED_WORDS` in `review_post()` and the banned list in the `CLAUDE.md` above.
- Never commit `.env`, `silvia_logs/`, or any rendered card PNG. `.gitignore` covers these.
