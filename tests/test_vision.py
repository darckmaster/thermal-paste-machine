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

def _coins_autour(cx, cy, demi=10) -> np.ndarray:
    """Les 4 coins d'un carré centré en (cx, cy), dans l'ordre horaire OpenCV.

    Factorisé hors de _marqueurs_synthetiques() pour être réutilisable par les
    tests qui ajoutent d'autres marqueurs synthétiques (ex. zone de dépose).
    """
    return np.array([
        [cx - demi, cy - demi],  # haut-gauche
        [cx + demi, cy - demi],  # haut-droit
        [cx + demi, cy + demi],  # bas-droit
        [cx - demi, cy + demi],  # bas-gauche
    ], dtype=np.float32)


def _marqueurs_synthetiques() -> dict:
    """Crée un dict de marqueurs synthétiques à des positions pixel connues.

    Les centres sont placés aux 4 coins d'un rectangle dans une image 600×400 px,
    en respectant la disposition physique relevée le 2026-08-01
    (voir modules/vision.py::_plateau_corner_positions_mm) :
        ID 3 → centre (100, 50)   → coin haut-gauche (= origine du repère mm)
        ID 0 → centre (500, 50)   → coin haut-droit
        ID 1 → centre (500, 350)  → coin bas-droit
        ID 2 → centre (100, 350)  → coin bas-gauche

    Le repère mm ayant lui aussi son Y dirigé vers le bas, un y pixel petit (50)
    correspond bien à un y mm petit (0) : pixels et mm vont dans le même sens.

    Chaque marqueur est représenté par 4 coins autour de son centre (±10 px).
    """
    return {
        2: _coins_autour(100, 350),
        3: _coins_autour(100, 50),
        0: _coins_autour(500, 50),
        1: _coins_autour(500, 350),
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

    x, y = vision.pixel_to_mm(100, 50, H)
    assert abs(x - 0) < tolerance and abs(y - 0) < tolerance, \
        f"ID 3 (haut-gauche, origine) attendu (0, 0), obtenu ({x:.1f}, {y:.1f})"

    x, y = vision.pixel_to_mm(100, 350, H)
    assert abs(x - 0) < tolerance and abs(y - WORK_AREA_HEIGHT_MM) < tolerance, \
        f"ID 2 (bas-gauche) attendu (0, {WORK_AREA_HEIGHT_MM}), obtenu ({x:.1f}, {y:.1f})"

    x, y = vision.pixel_to_mm(500, 350, H)
    assert abs(x - WORK_AREA_WIDTH_MM) < tolerance and abs(y - WORK_AREA_HEIGHT_MM) < tolerance, \
        f"ID 1 (bas-droit) attendu ({WORK_AREA_WIDTH_MM}, {WORK_AREA_HEIGHT_MM}), " \
        f"obtenu ({x:.1f}, {y:.1f})"

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


def test_warp_image_orientation_non_miroir(vision: VisionProcessor) -> None:
    """L'image redressée ne doit PAS être retournée verticalement par rapport à la photo.

    Régression du miroir vertical corrigé le 2026-08-01 : tant que le repère mm avait
    son Y dirigé vers le HAUT alors que les lignes d'une image se numérotent vers le
    BAS, warp_image() renvoyait le haut de la photo en bas de l'image redressée. Le bug
    était invisible sur un plateau à peu près symétrique, d'où sa longévité (présent
    depuis la Phase 2). Le repère mm descend désormais comme l'image, ce qui l'élimine.

    Principe du test : une photo blanche en haut / noire en bas doit rester blanche en
    haut / noire en bas une fois redressée.
    """
    marqueurs = _marqueurs_synthetiques()
    H = vision.compute_homography(marqueurs)

    # Photo source 600×400 : moitié HAUTE blanche (255), moitié BASSE noire (0)
    image_source = np.zeros((400, 600, 3), dtype=np.uint8)
    image_source[:200, :] = 255

    # Redresser sur un canevas carré ; les 4 marqueurs couvrent toute la photo utile
    taille = 192
    warpee = vision.warp_image(image_source, H, (taille, taille))

    moitie_haute = warpee[: taille // 2].mean()
    moitie_basse = warpee[taille // 2 :].mean()

    assert moitie_haute > moitie_basse, (
        f"image redressée retournée verticalement : moitié haute {moitie_haute:.1f} "
        f"vs moitié basse {moitie_basse:.1f} — la bande blanche du haut de la photo "
        f"ne doit pas ressortir en bas"
    )


def test_compute_homography_approx_deux_marqueurs(vision: VisionProcessor) -> None:
    """Avec seulement 2 marqueurs (ID3 haut-gauche, ID0 haut-droit), leurs centres
    doivent mapper vers leurs positions mm connues (±1 mm), comme compute_homography()
    mais sans les IDs du bas (1 et 2) — c'est le cas réel de la caméra Geeetech."""
    marqueurs = {3: _coins_autour(100, 70), 0: _coins_autour(500, 65)}
    H = vision.compute_homography_approx(marqueurs)

    tolerance = 1.0
    x, y = vision.pixel_to_mm(100, 70, H)
    assert abs(x - 0) < tolerance and abs(y - 0) < tolerance, \
        f"ID3 (haut-gauche, origine) attendu (0, 0), obtenu ({x:.1f}, {y:.1f})"

    x, y = vision.pixel_to_mm(500, 65, H)
    assert abs(x - WORK_AREA_WIDTH_MM) < tolerance and abs(y - 0) < tolerance, \
        f"ID0 (haut-droit) attendu ({WORK_AREA_WIDTH_MM}, 0), obtenu ({x:.1f}, {y:.1f})"


def test_compute_homography_approx_trois_marqueurs(vision: VisionProcessor) -> None:
    """Avec 3 marqueurs (sous-ensemble de _marqueurs_synthetiques), doit aussi fonctionner
    (ajustement par moindres carrés plutôt que solution exacte à 2 points)."""
    marqueurs = _marqueurs_synthetiques()
    del marqueurs[1]  # n'en garder que 3 : IDs 0, 2, 3 (on retire le coin bas-droit)

    H = vision.compute_homography_approx(marqueurs)
    x, y = vision.pixel_to_mm(100, 350, H)  # centre du marqueur ID2 (bas-gauche)

    tolerance = 1.0
    assert abs(x - 0) < tolerance and abs(y - WORK_AREA_HEIGHT_MM) < tolerance, \
        f"ID2 (bas-gauche) attendu (0, {WORK_AREA_HEIGHT_MM}), obtenu ({x:.1f}, {y:.1f})"


def test_compute_homography_approx_un_seul_marqueur_leve_erreur(vision: VisionProcessor) -> None:
    """compute_homography_approx() doit lever ValueError avec moins de 2 marqueurs."""
    marqueurs = {0: _coins_autour(100, 350)}

    with pytest.raises(ValueError):
        vision.compute_homography_approx(marqueurs)


def test_deposit_zone_bounds_mm(vision: VisionProcessor) -> None:
    """deposit_zone_bounds_mm() doit retourner les bornes mm cohérentes avec
    pixel_to_mm() appliqué directement aux centres des marqueurs 4 et 5."""
    marqueurs = _marqueurs_synthetiques()
    H = vision.compute_homography(marqueurs)

    # Marqueurs de zone à des positions pixel arbitraires (pas des coins de la zone de travail)
    marqueurs[4] = _coins_autour(200, 300)
    marqueurs[5] = _coins_autour(400, 100)

    x_min, y_min, x_max, y_max = vision.deposit_zone_bounds_mm(marqueurs, H)

    x4, y4 = vision.pixel_to_mm(200, 300, H)
    x5, y5 = vision.pixel_to_mm(400, 100, H)
    assert x_min == pytest.approx(min(x4, x5), abs=0.05)
    assert y_min == pytest.approx(min(y4, y5), abs=0.05)
    assert x_max == pytest.approx(max(x4, x5), abs=0.05)
    assert y_max == pytest.approx(max(y4, y5), abs=0.05)


def test_deposit_zone_bounds_mm_marqueurs_manquants(vision: VisionProcessor) -> None:
    """deposit_zone_bounds_mm() doit lever ValueError si un des deux marqueurs
    de zone (IDs 4/5 par défaut) est absent."""
    marqueurs = _marqueurs_synthetiques()  # pas de marqueurs 4/5
    H = vision.compute_homography(marqueurs)

    with pytest.raises(ValueError):
        vision.deposit_zone_bounds_mm(marqueurs, H)


def test_warp_region_dimensions_correctes(vision: VisionProcessor) -> None:
    """warp_region() doit retourner une image aux dimensions exactes demandées."""
    marqueurs = _marqueurs_synthetiques()
    H = vision.compute_homography(marqueurs)
    image_source = np.full((400, 600, 3), 128, dtype=np.uint8)

    result = vision.warp_region(image_source, H, (10.0, 5.0), 2.0, (100, 80))

    assert result.shape == (80, 100, 3), f"Dimensions attendues (80, 100, 3), obtenues {result.shape}"


def test_warp_region_pas_de_zone_noire_sur_bord_negatif(vision: VisionProcessor) -> None:
    """Régression du bug du 2026-07-30 (repli caméra Geeetech, écran "Tracer le chemin
    de dépose" entièrement noir après validation de la photo).

    Mécanisme exact identifié : avec compute_homography_approx() (2-3 marqueurs, pas de
    correction de perspective), un point proche du bord du plateau peut ressortir avec
    une coordonnée mm légèrement NÉGATIVE (imprécision normale de l'approximation, pas un
    bug de compute_homography_approx elle-même). L'ancien code faisait alors
    `warped[..., int(x_min * échelle):...]` sur un canevas dimensionné pour tout le
    WORK_AREA : un index négatif se lit en Python depuis la FIN du tableau — donc depuis
    l'autre bout du plateau, jamais photographié par la caméra Geeetech → image noire.

    warp_region() élimine ce risque : il ne construit jamais de canevas WORK_AREA, donc
    aucun index ne peut y "boucler" depuis la fin.
    """
    # Homographie approx réaliste (légère rotation caméra, 2 marqueurs seulement) :
    # ID3 = haut-gauche, ID0 = haut-droit — les deux marqueurs du haut, seuls visibles
    # par la caméra Geeetech (disposition relevée le 2026-08-01)
    markers = {
        3: np.array([[90, 60], [110, 58], [112, 78], [92, 80]], dtype=np.float32),
        0: np.array([[490, 55], [510, 53], [512, 73], [492, 75]], dtype=np.float32),
    }
    H = vision.compute_homography_approx(markers)

    # Point proche du bord x=0 du plateau : ressort en mm légèrement négatif avec cette
    # homographie approx (vérifié : x ≈ -2.9 mm) — reproduit le cas déclencheur du bug
    x_min, y_min = vision.pixel_to_mm(95, 65, H)
    assert x_min < 0, "prérequis du test : ce point doit ressortir en mm négatif avec l'homographie approx"

    px_per_mm = 8.0
    old_px_min = int(x_min * px_per_mm)
    work_area_canvas_width = int(WORK_AREA_WIDTH_MM * px_per_mm)
    assert old_px_min < 0 and work_area_canvas_width + old_px_min > 0, (
        "prérequis du test : l'ancien index doit être négatif ET boucler vers une position "
        "valide (mais fausse) du canevas — sinon Python lèverait une IndexError au lieu de boucler"
    )

    # Image source : fond blanc, avec une bande NOIRE côté "fin du tableau" (colonnes
    # hautes) pour simuler la partie du plateau jamais photographiée par la caméra —
    # c'est exactement là que l'ancien code irait lire par erreur (bouclage négatif)
    image = np.full((200, 600, 3), 255, dtype=np.uint8)
    image[:, 550:] = 0

    output_size = (40, 40)
    crop = vision.warp_region(image, H, (x_min, y_min), px_per_mm, output_size)

    assert crop.mean() > 100, (
        f"crop quasi noir (moyenne {crop.mean():.1f}/255) — warp_region a échantillonné "
        f"la mauvaise zone, comme le faisait l'ancien code avec l'index négatif"
    )


def test_warp_image_retourne_numpy_array(vision: VisionProcessor) -> None:
    """warp_image() doit retourner un np.ndarray."""
    marqueurs = _marqueurs_synthetiques()
    H = vision.compute_homography(marqueurs)
    image_source = np.full((400, 600, 3), 128, dtype=np.uint8)

    result = vision.warp_image(image_source, H, (300, 200))

    assert isinstance(result, np.ndarray), "warp_image() doit retourner un np.ndarray"
