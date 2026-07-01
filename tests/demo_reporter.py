# Démonstration de modules/reporter.py — génération du PDF sans matériel.
# Utilise une image et un tracé synthétiques (pas besoin de caméra ni de machine),
# pour vérifier que le PDF se construit correctement (mise en page, texte, calculs).
#
# Utilisation :
#   python3 tests/demo_reporter.py

import sys
import os

# Permettre les imports depuis la racine du projet
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from modules.reporter import Reporter
from modules.config import WORK_AREA_WIDTH_MM, WORK_AREA_HEIGHT_MM


def image_synthetique() -> np.ndarray:
    """Crée une fausse photo de pièce (fond gris uni avec un rectangle plus clair).

    Le rectangle simule une pièce visible sur la photo — juste pour vérifier
    que l'image s'insère correctement dans le PDF, pas pour un test visuel réaliste.
    """
    # Image BGR 640x480, fond gris moyen (comme une photo de plateau vide)
    image = np.full((480, 640, 3), 100, dtype=np.uint8)
    # Rectangle plus clair au centre pour simuler la pièce
    image[140:340, 170:470] = (200, 200, 200)
    return image


def trace_synthetique() -> list:
    """Crée un tracé factice en forme de W, en coordonnées machine (mm).

    Reprend l'idée du test réel de la session précédente (tracé en W),
    à l'intérieur de la zone de travail réelle (151 x 104 mm).
    """
    largeur = WORK_AREA_WIDTH_MM
    hauteur = WORK_AREA_HEIGHT_MM
    # 5 points formant un W, répartis sur toute la largeur de la zone
    return [
        (largeur * 0.1, hauteur * 0.8),
        (largeur * 0.3, hauteur * 0.2),
        (largeur * 0.5, hauteur * 0.8),
        (largeur * 0.7, hauteur * 0.2),
        (largeur * 0.9, hauteur * 0.8),
    ]


def main():
    print("=" * 60)
    print("  Démonstration reporter.py — génération PDF (sans matériel)")
    print("=" * 60)

    reporter = Reporter()  # Crée le dossier reports/ si nécessaire
    image = image_synthetique()
    points_mm = trace_synthetique()

    # Génère le PDF avec un statut de succès et une quantité de pâte réaliste
    print("\n[1/1] Génération du PDF...")
    chemin = reporter.generate(
        image=image,
        points_mm=points_mm,
        quantity=0.05,      # mm d'axe E par mm de tracé (valeur d'exemple)
        status="Succes",
    )
    print(f"      ✓ PDF généré : {chemin}")
    print(f"      Taille du fichier : {os.path.getsize(chemin)} octets")
    print("\nOuvre ce fichier pour vérifier visuellement la mise en page.")


if __name__ == '__main__':
    main()
