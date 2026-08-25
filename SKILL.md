---
name: workshop-builder
description: Turn an expert's knowledge into a live workshop — Why/What/How/Now structure, 150–200 cue-card slides built in the user's chosen slide platform in their brand, plus a "Now" asset and delivery playbook. Use when the user says "build a workshop," "workshop builder," "new lesson/masterclass," or wants to turn any expertise into a live training or YouTube-style lesson.
---

# Workshop Builder

Builds complete live workshops using the Workshop Mastery methodology (Time to Build). The output of every run: a full lesson outline, a branded slide deck of 150–200 cue-card slides, a tangible "Now" asset for attendees, and a one-page delivery checklist.

Core philosophy (never violate these):
- **Slides are cue cards, not a presentation.** Words on screen that spark the speaker's thoughts and keep them on track. One idea per slide.
- **Volume before refinement.** Don't think until there are 150 slides. Generate the full deck plain first; visuals and polish are a second pass.
- **Every slide change is a re-engagement point.** Target a new slide every 10–15 seconds (150–200 slides per 45–60 min).
- **The expert is involved at the beginning (interview) and the end (review). Claude fills the middle.** Never generate a workshop from thin air — extraction first, always.

## Phase 0 — Onboarding (gate; once per user/client)

Before any interview or outline work, the user's environment must exist. This skill ships with **no credentials and no accounts** — every user connects their own.

1. **Choose a workspace directory** for their workshops (e.g. `~/workshops/` or a client folder). Everything below lives there.
2. **Ask which platform they want slides built in:** Google Slides, Figma Slides, Gamma, Canva, or an outline-only handoff (Keynote/PowerPoint). Details per platform: `references/slide-platforms.md`.
3. **Connect their own account for that platform:**
   - *Google Slides:* walk them through creating their own Google Cloud OAuth client and authorizing it — full steps in `references/google-slides-generation.md`. Their credentials stay in their own `~/.config/gcloud/`; this skill never stores, reads back, or transmits them.
   - *Figma / Gamma / Canva:* they connect the matching integration (MCP/connector) on their own account.
   - *Outline-only:* nothing to connect.
4. **Build the brand environment** — check for `{workspace}/brand-tokens.json`; if missing, create it:
   - Gather from their website: logo URL(s), background/text/accent colors, heading + body font families, visual style notes. Prefer any brand assets or guides they already have over scraped guesses.
   - Write `brand-tokens.json` from `templates/brand-tokens.template.json` (includes their `slides_platform` choice). Download the primary logo into `{workspace}/assets/`.
   - Show the tokens for a quick confirm before proceeding.

The brand file is the environment for every workshop this user ever builds. Update it only when the brand changes.

## Phase 1 — Intake Worksheet

Copy `templates/intake-worksheet.md` to `{workspace}/{workshop-slug}/worksheet.md` and fill it with the expert (or accept their rough notes / a worksheet screenshot). Capture:
- Lesson name
- Why bullets (2–4 emotional buy-in angles: personal anecdote, status quo challenge, before/after)
- What checklist (~5–7 things they'll walk away with)
- How chapters (3–5 chapters, up to 7 max) — each with rough notes AND one metaphor, story, or visual
- The Now asset (worksheet, prompt, tool, sheet — the tangible walk-away)

**Naming:** after the worksheet (and again after the interview if a better mechanism emerged), generate 7–10 name candidates across the angles in `references/naming.md`; the expert picks or remixes. The chosen name + one-line promise become the cover slide.

## Phase 2 — Extraction Interview

Follow `references/interview-guide.md`. Interview the expert **one question at a time** to extract everything they know about the topic. They talk, you organize. Benchmark: roughly 8,000–10,000 words of raw expert answers before outlining. Going straight to generation without this produces garbage — the interview is where the expert's real knowledge enters the system.

## Phase 3 — Outline → Cue-Card Slides

Follow `references/why-what-how-now.md`. Map the interview material onto the matrix:

| Section | Slides | Role |
|---|---|---|
| Why | 10–15 | Heart — emotional buy-in, the hook |
| What | 5–10 | Brain — the specific outcome checklist |
| How | 60–80+ | Body — systems, frameworks, processes (3–5 chapters) |
| Now | 5–10 | Action — the immediate implementation step |

Produce `{workspace}/{workshop-slug}/outline.md` (human-readable full lesson outline) and `deck.json` in **concept form** — full checklists, timelines, and frameworks each on one slide (schema: `references/google-slides-generation.md`; layout + style: `references/deck-design-system.md`; start from `templates/deck-style-template.json`). Write speaker riff notes into each slide's `notes`. Get the expert's approval on the concepts before anything else.

**Phase 3.5 — Slide splitting (last step before build, only after concept approval):** run `uv run scripts/split_deck.py deck.json` to explode approved concept slides into progressive-reveal sequences (one new item per slide). Build from the resulting `deck.split.json`.

## Phase 4 — Build Deliverables

1. **Deck:** build on the user's `slides_platform` (paths for every platform: `references/slide-platforms.md`). For Google Slides:
   ```
   uv run scripts/build_deck.py {workshop-slug}/deck.json --brand {workspace}/brand-tokens.json
   ```
   It prints the presentation URL — open it for review. Whatever the platform, `deck.json` is always produced first; it's the platform-neutral source of truth.
2. **Now asset:** build the attendee walk-away (worksheet PDF, a prompt, a sheet — whatever Phase 1 defined).
3. **Delivery checklist:** copy the one-page checklist from `references/delivery-playbook.md` into the workshop folder, personalized (their opening line, their close plan).

## Output Structure

```
{workspace}/
├── brand-tokens.json          <- Phase 0, shared across all workshops
├── assets/                    <- logos etc.
└── {workshop-slug}/
    ├── worksheet.md           <- Phase 1
    ├── interview.md           <- Phase 2 raw extraction
    ├── outline.md             <- Phase 3
    ├── deck.json              <- Phase 3
    ├── deck-url.txt           <- Phase 4 (deck link)
    └── now-asset/             <- Phase 4
```

## Hard Rules

- Never skip Phase 0 or Phase 2. Onboarding and brand before interview; interview before outline.
- **Never store user credentials inside this skill, its repo, or the workspace.** Platform credentials live in the user's own system config (e.g. `~/.config/gcloud/`); brand-tokens.json holds brand data only.
- First deck pass is text-only cue cards (brand colors/fonts applied, no custom visuals). Visual slides get flagged `"type": "visual"` in deck.json as placeholders for the second pass.
- Deliverables get opened on screen after generating.
