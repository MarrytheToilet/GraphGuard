"""Unified visual style for GraphGuard figures.

Palette: light blue + light pink (per user request 2026-05-13).
All figures pull from this module so style stays consistent across reports.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# ---- core palette (very light pink + very light blue, soft pastels) ----
PINK       = "#FBD3DD"   # primary accent — very light pink
PINK_DARK  = "#E89AAE"   # contrast pink for emphasis
BLUE       = "#CFE7F5"   # secondary accent — very light blue
BLUE_DARK  = "#8FBED9"   # contrast blue for emphasis
GREEN      = "#CDEAD6"   # SATISFIED verdicts — very light green
GREEN_DARK = "#7FBE96"
LAVENDER   = "#DDD0EE"
PEACH      = "#FBDDC4"
YELLOW     = "#FBEFC0"
GRAY       = "#9AA0A6"
GRAY_LIGHT = "#E4E7EB"
BLACK      = "#1F1F23"
WHITE      = "#FFFFFF"

# Categorical palette for series — alternates pink/blue/green/lavender for
# visual variety while staying within the soft palette.
PALETTE = [
    PINK,
    BLUE,
    GREEN,
    LAVENDER,
    PEACH,
    YELLOW,
    PINK_DARK,
    BLUE_DARK,
]

# Redundant encoding for line plots so categories remain distinguishable when
# printed monochrome.
LINESTYLES = ["-", "--", "-.", ":", (0, (3, 1, 1, 1)),
              (0, (5, 2)), (0, (1, 1)), (0, (4, 1, 1, 1, 1, 1))]
MARKERS = ["o", "s", "^", "D", "v", "P", "X", "*"]


def apply_rc(font_size: int = 11) -> None:
    """Apply consistent rcParams. Call once at module import or script start."""
    plt.rcParams.update({
        "axes.facecolor":   WHITE,
        "figure.facecolor": WHITE,
        "axes.edgecolor":   BLACK,
        "axes.labelcolor":  BLACK,
        "axes.titlecolor":  BLACK,
        "xtick.color":      BLACK,
        "ytick.color":      BLACK,
        "text.color":       BLACK,
        "font.family":      ["DejaVu Sans"],
        "font.size":        font_size,
        "axes.titlesize":   font_size + 2,
        "axes.titleweight": "normal",
        "axes.labelsize":   font_size,
        "xtick.labelsize":  font_size - 1,
        "ytick.labelsize":  font_size - 1,
        "legend.fontsize":  font_size - 1,
        "legend.frameon":   True,
        "legend.facecolor": WHITE,
        "legend.edgecolor": GRAY_LIGHT,
        "axes.grid":        False,
        "axes.spines.top":   False,
        "axes.spines.right": False,
        # Embed TrueType fonts in vector exports instead of Matplotlib's
        # default Type 3 glyphs.
        "pdf.fonttype":      42,
        "ps.fonttype":       42,
    })


def export_pdf_and_png(fig, path: Path, *, dpi: int = 300, **kwargs) -> None:
    """Export a vector PDF plus a PNG preview from the same figure state."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    kwargs.setdefault("bbox_inches", "tight")
    kwargs.setdefault("pad_inches", 0.025)
    kwargs.setdefault("facecolor", fig.get_facecolor())
    fig.savefig(path, dpi=dpi, **kwargs)
    if path.suffix.lower() == ".pdf":
        preview = path.with_suffix(".png")
        fig.savefig(preview, dpi=dpi, **kwargs)
        print(f"  wrote {path} and {preview}")
    else:
        print(f"  wrote {path}")


def save_fig(fig, path: Path, *, dpi: int = 300, pad: float = 0.4) -> None:
    """Finalize layout and export a paper PDF with a matching PNG preview."""
    fig.tight_layout(pad=pad)
    export_pdf_and_png(fig, path, dpi=dpi)
    plt.close(fig)


def despine(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="x", which="both", length=3, color=GRAY)
    ax.tick_params(axis="y", which="both", length=3, color=GRAY)


def color_for_verdict(v: str) -> str:
    v = (v or "").upper()
    return {
        "VIOLATED":     PINK_DARK,
        "SATISFIED":    GREEN_DARK,
        "INCONCLUSIVE": GRAY,
    }.get(v, GRAY)


def annotate_bars(ax, bars, values, *, fmt: str = "{:.2f}",
                  dy: float = 0.02, fontsize: int = 9) -> None:
    """Write the value above each bar."""
    for b, v in zip(bars, values):
        if v is None:
            continue
        h = b.get_height()
        ax.text(b.get_x() + b.get_width() / 2,
                h + dy,
                fmt.format(v),
                ha="center", va="bottom",
                fontsize=fontsize, color=BLACK)
