# Google Slides Deck Generation

`scripts/build_deck.py` creates the presentation directly in Google Slides via the Slides REST API, authenticated with **the user's own Google credentials**. The deck lands in their own Google Drive. This skill never stores, reads back, or transmits those credentials — they live in the user's `~/.config/gcloud/` and are used only by Google's own tooling.

## One-Time Setup (per user, per machine)

Prerequisites: [gcloud CLI](https://cloud.google.com/sdk/docs/install) and [uv](https://docs.astral.sh/uv/) installed, and a Google account.

**Important:** plain `gcloud auth application-default login --scopes=...` FAILS with "Google blocked this access" — Google blocks gcloud's shared OAuth app from requesting sensitive scopes (Drive/Slides). The user must create their own OAuth client (~2 minutes, free):

1. In the [Google Cloud Console](https://console.cloud.google.com) (their account, any project — create one if needed):
   - **APIs & Services → OAuth consent screen**: choose **Internal** if they're on Google Workspace; otherwise **External** and add themselves as a test user (no verification needed either way).
   - **Credentials → Create OAuth client → Desktop app**, name it (e.g. `workshop-builder`), download the JSON to `~/.config/gcloud/workshop-builder-oauth.json` and `chmod 600` it.
2. Enable the APIs and authorize (they run these themselves — it opens a browser consent screen showing their own app's name):
   ```bash
   gcloud services enable slides.googleapis.com drive.googleapis.com
   gcloud auth application-default login \
     --client-id-file="$HOME/.config/gcloud/workshop-builder-oauth.json" \
     --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/presentations,https://www.googleapis.com/auth/drive
   ```

If a run fails with 403/insufficient scopes or "app blocked," this setup is what's missing.

## deck.json Schema

```json
{
  "title": "Workshop Title",
  "slides": [
    { "type": "cover",     "text": "WORKSHOP MASTERY", "sub": "How to teach live", "notes": "Opening line: All right team, welcome to..." },
    { "type": "section",   "text": "WHY" },
    { "type": "statement", "text": "A great teacher with average material beats an average teacher with great material.", "notes": "Origin story here — riff 2 min" },
    { "type": "list",      "text": "1. The outline\n2. The slides\n3. The tech\n4. The delivery\n5. The recording" },
    { "type": "quote",     "text": "\"Don't think until you've got 150 slides.\"" },
    { "type": "visual",    "text": "Why/What/How/Now matrix — 4 quadrants" },
    { "type": "closing",   "text": "Thank you", "sub": "Grab the worksheet below" }
  ]
}
```

Slide types → styling (all colors/fonts from brand-tokens.json):

| type | Use | Look |
|---|---|---|
| `cover` / `closing` | First/last slide | Accent background, big heading font, logo if URL is public |
| `section` | Why/What/How/Now + chapter dividers | Accent background |
| `statement` | The default cue card — one idea | Brand background, large centered heading text |
| `list` | Checklists, steps | Left-aligned body font |
| `quote` | Punchline lines | Accent-colored text |
| `visual` | Placeholder for the second visual pass | Muted `[ VISUAL: … ]` marker |

Any type can carry a smaller second line via the `sub` field. `notes` goes into speaker notes — put the riff prompts, stories, and timing cues there. The audience sees the cue card; the speaker sees the riff.

## Generation Rules

- One idea per slide. If a slide's text exceeds ~14 words (statements) it's two slides.
- Build a sentence progressively across 2–3 slides for emphasis rather than cramming.
- Every `section` divider is followed by a re-engage beat in the notes ("thumbs up check").
- `visual` placeholders: the first pass NEVER blocks on artwork. The second pass replaces them in the Google Slides editor.
- Target the slide budget in `why-what-how-now.md` (~150–200 total).

## Run + Verify

```bash
uv run scripts/build_deck.py {workshop}/deck.json --brand {workspace}/brand-tokens.json
```

Prints `N slides -> https://docs.google.com/presentation/d/...`. Save the URL to `{workshop}/deck-url.txt` and open it in the browser so the user sees it immediately. Spot-check: brand colors on dividers, fonts applied (must be Google Fonts family names), notes present, slide count matches the budget.

Limits worth knowing: batchUpdate is chunked at 100 requests (a slide ≈ 7–9 requests, so ~12 slides per chunk); 429/5xx get retried with backoff; a 200-slide deck builds in under a minute.
