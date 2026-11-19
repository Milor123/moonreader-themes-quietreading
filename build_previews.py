#!/usr/bin/env python3
"""Generate the HTML preview pages used for the comparison images.

Colours come from build_themes.py, so the previews can never drift from the
shipped .mrthemes files. Pages are served over HTTP (not file://) so the browser
is allowed to load the embedded font, then screenshotted headless.

    python3 build_previews.py
    python3 -m http.server 8791
    # http://127.0.0.1:8791/previews/theme.html?t=<slug>
"""

from pathlib import Path

import build_themes as bt

ROOT = Path(__file__).resolve().parent
PREVIEW_DIR = ROOT / "previews"

# Device geometry we emulate: a 1080x1920 phone (9:16) at DSF 3.
CARD_W, CARD_H = 360, 640      # CSS px
SP = 2.5                       # device px per sp: 20sp -> 50px -> 16.67 CSS px
LINE_HEIGHT = 1.62             # stand-in for pLineSpace=5

SAMPLE = [
    "En un lugar de la Mancha, de cuyo nombre no quiero acordarme, no ha mucho "
    "tiempo que vivía un hidalgo de los de lanza en astillero, adarga antigua, "
    "rocín flaco y galgo corredor.",
    "Es, pues, de saber que este sobredicho hidalgo, los ratos que estaba ocioso "
    "—que eran los más del año—, se daba a leer libros de caballerías, con tanta "
    "afición y gusto, que olvidó casi de todo punto el ejercicio de la caza, y aun "
    "la administración de su hacienda.",
    "Llenósele la fantasía de todo aquello que leía en los libros, así de "
    "encantamentos como de pendencias, batallas, desafíos, heridas, requiebros, "
    "amores, tormentas y disparates imposibles.",
    "\u201cMy dear Mr. Bennet,\u201d said his lady to him one day, \u201chave you "
    "heard that Netherfield Park is let at last?\u201d Mr. Bennet replied that he "
    "had not.",
]

def slug(name):
    return name.lower().replace(" ", "-")


def resolved_themes():
    """Every theme with its final colours and contrast ratio."""
    out = []
    for t in bt.THEMES:
        bg = bt.hex_to_rgb(t["bg"])
        fg = bt.fg_for_contrast(bg, bt.hex_to_rgb(t["anchor"]), t["target"])
        out.append({
            "name": t["name"],
            "slug": slug(t["name"]),
            "bg": bt.rgb_to_hex(bg),
            "fg": bt.rgb_to_hex(fg),
            "contrast": bt.contrast(bg, fg),
            "size": t["size"],
            "line": t["spacing"][0],
            "side": t["spacing"][2],
            "vert": t["spacing"][3],
            "mode": "Night" if t["name"].startswith("Night") else "Day",
        })
    return out


BASE_CSS = f"""
@font-face {{
  font-family: 'Gentium';
  src: url('../fonts/GentiumPlus-Regular.ttf') format('truetype');
  font-weight: 400;
  font-style: normal;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Gentium', Georgia, serif; -webkit-font-smoothing: antialiased; }}

.page {{
  width: {CARD_W}px; height: {CARD_H}px; overflow: hidden;
  background: var(--bg); color: var(--fg);
}}
.frame {{ display: flex; flex-direction: column; height: 100%;
          padding: var(--vpad) var(--pad); }}
.text {{
  flex: 1; min-height: 0; overflow: hidden;
  font-size: var(--fs); line-height: var(--lh);
  text-align: left; hyphens: auto;
}}
.text p {{ text-indent: 1.4em; }}
.text p:first-child {{ text-indent: 0; }}
/* let the page look like it continues instead of slicing a line in half */
.text {{ -webkit-mask-image: linear-gradient(to bottom, #000 87%, transparent 100%);
         mask-image: linear-gradient(to bottom, #000 87%, transparent 100%); }}
.meta {{
  margin-top: 13px; display: flex; justify-content: space-between;
  font-family: system-ui, sans-serif; font-size: 10px; letter-spacing: .1em;
  text-transform: uppercase; opacity: .6;
}}
"""


def card(t, width, height, fs, pad, vpad, show_meta=True):
    paras = "".join(f"<p>{p}</p>" for p in SAMPLE)
    meta = ""
    if show_meta:
        meta = (f'<div class="meta"><span>{t["name"]}</span>'
                f'<span>{t["contrast"]:.2f}:1</span></div>')
    return f"""<div class="page" data-slug="{t['slug']}" style="
     --bg:{t['bg']}; --fg:{t['fg']}; --fs:{fs}px; --lh:{LINE_HEIGHT};
     --pad:{pad}px; --vpad:{vpad}px; width:{width}px; height:{height}px;">
  <div class="frame"><div class="text">{paras}</div>{meta}</div>
</div>"""


def theme_page(themes):
    """All themes stacked; ?t=<slug> isolates one so a viewport shot is one page."""
    cards = "\n".join(
        card(t, CARD_W, CARD_H, round(t["size"] * SP / 3, 2),
             round(t["side"] / SP, 2), round(t["vert"] / SP, 2))
        for t in themes
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Moon+ Reader theme preview</title>
<style>{BASE_CSS}
body {{ background: #111; }}
body.solo .page:not(.active) {{ display: none; }}
</style></head>
<body>
{cards}
<script>
const want = new URLSearchParams(location.search).get('t');
if (want) {{
  document.body.classList.add('solo');
  const el = document.querySelector(`.page[data-slug="${{want}}"]`);
  if (el) el.classList.add('active');
}}
</script>
</body></html>
"""


def main():
    PREVIEW_DIR.mkdir(exist_ok=True)
    themes = resolved_themes()

    (PREVIEW_DIR / "theme.html").write_text(theme_page(themes), encoding="utf-8")

    for t in themes:
        print(f"{t['slug']:16s} bg={t['bg']} fg={t['fg']} {t['contrast']:.2f}:1")
    print(f"\nwrote {PREVIEW_DIR / 'theme.html'}")


if __name__ == "__main__":
    main()