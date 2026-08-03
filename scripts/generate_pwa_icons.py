"""
Génère les icônes de la PWA (192, 512, apple-touch-icon) à partir d'un dessin
vectoriel simple (silhouette de grue de chantier), cohérent avec le thème
sombre/jaune de l'application (mêmes couleurs que `utils/helpers.py`).

Ne dépend d'aucune police/emoji externe : tout est dessiné avec des formes
géométriques basiques (Pillow), donc reproductible sur n'importe quelle
machine. À relancer si les couleurs du thème changent.

Usage : python scripts/generate_pwa_icons.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

BG = "#0b0c11"
ACCENT = "#eab308"
ACCENT_2 = "#facc15"

OUT_DIR = Path(__file__).resolve().parent.parent / "static" / "icons"


def dessiner_icone(taille: int, marge_ratio: float = 0.16) -> Image.Image:
    """Dessine la silhouette de grue centrée sur un fond arrondi, à `taille` px."""
    img = Image.new("RGB", (taille, taille), BG)
    draw = ImageDraw.Draw(img)

    # Fond avec coins arrondis (cohérent avec le style "carte" de l'app)
    rayon = int(taille * 0.22)
    draw.rounded_rectangle([0, 0, taille - 1, taille - 1], radius=rayon, fill=BG)

    m = int(taille * marge_ratio)
    zone = taille - 2 * m  # zone utile pour le dessin

    # Mât vertical de la grue
    mat_largeur = max(2, int(zone * 0.09))
    mat_x = m + int(zone * 0.28)
    mat_haut = m + int(zone * 0.08)
    mat_bas = m + int(zone * 0.92)
    draw.rectangle([mat_x, mat_haut, mat_x + mat_largeur, mat_bas], fill=ACCENT)

    # Base (socle)
    socle_h = max(2, int(zone * 0.06))
    draw.rectangle(
        [mat_x - int(zone * 0.12), mat_bas - socle_h, mat_x + mat_largeur + int(zone * 0.12), mat_bas],
        fill=ACCENT,
    )

    # Flèche horizontale (boom) + petit contrepoids à l'arrière
    fleche_h = max(2, int(zone * 0.07))
    fleche_y = mat_haut
    fleche_avant_x = m + int(zone * 0.94)
    fleche_arriere_x = mat_x - int(zone * 0.16)
    draw.rectangle([fleche_arriere_x, fleche_y, fleche_avant_x, fleche_y + fleche_h], fill=ACCENT_2)
    # Contrepoids
    draw.rectangle(
        [fleche_arriere_x - int(zone * 0.05), fleche_y, fleche_arriere_x + int(zone * 0.02), fleche_y + int(zone * 0.14)],
        fill=ACCENT_2,
    )

    # Câble + charge suspendue
    cable_x = m + int(zone * 0.80)
    cable_haut = fleche_y + fleche_h
    cable_bas = m + int(zone * 0.55)
    draw.line([cable_x, cable_haut, cable_x, cable_bas], fill=ACCENT_2, width=max(1, int(zone * 0.02)))
    charge = int(zone * 0.10)
    draw.rectangle(
        [cable_x - charge // 2, cable_bas, cable_x + charge // 2, cable_bas + charge],
        fill=ACCENT,
    )

    return img


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for taille, nom in [(512, "icon-512.png"), (192, "icon-192.png")]:
        dessiner_icone(taille).save(OUT_DIR / nom)
        print("Généré :", OUT_DIR / nom)

    # apple-touch-icon : iOS n'aime pas la transparence et applique déjà ses
    # propres coins arrondis -> marge un peu plus large, coins non arrondis ici.
    apple = Image.new("RGB", (180, 180), BG)
    ImageDraw.Draw(apple).rectangle([0, 0, 179, 179], fill=BG)
    icone_apple = dessiner_icone(180, marge_ratio=0.20)
    apple.paste(icone_apple, (0, 0))
    apple_path = OUT_DIR / "apple-touch-icon.png"
    apple.save(apple_path)
    print("Généré :", apple_path)


if __name__ == "__main__":
    main()
