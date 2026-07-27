"""Render the social preview card from a real `alfred demo` digest.

The card is the repository's shop window (GitHub social preview, README hero),
and it quotes product output — so it is generated, never hand-drawn: regenerate
it whenever the demo digest changes rather than letting the picture drift from
what the command actually prints.

    pip install pillow          # not a project dependency, only needed here
    python docs/assets/make_social_preview.py

Source of truth for the text below: `alfred demo` (see src/alfred/demo/).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 640
BG = "#0d1117"
PANEL = "#161b22"
BORDER = "#30363d"
WHITE = "#e6edf3"
GREY = "#8b949e"
BLUE = "#58a6ff"
AMBER = "#f0883e"

MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
MONO_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
SANS_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

# (text, colour, bold) segments per line; None starts a blank line.
DIGEST: list[list[tuple[str, str, bool]] | None] = [
    [("Alfred · demo-bot · 2026-07-27", GREY, False)],
    None,
    [
        ("Tasks completed:          ", WHITE, False),
        ("3", WHITE, True),
        ("   [evt:demo-1-task, demo-2-task, demo-3-task]", BLUE, False),
    ],
    [
        ("Cost (tokens → €):   ", WHITE, False),
        ("1.18 €", WHITE, True),
        ("   [evt:demo-1-llm, demo-2-llm, demo-3-llm]", BLUE, False),
    ],
    [
        ("Escalations:              ", WHITE, False),
        ("1", WHITE, True),
        ("   [evt:demo-3-tool]", BLUE, False),
    ],
    [
        ("Deviations (mandate):     ", WHITE, False),
        ("1", AMBER, True),
        ("   [evt:demo-2-tool]", BLUE, False),
    ],
    [
        ("    └─ tool_not_allowed: 'read_pii' is not in allowed_tools", AMBER, False),
    ],
]


def main() -> None:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    title = ImageFont.truetype(SANS_BOLD, 56)
    subtitle = ImageFont.truetype(SANS, 27)
    mono = ImageFont.truetype(MONO, 21)
    mono_bold = ImageFont.truetype(MONO_BOLD, 21)
    footer = ImageFont.truetype(SANS, 23)
    footer_mono = ImageFont.truetype(MONO_BOLD, 23)

    d.text((64, 56), "Alfred", font=title, fill=WHITE)
    d.text((64, 130), "Accountability layer for AI agents", font=subtitle, fill=GREY)

    # The digest panel: the claim and its evidence, shown rather than described.
    top, bottom = 196, 470
    d.rounded_rectangle((64, top, W - 64, bottom), radius=12, fill=PANEL, outline=BORDER, width=2)

    y = top + 26
    for line in DIGEST:
        if line is None:
            y += 16
            continue
        x = 96
        for text, colour, bold in line:
            font = mono_bold if bold else mono
            d.text((x, y), text, font=font, fill=colour)
            x += int(d.textlength(text, font=font))
        y += 34

    d.text((64, 512), "Every line is anchored to a trace event ID.", font=footer, fill=WHITE)
    d.text((64, 550), "The ones that aren't, don't ship.", font=footer, fill=GREY)
    d.text((W - 64 - int(d.textlength("uvx alfred-ai demo", font=footer_mono)), 550),
           "uvx alfred-ai demo", font=footer_mono, fill=BLUE)

    out = Path(__file__).parent / "social-preview.png"
    img.save(out)
    print(f"wrote {out} ({W}x{H})")


if __name__ == "__main__":
    main()
