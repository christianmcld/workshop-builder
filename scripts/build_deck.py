#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""Build a cue-card workshop deck in Google Slides from deck.json + brand-tokens.json.

Usage:
  uv run build_deck.py path/to/deck.json --brand path/to/brand-tokens.json

Auth: uses gcloud Application Default Credentials with Slides/Drive scopes.
NOTE: this requires a custom OAuth client (Google blocks gcloud's shared client
from sensitive scopes) — full setup in references/google-slides-generation.md.
"""
import argparse
import json
import subprocess
import sys
import time

import requests

SLIDES = "https://slides.googleapis.com/v1/presentations"

# 16:9 page in EMU (1 inch = 914400 EMU; page = 10in x 5.625in)
PAGE_W, PAGE_H = 9144000, 5143500

STYLES = {
    #             font_role, size_pt, bold, bg_role,     text_role,    align
    "cover":     ("heading", 48, True,  "accent",     "accent_text", "CENTER"),
    "section":   ("heading", 44, True,  "accent",     "accent_text", "CENTER"),
    "statement": ("heading", 34, True,  "background", "text",        "CENTER"),
    "sub":       ("body",    24, False, "background", "text",        "CENTER"),
    "list":      ("body",    22, False, "background", "text",        "START"),
    "quote":     ("heading", 30, True,  "background", "accent",      "CENTER"),
    "visual":    ("body",    20, False, "background", "muted",       "CENTER"),
    "closing":   ("heading", 40, True,  "accent",     "accent_text", "CENTER"),
}


def token():
    for cmd in (
        ["gcloud", "auth", "application-default", "print-access-token"],
        ["gcloud", "auth", "print-access-token"],
    ):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip()
        except subprocess.CalledProcessError:
            continue
    sys.exit("No gcloud credentials. Run the auth command in this script's docstring.")


def hex_rgb(h):
    h = h.lstrip("#")
    return {"red": int(h[0:2], 16) / 255, "green": int(h[2:4], 16) / 255, "blue": int(h[4:6], 16) / 255}


def slide_requests(i, slide, brand):
    """Requests to create one styled cue-card slide."""
    sid, tid = f"s{i:04d}", f"s{i:04d}t"
    stype = slide.get("type", "statement")
    font_role, size, bold, bg_role, text_role, align = STYLES.get(stype, STYLES["statement"])
    colors, fonts = brand["colors"], brand["fonts"]
    text = slide.get("text", "")
    if slide.get("sub"):
        text += "\n" + slide["sub"]
    if stype == "visual":
        text = "[ VISUAL: " + (text or "diagram") + " ]"
    if not text:
        text = " "

    # centered text box with 7% margins
    mx, my = int(PAGE_W * 0.07), int(PAGE_H * 0.12)
    reqs = [
        {"createSlide": {"objectId": sid, "insertionIndex": i,
                         "slideLayoutReference": {"predefinedLayout": "BLANK"}}},
        {"updatePageProperties": {
            "objectId": sid,
            "pageProperties": {"pageBackgroundFill": {"solidFill": {"color": {"rgbColor": hex_rgb(colors[bg_role])}}}},
            "fields": "pageBackgroundFill.solidFill.color"}},
        {"createShape": {"objectId": tid, "shapeType": "TEXT_BOX",
                         "elementProperties": {
                             "pageObjectId": sid,
                             "size": {"width": {"magnitude": PAGE_W - 2 * mx, "unit": "EMU"},
                                      "height": {"magnitude": PAGE_H - 2 * my, "unit": "EMU"}},
                             "transform": {"scaleX": 1, "scaleY": 1, "translateX": mx, "translateY": my, "unit": "EMU"}}}},
        {"insertText": {"objectId": tid, "text": text}},
        {"updateShapeProperties": {
            "objectId": tid,
            "shapeProperties": {"contentAlignment": "MIDDLE"},
            "fields": "contentAlignment"}},
        {"updateTextStyle": {
            "objectId": tid, "textRange": {"type": "ALL"},
            "style": {"fontFamily": fonts[font_role], "fontSize": {"magnitude": size, "unit": "PT"},
                      "bold": bold,
                      "foregroundColor": {"opaqueColor": {"rgbColor": hex_rgb(colors[text_role])}}},
            "fields": "fontFamily,fontSize,bold,foregroundColor"}},
        {"updateParagraphStyle": {
            "objectId": tid, "textRange": {"type": "ALL"},
            "style": {"alignment": align}, "fields": "alignment"}},
    ]
    # sub line styled smaller
    if slide.get("sub"):
        main_len = len(slide.get("text", ""))
        reqs.append({"updateTextStyle": {
            "objectId": tid,
            "textRange": {"type": "FIXED_RANGE", "startIndex": main_len + 1, "endIndex": len(text)},
            "style": {"fontFamily": fonts["body"], "fontSize": {"magnitude": max(14, size - 16), "unit": "PT"}, "bold": False},
            "fields": "fontFamily,fontSize,bold"}})
    # logo on cover/closing if a public URL exists
    logo = brand.get("logo", {}).get("url", "")
    if stype in ("cover", "closing") and logo.startswith("https://"):
        reqs.append({"createImage": {
            "url": logo,
            "elementProperties": {
                "pageObjectId": sid,
                "size": {"width": {"magnitude": int(PAGE_W * 0.12), "unit": "EMU"},
                         "height": {"magnitude": int(PAGE_W * 0.12), "unit": "EMU"}},
                "transform": {"scaleX": 1, "scaleY": 1,
                              "translateX": int(PAGE_W * 0.44), "translateY": int(PAGE_H * 0.04), "unit": "EMU"}}}})
    return reqs


def batch(session, pres_id, reqs):
    for start in range(0, len(reqs), 100):
        chunk = reqs[start:start + 100]
        for attempt in range(4):
            r = session.post(f"{SLIDES}/{pres_id}:batchUpdate", json={"requests": chunk})
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(2 ** attempt)
                continue
            if not r.ok:
                sys.exit(f"batchUpdate failed ({r.status_code}): {r.text[:800]}")
            break


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("deck")
    ap.add_argument("--brand", required=True)
    args = ap.parse_args()

    deck = json.load(open(args.deck))
    brand = json.load(open(args.brand))
    brand["colors"].setdefault("accent_text", "#FFFFFF")
    brand["colors"].setdefault("muted", "#888888")
    slides = deck["slides"]

    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {token()}"

    r = s.post(SLIDES, json={"title": deck.get("title", "Workshop")})
    if not r.ok:
        sys.exit(f"Create failed ({r.status_code}): {r.text[:800]}\n"
                 "If 403: enable the API (gcloud services enable slides.googleapis.com) "
                 "and redo the ADC login with presentations+drive scopes (see docstring).")
    pres = r.json()
    pid = pres["presentationId"]
    default_slide = pres["slides"][0]["objectId"]

    reqs = []
    for i, sl in enumerate(slides):
        reqs.extend(slide_requests(i, sl, brand))
    reqs.append({"deleteObject": {"objectId": default_slide}})
    batch(s, pid, reqs)

    # speaker notes: second pass (notes shape ids only exist after creation)
    notes = [(i, sl["notes"]) for i, sl in enumerate(slides) if sl.get("notes")]
    if notes:
        full = s.get(f"{SLIDES}/{pid}", params={"fields": "slides(objectId,slideProperties.notesPage.notesProperties.speakerNotesObjectId)"}).json()
        note_ids = {sl["objectId"]: sl["slideProperties"]["notesPage"]["notesProperties"]["speakerNotesObjectId"]
                    for sl in full["slides"]}
        nreqs = [{"insertText": {"objectId": note_ids[f"s{i:04d}"], "text": txt}}
                 for i, txt in notes if f"s{i:04d}" in note_ids]
        batch(s, pid, nreqs)

    url = f"https://docs.google.com/presentation/d/{pid}/edit"
    print(f"{len(slides)} slides -> {url}")


if __name__ == "__main__":
    main()
