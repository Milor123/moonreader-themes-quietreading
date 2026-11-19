#!/usr/bin/env python3
"""Generate Moon+ Reader .mrthemes files from a small palette spec.

A .mrthemes file is a ZIP containing:
  - theme_<Name>.xml : an Android SharedPreferences <map> with the visual options
  - optional font files referenced by pFontName

Colors are stored as signed 32-bit ARGB integers, which is why the XML shows
negative numbers like -923692 (0xFFF1E7D4).

Usage:  python3 build_themes.py
Output: themes/<Name>.mrthemes
"""

import math
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FONT_DIR = ROOT / "fonts"
OUT_DIR = ROOT / "themes"

# --------------------------------------------------------------------------
# color math
# --------------------------------------------------------------------------


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#%02X%02X%02X" % rgb


def _srgb_to_lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _lin_to_srgb(c):
    c = max(0.0, min(1.0, c))
    v = c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
    return max(0, min(255, round(v * 255)))


def luminance(rgb):
    r, g, b = (_srgb_to_lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(rgb_a, rgb_b):
    la, lb = luminance(rgb_a), luminance(rgb_b)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


def lstar(rgb):
    y = luminance(rgb)
    f = y ** (1 / 3) if y > 0.008856 else 7.787 * y + 16 / 116
    return 116 * f - 16


def to_java_int(rgb):
    r, g, b = rgb
    u = (0xFF << 24) | (r << 16) | (g << 8) | b
    return u - (1 << 32) if u >= (1 << 31) else u


def fg_for_contrast(bg_rgb, anchor_rgb, target):
    """Scale the anchor's linear luminance until it reaches `target` contrast
    against bg_rgb, preserving the anchor's hue/chroma ratios.

    The anchor decides the side: if it is lighter than the background we raise
    it to `target`, if it is darker we lower it to `target`.
    """
    lb = luminance(bg_rgb)
    la = luminance(anchor_rgb)
    if la >= lb:
        need = target * (lb + 0.05) - 0.05   # text lighter than background
    else:
        need = (lb + 0.05) / target - 0.05   # text darker than background
    if need <= 0:
        raise ValueError("target contrast unreachable for this background")
    scale = need / la
    lin = [_srgb_to_lin(c) * scale for c in anchor_rgb]
    return tuple(_lin_to_srgb(c) for c in lin)


# --------------------------------------------------------------------------
# palette spec
# --------------------------------------------------------------------------
# bg      : background color
# anchor  : the tint the text should lean toward before contrast is normalized
# target  : desired WCAG contrast ratio for body text
# spacing : (line_space, paragraph_space, left/right margin, top/bottom margin)
# size    : pFontSize

THEMES = [
    {
        "name": "Night Ember",
        "bg": "#17130E",
        "anchor": "#E8CFA8",   # warm amber ink
        "target": 9.5,
        "size": 20.0,
        "spacing": (5, 8, 82, 90),
    },
    {
        "name": "Night Ink",
        "bg": "#1B1D1E",
        "anchor": "#D2D8D6",   # neutral, de-blued
        "target": 9.5,
        "size": 20.0,
        "spacing": (5, 8, 82, 90),
    },
    {
        "name": "Night Coal",
        "bg": "#0E0D0B",
        "anchor": "#B8A78F",   # very low light, lower luminance on purpose
        "target": 7.8,
        "size": 20.0,
        "spacing": (5, 8, 82, 90),
    },
    {
        "name": "Day Parchment",
        "bg": "#EFE4CD",
        "anchor": "#4A3A28",   # warm brown, never pure black
        "target": 10.4,
        "size": 20.0,
        "spacing": (5, 8, 82, 90),
    },
    {
        "name": "Day Linen",
        "bg": "#E7E2D8",
        "anchor": "#3A3A36",
        "target": 10.4,
        "size": 20.0,
        "spacing": (5, 8, 82, 90),
    },
    {
        "name": "Day Sepia",
        "bg": "#E6D5B4",
        "anchor": "#3B2E1E",   # heavier tint for very bright rooms
        "target": 10.4,
        "size": 20.0,
        "spacing": (5, 8, 82, 90),
    },
]

FONT_FILE = "GentiumPlus-Regular.ttf"

XML_TEMPLATE = """<?xml version='1.0' encoding='utf-8' standalone='yes' ?>
<map>
    <boolean name="pUseBackgroundImage" value="false" />
    <boolean name="pFontUnderline" value="false" />
    <boolean name="pFontBold" value="false" />
    <boolean name="pFontItalic" value="false" />
    <int name="pTopMargin2" value="{top}" />
    <boolean name="pFontAnti" value="true" />
    <int name="pBottomMargin2" value="{bottom}" />
    <int name="pParagraphSpace" value="{para}" />
    <int name="pFontScale" value="0" />
    <int name="pLeftMargin" value="{left}" />
    <boolean name="pFontShadow" value="false" />
    <float name="pFontSize" value="{size}" />
    <int name="pLineSpace" value="{line}" />
    <int name="pFontSpace" value="0" />
    <string name="pFontName">{font}</string>
    <int name="pFontColor" value="{fg}" />
    <int name="pRightMargin" value="{right}" />
    <boolean name="pTextJustified" value="false" />
    <int name="pBackgroundColor" value="{bg}" />
</map>
"""


def build(theme):
    bg = hex_to_rgb(theme["bg"])
    fg = fg_for_contrast(bg, hex_to_rgb(theme["anchor"]), theme["target"])
    line, para, side, vert = theme["spacing"]

    xml = XML_TEMPLATE.format(
        top=vert, bottom=vert, left=side, right=side,
        para=para, line=line, size=theme["size"], font=FONT_FILE,
        fg=to_java_int(fg), bg=to_java_int(bg),
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUT_DIR / f"{theme['name']}.mrthemes"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"theme_{theme['name']}.xml", xml)
        font = FONT_DIR / FONT_FILE
        if font.exists():
            z.write(font, FONT_FILE)
        else:
            print(f"  ! font missing: {font} (theme will use the device font)")

    return {
        "name": theme["name"],
        "file": target,
        "bg_hex": rgb_to_hex(bg),
        "fg_hex": rgb_to_hex(fg),
        "bg_int": to_java_int(bg),
        "fg_int": to_java_int(fg),
        "contrast": contrast(bg, fg),
        "bg_l": lstar(bg),
        "fg_l": lstar(fg),
    }


def verify(rows):
    """Re-open every produced archive and prove the file is what Moon+ expects."""
    ok = True
    for row in rows:
        with zipfile.ZipFile(row["file"]) as z:
            broken = z.testzip()
            if broken:
                print(f"FAIL corrupt entry in {row['file'].name}: {broken}")
                ok = False
                continue
            names = z.namelist()
            xml_name = f"theme_{row['name']}.xml"
            if xml_name not in names:
                print(f"FAIL {row['file'].name} has no {xml_name}")
                ok = False
                continue
            body = z.read(xml_name).decode("utf-8")
            if f'name="pFontColor" value="{row["fg_int"]}"' not in body:
                print(f"FAIL {row['file'].name} font color did not round-trip")
                ok = False
            if f'name="pBackgroundColor" value="{row["bg_int"]}"' not in body:
                print(f"FAIL {row['file'].name} background color did not round-trip")
                ok = False
            import xml.etree.ElementTree as ET
            root = ET.fromstring(body)
            if root.tag != "map" or len(root) != 19:
                print(f"FAIL {row['file'].name} malformed prefs map")
                ok = False
    return ok


def main():
    print(f"{'theme':16s} {'bg':8s} {'text':8s} {'contrast':>8s} {'bg L*':>6s} {'text L*':>8s}  file")
    rows = []
    for theme in THEMES:
        row = build(theme)
        rows.append(row)
        print(
            f"{row['name']:16s} {row['bg_hex']:8s} {row['fg_hex']:8s} "
            f"{row['contrast']:8.2f} {row['bg_l']:6.1f} {row['fg_l']:8.1f}  {row['file'].name}"
        )
    print()
    print("verification:", "OK" if verify(rows) else "FAILED")
    return 0 if verify(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())