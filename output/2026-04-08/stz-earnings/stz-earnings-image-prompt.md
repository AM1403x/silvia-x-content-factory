# STZ Earnings Card — ChatGPT / DALL-E Image Prompt

Paste the block below into ChatGPT-4o (with image generation) or DALL-E 3. Aspect ratio 16:9.

---

## Prompt

Create a premium institutional finance social card for X. Pure widescreen 16:9, exactly 1200 by 675 pixels. Pure jet black background, hex #0A0A0A. Absolutely no gradients, no 3D effects, no drop shadows, no stock photography, no illustrations, no logos. Only flat typography and geometric shapes. Minimalist Bloomberg Terminal meets Apple keynote aesthetic. Everything is crisp and editorial.

Top right corner, 28 pixels from top and 48 pixels from right: small sans-serif label "Q4 FY2026 Earnings" in dark muted gray, color #444, size 15pt, font weight 400. SF Pro Display or identical geometric grotesque throughout.

Center of the card, stacked vertically:

Row 1 — the ticker block. The three letters "STZ" in ultra-bold white sans-serif, 120pt, letter-spacing negative 4 pixels, color #FFFFFF, weight 800. Immediately to the right of "STZ" with 24 pixels of spacing, a horizontal pill badge. Pill dimensions roughly 120 by 48 pixels. Pill background rgba(34,197,94,0.15) (translucent green). Pill border 2 pixels solid, color #22C55E (bright emerald green). Pill border radius 6 pixels. Inside the pill, the word "BEAT" in ALL CAPS, color #22C55E, weight 700, size 24pt, letter-spacing 3 pixels, vertically centered.

Row 2 — the data blocks, positioned 44 pixels below the ticker row. Two equal data blocks side by side, separated by a thin vertical divider line (1 pixel wide, 70 pixels tall, color #222). 80 pixels of horizontal gap between blocks.

Left block: header "EPS" in uppercase gray #666, size 16pt, weight 500, letter-spacing 2 pixels, centered. Below the header (10 pixel gap): on the left side "$1.90" in bright emerald green #22C55E, weight 700, size 52pt. Next to it, aligned to baseline, 14 pixels of spacing: "vs $1.71" in darker gray #555, weight 400, size 24pt.

Right block: header "REVENUE" in the same uppercase gray style. Below: "$1.92B" in emerald green #22C55E weight 700 size 52pt, then "vs $1.86B" in dark gray #555 size 24pt next to it.

Row 3 — after-hours line, 28 pixels below the data blocks, centered. Text reads: "After hours: -2.0% on weak guide" where "After hours:" is muted gray #888 at 22pt, "-2.0%" is bright red #EF4444 at 22pt weight 700, and "on weak guide" is muted gray #888 at 22pt weight 400. 8 pixel gaps between each element. Important: the after-hours color is RED even though the main pill is GREEN, because the Q4 numbers beat but the FY27 guide missed and the stock dropped.

Footer bar — absolute bottom of the card, full width, 80 pixels tall. Bar background #111. Top edge of the bar: 2 pixel solid gold border #C9A84C. Inside the bar, three elements:
- Far left, 48 pixels from left edge: "@CFOSilvia" in gold #C9A84C, weight 600, size 15pt, letter-spacing 1.5 pixels
- Horizontally centered in the bar: an up-arrow glyph "↑" in gray #888 size 28pt, then the words "Show more" in white #FFFFFF weight 700 size 28pt, then another up-arrow "↑" in gray #888 size 28pt. 16 pixels of gap between each element. All three vertically centered in the bar.

Typography rules: tight tracking, editorial spacing, plenty of negative black space around every element. Crisp antialiased rendering. No background textures. No JPEG artifacts. Sharp, expensive, institutional feel. Think a Goldman Sachs equity research note if it were designed by Jony Ive.

Output at 1200x675 pixels, PNG-style crispness. Do not add any extra elements, borders, frames, watermarks, timestamps, or decorative flourishes beyond what is described above.

---

## Notes for regeneration

- This card has a rare split color scheme: GREEN pill (beat on current quarter) with RED after-hours (guide cut). Do not let the model normalize to all-green or all-red.
- If the model adds stock chart lines or candlesticks, add: "NO charts, NO graphs, NO candlesticks, NO market data lines. Only the typographic elements described."
- If the model softens the blacks, add: "Background must be pure jet black #0A0A0A, not charcoal or dark gray."
- If "@CFOSilvia" renders as a real Twitter embed, add: "@CFOSilvia is plain typographic text in gold, not a social media card or avatar."
