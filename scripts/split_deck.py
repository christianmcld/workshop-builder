#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Slide splitting — the LAST step before building the deck.

Takes an approved concept deck (full checklists, full timelines, full
frameworks on single slides) and explodes each multi-item slide into a
progressive-reveal sequence: item 1, then 1-2, then 1-2-3...

Usage:
  uv run split_deck.py deck.json            # writes deck.split.json
  uv run split_deck.py deck.json -o out.json

Rules:
- checklist: one slide per pill count (1..N). Speaker notes ride on the
  FIRST slide of the sequence; later slides get "(reveal N/M)".
- timeline: one slide per stage count; `slots` is pinned to the full stage
  count so dots keep their position as they appear.
- framework: bullets reveal one at a time the same way.
- Any slide with "split": false is left whole. Everything else passes through.
- Statements are NOT auto-split — breaking a long statement into 2-3 slides
  is a writing decision made during authoring (see deck-design-system.md).
"""
import argparse
import copy
import json


def reveals(slide, key):
    items = slide.get(key) or []
    if len(items) < 2 or slide.get("split") is False:
        slide.pop("split", None)
        return [slide]
    out = []
    # quadrant graphs reveal from a BARE axes slide (0 items), then one per slide
    start = 0 if slide.get("type") == "quadrant" else 1
    for n in range(start, len(items) + 1):
        s = copy.deepcopy(slide)
        s[key] = items[:n]
        s.pop("split", None)
        if slide.get("type") == "timeline":
            s["slots"] = len(items)
        if n == start:
            if slide.get("notes"):
                s["notes"] = slide["notes"]
        else:
            s["notes"] = f"(reveal {n}/{len(items)})"
        out.append(s)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("deck")
    ap.add_argument("-o", "--out")
    args = ap.parse_args()
    deck = json.load(open(args.deck))

    slides = []
    for s in deck["slides"]:
        key = {"checklist": "pills", "timeline": "stages", "framework": "bullets",
               "quadrant": "items", "numbered": "items"}.get(s.get("type"))
        slides.extend(reveals(s, key) if key else [s])

    before, after = len(deck["slides"]), len(slides)
    deck["slides"] = slides
    out = args.out or args.deck.replace(".json", ".split.json")
    json.dump(deck, open(out, "w"), indent=2)
    print(f"{before} concept slides -> {after} presentation slides -> {out}")


if __name__ == "__main__":
    main()
