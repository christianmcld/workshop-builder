#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Build a self-contained HTML slideshow from deck.json + brand-tokens.json.

The HTML alternative to the Google Slides builder: same deck.json, same brand
tokens, same layouts. Output is one index.html with zero dependencies beyond
Google Fonts, ready for GitHub Pages (see scripts/publish_pages.sh).

Usage:
  uv run build_html.py path/to/deck.split.json --brand brand-tokens.json -o out/index.html

Presenting: arrows / space / click to advance, "n" toggles speaker notes,
"f" fullscreen. Deep-link any slide with #12.
"""
import argparse
import html
import json
import re


def esc(s):
    return html.escape(s or "")


def marks(text, cls_accent="mk-accent", cls_serif="mk-serif"):
    """[[accent]] and {{serif}} spans -> HTML; newlines -> <br>."""
    t = esc(text or "")
    t = re.sub(r"\[\[(.+?)\]\]", rf'<span class="{cls_accent}">\1</span>', t, flags=re.S)
    t = re.sub(r"\{\{(.+?)\}\}", rf'<span class="{cls_serif}">\1</span>', t, flags=re.S)
    return t.replace("\n", "<br>")


def chrome(b):
    hw = b.get("chrome", {}).get("header_wordmark", "")
    fs = b.get("chrome", {}).get("footer_signature", "")
    return (f'<div class="hw">{esc(hw)}</div>' if hw else "") + \
           (f'<div class="sig">{esc(fs)}</div>' if fs else "")


def render_slide(s, b):
    t = s.get("type", "statement")
    mode = s.get("mode") or ("dark" if s.get("dark") else None)
    if mode is None:
        if t == "numbered":
            mode = "tone"
        elif t in ("cover", "closing", "framework", "visual", "timeline", "impact", "story") \
                or (t == "section" and s.get("number")):
            mode = "dark"
        else:
            mode = "light"
    text, sub, kick = s.get("text", ""), s.get("sub", ""), s.get("kicker", "")
    body = ""

    if t in ("cover", "closing"):
        body = f'<div class="dot"></div><div class="cover-t">{marks(text)}</div>' + \
               (f'<div class="cover-s serif">{marks(sub)}</div>' if sub else "")
    elif t == "section" and s.get("number"):
        body = f'<div class="wm">{esc(b.get("chrome", {}).get("watermark", ""))}</div>' \
               f'<div class="ch-num">{esc(str(s["number"]))}</div>' \
               + (f'<div class="ch-kick">——— {esc(kick).upper()}</div>' if kick else "") + \
               f'<div class="ch-title">{marks(text)}</div>'
    elif t == "section":
        body = f'<div class="sec">{marks(text)}</div>' + (f'<div class="sec-s">{marks(sub)}</div>' if sub else "")
    elif t == "statement":
        body = (f'<div class="kick">{esc(kick).upper()}</div>' if kick else "") + \
               f'<div class="st">{marks(text)}</div>' + \
               (f'<div class="st-s{" serif" if mode != "light" else ""}">{marks(sub)}</div>' if sub else "")
    elif t == "impact":
        body = f'<div class="wm">{esc(b.get("chrome", {}).get("watermark", ""))}</div>' \
               f'<div class="st imp">{marks(text)}</div>' + \
               (f'<div class="st-s serif">{marks(sub)}</div>' if sub else "")
    elif t == "quote":
        echo = " ".join((text or "").replace('"', "").split()[:2]).split()
        body = "".join(f'<div class="q-echo q-echo{i}">{esc(w)}</div>' for i, w in enumerate(echo)) + \
               f'<div class="q-card"><div class="q-text">{marks(text)}</div></div>'
    elif t == "story":
        body = (f'<div class="sto-kick">— {esc(kick).upper()}</div>' if kick else "") + \
               f'<div class="sto-t">{marks(text)}</div>' + \
               (f'<div class="sto-s">{marks(sub)}</div>' if sub else "")
    elif t == "list":
        body = f'<div class="card list-card">{marks(text)}</div>'
    elif t == "checklist":
        pills = "".join(f'<div class="pill"><span class="pdot"></span>{esc(p)}</div>' for p in s.get("pills", []))
        body = f'<div class="chk"><div class="chk-t">{marks(text)}</div><div class="pills">{pills}</div></div>'
    elif t == "framework":
        bl = "".join(f"<li>{esc(x)}</li>" for x in s.get("bullets", []))
        body = f'<div class="fw-card"><div class="fw-t">{marks(text)}</div><ul>{bl}</ul>' + \
               (f'<div class="fw-k">{marks(sub)}</div>' if sub else "") + "</div>"
    elif t == "numbered":
        rows = ""
        for j, it in enumerate(s.get("items", [])):
            if isinstance(it, str):
                it = {"text": it}
            rows += f'<div class="row"><span class="num">{j + 1:02d}</span>' \
                    f'<span class="row-t">{esc(it.get("text", ""))}</span>' + \
                    (f'<span class="row-d">{esc(it["desc"])}</span>' if it.get("desc") else "") + "</div>"
        body = (f'<div class="kick">{esc(kick).upper()}</div>' if kick else "") + \
               f'<div class="nb-t">{marks(text)}</div><div class="rows">{rows}</div>'
    elif t == "timeline":
        n = max(len(s.get("stages", [])), s.get("slots", 1), 1)
        st = ""
        for j, g in enumerate(s.get("stages", [])):
            left = 8 + (84 / max(n - 0.6, 1)) * (j + 0.55)
            st += f'<div class="tl-stage" style="left:{left}%">' \
                  + (f'<div class="tl-note">{esc(g.get("note", ""))}</div>') + \
                  f'<div class="tl-dot{" acc" if g.get("accent") else ""}"></div>' \
                  f'<div class="tl-chip">{esc(g.get("label", ""))}</div></div>'
        body = (f'<div class="kick tl-k">{esc(kick).upper()}</div>' if kick else "") + \
               (f'<div class="tl-t">{marks(text)}</div>' if text.strip() else "") + \
               f'<div class="tl-line"></div>{st}'
    elif t == "quotes":
        cards = ""
        for i, it in enumerate(s.get("items", [])):
            x = it.get("x", 0.1) * 100
            y = it.get("y", 0.2 + 0.15 * i) * 100
            w = it.get("w", 0.30) * 100
            cards += f'<div class="qq" style="left:{x}%;top:{y}%;width:{w}%">{esc(it.get("text", ""))}</div>'
        body = (f'<div class="qq-t">{marks(text)}</div>' if text.strip() else "") + cards
    elif t == "quadrant":
        ax = s.get("axes", {})
        items = ""
        slots = {"tl": (26, 30), "tr": (72, 30), "bl": (26, 72), "br": (72, 72)}
        used = {}
        for it in s.get("items", []):
            q = it.get("q", "tl")
            k = used.get(q, 0)
            used[q] = k + 1
            qx = it.get("x", slots[q][0] / 100 + (k % 2) * 0.11 - 0.05) * 100
            qy = it.get("y", slots[q][1] / 100 + (k // 2) * 0.16 - 0.06) * 100
            items += f'<div class="qd-item" style="left:{qx - 10}%;top:{qy - 7}%">{esc(it.get("text", "")).replace(chr(10), "<br>")}</div>'
        body = '<div class="qd-v"></div><div class="qd-h"></div>' + \
               "".join(f'<div class="qd-l qd-{k}">{esc(v)}</div>' for k, v in ax.items()) + items
    elif t == "evolution":
        gens = s.get("gens", [])
        svg = '<svg class="evo" viewBox="0 0 1000 560" preserveAspectRatio="xMidYMid meet">'
        gx0, gx1 = 130, 870
        step_x = (gx1 - gx0) / max(len(gens) - 1, 1)
        parents = [None]
        labels = ""
        for j, g in enumerate(gens):
            cx = gx0 + j * step_x
            n, win = g.get("count", 5), g.get("win", 0)
            clusters = parents if g.get("per_parent") and parents != [None] else [None]
            k_cl = len(clusters)
            band_t, band_b, cgap = 150, 470, 40
            cl_h = (band_b - band_t - (k_cl - 1) * cgap) / k_cl
            gap = min(36, cl_h / max(n - 1, 1))
            newp = []
            for ci, parent in enumerate(clusters):
                top = band_t + ci * (cl_h + cgap)
                ccy = top + cl_h / 2 if k_cl > 1 else 310
                ys = [ccy - gap * (n - 1) / 2 + k * gap for k in range(n)]
                for k, yy in enumerate(ys):
                    winner = k < win
                    if winner:
                        newp.append((cx, yy))
                    svg += f'<circle cx="{cx}" cy="{yy:.0f}" r="9" class="{"ew" if winner else "ek"}"/>'
                if parent is not None:
                    svg += f'<line x1="{parent[0] + 12}" y1="{parent[1]:.0f}" x2="{cx - 16}" y2="{ys[0]:.0f}" class="el"/>'
            parents = newp or [None]
            if g.get("label"):
                labels += f'<div class="evo-l" style="left:{cx / 10}%">{esc(g["label"])}</div>'
        svg += "</svg>"
        body = (f'<div class="kick tl-k">{esc(kick).upper()}</div>' if kick else "") + \
               (f'<div class="tl-t">{marks(text)}</div>' if text.strip() else "") + svg + labels
    else:  # visual placeholder
        body = f'<div class="vis">[ VISUAL: {esc(text)} ]</div>'

    notes = esc(s.get("notes", ""))
    return f'<section class="slide m-{mode} t-{t}" data-notes="{notes}">{body}{chrome(b)}</section>'


CSS = """
*{margin:0;padding:0;box-sizing:border-box}
html,body{height:100%;background:#000;overflow:hidden}
#stage{position:relative;width:100vw;height:100vh}
.slide{position:absolute;inset:0;display:none;overflow:hidden;font-family:var(--body),serif}
.slide.on{display:block}
.m-light{background:var(--bg);color:var(--ink)}
.m-dark{background:var(--dbg);color:var(--dink)}
.m-tone{background:var(--tbg);color:var(--tink)}
.hw{position:absolute;top:3.5%;width:100%;text-align:center;font-family:var(--wordmark),sans-serif;font-weight:700;font-size:1.4vmin;letter-spacing:.6em;text-indent:.6em}
.sig{position:absolute;bottom:3.5%;width:100%;text-align:center;font-family:var(--hand),cursive;font-size:2.6vmin;opacity:.75}
.m-light .hw,.m-light .sig{color:var(--ink)} .m-dark .hw,.m-dark .sig{color:var(--dmut)} .m-tone .hw{color:var(--tink)} .m-tone .sig{color:var(--tmut)}
.serif{font-family:var(--head),serif}
.mk-serif{font-family:var(--head),serif;font-style:italic;font-weight:400}
.m-light .mk-serif{color:var(--faint)} .m-dark .mk-serif{color:var(--dmut)} .m-tone .mk-serif{color:var(--tserif)}
.mk-accent{font-weight:700}
.m-light .mk-accent{background:var(--acc);color:var(--ink);padding:0 .15em}
.m-dark .mk-accent,.m-tone .mk-accent{color:var(--acc)}
.kick{position:absolute;top:20%;width:100%;text-align:center;font-family:var(--mono),monospace;font-weight:700;font-size:1.7vmin;letter-spacing:.15em}
.m-light .kick{color:var(--ink)} .m-light .kick{background:none}
.m-light .kick::after{content:""}
.m-light .kick{width:auto;left:50%;transform:translateX(-50%);background:var(--acc);padding:.3em .6em}
.m-dark .kick,.m-tone .kick{color:var(--acc)}
.st{position:absolute;top:32%;left:10%;right:10%;text-align:center;font-weight:700;font-size:4.6vmin;line-height:1.25}
.st-s{position:absolute;top:52%;left:12%;right:12%;text-align:center;font-size:2.6vmin;line-height:1.5}
.m-light .st-s{color:var(--mut)} .m-dark .st-s{color:var(--dmut)} .m-tone .st-s{color:var(--tmut)}
.imp{top:36%;font-size:5vmin}
.cover-t{position:absolute;top:36%;left:8%;right:8%;text-align:center;font-family:var(--head),serif;font-weight:700;font-size:7vmin}
.cover-s{position:absolute;top:56%;left:15%;right:15%;text-align:center;font-size:2.4vmin;color:var(--dmut)}
.dot{position:absolute;top:25%;left:calc(50% - 1.2vmin);width:2.4vmin;height:2.4vmin;border-radius:50%;background:var(--acc)}
.sec{position:absolute;top:38%;left:10%;right:10%;text-align:center;font-family:var(--head),serif;font-weight:700;font-size:7.5vmin}
.sec-s{position:absolute;top:58%;left:10%;right:10%;text-align:center;font-size:2.4vmin;color:var(--mut)}
.wm{position:absolute;top:-4%;left:46%;font-family:var(--head),serif;font-weight:700;font-size:24vmin;white-space:nowrap;color:var(--wmc);pointer-events:none}
.ch-num{position:absolute;left:4%;top:60%;font-size:11vmin;font-weight:700;color:var(--wmc)}
.ch-kick{position:absolute;left:20%;top:63%;font-family:var(--mono),monospace;font-size:1.7vmin;letter-spacing:.15em;color:var(--dmut)}
.ch-title{position:absolute;left:20%;top:67%;font-size:5.5vmin;font-weight:700}
.q-card{position:absolute;left:14%;right:14%;top:28%;height:44%;background:var(--sec);border-radius:3vmin;display:flex;align-items:center;justify-content:center;padding:0 4%}
.q-text{font-family:var(--head),serif;font-style:italic;font-weight:700;font-size:4.4vmin;text-align:center;color:var(--tbg);line-height:1.3}
.q-echo{position:absolute;font-family:var(--head),serif;font-style:italic;font-weight:700;font-size:26vmin;color:var(--echo);pointer-events:none}
.q-echo0{top:-8%;left:55%}.q-echo1{bottom:-14%;left:58%}
.sto-kick{position:absolute;left:8%;top:30%;font-family:var(--head),serif;font-size:1.9vmin;letter-spacing:.12em;color:var(--dmut)}
.sto-t{position:absolute;left:8%;right:8%;top:35%;font-weight:700;font-size:4.4vmin;line-height:1.2}
.sto-s{position:absolute;left:8%;right:8%;top:56%;font-family:var(--head),serif;font-size:2.3vmin;line-height:1.9;color:var(--dmut);white-space:pre-line}
.chk{position:absolute;inset:0}
.chk-t{position:absolute;left:7%;top:38%;width:32%;font-weight:700;font-size:4.2vmin;line-height:1.2;text-align:left}
.pills{position:absolute;left:46%;right:7%;top:50%;transform:translateY(-50%);display:flex;flex-direction:column;gap:1.6vmin}
.pill{background:var(--surf);border:1px solid var(--brd);border-radius:2.2vmin;padding:1.8vmin 2.2vmin 1.8vmin 6vmin;font-size:2vmin;color:var(--ink);position:relative;text-align:left}
.pdot{position:absolute;left:2vmin;top:50%;transform:translateY(-50%);width:2.4vmin;height:2.4vmin;border-radius:50%;background:var(--acc)}
.fw-card{position:absolute;left:12%;top:12%;width:52%;height:74%;background:var(--dsurf);border-radius:3vmin;padding:4% 4%}
.m-tone .fw-card{background:var(--tsurf)}
.fw-t{font-weight:700;font-size:3.4vmin;margin-bottom:2.5vmin;text-align:left}
.fw-card ul{list-style:none;text-align:left}
.fw-card li{font-size:2.1vmin;margin-bottom:1.8vmin;padding-left:1.6em;position:relative}
.fw-card li::before{content:"•";position:absolute;left:.3em}
.fw-k{position:absolute;bottom:8%;left:8%;right:8%;font-weight:700;font-size:2.1vmin;text-align:left;white-space:pre-line}
.nb-t{position:absolute;left:10%;right:10%;top:16%;font-weight:700;font-size:4.4vmin;text-align:left;line-height:1.2}
.rows{position:absolute;left:10%;right:10%;top:40%}
.row{display:flex;align-items:baseline;gap:3vmin;padding:1.6vmin 0;border-bottom:1px solid color-mix(in srgb,currentColor 25%,transparent)}
.row:last-child{border-bottom:none}
.num{font-family:var(--head),serif;font-style:italic;font-size:2.2vmin;color:var(--tserif);min-width:3vmin}
.m-light .num{color:var(--faint)} .m-dark .num{color:var(--dmut)}
.row-t{font-weight:700;font-size:2.3vmin;text-align:left;flex:1}
.row-d{font-size:1.8vmin;opacity:.75;text-align:right}
.tl-k{top:10%}
.tl-t{position:absolute;left:8%;top:16%;font-weight:700;font-size:3.6vmin;text-align:left}
.tl-line{position:absolute;left:8%;right:8%;top:62%;height:2px;background:currentColor}
.tl-line::after{content:"";position:absolute;right:-1px;top:-5px;border-left:12px solid currentColor;border-top:6px solid transparent;border-bottom:6px solid transparent}
.tl-stage{position:absolute;top:62%;transform:translateX(-50%);text-align:center}
.tl-note{position:absolute;bottom:5vmin;left:50%;transform:translateX(-50%);white-space:nowrap;font-size:1.8vmin;opacity:.75}
.tl-dot{width:2.2vmin;height:2.2vmin;border-radius:50%;background:currentColor;margin:-1.1vmin auto 0}
.tl-dot.acc{background:var(--acc)}
.tl-chip{margin-top:2.4vmin;border:1px solid color-mix(in srgb,currentColor 50%,transparent);background:var(--dsurf);border-radius:1.2vmin;padding:1vmin 2vmin;font-weight:700;font-size:1.9vmin;white-space:nowrap}
.m-tone .tl-chip{background:var(--tsurf)}
.qq-t{position:absolute;top:10%;width:100%;text-align:center;font-weight:700;font-size:3.2vmin}
.qq{position:absolute;background:var(--surf);border:1px solid var(--brd);border-radius:1.8vmin;padding:2vmin;font-size:1.75vmin;color:var(--ink);text-align:left;box-shadow:0 .8vmin 2.4vmin rgba(0,0,0,.10)}
.qd-v{position:absolute;left:50%;top:16%;bottom:20%;width:2px;background:var(--mut)}
.qd-h{position:absolute;left:16%;right:16%;top:52%;height:2px;background:var(--mut)}
.qd-v::before,.qd-v::after,.qd-h::before,.qd-h::after{content:"";position:absolute;border:solid transparent}
.qd-l{position:absolute;font-weight:700;font-size:2.2vmin;color:var(--faint)}
.qd-top{top:9%;width:100%;text-align:center}.qd-bottom{top:81.5%;width:100%;text-align:center}
.qd-left{left:2%;top:49%;width:12%;text-align:right}.qd-right{right:2%;top:49%;width:12%;text-align:left}
.qd-item{position:absolute;width:20%;font-size:1.75vmin;text-align:left}
.evo{position:absolute;left:0;right:0;top:18%;height:64%;width:100%}
.ew{fill:var(--acc)} .ek{fill:currentColor;opacity:.4} .el{stroke:currentColor;opacity:.5;stroke-width:1.5}
.evo-l{position:absolute;top:86.5%;transform:translateX(-50%);font-family:var(--mono),monospace;font-size:1.7vmin;opacity:.75}
.vis{position:absolute;top:45%;width:100%;text-align:center;font-size:2.4vmin;color:var(--dmut)}
#hud{position:fixed;bottom:1.2vmin;right:1.6vmin;color:#888;font:1.6vmin/1 monospace;z-index:9}
#notes{position:fixed;left:0;right:0;bottom:0;max-height:30%;overflow:auto;background:rgba(0,0,0,.88);color:#eee;font:2vmin/1.5 monospace;padding:2vmin 3vmin;display:none;z-index:9}
"""

JS = """
const slides=[...document.querySelectorAll('.slide')];let i=0;
function show(n){i=Math.max(0,Math.min(slides.length-1,n));slides.forEach((s,j)=>s.classList.toggle('on',j===i));
 location.hash=i+1;document.getElementById('hud').textContent=(i+1)+' / '+slides.length;
 const nt=slides[i].dataset.notes||'';const nb=document.getElementById('notes');nb.textContent=nt;}
addEventListener('keydown',e=>{if(['ArrowRight','ArrowDown','PageDown',' '].includes(e.key)){e.preventDefault();show(i+1)}
 else if(['ArrowLeft','ArrowUp','PageUp'].includes(e.key)){e.preventDefault();show(i-1)}
 else if(e.key==='n'){const nb=document.getElementById('notes');nb.style.display=nb.style.display==='block'?'none':'block'}
 else if(e.key==='f'){document.documentElement.requestFullscreen?.()}
 else if(e.key==='Home'){show(0)}else if(e.key==='End'){show(slides.length-1)}});
addEventListener('click',e=>{if(e.clientX>innerWidth/2)show(i+1);else show(i-1)});
addEventListener('hashchange',()=>{const n=(parseInt(location.hash.slice(1))||1)-1;if(n!==i)show(n)});
show((parseInt(location.hash.slice(1))||1)-1);
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("deck")
    ap.add_argument("--brand", required=True)
    ap.add_argument("-o", "--out", default="index.html")
    args = ap.parse_args()
    deck = json.load(open(args.deck))
    b = json.load(open(args.brand))
    c = dict(b["colors"])
    f = dict(b["fonts"])
    c.setdefault("secondary", c.get("accent_soft", "#DDD"))
    c.setdefault("quote_echo", c.get("border", "#EEE"))
    c.setdefault("watermark_dark", c.get("dark_surface", "#1B1B1B"))
    c.setdefault("ink_faint", c.get("muted", "#888"))
    for k, v in {"tone_background": c.get("dark_background"), "tone_surface": c.get("dark_surface"),
                 "tone_text": c.get("dark_text"), "tone_muted": c.get("dark_muted"),
                 "tone_serif": c.get("dark_muted")}.items():
        c.setdefault(k, v)
    f.setdefault("mono", "JetBrains Mono")
    f.setdefault("wordmark", f.get("body", "Inter"))
    fams = sorted({f.get(k) for k in ("heading", "body", "handwritten", "mono", "wordmark") if f.get(k)})
    gf = "&".join("family=" + fam.replace(" ", "+") + ":ital,wght@0,400;0,700;1,400;1,700" for fam in fams)
    root = (f'--bg:{c["background"]};--ink:{c["text"]};--mut:{c["muted"]};--faint:{c["ink_faint"]};'
            f'--acc:{c["accent"]};--surf:{c["surface"]};--brd:{c.get("border", "#DDD")};'
            f'--dbg:{c["dark_background"]};--dink:{c["dark_text"]};--dmut:{c["dark_muted"]};--dsurf:{c["dark_surface"]};'
            f'--tbg:{c["tone_background"]};--tink:{c["tone_text"]};--tmut:{c["tone_muted"]};--tsurf:{c["tone_surface"]};'
            f'--tserif:{c["tone_serif"]};--sec:{c["secondary"]};--echo:{c["quote_echo"]};--wmc:{c["watermark_dark"]};'
            f'--head:"{f["heading"]}";--body:"{f["body"]}";--hand:"{f.get("handwritten", f["body"])}";'
            f'--mono:"{f["mono"]}";--wordmark:"{f["wordmark"]}"')
    slides = "\n".join(render_slide(s, b) for s in deck["slides"])
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(deck.get("title", "Workshop"))}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?{gf}&display=swap" rel="stylesheet">
<style>:root{{{root}}}{CSS}</style></head>
<body><div id="stage">{slides}</div><div id="hud"></div><div id="notes"></div>
<script>{JS}</script></body></html>"""
    with open(args.out, "w") as fh:
        fh.write(doc)
    print(f"{len(deck['slides'])} slides -> {args.out}")


if __name__ == "__main__":
    main()
