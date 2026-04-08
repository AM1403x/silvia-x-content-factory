# Calvin & Hobbes Image Style Guide for @CFOSilvia

The @CFOSilvia X account uses a consistent Bill Watterson / Calvin and Hobbes inspired illustration style for every post image. Every image follows this base spec. Individual posts only change the scene, props, and mood.

## Base style spec (always include in every prompt)

```
Illustrate in the style of Bill Watterson's Calvin and Hobbes. Hand-drawn ink
outlines with visible pen strokes, soft watercolor fills with slight edge
bleed, off-white cream paper background with light watercolor wash texture.
Flat watercolor coloring with minimal shading, just enough to give volume.
No photographic realism, no digital gradients, no 3D effects, no drop
shadows, no corporate logos except a generic monitor UI.

Landscape aspect ratio, roughly 3:2 or 16:10. Paper-like warmth throughout.
Think classic Sunday comic page illustration, not modern vector art.
```

## Recurring character (always the same person)

```
Central character: a young adult man in his late 20s to early 30s. Messy
short brown hair, slightly unkempt. Clean-shaven, expressive eyebrows,
animated face. Wears a white long-sleeve dress shirt (often with sleeves
rolled to mid-forearm) and a tie. The tie color changes with the mood
of each post (see per-post guidance below). Dark trousers, brown belt.
Classic office worker / analyst silhouette.

The character's emotion is the whole story. Face and body language carry
the narrative, props carry the context.
```

## Recurring setting

```
Office environment: wooden desk, black office chair, computer monitor
showing a chart (green up arrow, red down arrow, or both), ceramic coffee
mug, occasional sheets of paper on or around the desk. The monitor chart
is always the strongest color anchor in the frame. Cream paper background
dominates.
```

## Color palette

- White / cream background
- Warm brown wood (desk, frames)
- White shirt
- Mood-based tie color (changes per post)
- Messy brown hair
- Green #22C55E for up moves on the monitor
- Red #EF4444 for down moves on the monitor
- Muted earth tones for props (coffee, books, oil barrels)
- Occasional bright accent (orange sunrise, green grass) for outdoor references

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

## Prop vocabulary (use relevant ones per post)

- Monitor with chart — the main context anchor, always present
- Coffee mug with steam — baseline prop
- Paper airplane — airline earnings
- Beer bottle with "MODELO" or similar label — beverage / Constellation
- Wine glass (upright or spilled) — wine sector / STZ trouble
- Oil barrel (upright or tipped) — energy / oil moves
- FOMC document / Fed minutes — central bank events
- Wall portrait of Eccles Building — Fed references
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
5. Paper background wash fills negative space.
6. Visible ink outlines on everything — do not smooth into vector.

## Hard rules (copy into every prompt)

```
- No photographic realism
- No digital gradients, no drop shadows, no 3D rendering
- No corporate logos except a generic monitor UI (no real Delta logo,
  no real Modelo logo, no real Fed seal)
- No text on the image except what is explicitly required (chart numbers,
  calendar date, document label)
- No stock photography elements
- No vector art look — must feel hand-drawn with watercolor
- Character consistency: same young adult man in every post
```

## How to use this guide

When generating a new post image prompt:

1. Start with the base style spec block.
2. Add the recurring character description.
3. Describe the specific scene, mood, and props relevant to this post.
4. Pick the tie color from the mood table.
5. Pick 2-4 props from the vocabulary that match the story.
6. End with the hard rules block.

See the four image prompt files in `output/2026-04-08/*/` for examples of
fully-formed post-specific prompts following this guide.
