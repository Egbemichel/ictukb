"""Draw the figures of the project report into docs/images/ (architecture, search flow, document life cycle)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "docs" / "images"
FONT = "DejaVu Sans"
INK = "#1f2933"
BLUE, BLUE_L = "#2f6690", "#dbe8f3"
TEAL, TEAL_L = "#2a9d8f", "#d9f0ed"
ORANGE, ORANGE_L = "#e07a1f", "#fbe6d2"
GREY, GREY_L = "#6b7785", "#eceff2"
GREEN, GREEN_L = "#3a8f4f", "#dcefe1"
RED, RED_L = "#b8433a", "#f6dcd9"


def canvas(w, h):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100 * h / w)
    ax.axis("off")
    return fig, ax


def box(ax, x, y, w, h, text, fc, ec, size=9, bold=False, radius=1.2):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0.2,rounding_size={radius}", fc=fc, ec=ec, lw=1.4))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size, color=INK, fontfamily=FONT,
            fontweight="bold" if bold else "normal", linespacing=1.35)


def panel(ax, x, y, w, h, ec):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.2,rounding_size=1.5", fc="white", ec=ec, lw=1.6, ls="--"))


def label(ax, x, y, text, color, size=8, ha="center", bold=False):
    ax.text(x, y, text, ha=ha, va="center", fontsize=size, color=color, fontfamily=FONT,
            fontweight="bold" if bold else "normal", linespacing=1.25)


def arrow(ax, p1, p2, color=GREY, rad=0.0, both=False):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="<|-|>" if both else "-|>", mutation_scale=13, lw=1.5, color=color,
                                 connectionstyle=f"arc3,rad={rad}", shrinkA=2, shrinkB=2))


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / name, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def architecture():
    fig, ax = canvas(13, 8.6)  # x 0..100, y 0..66.2
    panel(ax, 1, 3, 22, 49, GREY)
    panel(ax, 27, 3, 24, 49, BLUE)
    panel(ax, 55, 3, 19, 49, TEAL)
    panel(ax, 78, 3, 21, 49, ORANGE)
    label(ax, 2.5, 49.2, "Sources of information", GREY, 10, "left", True)
    label(ax, 28.5, 49.2, "Collection and processing", BLUE, 10, "left", True)
    label(ax, 56.5, 49.2, "Storage", TEAL, 10, "left", True)
    label(ax, 79.5, 49.2, "Service", ORANGE, 10, "left", True)

    sources = [("Official documents\n(notices, PDFs, scans)", 37), ("University website", 27),
               ("Spreadsheets\n(directories, bus)", 17), ("Official WhatsApp\ngroups (admins only)", 7)]
    for text, y in sources:
        box(ax, 3, y, 18, 8, text, GREY_L, GREY)

    box(ax, 29, 37, 20, 8, "GitHub repository\nreviewed documents,\ntests, automation", BLUE_L, BLUE)
    box(ax, 29, 24.5, 20, 9.5, "Python pipeline\ncheck, split into passages,\nconvert to vectors, index", BLUE_L, BLUE)
    box(ax, 29, 8, 20, 8, "WhatsApp listener\n(free web host)", BLUE_L, BLUE)

    box(ax, 57, 40, 15, 7, "Cloudinary\noriginal files, images", TEAL_L, TEAL)
    box(ax, 57, 27, 15, 10, "Neon database\ndocuments, passages\nand vectors", TEAL_L, TEAL)

    box(ax, 80, 27, 17, 16, "Cloudflare Worker\npublic interface:\nsearch, answer check,\nkeys, feedback", ORANGE_L, ORANGE)
    box(ax, 80, 8, 17, 10, "Workers AI\nvectors and\nanswer check", ORANGE_L, ORANGE)
    box(ax, 80, 57.5, 17, 7.5, "Student chatbots\n(any program)", GREEN_L, GREEN)

    arrow(ax, (21.2, 41), (28.8, 41))
    arrow(ax, (21.2, 31), (28.8, 30))
    arrow(ax, (21.2, 21), (28.8, 26.5))
    arrow(ax, (21.2, 11), (28.8, 12))
    arrow(ax, (39, 36.8), (39, 34.4))
    label(ax, 44, 35.6, "approved", GREY, 7.5)
    arrow(ax, (49.2, 29), (56.8, 31), color=TEAL)
    arrow(ax, (49.2, 33.5), (56.8, 42.5), color=TEAL)
    arrow(ax, (72.2, 32), (79.8, 33), color=ORANGE, both=True)
    arrow(ax, (88.5, 26.8), (88.5, 18.2), color=ORANGE, both=True)
    arrow(ax, (88.5, 57.3), (88.5, 43.2), color=GREEN, both=True)
    label(ax, 94, 50.4, "questions\nand answers", GREEN, 7.5)
    arrow(ax, (49.2, 12), (79.8, 29), color=BLUE, rad=0.15)
    label(ax, 68, 11, "posts from\nthe groups", BLUE, 7.5)

    label(ax, 1, 63.5, "Figure 4.1. Architecture of the knowledge base", INK, 11, "left", True)
    save(fig, "architecture.png")


def search_flow():
    fig, ax = canvas(13, 8.4)  # y 0..64.6
    box(ax, 2, 40, 14, 10, "1. A student\nasks a question", GREEN_L, GREEN, size=9.5)
    box(ax, 21, 40, 14, 10, "2. The question is\nturned into\nnumbers (vector)", BLUE_L, BLUE, size=9)
    box(ax, 41, 50, 17, 8, "3a. Find passages\nwith similar meaning", TEAL_L, TEAL, size=9)
    box(ax, 41, 32, 17, 8, "3b. Find passages\nwith the same words", TEAL_L, TEAL, size=9)
    box(ax, 63, 40, 14, 10, "4. Merge the two\nlists (best of\nboth)", BLUE_L, BLUE, size=9)
    box(ax, 82, 40, 16, 10, "5. Keep the\nbest passages", BLUE_L, BLUE, size=9.5)
    arrow(ax, (16.2, 45), (20.8, 45))
    arrow(ax, (35.2, 47.5), (40.8, 53))
    arrow(ax, (35.2, 42.5), (40.8, 37))
    arrow(ax, (58.2, 54), (66, 50.3))
    arrow(ax, (58.2, 36), (66, 39.7))
    arrow(ax, (77.2, 45), (81.8, 45))

    box(ax, 33, 3, 34, 9, "6. Do the passages answer the question?\nLook at the best similarity (0 to 1)", ORANGE_L, ORANGE,
        size=9.5, bold=True)
    arrow(ax, (90, 39.6), (67.2, 10), rad=-0.15)
    box(ax, 1, 3, 25, 9, "7a. 0.70 or more:\naccept without a check\nconfidence = high", GREEN_L, GREEN, size=9)
    box(ax, 74, 3, 25, 9, "7b. Below 0.45:\nreject without a check\nconfidence = low", RED_L, RED, size=9)
    box(ax, 28, 19, 44, 9, "7c. In between: a small language model reads the\nfirst three passages and answers YES or NO",
        BLUE_L, BLUE, size=8.5)
    arrow(ax, (32.8, 7.5), (26.4, 7.5), color=GREEN)
    label(ax, 29.6, 10.3, "strong", GREEN)
    arrow(ax, (67.2, 5.5), (73.8, 5.5), color=RED)
    label(ax, 70.5, 8.3, "weak", RED)
    arrow(ax, (50, 12.4), (50, 18.8), color=BLUE)
    label(ax, 54, 15.6, "unclear", BLUE, ha="left")
    label(ax, 50, 0, "YES means confidence high. NO means confidence low. A chatbot should answer only when the confidence is high.", INK, 8.5)
    label(ax, 1, 62, "Figure 3.2. How a question is searched and checked", INK, 11, "left", True)
    save(fig, "search-flow.png")


def lifecycle():
    fig, ax = canvas(13, 4.6)  # y 0..35.4
    steps = [("1. Collect\nthe source\n(official file\nor page)", GREY_L, GREY),
             ("2. Write the\ndocument\n(status: draft)", BLUE_L, BLUE),
             ("3. A person\nchecks it against\nthe source", BLUE_L, BLUE),
             ("4. Verified:\nit becomes\nsearchable", GREEN_L, GREEN),
             ("5. Re-check\nbefore its\ndeadline", ORANGE_L, ORANGE),
             ("6. Update it,\nor retire it\n(deprecated)", GREY_L, GREY)]
    w, gap = 14.2, 2.6
    x = 1.5
    centers = []
    for i, (text, fc, ec) in enumerate(steps):
        box(ax, x, 15, w, 14, text, fc, ec, size=9)
        centers.append(x + w / 2)
        if i:
            arrow(ax, (x - gap + 0.2, 22), (x - 0.2, 22))
        x += w + gap
    # the loop goes below the boxes: from step 5 back to step 3
    ax.plot([centers[4], centers[4], centers[2], centers[2]], [14.6, 9, 9, 14.6], color=ORANGE, lw=1.5, solid_capstyle="round")
    arrow(ax, (centers[2], 10), (centers[2], 14.6), color=ORANGE)
    label(ax, (centers[2] + centers[4]) / 2, 5.5, "if the information changed, check it again", ORANGE, 8.5)
    label(ax, 1, 33, "Figure 3.1. Life cycle of a document", INK, 11, "left", True)
    save(fig, "document-lifecycle.png")


if __name__ == "__main__":
    architecture()
    search_flow()
    lifecycle()
    print("figures written to", OUT)
