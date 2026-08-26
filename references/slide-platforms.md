# Slide Platforms

Asked once during Phase 0 onboarding, stored as `slides_platform` in the user's brand-tokens.json. The Workshop Mastery rule: use whatever tool works for you — the workflow (outline → dot points → slides) is the only prescription. So `deck.json` is ALWAYS generated first as the platform-neutral source of truth; the platform only changes the final build step.

Every platform requires the **user's own account** — this skill ships with no credentials and connects to nothing on its own.

## `google-slides`

`uv run scripts/build_deck.py deck.json --brand brand-tokens.json` → full deck via the Slides API into the user's own Google Drive, brand colors/fonts applied, speaker notes populated. Requires the user's one-time OAuth setup: `google-slides-generation.md`. The most automated path.

## `figma`

Requires the user's Figma account with a Figma integration (MCP) connected to their agent. Create a Figma Slides file; generate slides from deck.json applying brand tokens (if a Figma skill like `/figma-use` is available, read it first). Best when the user wants to visually polish decks in Figma afterward. Slowest path for 150–200 slides — batch the work.

## `gamma`

Requires the user's Gamma account with the Gamma integration (MCP) connected. Feed it the deck.json content section by section with explicit instructions: cue-card style, one idea per card, brand colors/fonts from brand-tokens. Fastest path, least brand fidelity — warn the user that Gamma's AI restyles things, and that edits happen in Gamma's editor (the API cannot edit existing gammas).

## `canva`

Requires the user's Canva account with the Canva integration (MCP) connected. Apply brand via their Canva Brand Kit if they have one, otherwise pass brand-tokens colors/fonts in the generation instructions. Good for users who already live in Canva.

## `html` (GitHub Pages)

No Google account needed. `uv run scripts/build_html.py deck.split.json --brand brand-tokens.json -o site/index.html` renders the deck as ONE self-contained HTML slideshow: every layout from the design system, brand tokens as CSS variables, Google Fonts, keyboard/click navigation, speaker notes on "n", fullscreen on "f", deep links (#12).

Hosting is the USER'S OWN GitHub: with their `gh` CLI authenticated, `scripts/publish_pages.sh site/ workshop-name` creates a repo under their account, pushes, enables GitHub Pages, and prints their live URL (https://THEM.github.io/workshop-name/). Re-run after rebuilds to update. Their account, their repo, their page. Presenting = open the URL and hit "f"; it also works from the raw file with no hosting at all.

## `outline-only`

For Keynote/PowerPoint users or anyone who builds slides by hand. Deliver `outline.md` plus a `deck-cards.md` export: one heading per slide in order, notes as blockquotes under each. They paste/build at their own pace — this is literally the original manual workflow.

## Changing platforms

Edit `slides_platform` in brand-tokens.json (and connect the new platform's account). Because deck.json is platform-neutral, any past workshop can be rebuilt on a new platform without redoing Phases 1–3.
