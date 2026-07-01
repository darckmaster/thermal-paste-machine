import cv2
import numpy as np
import pytest

from modules.vision import VisionProcessor
from modules.config import (
    ARUCO_DICT_ID,
    ARUCO_MARKER_SIZE_MM,
    WORK_AREA_WIDTH_MM,
    WORK_AREA_HEIGHT_MM,
)


@pytest.fixture
def vision() -> VisionProcessor:
    """Fixture pytest : crée un VisionProcessor avec la config du projet."""
    return VisionProcessor(aruco_dict_id=ARUCO_DICT_ID, marker_real_size_mm=ARUCO_MARKER_SIZE_MM)


def _image_avec_marqueur(marker_id: int) -> np.ndarray:
    """Génère une image BGR synthétique contenant un marqueur ArUco centré sur fond blanc.

    Utilisée pour les tests unitaires — pas besoin de caméra ni de marqueurs physiques.
    """
    # Charger le dictionnaire pour générer les images de test
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

    # Générer l'image du marqueur seul (100×100 pixels)
    marker_img = cv2.aruco.generateImageMarker(aruco_dict, marker_id, 100)

    # Placer le marqueur au centre d'un fond blanc 300×300
    # La bordure blanche est importante : le détecteur ArUco a besoin d'espace autour du marqueur
    background = np.ones((300, 300), dtype=np.uint8) * 255
    background[100:200, 100:200] = marker_img

    # Convertir en BGR (3 canaux) — format attendu par detect_markers()
    return cv2.cvtColor(background, cv2.COLOR_GRAY2BGR)


def test_detection_marqueur_id0(vision: VisionProcessor) -> None:
    """detect_markers() doit détecter le marqueur ID 0 dans une image synthétique."""
    image = _image_avec_marqueur(marker_id=0)
    detected = vision.detect_markers(image)

    assert 0 in detected, "Le marqueur ID 0 doit être présent dans le résultat"


def test_detection_retourne_quatre_coins(vision: VisionProcessor) -> None:
    """Chaque marqueur détecté doit avoir exactement 4 coins de forme (4, 2)."""
    image = _image_avec_marqueur(marker_id=1)
    detected = vision.detect_markers(image)

    assert 1 in detected, "Le marqueur ID 1 doit être détecté"
    coins = detected[1]

    # (4, 2) = 4 coins × 2 coordonnées pixel (x, y)
    assert coins.shape == (4, 2), f"Forme attendue (4, 2), obtenue {coins.shape}"


def test_detection_image_vide_retourne_dict_vide(vision: VisionProcessor) -> None:
    """Sur une image sans marqueur, detect_markers() doit retourner un dict vide."""
    # Image entièrement blanche — aucun motif ArUco ne peut y être trouvé
    image_vide = np.ones((300, 300, 3), dtype=np.uint8) * 255
    detected = vision.detect_markers(image_vide)

    assert detected == {}, f"Aucun marqueur attendu sur fond blanc, obtenu : {detected}"


def test_detection_plusieurs_marqueurs(vision: VisionProcessor) -> None:
    """detect_markers() doit détecter plusieurs marqueurs dans la même image."""
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

    # Créer une grande image avec les marqueurs 0 et 1 côte à côte
    background = np.ones((300, 600), dtype=np.uint8) * 255
    background[100:200, 50:150] = cv2.aruco.generateImageMarker(aruco_dict, 0, 100)
    background[100:200, 450:550] = cv2.aruco.generateImageMarker(aruco_dict, 1, 100)

    image = cv2.cvtColor(background, cv2.COLOR_GRAY2BGR)
    detected = vision.detect_markers(image)

    assert 0 in detected, "Marqueur ID 0 non détecté dans l'image combinée"
    assert 1 in detected, "Marqueur ID 1 non détecté dans l'image combinée"


def test_init_dictionnaire_inconnu() -> None:
    """VisionProcessor doit lever ValueError si le dictionnaire n'est pas reconnu."""
    with pytest.raises(ValueError):
        VisionProcessor(aruco_dict_id="DICT_INEXISTANT")


# ---------------------------------------------------------------------------
# Fixture partagée pour les tests d'homographie (Session 2)
# ---------------------------------------------------------------------------

