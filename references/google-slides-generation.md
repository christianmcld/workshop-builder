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

Slide types: `cover`, `closing`, `section`, `statement`, `quote`, `list`, `checklist` (with a `"pills": [...]` array), `framework` (with `"bullets": [...]` and a `sub` kicker), `visual`. Layout, styling, and the length budgets for each are defined in `deck-design-system.md` — read it before generating any deck.json.

Any type can carry a smaller second line via the `sub` field. `notes` goes into speaker notes — put the riff prompts, stories, and timing cues there. The audience sees the cue card; the speaker sees the riff. Checklist example:

```json
{ "type": "checklist", "text": "By the end of\ntoday you'll have.",
  "pills": ["A repeatable lesson framework", "A full cue-card deck"] }
```

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

## Comment-Driven Revision Loop

The expert can leave comments directly on deck slides in Google Slides; read them with the Drive API (already in scope):

```
GET https://www.googleapis.com/drive/v3/files/{presentationId}/comments
    ?fields=comments(id,content,anchor,resolved,author(displayName),quotedFileContent,replies(content))&pageSize=100
```

- Map each comment to its slide via `anchor` (slide objectIds are deterministic: `s0000`, `s0001`, …) and `quotedFileContent` (the text they highlighted). If both are ambiguous, the slide's content usually disambiguates.
- Apply the requested change to the source `deck.json` FIRST (it stays the source of truth), then either patch the affected slides in place (`deleteObject` + re-emit that slide's requests at the same index) or rebuild fresh if changes are broad. Note a rebuild is a new file — comments live on the old one, so prefer in-place patching when comment threads matter.
- Close the loop in the thread: `POST .../comments/{id}/replies` with what changed, and mark `resolved` — the expert sees exactly what happened to each note.
- Skip comments already `resolved: true`.
