# Extraction Interview Guide

The expert is involved at the beginning and the end; Claude fills the middle. This interview IS the beginning — it's where the expert's real knowledge enters the system. Skipping it produces generic garbage ("Hey Claude, make me a lesson on X" = trash).

## Setup

- Load the user's brand/context first: brand-tokens.json, plus any master brand brief, audience/avatar, or tone-of-voice files they have.
- Have the Phase 1 worksheet in front of you — it's the map of what to extract.
- Tell the expert: "I'll interview you one question at a time. Answer by voice dictation if you can (longer, rawer answers are better). I'll ask for context when I need it — don't pre-explain."

## Rules

1. **One question at a time.** Never a battery of questions. Wait for the answer, then decide the next question from what they said.
2. **They talk, you organize.** Don't teach back, don't summarize after every answer, don't editorialize. Bank the material.
3. **Chase stories and metaphors hard.** Every How chapter needs at least one story, metaphor, or visual. If an answer is pure mechanics, follow up: "What's a moment you saw this play out?" / "What do you compare this to when you explain it to a beginner?"
4. **Extract the numbers.** Specifics make slides ("$200 Cam Link," "1,250 slides in 90 minutes," "20 minutes early"). Vague claims don't.
5. **Target: 8,000–10,000 words of raw answers** before you outline. Roughly 60–90 minutes of dictated talking.

## Question Arc (adapt, don't recite)

1. **Mindset/reframe:** "What do people fundamentally get wrong about {topic} before you teach them?"
2. **The Why material:** "Tell me about a moment that made you realize {topic} mattered." / "What happens to people who never learn this?"
3. **Per chapter (from the worksheet), loop:**
   - "Walk me through {chapter} start to finish, like I'm a smart beginner."
   - "Where do people screw this up?"
   - "Story or example of this working?"
   - "If they remember one sentence from this chapter, what is it?"
4. **The Now:** "The lesson ends. What's the very first thing they should do tonight? What would you hand them to make that easy?"
5. **Sweep:** "What did I not ask about that you'd hate to leave out?"

## Output

Write the organized raw material to `{workshop-slug}/interview.md`, grouped by Why/What/How-chapter/Now, with stories and metaphors tagged inline (`**STORY:**`, `**METAPHOR:**`, `**VISUAL:**`, `**NUMBER:**`). This file is the sole source for Phase 3 — the outline must not contain claims that aren't in it.
