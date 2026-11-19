"""Draw the figures of the project report into docs/images/ (architecture, search flow, document life cycle).

Each figure is drawn twice: with English text for the English report, and with French text and French
file names for the French report.
"""

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

TEXT = {
    "en": {
        "files": ("architecture.png", "search-flow.png", "document-lifecycle.png"),
        "arch_title": "Figure 4.1. Architecture of the knowledge base",
        "panels": ("Sources of information", "Collection and processing", "Storage", "Service"),
        "sources": ("Official documents\n(notices, PDFs, scans)", "University website", "Spreadsheets\n(directories, bus)",
                    "Official WhatsApp\ngroups (admins only)"),
        "repo": "GitHub repository\nreviewed documents,\ntests, automation",
        "pipe": "Python pipeline\ncheck, split into passages,\nconvert to vectors, index",
        "listener": "WhatsApp listener\n(free web host)",
        "cloud": "Cloudinary\noriginal files, images",
        "neon": "Neon database\ndocuments, passages\nand vectors",
        "worker": "Cloudflare Worker\npublic interface:\nsearch, answer check,\nkeys, feedback",
        "ai": "Workers AI\nvectors and\nanswer check",
        "bots": "Student chatbots\n(any program)",
        "approved": "approved",
        "qa": "questions\nand answers",
        "posts": "posts from\nthe groups",
        "flow_title": "Figure 3.2. How a question is searched and checked",
        "s1": "1. A student\nasks a question",
        "s2": "2. The question is\nturned into\nnumbers (vector)",
        "s3a": "3a. Find passages\nwith similar meaning",
        "s3b": "3b. Find passages\nwith the same words",
        "s4": "4. Merge the two\nlists (best of\nboth)",
        "s5": "5. Keep the\nbest passages",
        "s6": "6. Do the passages answer the question?\nLook at the best similarity (0 to 1)",
        "s7a": "7a. 0.70 or more:\naccept without a check\nconfidence = high",
        "s7b": "7b. Below 0.45:\nreject without a check\nconfidence = low",
        "s7c": "7c. In between: a small language model reads the\nfirst three passages and answers YES or NO",
        "strong": "strong",
        "weak": "weak",
        "unclear": "unclear",
        "foot": "YES means confidence high. NO means confidence low. A chatbot should answer only when the confidence is high.",
        "life_title": "Figure 3.1. Life cycle of a document",
        "steps": ("1. Collect\nthe source\n(official file\nor page)", "2. Write the\ndocument\n(status: draft)",
                  "3. A person\nchecks it against\nthe source", "4. Verified:\nit becomes\nsearchable",
                  "5. Re-check\nbefore its\ndeadline", "6. Update it,\nor retire it\n(deprecated)"),
        "loop": "if the information changed, check it again",
    },
    "fr": {
        "files": ("architecture-systeme.png", "parcours-recherche.png", "cycle-de-vie-document.png"),
        "arch_title": "Figure 4.1. Architecture de la base de connaissances",
        "panels": ("Sources d'information", "Collecte et traitement", "Stockage", "Service"),
        "sources": ("Documents officiels\n(avis, PDF, scans)", "Site web de\nl'université", "Tableurs\n(annuaires, bus)",
                    "Groupes WhatsApp\nofficiels (admins\nseulement)"),
        "repo": "Dépôt GitHub\ndocuments relus,\ntests, automatisation",
        "pipe": "Chaîne Python\nvérifier, découper en passages,\nconvertir en vecteurs, indexer",
        "listener": "Lecteur WhatsApp\n(hébergeur gratuit)",
        "cloud": "Cloudinary\nfichiers originaux,\nimages",
        "neon": "Base Neon\ndocuments, passages\net vecteurs",
        "worker": "Worker Cloudflare\ninterface publique :\nrecherche, vérification\ndes réponses, clés,\nretours",
        "ai": "Workers AI\nvecteurs et\nvérification",
        "bots": "Chatbots des\nétudiants\n(tout programme)",
        "approved": "approuvé",
        "qa": "questions\net réponses",
        "posts": "messages\ndes groupes",
        "flow_title": "Figure 3.2. Comment une question est cherchée et vérifiée",
        "s1": "1. Un étudiant\npose une question",
        "s2": "2. La question est\ntransformée en\nnombres (vecteur)",
        "s3a": "3a. Chercher les passages\nde sens proche",
        "s3b": "3b. Chercher les passages\naux mêmes mots",
        "s4": "4. Fusionner les\ndeux listes (le\nmeilleur des deux)",
        "s5": "5. Garder les\nmeilleurs passages",
        "s6": "6. Les passages répondent-ils à la question ?\nVoir la meilleure similarité (0 à 1)",
        "s7a": "7a. 0,70 ou plus :\naccepter sans vérification\nconfiance = élevée",
        "s7b": "7b. Moins de 0,45 :\nrejeter sans vérification\nconfiance = faible",
        "s7c": "7c. Entre les deux : un petit modèle de langage lit les\ntrois premiers passages et répond OUI ou NON",
        "strong": "forte",
        "weak": "faible",
        "unclear": "incertaine",
        "foot": "OUI = confiance élevée. NON = confiance faible. Un chatbot ne doit répondre que si la confiance est élevée.",
        "life_title": "Figure 3.1. Cycle de vie d'un document",
        "steps": ("1. Collecter\nla source\n(fichier ou page\nofficiel)", "2. Rédiger le\ndocument\n(statut : draft)",
                  "3. Une personne\nle compare avec\nla source", "4. Vérifié :\nil devient\nconsultable",
                  "5. Revérifier\navant son\néchéance", "6. Mettre à jour,\nou retirer\n(deprecated)"),
        "loop": "si l'information a changé, la vérifier de nouveau",
    },
}


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


