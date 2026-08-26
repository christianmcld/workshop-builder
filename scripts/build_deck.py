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


def parse_marks(text):
    """Strip [[accent]] and {{serif-italic}} markers.
    Returns (clean_text, [(start, end, kind), ...]) with kind in {"accent", "serif"}."""
    marks = []
    clean, i = "", 0
    pairs = [("[[", "]]", "accent"), ("{{", "}}", "serif")]
    while i < len(text):
        hit = None
        for op, cl, kind in pairs:
            a = text.find(op, i)
            if a >= 0 and (hit is None or a < hit[0]):
                b = text.find(cl, a)
                if b >= 0:
                    hit = (a, b, kind)
        if hit is None:
            clean += text[i:]
            break
        a, b, kind = hit
        clean += text[i:a]
        marks.append((len(clean), len(clean) + b - a - 2, kind))
        clean += text[a + 2:b]
        i = b + 2
    return clean, marks


class Deck:
    def __init__(self, brand):
        self.b = brand
        self.c = brand["colors"]
        self.f = brand["fonts"]
        self.chrome = brand.get("chrome", {})
        self.reqs = []
        self.n = 0
        self._uid = 0
        self.prefix = "el"

    def uid(self, tag):
        self._uid += 1
        return f"{self.prefix}{self._uid:05d}{tag}"

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
        ]  # plain neon dot — no glyph (design review: checkmark off-center, dot alone is cleaner)

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

    def accent_style(self, dark):
        """Accent treatment for text (design review): on dark, pure accent as the
        text color; on light, ink text on an accent highlight — never accent-
        colored text on a light background."""
        if dark:
            return {"foregroundColor": {"opaqueColor": {"rgbColor": rgb(self.c["accent"])}}}, "foregroundColor"
        return ({"foregroundColor": {"opaqueColor": {"rgbColor": rgb(self.c["text"])}},
                 "backgroundColor": {"opaqueColor": {"rgbColor": rgb(self.c["accent"])}}},
                "foregroundColor,backgroundColor")

    def kicker(self, page, text, dark, y=0.20, align="CENTER", x=0.10, w=0.80, plain=False, font=None):
        base = (self.c["dark_muted"] if dark else self.c["muted"]) if plain else \
               (self.c["dark_text"] if dark else self.c["text"])
        tid = self.text_box(page, text.upper(), int(PAGE_W * x), int(PAGE_H * y),
                            int(PAGE_W * w), int(PAGE_H * 0.06),
                            font or self.f.get("mono", self.f["body"]), 13, base, bold=True, align=align)
        if not plain:
            style, fields = self.accent_style(dark)
            self.reqs.append({"updateTextStyle": {"objectId": tid, "textRange": {"type": "ALL"},
                                                  "style": style, "fields": fields}})
        return tid

    def apply_marks(self, tid, marks, dark, font, size, bold):
        accent_style, accent_fields = self.accent_style(dark)
        if getattr(self, "mode", None) == "tone":
            serif_color = self.c.get("tone_serif", self.c["accent_soft"])
        elif dark:
            serif_color = self.c["dark_muted"]
        else:
            serif_color = self.c.get("ink_faint", self.c["muted"])
        for a, b, kind in marks:
            if kind == "accent":
                style, fields = dict(accent_style), accent_fields
                style.update({"fontFamily": font, "fontSize": {"magnitude": size, "unit": "PT"}, "bold": bold})
                fields = "fontFamily,fontSize,bold," + fields
            else:  # serif italic secondary tone (the "recommended funnels" / "I had a winner" pattern)
                style = {"fontFamily": self.f["heading"], "italic": True, "bold": False,
                         "fontSize": {"magnitude": size, "unit": "PT"},
                         "foregroundColor": {"opaqueColor": {"rgbColor": rgb(serif_color)}}}
                fields = "fontFamily,italic,bold,fontSize,foregroundColor"
            self.reqs.append({"updateTextStyle": {
                "objectId": tid, "textRange": {"type": "FIXED_RANGE", "startIndex": a, "endIndex": b},
                "style": style, "fields": fields}})

    def watermark(self, page):
        """Giant faint brand mark tucked in the top-right corner, cropped by the
        slide edge — slightly lighter than the dark background."""
        wm = self.chrome.get("watermark") or self.chrome.get("header_wordmark", "").replace(" ", "")
        if not wm:
            return
        color = (self.c.get("tone_watermark", self.c.get("watermark_dark", self.c["dark_surface"]))
                 if getattr(self, "mode", None) == "tone"
                 else self.c.get("watermark_dark", self.c["dark_surface"]))
        self.text_box(page, wm, int(PAGE_W * 0.45), int(-PAGE_H * 0.10), int(PAGE_W * 1.30),
                      int(PAGE_H * 0.45), self.f["heading"], 130, color, bold=True,
                      align="START", valign="TOP")

    # ---- slide types -------------------------------------------------------
    def add_slide(self, s):
        i = self.n
        page = f"s{i:04d}"
        self.reqs.append({"createSlide": {"objectId": page, "insertionIndex": i,
                                          "slideLayoutReference": {"predefinedLayout": "BLANK"}}})
        self.render_onto(page, s, index=i)

    def render_onto(self, page, s, index=0):
        self.n = index + 1
        t = s.get("type", "statement")
        mode = s.get("mode")
        if mode is None:
            if "dark" in s:
                mode = "dark" if s["dark"] else "light"
            elif t == "numbered":
                mode = "tone"
            elif (t in ("cover", "closing", "framework", "visual", "timeline", "impact", "story")
                  or (t == "section" and bool(s.get("number")))):
                mode = "dark"
            else:
                mode = "light"
        dark = mode in ("dark", "tone")
        self.mode = mode
        bg = {"light": self.c["background"], "dark": self.c["dark_background"],
              "tone": self.c.get("tone_background", self.c["dark_background"])}[mode]
        self.reqs.append(
            {"updatePageProperties": {"objectId": page,
                                      "pageProperties": {"pageBackgroundFill": {"solidFill": {"color": {"rgbColor": rgb(bg)}}}},
                                      "fields": "pageBackgroundFill.solidFill.color"}})
        if mode == "tone":
            ink = self.c.get("tone_text", self.c["dark_text"])
            muted = self.c.get("tone_muted", self.c["dark_muted"])
        else:
            ink = self.c["dark_text"] if dark else self.c["text"]
            muted = self.c["dark_muted"] if dark else self.c["muted"]
        text = s.get("text", " ")
        sub = s.get("sub")

        if t in ("cover", "closing"):
            x, y = pct(0.08, 0.34)
            w, h = pct(0.84, 0.32)
            self.text_box(page, text, x, y, w, h, self.f["heading"], 52, ink, bold=True,
                          sub=sub, sub_size=20, sub_color=muted, sub_font=self.f["heading"])
            dx, _ = pct(0.485, 0)
            d = int(PAGE_H * 0.045)
            self.check_dot(page, dx, int(PAGE_H * 0.24), d)
        elif t == "section" and s.get("number"):
            # chapter-number layout (Tom): giant faint numeral, dash kicker,
            # big bold title low-left, watermark cropped in the corner
            self.watermark(page)
            self.text_box(page, str(s["number"]), int(PAGE_W * 0.04), int(PAGE_H * 0.60),
                          int(PAGE_W * 0.16), int(PAGE_H * 0.28), self.f["body"], 80,
                          self.c.get("watermark_dark", self.c["dark_muted"]), bold=True,
                          align="START", valign="MIDDLE")
            if s.get("kicker"):
                self.kicker(page, "——— " + s["kicker"], dark, y=0.62, align="START", x=0.20, w=0.72, plain=True)
            clean, marks = parse_marks(text)
            tid = self.text_box(page, clean, int(PAGE_W * 0.20), int(PAGE_H * 0.68),
                                int(PAGE_W * 0.74), int(PAGE_H * 0.18), self.f["body"], 40, ink,
                                bold=True, align="START", valign="TOP")
            self.apply_marks(tid, marks, dark, self.f["body"], 40, True)
        elif t == "section":
            # singular text blocks are always centered (left-align is reserved
            # for two-column layouts) — per Christian's design review
            clean, marks = parse_marks(text)
            x, y = pct(0.10, 0.30)
            w, h = pct(0.80, 0.40)
            tid = self.text_box(page, clean, x, y, w, h, self.f["heading"], 54, ink, bold=True,
                                sub=sub, sub_size=20, sub_color=muted)
            self.apply_marks(tid, marks, dark, self.f["heading"], 54, True)
        elif t == "statement":
            if s.get("kicker"):
                self.kicker(page, s["kicker"], dark)
            clean, marks = parse_marks(text)
            x, y = pct(0.10, 0.30)
            w, h = pct(0.80, 0.40)
            tid = self.text_box(page, clean, x, y, w, h, self.f["body"], 32, ink, bold=True,
                                line_spacing=115, sub=sub, sub_size=19, sub_color=muted,
                                sub_font=self.f["heading"] if dark else None)
            self.apply_marks(tid, marks, dark, self.f["body"], 32, True)
        elif t == "impact":
            # hard-hitting statement / quote alternative: dark, giant cropped
            # watermark in the corner, bold centered line
            self.watermark(page)
            clean, marks = parse_marks(text)
            x, y = pct(0.10, 0.32)
            w, h = pct(0.80, 0.36)
            tid = self.text_box(page, clean, x, y, w, h, self.f["body"], 36, ink, bold=True,
                                line_spacing=115, sub=sub, sub_size=18, sub_color=muted,
                                sub_font=self.f["heading"])
            self.apply_marks(tid, marks, dark, self.f["body"], 36, True)
        elif t == "story":
            # story beat: muted mono kicker, bold left headline, mono sub paragraphs
            if s.get("kicker"):
                self.kicker(page, "— " + s["kicker"], dark, y=0.30, align="START", x=0.08, w=0.84,
                            plain=True, font=self.f["heading"])
            clean, marks = parse_marks(text)
            tid = self.text_box(page, clean, int(PAGE_W * 0.08), int(PAGE_H * 0.36),
                                int(PAGE_W * 0.84), int(PAGE_H * 0.20), self.f["body"], 30, ink,
                                bold=True, align="START", valign="TOP")
            self.apply_marks(tid, marks, dark, self.f["body"], 30, True)
            if sub:
                self.text_box(page, sub, int(PAGE_W * 0.08), int(PAGE_H * 0.58),
                              int(PAGE_W * 0.84), int(PAGE_H * 0.28),
                              self.f["heading"], 15, muted,
                              align="START", valign="TOP", line_spacing=170)
        elif t == "numbered":
            # numbered agenda rows (TTB style): mono preheadline via kicker,
            # dual-tone title, serif-italic numerals, bold rows, light
            # right-aligned descriptors, hairline dividers between rows
            if s.get("kicker"):
                self.kicker(page, s["kicker"], dark, y=0.11, align="START", x=0.10, w=0.80, plain=True)
            clean, marks = parse_marks(text)
            tid = self.text_box(page, clean, int(PAGE_W * 0.10), int(PAGE_H * 0.16),
                                int(PAGE_W * 0.80), int(PAGE_H * 0.13), self.f["body"], 34, ink,
                                bold=True, align="START", valign="TOP")
            self.apply_marks(tid, marks, dark, self.f["body"], 34, True)
            items = s.get("items", [])
            serif_c = (self.c.get("tone_serif") if mode == "tone" else
                       (self.c["dark_muted"] if dark else self.c.get("ink_faint", self.c["muted"])))
            y0, step = 0.34, min(0.115, 0.54 / max(len(items), 1))
            for j, it in enumerate(items):
                if isinstance(it, str):
                    it = {"text": it}
                yy = int(PAGE_H * (y0 + j * step))
                self.text_box(page, f"{j + 1:02d}", int(PAGE_W * 0.10), yy, int(PAGE_W * 0.06),
                              int(PAGE_H * 0.08), self.f["heading"], 17, serif_c,
                              italic=True, align="START", valign="TOP")
                self.text_box(page, it.get("text", ""), int(PAGE_W * 0.17), yy, int(PAGE_W * 0.45),
                              int(PAGE_H * 0.08), self.f["body"], 17, ink,
                              bold=True, align="START", valign="TOP")
                if it.get("desc"):
                    self.text_box(page, it["desc"], int(PAGE_W * 0.60), yy, int(PAGE_W * 0.30),
                                  int(PAGE_H * 0.08), self.f["body"], 13, muted,
                                  align="END", valign="TOP")
                if j < len(items) - 1:
                    lid = self.uid("h")
                    self.reqs += [
                        {"createLine": {"objectId": lid, "lineCategory": "STRAIGHT",
                                        "elementProperties": {"pageObjectId": page,
                                                              "size": {"width": {"magnitude": int(PAGE_W * 0.80), "unit": "EMU"},
                                                                       "height": {"magnitude": 1, "unit": "EMU"}},
                                                              "transform": {"scaleX": 1, "scaleY": 1,
                                                                            "translateX": int(PAGE_W * 0.10),
                                                                            "translateY": yy + int(PAGE_H * (step - 0.028)),
                                                                            "unit": "EMU"}}}},
                        {"updateLineProperties": {"objectId": lid,
                                                  "lineProperties": {
                                                      "lineFill": {"solidFill": {"color": {"rgbColor": rgb(muted)}, "alpha": 0.35}},
                                                      "weight": {"magnitude": 0.5, "unit": "PT"}},
                                                  "fields": "lineFill.solidFill,weight"}},
                    ]
        elif t == "quote":
            # brand-example treatment: faint oversized quote-echo behind, secondary
            # grey-blue card, deep-teal serif bold italic text
            echo = " ".join(text.replace('"', "").split()[:2])
            echo_c = self.c.get("quote_echo", self.c["border"])
            self.text_box(page, '"' + echo.split()[0] if echo else "", int(PAGE_W * 0.55), int(-PAGE_H * 0.06),
                          int(PAGE_W * 0.75), int(PAGE_H * 0.45), self.f["heading"], 150, echo_c,
                          bold=True, italic=True, align="START", valign="TOP")
            if len(echo.split()) > 1:
                self.text_box(page, echo.split()[1], int(PAGE_W * 0.55), int(PAGE_H * 0.68),
                              int(PAGE_W * 0.75), int(PAGE_H * 0.45), self.f["heading"], 150, echo_c,
                              bold=True, italic=True, align="START", valign="TOP")
            cx, cy = pct(0.14, 0.28)
            cw, ch = pct(0.72, 0.44)
            self.round_rect(page, cx, cy, cw, ch, self.c.get("secondary", self.c["accent_soft"]))
            self.text_box(page, text, cx + int(PAGE_W * 0.03), cy, cw - int(PAGE_W * 0.06), ch,
                          self.f["heading"], 30, self.c.get("tone_background", self.c["text"]),
                          bold=True, italic=True, line_spacing=120)
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
            n = max(len(pills), 1)
            gap = int(PAGE_H * (0.03 if n <= 4 else 0.02))
            avail = int(PAGE_H * 0.77)  # 0.11 .. 0.88, clear of chrome
            ph = min(int(PAGE_H * 0.125), int((avail - (n - 1) * gap) / n))
            total = n * ph + (n - 1) * gap if pills else 0
            py = max(int(PAGE_H * 0.11), int((PAGE_H - total) / 2))
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
            self.round_rect(page, cx, cy, cw, ch, self.c.get("tone_surface", self.c["dark_surface"]) if self.mode == "tone" else self.c["dark_surface"])
            pad = int(PAGE_W * 0.03)
            self.text_box(page, text, cx + pad, cy + int(PAGE_H * 0.035), cw - 2 * pad, int(PAGE_H * 0.11),
                          self.f["body"], 26, ink, bold=True, align="START", valign="TOP")
            if s.get("bullets"):
                self.text_box(page, "\n".join("•  " + b for b in s["bullets"]),
                              cx + pad, cy + int(PAGE_H * 0.16), cw - 2 * pad, int(PAGE_H * 0.42),
                              self.f["body"], 15, ink, align="START", valign="TOP",
                              line_spacing=150)
            if sub:
                self.text_box(page, sub, cx + pad, cy + int(PAGE_H * 0.60), cw - 2 * pad, int(PAGE_H * 0.12),
                              self.f["body"], 15, ink, bold=True, align="START", valign="TOP")
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
                                self.c.get("tone_surface", self.c["dark_surface"]) if self.mode == "tone" else self.c["dark_surface"], outline=muted)
                self.text_box(page, st.get("label", ""), cx - chip_w // 2, ly + int(PAGE_H * 0.05),
                              chip_w, chip_h, self.f["body"], 14, ink, bold=True)
                if st.get("note"):
                    nw = int(PAGE_W * 0.18)
                    self.text_box(page, st["note"], cx - nw // 2, ly - int(PAGE_H * 0.14), nw,
                                  int(PAGE_H * 0.09), self.f["body"], 13, muted)
        elif t == "quadrant":
            # cross-graph: two double-arrow axes with labeled ends; items are
            # placed per quadrant. Split shows bare axes first, then one item
            # per slide. Light background (Tom's pattern).
            axes = s.get("axes", {})
            cxp, cyp = 0.5, 0.52
            vx, vy0, vy1 = int(PAGE_W * cxp), int(PAGE_H * 0.16), int(PAGE_H * 0.80)
            hx0, hx1, hy = int(PAGE_W * 0.16), int(PAGE_W * 0.84), int(PAGE_H * cyp)
            for (x0, y0, w0, h0) in [(vx, vy0, 1, vy1 - vy0), (hx0, hy, hx1 - hx0, 1)]:
                lid = self.uid("l")
                self.reqs += [
                    {"createLine": {"objectId": lid, "lineCategory": "STRAIGHT",
                                    "elementProperties": {"pageObjectId": page,
                                                          "size": {"width": {"magnitude": max(w0, 1), "unit": "EMU"},
                                                                   "height": {"magnitude": max(h0, 1), "unit": "EMU"}},
                                                          "transform": {"scaleX": 1, "scaleY": 1, "translateX": x0,
                                                                        "translateY": y0, "unit": "EMU"}}}},
                    {"updateLineProperties": {"objectId": lid,
                                              "lineProperties": {
                                                  "lineFill": {"solidFill": {"color": {"rgbColor": rgb(muted)}}},
                                                  "weight": {"magnitude": 2, "unit": "PT"},
                                                  "startArrow": "FILL_ARROW", "endArrow": "FILL_ARROW"},
                                              "fields": "lineFill.solidFill.color,weight,startArrow,endArrow"}},
                ]
            lbl = self.f["body"]
            for key, (lx, ly, lw, al) in {
                    "top": (0.30, 0.085, 0.40, "CENTER"), "bottom": (0.30, 0.815, 0.40, "CENTER"),
                    "left": (0.015, cyp - 0.035, 0.13, "END"), "right": (0.855, cyp - 0.035, 0.13, "START")}.items():
                if axes.get(key):
                    self.text_box(page, axes[key], int(PAGE_W * lx), int(PAGE_H * ly),
                                  int(PAGE_W * lw), int(PAGE_H * 0.07), lbl, 16,
                                  self.c.get("ink_faint", muted), bold=True, align=al)
            slots = {"tl": (0.26, 0.30), "tr": (0.72, 0.30), "bl": (0.26, 0.72), "br": (0.72, 0.72)}
            used = {}
            for it in s.get("items", []):
                q = it.get("q", "tl")
                n = used.get(q, 0)
                used[q] = n + 1
                qx, qy = it.get("x"), it.get("y")
                if qx is None:
                    qx, qy = slots.get(q, (0.5, 0.5))
                    qx += (n % 2) * 0.11 - 0.05
                    qy += (n // 2) * 0.16 - 0.06
                self.text_box(page, it.get("text", ""), int(PAGE_W * (qx - 0.10)), int(PAGE_H * (qy - 0.07)),
                              int(PAGE_W * 0.20), int(PAGE_H * 0.14), self.f["body"], 13, ink,
                              align="START", valign="MIDDLE", line_spacing=125)
        elif t == "quotes":
            # scattered quote cards (Reddit/review style): rounded, overlapping,
            # spread across the page. Optional centered title. Cards are
            # placeholders the visual pass can swap for real screenshots.
            if text.strip():
                x, _ = pct(0.15, 0)
                w, _ = pct(0.70, 0)
                self.text_box(page, text, x, int(PAGE_H * 0.10), w, int(PAGE_H * 0.10),
                              self.f["body"], 22, ink, bold=True)
            default_spots = [(0.06, 0.22), (0.52, 0.18), (0.30, 0.42), (0.64, 0.50),
                             (0.10, 0.62), (0.44, 0.70), (0.72, 0.30)]
            for j, it in enumerate(s.get("items", [])):
                qx, qy = it.get("x"), it.get("y")
                if qx is None:
                    qx, qy = default_spots[j % len(default_spots)]
                qw = it.get("w", 0.30)
                qh = it.get("h", 0.17)
                card_fill = self.c["surface"] if not dark else (
                    self.c.get("tone_surface", self.c["dark_surface"]) if mode == "tone" else self.c["dark_surface"])
                self.round_rect(page, int(PAGE_W * qx), int(PAGE_H * qy), int(PAGE_W * qw),
                                int(PAGE_H * qh), card_fill,
                                outline=self.c["border"] if not dark else None)
                self.text_box(page, it.get("text", ""), int(PAGE_W * (qx + 0.015)), int(PAGE_H * qy),
                              int(PAGE_W * (qw - 0.03)), int(PAGE_H * qh), self.f["body"], 12,
                              self.c["text"] if not dark else ink, align="START", valign="MIDDLE",
                              line_spacing=115)
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
    ap.add_argument("--into", help="existing presentation id: re-render slides IN PLACE "
                                   "(preserves slide ids + comment history)")
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
    c.setdefault("watermark_dark", c["dark_surface"])
    c.setdefault("ink_faint", c["muted"])
    brand.setdefault("fonts", {}).setdefault("mono", "JetBrains Mono")

    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {token()}"
    if args.into:
        pid = args.into
        cur = s.get(f"{SLIDES}/{pid}", params={"fields": "slides(objectId,pageElements(objectId))"})
        if not cur.ok:
            sys.exit(f"Fetch failed ({cur.status_code}): {cur.text[:400]}")
        existing = cur.json().get("slides", [])
        d = Deck(brand)
        # unique prefix so new element ids never collide with a previous render's
        d.prefix = "r" + format(abs(hash(pid)) % 8999 + 1000, "d")
        # clear elements on kept slides, re-render onto them; add/remove slides to match
        for i, sl in enumerate(deck_data["slides"]):
            if i < len(existing):
                page = existing[i]["objectId"]
                for el in existing[i].get("pageElements", []):
                    d.reqs.append({"deleteObject": {"objectId": el["objectId"]}})
                d.render_onto(page, sl, index=i)
            else:
                d.n = i
                d.add_slide(sl)
        for extra in existing[len(deck_data["slides"]):]:
            d.reqs.append({"deleteObject": {"objectId": extra["objectId"]}})
        batch(s, pid, d.reqs)
    else:
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

    # notes: skip in --into mode (existing speaker notes persist; re-inserting would duplicate)
    notes = [] if args.into else [(i, sl["notes"]) for i, sl in enumerate(deck_data["slides"]) if sl.get("notes")]
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
