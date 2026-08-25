# Deck Design System (learned from the TTB 3.0 Workshop Mastery deck)

The layout language `build_deck.py` v2 renders. Derived by studying Tom Noske's actual 118-slide Workshop Mastery deck; every rule below earned its place in a live rebuild.

## Persistent chrome (every slide)

- **Header wordmark** top-center: small, letterspaced caps in the body font (letterspace manually — the Slides API has no tracking control: `"F I E L D W O R K"`). From `chrome.header_wordmark` in brand-tokens.
- **Signature footer** bottom-center: the speaker's name in the handwritten font (`chrome.footer_signature`). This is the "tom noske" script footer pattern — it makes 200 plain slides feel like one designed object.
- Chrome inverts color automatically on dark slides.

## Slide types

| type | Layout | When |
|---|---|---|
| `cover` / `closing` | Dark background, display-font title centered, accent dot above, sub in muted | First/last slide |
| `section` | Huge display type, centered, optional sub ("Chapter 1 of 3") | Why/What/How/Now + chapter dividers |
| `statement` | Body font bold, centered, `sub` stacked lighter below | The default cue card |
| `quote` | Soft-accent rounded card, display italic, ink text | Punchlines |
| `list` | White rounded card, left-aligned lines | Simple enumerations |
| `checklist` | Big title left third + rounded pill cards right, each with a plain accent dot (no glyph) | Outcome lists, "by the end of today" |
| `framework` | Dark slide, dark-surface rounded card: title / bullets / bold kicker (`sub`) | Named systems and models |
| `timeline` | Dark slide: arrow line, stage dots, chip labels below, notes above; optional `"accent": true` on the payoff stage | Journeys, compounding, phased concepts |
| `visual` | Dark slide, muted `[ VISUAL: … ]` placeholder | Second-pass artwork slots |
| `numbered` | Dark: dual-tone title + mono rows with muted `01 02 03` numerals and `→` flows | Funnel lists, option menus, step sequences |
| `story` | Dark: muted mono kicker, bold left headline, mono muted paragraphs below | Narrative beats inside the Why/How |
| `impact` | Dark: bold centered statement over a giant faint watermark cropped in the top-right corner (`chrome.watermark`, `colors.watermark_dark` — slightly lighter than the background) | Hard-hitting statements; alternative to `quote` |
| `section` + `number` | Dark chapter divider: giant faint numeral left, dash mono kicker, big bold title low-left, corner watermark | Numbered chapter opens |
| `quadrant` | Light cross-graph: double-arrow axes with muted end labels (`axes: {top,bottom,left,right}`), items placed per quadrant (`q: tl/tr/bl/br`, optional explicit `x`/`y` fractions) | 2×2 concept maps |

Dual-tone type (any `text` field): `{{phrase}}` renders in the display serif, italic, in the secondary tone (ink_faint/dark_muted) — the "Time to Build *recommended funnels*" / "In 2024 *I had a winner*" pattern. Pair one bold sans phrase with one serif italic phrase.

Statement extras (use sparingly, ~1 per 10 slides):
- `"kicker": "— The Setup"` — mono-font caps eyebrow in accent above the statement (the "— IN 2024" pattern).
- `[[accent phrase]]` inside `text` — on dark slides the span renders in the accent color; on light slides it renders as ink text on an accent HIGHLIGHT (text background). Accent-colored text never appears on light backgrounds. Kickers get the same treatment.

## Copy voice (how the sentences are written)

Distilled from studying full Time to Build decks; blend with the expert's own voice profile before writing final copy.

- **The three-beat slide:** mono kicker sets up ("— THANKFULLY") → bold line delivers ("You guys can learn from my mistakes") → mono sub lands the twist ("So this will not happen to you."). The sub COMPLETES or SUBVERTS the headline — never repeats it.
- **Binary stakes:** small setup line, big payoff line, emotional half in serif italic ("You either add, track and optimize those steps / Or you don't {{have a business}}.").
- **False beliefs go in quotation marks** and get answered in the sub ("\"I need 10x ROAS to scale.\" / You don't.").
- **Stories are told in first-person slide titles** ("In 2024 I had a winner", "Here was my fancy new funnel") — the deck IS the narration.
- One thought per slide; build a sentence across 2–3 slides for emphasis. Short words. Specific numbers over adjectives. Speak TO the room ("you"), not about a topic.
- Riff prompts, timing cues, and the stories behind each line live in speaker notes, never on the slide.