def architecture(T):
    fig, ax = canvas(13, 8.6)  # x 0..100, y 0..66.2
    panel(ax, 1, 3, 22, 49, GREY)
    panel(ax, 27, 3, 24, 49, BLUE)
    panel(ax, 55, 3, 19, 49, TEAL)
    panel(ax, 78, 3, 21, 49, ORANGE)
    for (x, col), name in zip(((2.5, GREY), (28.5, BLUE), (56.5, TEAL), (79.5, ORANGE)), T["panels"], strict=True):
        label(ax, x, 49.2, name, col, 10, "left", True)

    for text, y in zip(T["sources"], (37, 27, 17, 7), strict=True):
        box(ax, 3, y, 18, 8, text, GREY_L, GREY)

    box(ax, 29, 37, 20, 8, T["repo"], BLUE_L, BLUE)
    box(ax, 29, 24.5, 20, 9.5, T["pipe"], BLUE_L, BLUE)
    box(ax, 29, 8, 20, 8, T["listener"], BLUE_L, BLUE)

    box(ax, 57, 40, 15, 7, T["cloud"], TEAL_L, TEAL)
    box(ax, 57, 27, 15, 10, T["neon"], TEAL_L, TEAL)

    box(ax, 80, 27, 17, 16, T["worker"], ORANGE_L, ORANGE)
    box(ax, 80, 8, 17, 10, T["ai"], ORANGE_L, ORANGE)
    box(ax, 80, 56, 17, 9, T["bots"], GREEN_L, GREEN)

    arrow(ax, (21.2, 41), (28.8, 41))
    arrow(ax, (21.2, 31), (28.8, 30))
    arrow(ax, (21.2, 21), (28.8, 26.5))
    arrow(ax, (21.2, 11), (28.8, 12))
    arrow(ax, (39, 36.8), (39, 34.4))
    label(ax, 44.5, 35.6, T["approved"], GREY, 7.5)
    arrow(ax, (49.2, 29), (56.8, 31), color=TEAL)
    arrow(ax, (49.2, 33.5), (56.8, 42.5), color=TEAL)
    arrow(ax, (72.2, 32), (79.8, 33), color=ORANGE, both=True)
    arrow(ax, (88.5, 26.8), (88.5, 18.2), color=ORANGE, both=True)
    arrow(ax, (88.5, 55.8), (88.5, 43.2), color=GREEN, both=True)
    label(ax, 94, 50, T["qa"], GREEN, 7.5)
    arrow(ax, (49.2, 12), (79.8, 29), color=BLUE, rad=0.15)
    label(ax, 68, 11, T["posts"], BLUE, 7.5)

    label(ax, 1, 63.5, T["arch_title"], INK, 11, "left", True)
    save(fig, T["files"][0])


