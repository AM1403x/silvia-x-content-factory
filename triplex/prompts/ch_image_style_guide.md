# @CFOSilvia Image Prompt Style Guide

Every @CFOSilvia post ships with a scene-based image prompt. The actual visual style comes from a reference image you attach to ChatGPT-4o (or DALL-E 3 / Midjourney) alongside the prompt — the model matches the reference for style, and the prompt only describes the scene content.

## Workflow

1. Pick one prior @CFOSilvia image as the visual reference (same character, same aesthetic).
2. Open ChatGPT-4o image generation.
3. Attach the reference image.
4. Paste the scene prompt from the post's `-image-prompt.md` file.
5. Generate.

Do not include style adjectives (watercolor, ink, comic, hand-drawn, etc.) in the prompt — the attached reference carries all of that.

## What every scene prompt should describe

1. **The character** — the recurring young adult man, messy short brown hair, clean-shaven, expressive eyebrows, white long-sleeve dress shirt (sleeves sometimes rolled), tie in a mood-appropriate color, dark trousers.
2. **The pose and expression** — body language carries the story. Celebration, conflicted, skeptical, euphoric, tired, etc. Face does most of the work.
3. **The setting** — wooden office desk, black office chair, computer monitor with a chart, ceramic coffee mug. Occasionally a wall element (framed painting, window) or floor prop.
4. **The story-specific props** — the one or two objects that tell the viewer what happened today. Examples: tipped oil barrel (oil crash), Modelo beer bottle (beverage beat), FOMC document (Fed minutes), paper airplane (airline earnings), round table with chairs knocked over (FOMC dissent), peace dove window (geopolitical resolution), chip wafer (semiconductor story).
5. **The composition** — character centered or right-of-center, monitor on the left third, background wall elements in the corners, props on the desk or floor for visual balance.
6. **The mood line** — one sentence at the end telling the viewer what they should feel.
7. **Hard rules** — no corporate logos (monitor shows only the plain ticker), no text on the image except what is explicitly required, no photographic realism, character must match the reference.

## Tie color language (per post mood)

| Mood | Tie color |
|---|---|
| Pure celebration / rally | Bright emerald green |
| Cautious optimism | Navy blue |
| Mixed feelings / conflict | Deep burgundy or gold |
| Serious / Fed / policy | Dark gray or charcoal |
| Warning / down day | Red-brown |
| Neutral / daily wrap (green day) | Bright green |
| Neutral / daily wrap (red day) | Red-brown |

## Prop vocabulary

- Monitor with chart — the main context anchor, always present
- Coffee mug with steam — baseline prop
- Paper airplane — airline earnings
- Beer bottle with "MODELO" or similar label — beverage / Constellation
- Wine glass (upright or spilled) — wine sector / STZ trouble
- Oil barrel (upright or tipped) — energy / oil moves
- FOMC document / Fed minutes — central bank events
- Wall painting of Eccles Building — Fed references
- Round table with chairs (some knocked over) — FOMC dissents
- Magnifying glass — research / earnings deep dive
- Wall calendar — date-anchored posts
- Stock ticker tape — market-wide stories
- Peace dove / olive branch in a window — geopolitical resolution
- Papers flying around — sudden news / rally energy
- Airplane ticket stub, passport — travel sector
- Semiconductor chip — chip stock posts
- Gold bar — precious metals posts
- Bitcoin coin — crypto posts

## Composition rules

1. Character centered-right in the frame, facing slightly toward the viewer.
2. Monitor with chart on the left third as the context anchor.
3. Floor / desk props at the bottom.
4. Background wall elements (window, portrait) in upper corners.
5. The story-specific prop gets its own visual weight — do not clutter.

## Hard rules (copy into every prompt)

```
- No photographic realism
- No corporate logos except a generic monitor UI (no real Delta logo,
  no real Modelo logo, no real Fed seal)
- No text on the image except what is explicitly required (chart numbers,
  calendar date, document label)
- No stock photography elements
- Character must match the attached reference image
```

## How to use this guide

When generating a new post image prompt:

1. Attach a reference image from a prior @CFOSilvia post.
2. Describe the recurring character.
3. Describe the specific scene, mood, and props relevant to this post.
4. Pick the tie color from the mood table.
5. Pick 2-4 props from the vocabulary that match the story.
6. End with the hard rules block.

See the four image prompt files in `output/2026-04-08/*/` for examples of
fully-formed post-specific scene prompts.
