# Output Formats

Asked once during Phase 0 onboarding, stored as `slides_platform` in the user's brand-tokens.json. `deck.json` is ALWAYS generated first as the platform-neutral source of truth; the format only changes the final build step. Every format uses the **user's own accounts and their own brand tokens** — the skill ships with no credentials and no default brand.

## The two outputs

### `google-slides`

```bash
uv run scripts/build_deck.py deck.split.json --brand brand-tokens.json            # first build
uv run scripts/build_deck.py deck.split.json --brand brand-tokens.json --into ID  # every edit after
```

Full deck via the Slides API into the user's own Google Drive: brand colors/fonts applied, speaker notes populated, in-place editing that preserves comments and `"locked"` hand-built slides. Requires the user's one-time OAuth setup (`google-slides-generation.md`). Choose this when the user wants to hand-polish slides in the Google Slides editor and collect comments there.

### `html` (GitHub Pages)

```bash
uv run scripts/build_html.py deck.split.json --brand brand-tokens.json -o site/index.html
./scripts/publish_pages.sh site/ workshop-name    # their gh CLI, their repo, their Pages URL
```

One self-contained index.html: every layout in the design system, brand tokens as CSS variables, Google Fonts, keyboard/click navigation, speaker notes on "n", fullscreen on "f", deep links (#12). Publishes to the user's own GitHub Pages (https://THEM.github.io/workshop-name/); re-run the two commands to update. No Google account anywhere. Choose this when the user wants zero OAuth setup, instant scriptable edits (deck.json is the only thing you ever change — rebuild takes a second), or a shareable URL. Hand-edits belong in deck.json, not the HTML: the file is a build artifact.

## Other tools (manual paths, no automation)

Figma, Gamma, Canva, Keynote, PowerPoint: deliver `outline.md` plus the concept `deck.json` and let the user build in their tool of choice, or drive a connected integration (MCP) on their own account if one exists. These are accommodations, not first-class outputs.

## Changing formats

Edit `slides_platform` in brand-tokens.json. Because deck.json is platform-neutral, any past workshop rebuilds on the other output without redoing Phases 1–3.