def search_flow(T):
    fig, ax = canvas(13, 8.4)  # y 0..64.6
    box(ax, 2, 40, 14, 10, T["s1"], GREEN_L, GREEN, size=9)
    box(ax, 21, 40, 14, 10, T["s2"], BLUE_L, BLUE, size=8.5)
    box(ax, 41, 50, 17, 8, T["s3a"], TEAL_L, TEAL, size=8.5)
    box(ax, 41, 32, 17, 8, T["s3b"], TEAL_L, TEAL, size=8.5)
    box(ax, 63, 40, 14, 10, T["s4"], BLUE_L, BLUE, size=8.5)
    box(ax, 82, 40, 16, 10, T["s5"], BLUE_L, BLUE, size=9)
    arrow(ax, (16.2, 45), (20.8, 45))
    arrow(ax, (35.2, 47.5), (40.8, 53))
    arrow(ax, (35.2, 42.5), (40.8, 37))
    arrow(ax, (58.2, 54), (66, 50.3))
    arrow(ax, (58.2, 36), (66, 39.7))
    arrow(ax, (77.2, 45), (81.8, 45))

    box(ax, 31, 3, 38, 9, T["s6"], ORANGE_L, ORANGE, size=8.5, bold=True)
    arrow(ax, (90, 39.6), (69.2, 10), rad=-0.15)
    box(ax, 1, 3, 24, 9, T["s7a"], GREEN_L, GREEN, size=8.5)
    box(ax, 75, 3, 24, 9, T["s7b"], RED_L, RED, size=8.5)
    box(ax, 26, 19, 48, 9, T["s7c"], BLUE_L, BLUE, size=8.5)
    arrow(ax, (30.8, 7.5), (25.8, 7.5), color=GREEN)
    label(ax, 28.3, 10.2, T["strong"], GREEN)
    arrow(ax, (69.2, 7.5), (74.2, 7.5), color=RED)
    label(ax, 71.7, 10.2, T["weak"], RED)
    arrow(ax, (50, 12.4), (50, 18.8), color=BLUE)
    label(ax, 54, 15.6, T["unclear"], BLUE, ha="left")
    label(ax, 50, 0, T["foot"], INK, 8.5)
    label(ax, 1, 62, T["flow_title"], INK, 11, "left", True)
    save(fig, T["files"][1])


def lifecycle(T):
    fig, ax = canvas(13, 4.6)  # y 0..35.4
    colors = ((GREY_L, GREY), (BLUE_L, BLUE), (BLUE_L, BLUE), (GREEN_L, GREEN), (ORANGE_L, ORANGE), (GREY_L, GREY))
    w, gap = 14.2, 2.6
    x = 1.5
    centers = []
    for i, (text, (fc, ec)) in enumerate(zip(T["steps"], colors, strict=True)):
        box(ax, x, 15, w, 14, text, fc, ec, size=9)
        centers.append(x + w / 2)
        if i:
            arrow(ax, (x - gap + 0.2, 22), (x - 0.2, 22))
        x += w + gap
    # the loop goes below the boxes: from step 5 back to step 3
    ax.plot([centers[4], centers[4], centers[2], centers[2]], [14.6, 9, 9, 14.6], color=ORANGE, lw=1.5, solid_capstyle="round")
    arrow(ax, (centers[2], 10), (centers[2], 14.6), color=ORANGE)
    label(ax, (centers[2] + centers[4]) / 2, 5.5, T["loop"], ORANGE, 8.5)
    label(ax, 1, 33, T["life_title"], INK, 11, "left", True)
    save(fig, T["files"][2])


if __name__ == "__main__":
    for text in TEXT.values():
        architecture(text)
        search_flow(text)
        lifecycle(text)
    print("figures written to", OUT)