def _marqueurs_synthetiques() -> dict:
    """Crée un dict de marqueurs synthétiques à des positions pixel connues.

    Les centres sont placés aux 4 coins d'un rectangle dans une image 600×400 px,
    en respectant la convention réelle validée sur machine le 2026-07-01
    (voir modules/vision.py::compute_homography) :
        ID 0 → centre (100, 350)  → coin bas-gauche
        ID 1 → centre (100, 50)   → coin haut-gauche
        ID 2 → centre (500, 50)   → coin haut-droit
        ID 3 → centre (500, 350)  → coin bas-droit

    Chaque marqueur est représenté par 4 coins autour de son centre (±10 px).
    """
    def coins_autour(cx, cy, demi=10):
        # Les 4 coins d'un carré centré en (cx, cy), dans l'ordre horaire OpenCV
        return np.array([
            [cx - demi, cy - demi],  # haut-gauche
            [cx + demi, cy - demi],  # haut-droit
            [cx + demi, cy + demi],  # bas-droit
            [cx - demi, cy + demi],  # bas-gauche
        ], dtype=np.float32)

    return {
        0: coins_autour(100, 350),
        1: coins_autour(100, 50),
        2: coins_autour(500, 50),
        3: coins_autour(500, 350),
    }


def test_compute_homography_retourne_matrice_3x3(vision: VisionProcessor) -> None:
    """compute_homography() doit retourner une matrice numpy de forme (3, 3)."""
    marqueurs = _marqueurs_synthetiques()
    H = vision.compute_homography(marqueurs)

    assert isinstance(H, np.ndarray), "H doit être un np.ndarray"
    assert H.shape == (3, 3), f"H doit être (3, 3), obtenu {H.shape}"


def test_compute_homography_marqueurs_manquants(vision: VisionProcessor) -> None:
    """compute_homography() doit lever ValueError si un marqueur est absent."""
    marqueurs_incomplets = {0: np.zeros((4, 2)), 1: np.zeros((4, 2))}  # IDs 2 et 3 absents

    with pytest.raises(ValueError):
        vision.compute_homography(marqueurs_incomplets)


def test_pixel_to_mm_coins_de_la_zone(vision: VisionProcessor) -> None:
    """Les centres des marqueurs doivent mapper vers les coins de la zone de travail (±1 mm)."""
    marqueurs = _marqueurs_synthetiques()
    H = vision.compute_homography(marqueurs)

    # Tolérance : 1 mm (les centres synthétiques sont exacts, l'erreur vient des flottants)
    tolerance = 1.0

    x, y = vision.pixel_to_mm(100, 350, H)
    assert abs(x - 0) < tolerance and abs(y - 0) < tolerance, \
        f"ID 0 (bas-gauche) attendu (0, 0), obtenu ({x:.1f}, {y:.1f})"

    x, y = vision.pixel_to_mm(500, 350, H)
    assert abs(x - WORK_AREA_WIDTH_MM) < tolerance and abs(y - 0) < tolerance, \
        f"ID 3 (bas-droit) attendu ({WORK_AREA_WIDTH_MM}, 0), obtenu ({x:.1f}, {y:.1f})"

    x, y = vision.pixel_to_mm(300, 200, H)
    assert abs(x - WORK_AREA_WIDTH_MM / 2) < tolerance and abs(y - WORK_AREA_HEIGHT_MM / 2) < tolerance, \
        f"Centre attendu ({WORK_AREA_WIDTH_MM/2}, {WORK_AREA_HEIGHT_MM/2}), obtenu ({x:.1f}, {y:.1f})"


def test_warp_image_dimensions_correctes(vision: VisionProcessor) -> None:
    """warp_image() doit retourner une image aux dimensions exactes demandées."""
    marqueurs = _marqueurs_synthetiques()
    H = vision.compute_homography(marqueurs)

    # Image source quelconque (600×400, fond gris)
    image_source = np.full((400, 600, 3), 128, dtype=np.uint8)

    output_size = (300, 200)  # 2 px/mm sur une zone 150×100 mm
    image_warpee = vision.warp_image(image_source, H, output_size)

    assert image_warpee.shape == (200, 300, 3), \
        f"Dimensions attendues (200, 300, 3), obtenues {image_warpee.shape}"


def test_warp_image_retourne_numpy_array(vision: VisionProcessor) -> None:
    """warp_image() doit retourner un np.ndarray."""
    marqueurs = _marqueurs_synthetiques()
    H = vision.compute_homography(marqueurs)
    image_source = np.full((400, 600, 3), 128, dtype=np.uint8)

    result = vision.warp_image(image_source, H, (300, 200))

    assert isinstance(result, np.ndarray), "warp_image() doit retourner un np.ndarray"