## The three registers (light / dark / tone)

Professional decks run THREE color registers, not two (the Time to Build pattern: cream, near-black, and deep green with gold accents):

- **light** — paper background. The teaching register: statements, lists, checklists, quotes.
- **dark** — near-black. The drama register: cover, closing, impact, chapters, stories.
- **tone** — the brand's deep mid-color (`tone_*` tokens: a dark, desaturated relative of the accent — deep moss for a lime brand, deep green for Tom). The structure register: `numbered` defaults here; timelines and frameworks sit well here too. Serif-italic `{{...}}` spans render in `tone_serif` (the "gold" of the brand — a soft warm derivative of the accent).

Set per slide with `"mode": "light" | "dark" | "tone"`. Cycling registers between sections is itself a re-engagement device.

## Light/dark rhythm

Light slides teach (statements, lists, checklists, quotes). Dark slides bookend and carry the visual weight: cover, closing, frameworks, timelines, and all `visual` placeholders. Mixing modes is deliberate — a dark slide after a light run is itself a re-engagement.

## Slide splitting (sub-skill — the LAST step)

Author and review the deck in **concept form**: the full checklist, full timeline, full framework each on ONE slide, so the client can approve whole ideas. Only after concepts are approved, run:

```bash
uv run scripts/split_deck.py {workshop}/deck.json   # -> deck.split.json
```

It explodes every multi-item `checklist`/`timeline`/`framework`/`quadrant` into a progressive-reveal sequence (quadrants start from a BARE axes slide, then place one item per slide) (item 1, then 1–2, then 1–2–3 — the "By the end of today you'll have" pattern), keeps notes on the first slide of each run, and pins timeline dot positions. Mark a slide `"split": false` to keep it whole. Long **statements** are split during authoring, not by the script — breaking one sentence across 2–3 slides is a writing decision. Build the deck from the `.split.json`.

## Rules that came from real failures

1. **Singular text blocks are always center-aligned, centered on the slide.** Left-aligned copy exists ONLY in two-column layouts (checklist title + pills, framework cards, list cards). Came from live design review of the first template deck. Same review: pill dots carry no glyph, and the signature footer uses the speaker's proper-case name.

1. **Accent colors are punctuation, never text on light backgrounds.** v1 rendered quotes in accent color on paper — unreadable. Quotes are now ink-on-soft-accent-card.
2. **Progressive reveal drives the 10–15 second rhythm.** A checklist of 5 items is FIVE slides — same layout, one new pill each. The generator duplicates the slide adding one pill at a time; the renderer just draws what it's given.
3. **Fixed-geometry cards overflow.** Framework bullets that wrap collided with the kicker. Keep framework bullets ≤ 4, each ≤ 8 words; the kicker is anchored low with dead air between — dead air is on-style.
4. **Length budgets prevent ugly wraps:** cover/section `sub` ≤ 60 chars; statement `text` ≤ 60 chars (≈2 lines at 32pt); pills ≤ 55 chars.
5. **Dark slides bookend, light slides teach.** Cover, closing, and frameworks are dark; everything else is paper. That contrast is the deck's pulse.
6. **Fonts must be Google Fonts family names** — the Slides API resolves by name only (no weights beyond bold, no tracking).

## Brand tokens the renderer expects

```json
"chrome": { "header_wordmark": "B R A N D", "footer_signature": "founder name" },
"colors": {
  "background": "...", "surface": "...", "border": "...",
  "text": "...", "muted": "...",
  "accent": "...", "accent_text": "...", "accent_soft": "...",
  "dark_background": "...", "dark_surface": "...", "dark_text": "...", "dark_muted": "..."
},
"fonts": { "heading": "display", "body": "workhorse", "handwritten": "signature" }
```

Missing dark/surface values fall back to sensible derivations of the light palette, so a minimal brand file still renders.

## QA loop (do this every build)

1. Build; the script prints the deck URL.
2. Pull rendered thumbnails headlessly via `GET /presentations/{id}/pages/{slideId}/thumbnail` (slide ids are `s0000`, `s0001`, …) and actually look at them — one per slide type minimum.
3. Check: chrome present, contrast, no text overflow/collision, fonts resolved, notes populated.
4. Fix the renderer or the copy, rebuild (each build is a fresh deck; delete rejects).
