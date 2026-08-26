# Workshop Builder

A Claude Code skill that turns an expert's knowledge into a complete live workshop, using the Workshop Mastery methodology (Time to Build): **Why / What / How / Now** structure, 150–200 cue-card slides per 45–60 minute lesson, a tangible "Now" asset for attendees, and a delivery playbook.

## What it produces

- A full lesson outline extracted from a one-question-at-a-time expert interview
- A branded slide deck in **your** brand and **your** choice of two outputs: Google Slides (built and edited via API in your own Drive) or a self-contained HTML presentation hosted on your own GitHub Pages
- The attendee walk-away asset (worksheet, prompt, tool)
- A one-page delivery checklist (opening line, Q&A management, close countdown, recording redundancy)

## Bring your own accounts and your own brand

This skill ships with **no credentials and no default brand** — onboarding captures each user's colors, fonts, and voice into their own `brand-tokens.json`, and every deck renders in that brand. During onboarding it asks which slide platform you want and walks you through connecting your own account (for Google Slides: your own OAuth client in your own Google Cloud project — see [references/google-slides-generation.md](references/google-slides-generation.md)). Credentials never live in this repo or your workshop workspace.

## Install

Copy (or clone) this directory into your skills location, e.g.:

```bash
git clone https://github.com/christianmcld/workshop-builder ~/.claude/skills/workshop-builder
```

Then ask Claude to "build a workshop" — it will run onboarding the first time.

## Layout

```
SKILL.md                                   the skill entry point (5 phases)
references/why-what-how-now.md             the lesson structure + slide philosophy
references/naming.md                       workshop naming: 6 angles + rules
references/interview-guide.md              extraction interview protocol
references/slide-platforms.md              per-platform build paths
references/google-slides-generation.md     Slides API builder: setup, schema, rules
references/deck-design-system.md           the rendered layout system + hard-won rules
references/delivery-playbook.md            open/engage/Q&A/close + recording redundancy
templates/brand-tokens.template.json       per-user brand environment file
templates/intake-worksheet.md              the pre-interview worksheet
templates/deck-style-template.json         one slide of every pattern (the seed deck)
scripts/build_deck.py                      Google Slides deck builder (uv run)
scripts/split_deck.py                      slide splitting: concepts -> progressive reveals
scripts/build_html.py                      HTML slideshow builder (GitHub Pages ready)
scripts/publish_pages.sh                   publish the HTML deck to the user's own GitHub Pages
```

## Credits

Methodology from Tom Noske's Workshop Mastery lesson (Time to Build). Skill packaging by Christian McLeod.
