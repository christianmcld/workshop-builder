#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""Build a cue-card workshop deck in Google Slides from deck.json + brand-tokens.json.

v2 layout engine, modeled on the Time to Build deck structure:
persistent header wordmark + signature footer, centered statements with stacked
subs, lower-left chapter titles, pill-card checklists, dark framework cards.

Usage:
  uv run build_deck.py path/to/deck.json --brand path/to/brand-tokens.json

Auth: gcloud ADC with Slides/Drive scopes via the user's OWN OAuth client
(Google blocks gcloud's shared client from sensitive scopes) — setup in
references/google-slides-generation.md.
"""
import argparse
import json
import subprocess
import sys
import time

import requests

SLIDES = "https://slides.googleapis.com/v1/presentations"
PAGE_W, PAGE_H = 9144000, 5143500  # 16:9 in EMU (1in = 914400)


def token():
    for cmd in (["gcloud", "auth", "application-default", "print-access-token"],
                ["gcloud", "auth", "print-access-token"]):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip()
        except subprocess.CalledProcessError:
            continue
    sys.exit("No gcloud credentials. See references/google-slides-generation.md setup.")


def rgb(h):
    h = h.lstrip("#")
    return {"red": int(h[0:2], 16) / 255, "green": int(h[2:4], 16) / 255, "blue": int(h[4:6], 16) / 255}


def pct(w, h):  # page-relative EMU
    return int(PAGE_W * w), int(PAGE_H * h)


def parse_spans(text):
    """Strip [[accent]] markers; return (clean_text, [(start, end), ...])."""
    clean, spans, i = "", [], 0
    while True:
        a = text.find("[[", i)
        if a < 0:
            clean += text[i:]
            break
        b = text.find("]]", a)
        if b < 0:
            clean += text[i:]
            break
        clean += text[i:a]
        spans.append((len(clean), len(clean) + b - a - 2))
        clean += text[a + 2:b]
        i = b + 2
    return clean, spans


class Deck:
    def __init__(self, brand):
        self.b = brand
        self.c = brand["colors"]
        self.f = brand["fonts"]
        self.chrome = brand.get("chrome", {})
        self.reqs = []
        self.n = 0
        self._uid = 0

    def uid(self, tag):
        self._uid += 1
        return f"el{self._uid:05d}{tag}"

    # ---- low-level helpers -------------------------------------------------
    def text_box(self, page, text, x, y, w, h, font, size, color, bold=False,
                 italic=False, align="CENTER", valign="MIDDLE", line_spacing=None,
                 sub=None, sub_size=None, sub_color=None, sub_font=None):
        """Text box; optional smaller `sub` block appended on new lines."""
        tid = self.uid("t")
        full = text + ("\n" + sub if sub else "")
        self.reqs += [
            {"createShape": {"objectId": tid, "shapeType": "TEXT_BOX",
                             "elementProperties": {"pageObjectId": page,
                                                   "size": {"width": {"magnitude": w, "unit": "EMU"},
                                                            "height": {"magnitude": h, "unit": "EMU"}},
                                                   "transform": {"scaleX": 1, "scaleY": 1, "translateX": x,
                                                                 "translateY": y, "unit": "EMU"}}}},
            {"insertText": {"objectId": tid, "text": full}},
            {"updateShapeProperties": {"objectId": tid, "shapeProperties": {"contentAlignment": valign},
                                       "fields": "contentAlignment"}},
            {"updateTextStyle": {"objectId": tid, "textRange": {"type": "ALL"},
                                 "style": {"fontFamily": font, "fontSize": {"magnitude": size, "unit": "PT"},
                                           "bold": bold, "italic": italic,
                                           "foregroundColor": {"opaqueColor": {"rgbColor": rgb(color)}}},
                                 "fields": "fontFamily,fontSize,bold,italic,foregroundColor"}},
            {"updateParagraphStyle": {"objectId": tid, "textRange": {"type": "ALL"},
                                      "style": {"alignment": align,
                                                **({"lineSpacing": line_spacing} if line_spacing else {})},
                                      "fields": "alignment" + (",lineSpacing" if line_spacing else "")}},
        ]
        if sub:
            self.reqs.append({"updateTextStyle": {
                "objectId": tid,
                "textRange": {"type": "FIXED_RANGE", "startIndex": len(text) + 1, "endIndex": len(full)},
                "style": {"fontFamily": sub_font or self.f["body"],
                          "fontSize": {"magnitude": sub_size or max(14, size - 14), "unit": "PT"},
                          "bold": False, "italic": False,
                          "foregroundColor": {"opaqueColor": {"rgbColor": rgb(sub_color or color)}}},
                "fields": "fontFamily,fontSize,bold,italic,foregroundColor"}})
        return tid

    def round_rect(self, page, x, y, w, h, fill, outline=None):
        rid = self.uid("r")
        self.reqs += [
            {"createShape": {"objectId": rid, "shapeType": "ROUND_RECTANGLE",
                             "elementProperties": {"pageObjectId": page,
                                                   "size": {"width": {"magnitude": w, "unit": "EMU"},
                                                            "height": {"magnitude": h, "unit": "EMU"}},
                                                   "transform": {"scaleX": 1, "scaleY": 1, "translateX": x,
                                                                 "translateY": y, "unit": "EMU"}}}},
            {"updateShapeProperties": {
                "objectId": rid,
                "shapeProperties": {
                    "shapeBackgroundFill": {"solidFill": {"color": {"rgbColor": rgb(fill)}}},
                    "outline": ({"outlineFill": {"solidFill": {"color": {"rgbColor": rgb(outline)}}},
                                 "weight": {"magnitude": 1, "unit": "PT"}} if outline
                                else {"propertyState": "NOT_RENDERED"})},
                "fields": "shapeBackgroundFill.solidFill.color,outline"}},
        ]
        return rid

    def check_dot(self, page, x, y, d):
        did = self.uid("d")
        self.reqs += [
            {"createShape": {"objectId": did, "shapeType": "ELLIPSE",
                             "elementProperties": {"pageObjectId": page,
                                                   "size": {"width": {"magnitude": d, "unit": "EMU"},
                                                            "height": {"magnitude": d, "unit": "EMU"}},
                                                   "transform": {"scaleX": 1, "scaleY": 1, "translateX": x,
                                                                 "translateY": y, "unit": "EMU"}}}},
            {"updateShapeProperties": {"objectId": did,
                                       "shapeProperties": {
                                           "shapeBackgroundFill": {"solidFill": {"color": {"rgbColor": rgb(self.c["accent"])}}},
                                           "outline": {"propertyState": "NOT_RENDERED"}},
                                       "fields": "shapeBackgroundFill.solidFill.color,outline"}},
            {"insertText": {"objectId": did, "text": "✓"}},
            {"updateShapeProperties": {"objectId": did, "shapeProperties": {"contentAlignment": "MIDDLE"},
                                       "fields": "contentAlignment"}},
            {"updateTextStyle": {"objectId": did, "textRange": {"type": "ALL"},
                                 "style": {"fontFamily": self.f["body"], "bold": True,
                                           "fontSize": {"magnitude": 10, "unit": "PT"},
                                           "foregroundColor": {"opaqueColor": {"rgbColor": rgb(self.c["accent_text"])}}},
                                 "fields": "fontFamily,bold,fontSize,foregroundColor"}},
        ]

    # ---- chrome ------------------------------------------------------------
    def chrome_els(self, page, dark):
        ink = self.c["dark_text"] if dark else self.c["text"]
        muted = self.c["dark_muted"] if dark else self.c["muted"]
        hw = self.chrome.get("header_wordmark")
        fs = self.chrome.get("footer_signature")
        if hw:
            x, _ = pct(0.25, 0)
            w, _ = pct(0.5, 0)
            self.text_box(page, hw, x, int(PAGE_H * 0.035), w, int(PAGE_H * 0.06),
                          self.f["body"], 11, ink, bold=True)
        if fs:
            x, _ = pct(0.25, 0)
            w, _ = pct(0.5, 0)
            self.text_box(page, fs, x, int(PAGE_H * 0.905), w, int(PAGE_H * 0.07),
                          self.f.get("handwritten", self.f["body"]), 20, muted)

    def accent_text(self, dark):
        """Accent used AS text: pure accent on dark, darker accent on light."""
        return self.c["accent"] if dark else self.c.get("accent_text_light", self.c["accent"])

    def kicker(self, page, text, dark, y=0.20):
        x, _ = pct(0.10, 0)
        w, _ = pct(0.80, 0)
        self.text_box(page, text.upper(), x, int(PAGE_H * y), w, int(PAGE_H * 0.06),
                      self.f.get("mono", self.f["body"]), 13, self.accent_text(dark), bold=True)

    def accent_spans(self, tid, spans, dark, font, size, bold):
        for a, b in spans:
            self.reqs.append({"updateTextStyle": {
                "objectId": tid, "textRange": {"type": "FIXED_RANGE", "startIndex": a, "endIndex": b},
                "style": {"fontFamily": font, "fontSize": {"magnitude": size, "unit": "PT"}, "bold": bold,
                          "foregroundColor": {"opaqueColor": {"rgbColor": rgb(self.accent_text(dark))}}},
                "fields": "fontFamily,fontSize,bold,foregroundColor"}})

    # ---- slide types -------------------------------------------------------
    def add_slide(self, s):
        i = self.n
        self.n += 1
        page = f"s{i:04d}"
        t = s.get("type", "statement")
        dark = s["dark"] if "dark" in s else t in ("cover", "closing", "framework", "visual", "timeline")
        bg = self.c["dark_background"] if dark else self.c["background"]
        self.reqs += [
            {"createSlide": {"objectId": page, "insertionIndex": i,
                             "slideLayoutReference": {"predefinedLayout": "BLANK"}}},
            {"updatePageProperties": {"objectId": page,
                                      "pageProperties": {"pageBackgroundFill": {"solidFill": {"color": {"rgbColor": rgb(bg)}}}},
                                      "fields": "pageBackgroundFill.solidFill.color"}},
        ]
        ink = self.c["dark_text"] if dark else self.c["text"]
        muted = self.c["dark_muted"] if dark else self.c["muted"]
        text = s.get("text", " ")
        sub = s.get("sub")

        if t in ("cover", "closing"):
            x, y = pct(0.08, 0.34)
            w, h = pct(0.84, 0.32)
            self.text_box(page, text, x, y, w, h, self.f["heading"], 52, ink, bold=True,
                          sub=sub, sub_size=20, sub_color=muted)
            dx, _ = pct(0.485, 0)
            d = int(PAGE_H * 0.045)
            self.check_dot(page, dx, int(PAGE_H * 0.24), d)
        elif t == "section":
            x, y = pct(0.07, 0.52)
            w, h = pct(0.75, 0.3)
            self.text_box(page, text, x, y, w, h, self.f["heading"], 54, ink, bold=True,
                          align="START", valign="TOP", sub=sub, sub_size=20, sub_color=muted)
        elif t == "statement":
            if s.get("kicker"):
                self.kicker(page, s["kicker"], dark)
            clean, spans = parse_spans(text)
            x, y = pct(0.10, 0.30)
            w, h = pct(0.80, 0.40)
            tid = self.text_box(page, clean, x, y, w, h, self.f["body"], 32, ink, bold=True,
                                line_spacing=115, sub=sub, sub_size=19, sub_color=muted)
            self.accent_spans(tid, spans, dark, self.f["body"], 32, True)
        elif t == "quote":
            cx, cy = pct(0.14, 0.30)
            cw, ch = pct(0.72, 0.40)
            self.round_rect(page, cx, cy, cw, ch, self.c["accent_soft"])
            self.text_box(page, text, cx + int(PAGE_W * 0.03), cy, cw - int(PAGE_W * 0.06), ch,
                          self.f["heading"], 26, self.c["text"], bold=True, italic=True, line_spacing=115)
        elif t == "list":
            cx, cy = pct(0.26, 0.22)
            cw, ch = pct(0.48, 0.56)
            self.round_rect(page, cx, cy, cw, ch, self.c["surface"] if not dark else self.c["dark_surface"],
                            outline=self.c["border"] if not dark else None)
            self.text_box(page, text, cx + int(PAGE_W * 0.03), cy, cw - int(PAGE_W * 0.06), ch,
                          self.f["body"], 19, ink, align="START", line_spacing=140)
        elif t == "checklist":
            # big title left, pill cards right; reveal rhythm = one new pill per slide
            x, y = pct(0.07, 0.36)
            w, h = pct(0.34, 0.34)
            self.text_box(page, text, x, y, w, h, self.f["body"], 34, ink, bold=True,
                          align="START", valign="MIDDLE", line_spacing=112)
            pills = s.get("pills", [])
            px, _ = pct(0.46, 0)
            pw, _ = pct(0.47, 0)
            ph = int(PAGE_H * 0.125)
            gap = int(PAGE_H * 0.03)
            total = len(pills) * ph + (len(pills) - 1) * gap if pills else 0
            py = max(int(PAGE_H * 0.12), int((PAGE_H - total) / 2))
            for p in pills:
                self.round_rect(page, px, py, pw, ph, self.c["surface"], outline=self.c["border"])
                d = int(PAGE_H * 0.05)
                self.check_dot(page, px + int(PAGE_W * 0.018), py + int((ph - d) / 2), d)
                self.text_box(page, p, px + int(PAGE_W * 0.055), py, pw - int(PAGE_W * 0.075), ph,
                              self.f["body"], 15, self.c["text"], align="START", line_spacing=110)
                py += ph + gap
        elif t == "framework":
            # dark slide, dark-surface card: title / divider / bullets / kicker
            cx, cy = pct(0.12, 0.12)
            cw, ch = pct(0.52, 0.74)
            self.round_rect(page, cx, cy, cw, ch, self.c["dark_surface"])
            pad = int(PAGE_W * 0.03)
            self.text_box(page, text, cx + pad, cy + int(PAGE_H * 0.035), cw - 2 * pad, int(PAGE_H * 0.11),
                          self.f["body"], 26, self.c["dark_text"], bold=True, align="START", valign="TOP")
            if s.get("bullets"):
                self.text_box(page, "\n".join("•  " + b for b in s["bullets"]),
                              cx + pad, cy + int(PAGE_H * 0.16), cw - 2 * pad, int(PAGE_H * 0.42),
                              self.f["body"], 15, self.c["dark_text"], align="START", valign="TOP",
                              line_spacing=150)
            if sub:
                self.text_box(page, sub, cx + pad, cy + int(PAGE_H * 0.60), cw - 2 * pad, int(PAGE_H * 0.12),
                              self.f["body"], 15, self.c["dark_text"], bold=True, align="START", valign="TOP")
        elif t == "timeline":
            # dark slide: arrow line, dot per stage, chip label below, note above.
            # progressive reveal = generator emits N slides, adding one stage each.
            if s.get("kicker"):
                self.kicker(page, s["kicker"], dark, y=0.10)
            if text.strip():
                x, _ = pct(0.08, 0)
                w, _ = pct(0.84, 0)
                self.text_box(page, text, x, int(PAGE_H * 0.16), w, int(PAGE_H * 0.12),
                              self.f["body"], 26, ink, bold=True, align="START")
            stages = s.get("stages", [])
            lid = self.uid("l")
            ly = int(PAGE_H * 0.62)
            lx, lw = int(PAGE_W * 0.08), int(PAGE_W * 0.84)
            self.reqs += [
                {"createLine": {"objectId": lid, "lineCategory": "STRAIGHT",
                                "elementProperties": {"pageObjectId": page,
                                                      "size": {"width": {"magnitude": lw, "unit": "EMU"},
                                                               "height": {"magnitude": 1, "unit": "EMU"}},
                                                      "transform": {"scaleX": 1, "scaleY": 1, "translateX": lx,
                                                                    "translateY": ly, "unit": "EMU"}}}},
                {"updateLineProperties": {"objectId": lid,
                                          "lineProperties": {
                                              "lineFill": {"solidFill": {"color": {"rgbColor": rgb(ink)}}},
                                              "weight": {"magnitude": 2, "unit": "PT"},
                                              "endArrow": "FILL_ARROW"},
                                          "fields": "lineFill.solidFill.color,weight,endArrow"}},
            ]
            slots = max(len(stages), s.get("slots", len(stages)) or 1)
            step = lw / (slots + 0.4)
            for j, st in enumerate(stages):
                cx = lx + int(step * (j + 0.55))
                d = int(PAGE_H * 0.032)
                did = self.uid("p")
                self.reqs += [
                    {"createShape": {"objectId": did, "shapeType": "ELLIPSE",
                                     "elementProperties": {"pageObjectId": page,
                                                           "size": {"width": {"magnitude": d, "unit": "EMU"},
                                                                    "height": {"magnitude": d, "unit": "EMU"}},
                                                           "transform": {"scaleX": 1, "scaleY": 1,
                                                                         "translateX": cx - d // 2,
                                                                         "translateY": ly - d // 2, "unit": "EMU"}}}},
                    {"updateShapeProperties": {"objectId": did,
                                               "shapeProperties": {
                                                   "shapeBackgroundFill": {"solidFill": {"color": {"rgbColor": rgb(
                                                       self.c["accent"] if st.get("accent") else ink)}}},
                                                   "outline": {"propertyState": "NOT_RENDERED"}},
                                               "fields": "shapeBackgroundFill.solidFill.color,outline"}},
                ]
                chip_w, chip_h = int(PAGE_W * 0.14), int(PAGE_H * 0.085)
                self.round_rect(page, cx - chip_w // 2, ly + int(PAGE_H * 0.05), chip_w, chip_h,
                                self.c["dark_surface"], outline=self.c["dark_muted"])
                self.text_box(page, st.get("label", ""), cx - chip_w // 2, ly + int(PAGE_H * 0.05),
                              chip_w, chip_h, self.f["body"], 14, self.c["dark_text"], bold=True)
                if st.get("note"):
                    nw = int(PAGE_W * 0.18)
                    self.text_box(page, st["note"], cx - nw // 2, ly - int(PAGE_H * 0.14), nw,
                                  int(PAGE_H * 0.09), self.f["body"], 13, self.c["dark_muted"])
        elif t == "visual":
            x, y = pct(0.10, 0.40)
            w, h = pct(0.80, 0.20)
            self.text_box(page, "[ VISUAL: " + text + " ]", x, y, w, h, self.f["body"], 18, muted)
        else:
            sys.exit(f"Unknown slide type: {t}")

        self.chrome_els(page, dark)


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

    deck_data = json.load(open(args.deck))
    brand = json.load(open(args.brand))
    c = brand["colors"]
    for k, v in {"accent_text": "#111111", "muted": "#888888", "surface": "#FFFFFF",
                 "border": c.get("muted", "#DDDDDD"),
                 "dark_background": c.get("text", "#111111"),
                 "dark_surface": c.get("text", "#181818"),
                 "dark_text": c.get("background", "#F4F4F4"),
                 "dark_muted": "#A3A29B", "accent_soft": c.get("accent", "#EEEEEE"),
                 "accent_text_light": c.get("accent", "#333333")}.items():
        c.setdefault(k, v)
    brand.setdefault("fonts", {}).setdefault("mono", "JetBrains Mono")

    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {token()}"
    r = s.post(SLIDES, json={"title": deck_data.get("title", "Workshop")})
    if not r.ok:
        sys.exit(f"Create failed ({r.status_code}): {r.text[:600]}\nCheck OAuth setup "
                 "(references/google-slides-generation.md).")
    pres = r.json()
    pid, default_slide = pres["presentationId"], pres["slides"][0]["objectId"]

    d = Deck(brand)
    for sl in deck_data["slides"]:
        d.add_slide(sl)
    d.reqs.append({"deleteObject": {"objectId": default_slide}})
    batch(s, pid, d.reqs)

    notes = [(i, sl["notes"]) for i, sl in enumerate(deck_data["slides"]) if sl.get("notes")]
    if notes:
        full = s.get(f"{SLIDES}/{pid}",
                     params={"fields": "slides(objectId,slideProperties.notesPage.notesProperties.speakerNotesObjectId)"}).json()
        nid = {sl["objectId"]: sl["slideProperties"]["notesPage"]["notesProperties"]["speakerNotesObjectId"]
               for sl in full["slides"]}
        batch(s, pid, [{"insertText": {"objectId": nid[f"s{i:04d}"], "text": txt}}
                       for i, txt in notes if f"s{i:04d}" in nid])

    print(f"{len(deck_data['slides'])} slides -> https://docs.google.com/presentation/d/{pid}/edit")


if __name__ == "__main__":
    main()
