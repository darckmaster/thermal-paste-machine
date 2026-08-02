import math

import cv2
import numpy as np
import pytest

from modules.vision import (
    VisionProcessor,
    detect_deposit_zones_mm,
    _candidate_pairs,
    _rectangle_from_diagonal,
    ANOMALIE_ANGLE,
    ANOMALIE_CONFLIT,
    ANOMALIE_DIAGONALE,
    ANOMALIE_INVERSEE,
)
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
        ID 3 → centre (100, 50)   → coin haut-gauche → mm (0, HAUTEUR)
        ID 0 → centre (500, 50)   → coin haut-droit  → mm (LARGEUR, HAUTEUR)
        ID 1 → centre (500, 350)  → coin bas-droit   → mm (LARGEUR, 0)
        ID 2 → centre (100, 350)  → coin bas-gauche  → mm (0, 0) = ORIGINE

    ⚠️ Depuis le lot C2bis, pixels et millimètres vont en sens OPPOSÉS en Y : un y
    pixel petit (50, le haut de l'image) correspond à un y mm grand (la hauteur du
    plateau). C'est le fait central de ce lot, et c'est ce que les trois warp_*
    compensent pour que l'opérateur voie quand même le plateau à l'endroit.

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

    x, y = vision.pixel_to_mm(100, 350, H)
    assert abs(x - 0) < tolerance and abs(y - 0) < tolerance, \
        f"ID 2 (bas-gauche, origine) attendu (0, 0), obtenu ({x:.1f}, {y:.1f})"

    x, y = vision.pixel_to_mm(100, 50, H)
    assert abs(x - 0) < tolerance and abs(y - WORK_AREA_HEIGHT_MM) < tolerance, \
        f"ID 3 (haut-gauche) attendu (0, {WORK_AREA_HEIGHT_MM}), obtenu ({x:.1f}, {y:.1f})"

    x, y = vision.pixel_to_mm(500, 50, H)
    assert abs(x - WORK_AREA_WIDTH_MM) < tolerance and abs(y - WORK_AREA_HEIGHT_MM) < tolerance, \
        f"ID 0 (haut-droit) attendu ({WORK_AREA_WIDTH_MM}, {WORK_AREA_HEIGHT_MM}), " \
        f"obtenu ({x:.1f}, {y:.1f})"

    x, y = vision.pixel_to_mm(300, 200, H)
    assert abs(x - WORK_AREA_WIDTH_MM / 2) < tolerance and abs(y - WORK_AREA_HEIGHT_MM / 2) < tolerance, \
        f"Centre attendu ({WORK_AREA_WIDTH_MM/2}, {WORK_AREA_HEIGHT_MM/2}), obtenu ({x:.1f}, {y:.1f})"


def test_boussole_de_la_convention_du_repere(vision: VisionProcessor) -> None:
    """LE test qui épingle la convention du repère en un seul endroit.

    Si quelqu'un remet un jour la convention en question — volontairement ou par
    accident — c'est ce test qui doit hurler en premier, avant les vingt autres qui
    ne feraient que constater les dégâts en aval. Il vérifie les quatre faits qui,
    ensemble, DÉFINISSENT le repère du plateau arrêté au lot C2bis :

        1. le marqueur 2 (bas-gauche) est l'origine        → (0, 0)
        2. le marqueur 3 (haut-gauche) est sur l'axe Y     → (0, hauteur), Y MONTE
        3. l'image redressée n'est pas en miroir           → l'opérateur voit juste
        4. la diagonale d'une zone saine descend à l'écran → dy < 0

    Les points 2 et 4 sont les deux faces d'une même pièce : retourner Y retourne le
    signe des diagonales de zone, et c'est là que se cachait tout le travail du lot.
    """
    marqueurs = _marqueurs_synthetiques()
    H = vision.compute_homography(marqueurs)

    # 1. Origine sur le marqueur 2
    x, y = vision.pixel_to_mm(100, 350, H)
    assert (x, y) == pytest.approx((0.0, 0.0), abs=1.0), \
        "l'origine du repère doit être le centre du marqueur 2 (bas-gauche)"

    # 2. Y monte : le marqueur 3, physiquement AU-DESSUS du 2, a un y mm PLUS GRAND
    _, y_haut = vision.pixel_to_mm(100, 50, H)
    assert y_haut > y, "l'axe Y doit croître vers le HAUT de l'image"
    assert y_haut == pytest.approx(WORK_AREA_HEIGHT_MM, abs=1.0)

    # 3. Pas de miroir : une photo blanche en haut reste blanche en haut
    photo = np.zeros((400, 600, 3), dtype=np.uint8)
    photo[:200, :] = 255
    redressee = vision.warp_image(photo, H, (192, 192))
    assert redressee[:96].mean() > redressee[96:].mean(), \
        "l'image redressée est en miroir vertical — l'opérateur verrait le plateau à l'envers"

    # 4. La diagonale d'une zone bien montée va vers la droite et vers le BAS de
    #    l'écran, donc dx > 0 et dy < 0 dans un repère dont le Y monte
    layout = detect_deposit_zones_mm(_zone_centers(4, 40.0, 100.0))
    zone = layout.zones[0]
    haut_gauche, _, bas_droit, _ = zone.corners_mm
    assert bas_droit[0] > haut_gauche[0], "le coin bas-droit est à droite du haut-gauche"
    assert bas_droit[1] < haut_gauche[1], \
        "le coin bas-droit doit avoir un y PLUS PETIT : c'est ce qui traduit Y montant"


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

    Régression du miroir vertical présent de la Phase 2 au 2026-08-01 : le repère mm
    avait alors son Y dirigé vers le HAUT alors que les lignes d'une image se numérotent
    vers le BAS, et warp_image() renvoyait le haut de la photo en bas de l'image
    redressée. Le bug était invisible sur un plateau à peu près symétrique, d'où sa
    longévité — il a été démasqué par le calcul, pas à l'œil.

    ⚠️ Le repère mm est REPASSÉ en Y montant au lot C2bis, pour aligner le logiciel sur
    le repère physique de la machine. Le miroir ne revient pas pour autant : ce sont
    désormais les trois warp_* qui retournent Y explicitement
    (y_pixel = (hauteur_mm − y_mm) × échelle). Ce test est le garde-fou de cette ligne —
    NE PAS L'AFFAIBLIR : c'est lui qui garantit que ce qu'on voit à l'écran est ce qui
    se passe sur le plateau, la règle posée par l'étudiant.

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
    mais sans les IDs du bas (1 et 2) — c'est le cas réel de la caméra Geeetech.

    Noter que l'ORIGINE du repère (le marqueur 2) n'est ici pas visible : sa position
    est extrapolée à partir de la taille de plateau configurée. C'est ce que signale
    PlateauReference.origin_extrapolated, et ce qui rend l'action M1 (mesurer le
    plateau) déterminante pour la précision réelle de la dépose.
    """
    marqueurs = {3: _coins_autour(100, 70), 0: _coins_autour(500, 65)}
    H = vision.compute_homography_approx(marqueurs)

    tolerance = 1.0
    x, y = vision.pixel_to_mm(100, 70, H)
    assert abs(x - 0) < tolerance and abs(y - WORK_AREA_HEIGHT_MM) < tolerance, \
        f"ID3 (haut-gauche) attendu (0, {WORK_AREA_HEIGHT_MM}), obtenu ({x:.1f}, {y:.1f})"

    x, y = vision.pixel_to_mm(500, 65, H)
    assert abs(x - WORK_AREA_WIDTH_MM) < tolerance and abs(y - WORK_AREA_HEIGHT_MM) < tolerance, \
        f"ID0 (haut-droit) attendu ({WORK_AREA_WIDTH_MM}, {WORK_AREA_HEIGHT_MM}), " \
        f"obtenu ({x:.1f}, {y:.1f})"


def test_compute_homography_approx_trois_marqueurs(vision: VisionProcessor) -> None:
    """Avec 3 marqueurs (sous-ensemble de _marqueurs_synthetiques), doit aussi fonctionner
    (ajustement par moindres carrés plutôt que solution exacte à 2 points)."""
    marqueurs = _marqueurs_synthetiques()
    del marqueurs[1]  # n'en garder que 3 : IDs 0, 2, 3 (on retire le coin bas-droit)

    H = vision.compute_homography_approx(marqueurs)
    x, y = vision.pixel_to_mm(100, 350, H)  # centre du marqueur ID2 (bas-gauche, origine)

    tolerance = 1.0
    assert abs(x - 0) < tolerance and abs(y - 0) < tolerance, \
        f"ID2 (bas-gauche, origine) attendu (0, 0), obtenu ({x:.1f}, {y:.1f})"


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


# ===========================================================================
# Zones de dépose — géométrie (lot A)
# ===========================================================================

# Format du produit utilisé par tous les tests de zone : 60 mm × 40 mm,
# soit une diagonale de sqrt(60² + 40²) ≈ 72,11 mm
PRODUIT_W = 60.0
PRODUIT_H = 40.0


def _zone_centers(id_tl: int, x: float, y: float,
                  w: float = PRODUIT_W, h: float = PRODUIT_H,
                  rotation_deg: float = 0.0) -> dict:
    """Fabrique les 2 centres de marqueurs d'une zone dont le coin haut-gauche
    est en (x, y), coordonnées mm du plateau (Y montant).

    Le marqueur haut-gauche porte l'ID id_tl, le bas-droit id_tl + 1.
    Le vecteur diagonale d'un rectangle tourné de θ est le vecteur diagonale non
    tourné, tourné de θ — c'est la relation utilisée à la reconstruction, appliquée
    ici dans l'autre sens pour fabriquer les données de test.

    ⚠️ Le vecteur diagonale non tourné vaut (w, −h) et non (w, +h) : depuis le lot
    C2bis l'axe Y du plateau monte, donc descendre le long de la hauteur fait
    DÉCROÎTRE y. Toutes les positions de zone des tests ci-dessous ont été remontées
    en conséquence, pour que les coins restent dans le plateau (0 → ~190 mm).
    """
    theta = math.radians(rotation_deg)
    dx = w * math.cos(theta) + h * math.sin(theta)
    dy = w * math.sin(theta) - h * math.cos(theta)
    return {id_tl: (x, y), id_tl + 1: (x + dx, y + dy)}


def _plateau_de_trois_zones() -> dict:
    """Trois zones bien montées, disposées comme sur le croquis de l'étudiant.

    IDs 4/5, 6/7 et 8/9. Point important : les tags 5 et 6 sont consécutifs, tout
    comme 7 et 8 — l'algorithme voit donc forcément les paires FANTÔMES (5,6) et
    (7,8), formées du coin bas-droit d'une zone et du coin haut-gauche de la
    suivante. C'est le cas d'ambiguïté réel que le filtrage par diagonale élimine.
    """
    centres = {}
    centres.update(_zone_centers(4, 10.0, 180.0))    # zone A, en haut à gauche
    centres.update(_zone_centers(6, 110.0, 180.0))   # zone B, en haut à droite
    centres.update(_zone_centers(8, 10.0, 110.0))    # zone C, en bas à gauche
    return centres


# ------------------------------------------------------------------ appariement

def test_candidate_pairs_ignore_les_marqueurs_du_plateau() -> None:
    """Les IDs 0-3 étant réservés aux coins du plateau, la paire (2,3) qu'ils
    forment ne doit jamais être proposée comme zone de dépose."""
    paires = _candidate_pairs([0, 1, 2, 3, 4, 5], first_zone_marker_id=4)

    assert (2, 3) not in paires, "les coins du plateau ne forment pas une zone"
    assert (4, 5) in paires


def test_candidate_pairs_enumere_les_recouvrements() -> None:
    """Un tag doit pouvoir apparaître dans deux paires candidates — c'est justement
    l'ambiguïté que les étapes suivantes lèveront."""
    paires = _candidate_pairs([4, 5, 6], first_zone_marker_id=4)

    assert (4, 5) in paires and (5, 6) in paires


# ------------------------------------------------------------------ cas nominal

def test_trois_zones_bien_montees_toutes_valides() -> None:
    """Sur un plateau conforme, les 3 zones réelles sont retenues et les 2 paires
    fantômes (5,6) et (7,8) sont éliminées par leur diagonale aberrante."""
    layout = detect_deposit_zones_mm(_plateau_de_trois_zones())

    assert len(layout.zones) == 3, f"3 zones attendues, obtenu : {layout.zones}"
    assert len(layout.valid_zones) == 3, "aucune anomalie ne devait être relevée"
    assert not layout.has_anomalies

    paires = {(z.id_top_left, z.id_bottom_right) for z in layout.zones}
    assert paires == {(4, 5), (6, 7), (8, 9)}

    # Tous les tags sont utilisés : aucun ne doit rester orphelin
    assert layout.unpaired_ids == []


def test_format_du_produit_deduit_sans_saisie_operateur() -> None:
    """Le format (w, h) doit être retrouvé à partir des seules diagonales, sans que
    l'opérateur n'ait rien à saisir."""
    layout = detect_deposit_zones_mm(_plateau_de_trois_zones())

    w, h = layout.product_size_mm
    assert w == pytest.approx(PRODUIT_W, abs=0.5)
    assert h == pytest.approx(PRODUIT_H, abs=0.5)
    assert layout.reference_diagonal_mm == pytest.approx(
        math.hypot(PRODUIT_W, PRODUIT_H), abs=0.5
    )


def test_coins_reconstruits_dans_l_ordre_horaire() -> None:
    """Les 4 coins doivent sortir dans l'ordre haut-gauche, haut-droit, bas-droit,
    bas-gauche — l'ordre attendu pour tracer le contour sans croisement."""
    layout = detect_deposit_zones_mm(_zone_centers(4, 10.0, 60.0))
    zone = layout.zones[0]

    haut_gauche, haut_droit, bas_droit, bas_gauche = zone.corners_mm

    assert haut_gauche == pytest.approx((10.0, 60.0), abs=0.1)
    assert haut_droit == pytest.approx((70.0, 60.0), abs=0.1)
    assert bas_droit == pytest.approx((70.0, 20.0), abs=0.1)
    assert bas_gauche == pytest.approx((10.0, 20.0), abs=0.1)

    # L'origine du repère de la zone est son coin BAS-gauche depuis le lot C2bis
    assert zone.origin_mm == pytest.approx((10.0, 20.0), abs=0.1)


# ------------------------------------------------------------------ anomalies

def test_zone_montee_a_l_envers_detectee() -> None:
    """Une zone dont les deux marqueurs sont intervertis pointe vers le haut-gauche
    au lieu du bas-droit : sa diagonale vaut (−, +) au lieu de (+, −)."""
    centres = _plateau_de_trois_zones()
    # Intervertir les positions des tags 8 et 9 — le montage est fait à l'envers
    centres[8], centres[9] = centres[9], centres[8]

    layout = detect_deposit_zones_mm(centres)

    zone_inversee = [z for z in layout.zones if z.id_top_left == 8]
    assert len(zone_inversee) == 1, "la zone doit rester listée pour être signalée"
    assert ANOMALIE_INVERSEE in zone_inversee[0].anomalies
    assert not zone_inversee[0].is_valid
    assert layout.has_anomalies

    # Les 2 autres zones restent exploitables : une anomalie n'invalide pas le plateau
    assert len(layout.valid_zones) == 2


def test_zone_trop_inclinee_signalee() -> None:
    """Au-delà du seuil (10° par défaut), une zone est signalée comme mal vissée."""
    centres = {}
    centres.update(_zone_centers(4, 10.0, 180.0))
    centres.update(_zone_centers(6, 110.0, 180.0))
    centres.update(_zone_centers(8, 10.0, 110.0, rotation_deg=25.0))  # de travers

    layout = detect_deposit_zones_mm(centres)

    zone_penchee = [z for z in layout.zones if z.id_top_left == 8][0]
    assert ANOMALIE_ANGLE in zone_penchee.anomalies
    assert zone_penchee.rotation_deg == pytest.approx(25.0, abs=1.0)


def test_legere_inclinaison_toleree() -> None:
    """Une rotation de montage de quelques degrés est normale et ne doit pas invalider
    la zone — c'est tout l'intérêt de gérer la rotation."""
    centres = {}
    centres.update(_zone_centers(4, 10.0, 180.0))
    centres.update(_zone_centers(6, 110.0, 180.0))
    centres.update(_zone_centers(8, 10.0, 110.0, rotation_deg=4.0))

    layout = detect_deposit_zones_mm(centres)

    zone = [z for z in layout.zones if z.id_top_left == 8][0]
    assert zone.is_valid, f"une zone à 4° doit rester exploitable ({zone.anomalies})"
    assert zone.rotation_deg == pytest.approx(4.0, abs=1.0)


def test_paire_fantome_de_meme_longueur_ne_casse_pas_le_plateau() -> None:
    """Régression : sur un plateau en grille, une paire fantôme peut avoir EXACTEMENT
    la longueur de diagonale de référence, et le filtrage par longueur ne suffit pas.

    Deux zones 60×40 côte à côte espacées de 60 mm : la paire (5,6), formée du coin
    bas-droit de la première et du coin haut-gauche de la seconde, a pour vecteur
    (60, +40) contre (60, −40) pour les vraies zones — même longueur au millimètre
    près. Elle empruntant leurs tags, elle invalidait les deux zones réelles par
    conflit : un plateau parfaitement monté devenait inexploitable.

    Le tri par SIGNE des composantes l'écarte : une zone réelle avance en X et
    redescend en Y, le Y du repère plateau étant dirigé vers le haut depuis le lot
    C2bis. Une paire dont les deux composantes ont le MÊME signe est un fantôme.
    """
    centres = {}
    centres.update(_zone_centers(4, 10.0, 180.0))
    centres.update(_zone_centers(6, 130.0, 180.0))

    # Prérequis du test : vérifier que le fantôme a bien la longueur de référence,
    # sinon le test passerait pour de mauvaises raisons
    fantome = (centres[6][0] - centres[5][0], centres[6][1] - centres[5][1])
    assert math.hypot(*fantome) == pytest.approx(
        math.hypot(PRODUIT_W, PRODUIT_H), abs=0.01
    ), "prérequis : la paire fantôme doit avoir exactement la longueur de référence"

    layout = detect_deposit_zones_mm(centres)

    paires = {(z.id_top_left, z.id_bottom_right) for z in layout.zones}
    assert paires == {(4, 5), (6, 7)}, "le fantôme (5,6) ne doit pas être retenu"
    assert len(layout.valid_zones) == 2, "les deux zones réelles doivent rester saines"
    assert not layout.has_anomalies


def test_plateau_entierement_inverse_reste_identifie() -> None:
    """Régression : si TOUTES les zones sont montées à l'envers, elles doivent quand
    même être reconnues et signalées comme telles.

    Le piège corrigé : la longueur de référence était calculée sur les seules paires
    d'orientation plausible. Toutes les vraies zones étant inversées, elles sortaient du
    vote, et les rares paires fantômes d'orientation plausible fixaient seules la
    référence — les vraies zones étaient alors rejetées comme orphelines pendant que des
    FANTÔMES étaient présentés comme des zones valides. Un résultat faux et silencieux.

    Le vote porte désormais sur toutes les paires d'orientation cohérente, inversées
    comprises : les vraies zones, qui partagent la même longueur, forment le groupe
    majoritaire et l'emportent.
    """
    centres = {}
    for id_tl, (x, y) in ((4, (10.0, 180.0)), (6, (130.0, 180.0)), (8, (10.0, 100.0))):
        zone = _zone_centers(id_tl, x, y)
        # Intervertir les deux marqueurs : la zone est montée à l'envers
        centres[id_tl] = zone[id_tl + 1]
        centres[id_tl + 1] = zone[id_tl]

    layout = detect_deposit_zones_mm(centres)

    paires = {(z.id_top_left, z.id_bottom_right) for z in layout.zones}
    assert paires == {(4, 5), (6, 7), (8, 9)}, (
        f"les 3 vraies zones doivent être identifiées, obtenu {paires} "
        f"(orphelins : {layout.unpaired_ids})"
    )
    for zone in layout.zones:
        assert ANOMALIE_INVERSEE in zone.anomalies
    assert layout.valid_zones == [], "aucune zone inversée n'est exploitable"
    assert layout.unpaired_ids == [], "aucun marqueur ne doit être déclaré orphelin"


def test_paires_en_conflit_invalidees_toutes_les_deux() -> None:
    """Si deux paires à la bonne longueur se disputent un marqueur, aucune des deux
    n'est exploitable : impossible de savoir laquelle est la vraie zone."""
    # (4,5) et (5,6) ont toutes deux une diagonale (60, −40) → le tag 5 est revendiqué
    # par les deux, ce qui est géométriquement impossible
    centres = {
        4: (10.0, 180.0),
        5: (70.0, 140.0),
        6: (130.0, 100.0),
    }

    layout = detect_deposit_zones_mm(centres)

    assert len(layout.zones) == 2
    for zone in layout.zones:
        assert ANOMALIE_CONFLIT in zone.anomalies
    assert layout.valid_zones == []


def test_diagonale_hors_norme_ecarte_la_paire() -> None:
    """Une paire dont la diagonale ne ressemble à aucune autre est écartée, et ses
    marqueurs se retrouvent signalés comme orphelins."""
    centres = _plateau_de_trois_zones()
    # Ajouter une paire (20,21) au format manifestement différent (zone deux fois plus
    # grande) : elle ne doit pas être confondue avec les vraies zones
    centres.update(_zone_centers(20, 10.0, 100.0, w=120.0, h=80.0))

    layout = detect_deposit_zones_mm(centres)

    paires = {(z.id_top_left, z.id_bottom_right) for z in layout.zones}
    assert (20, 21) not in paires, "la paire hors format ne doit pas être retenue"
    assert layout.unpaired_ids == [20, 21]
    assert layout.has_anomalies, "des marqueurs orphelins doivent alerter l'opérateur"


# ------------------------------------------------------------------ cas limites

def test_plateau_sans_marqueur_ne_plante_pas() -> None:
    """Aucun marqueur : le résultat doit être vide, sans exception."""
    layout = detect_deposit_zones_mm({})

    assert layout.zones == []
    assert layout.unpaired_ids == []
    assert layout.product_size_mm is None
    assert layout.reference_diagonal_mm is None


def test_zone_unique_ne_permet_pas_de_detecter_un_mauvais_montage() -> None:
    """Limite documentée du dispositif : avec une seule zone, celle-ci définit à elle
    seule la référence de format. Sa rotation ressort donc nulle même si elle est
    physiquement de travers — il faut au moins deux zones pour comparer.

    Ce test fige ce comportement pour qu'il ne soit pas pris plus tard pour un bug.
    """
    layout = detect_deposit_zones_mm(_zone_centers(4, 10.0, 100.0, rotation_deg=30.0))

    assert len(layout.valid_zones) == 1
    assert layout.valid_zones[0].rotation_deg == pytest.approx(0.0, abs=0.01)


def test_rectangle_from_diagonal_solution_unique() -> None:
    """Le format de référence étant ORIENTÉ (issu de la médiane des zones), la
    rotation se déduit sans ambiguïté : une diagonale (60, −40) pour un produit
    60×40 donne exactement 0°.

    Le signe moins sur la composante Y est la convention du lot C2bis : l'axe Y du
    plateau monte, donc la diagonale d'une zone bien montée descend à l'écran.
    """
    coins, rotation_deg, taille = _rectangle_from_diagonal(
        (0.0, 40.0), (60.0, 0.0), PRODUIT_W, PRODUIT_H
    )

    assert rotation_deg == pytest.approx(0.0, abs=0.01)
    assert taille == (PRODUIT_W, PRODUIT_H)
    assert coins[2] == pytest.approx((60.0, 0.0), abs=0.01), \
        "le coin bas-droit doit retomber sur l'extrémité de la diagonale"


def test_rectangle_from_diagonal_ne_reinterprete_pas_une_forte_rotation() -> None:
    """Régression : une forte rotation ne doit PAS être réinterprétée en petite
    rotation avec les côtés échangés.

    Un rectangle 60×40 tourné de 25,8° a la même direction de diagonale qu'un 40×60
    posé droit. Tant que la fonction envisageait les deux solutions symétriques et
    gardait la plus petite rotation, une zone vissée de travers ressortait à ~2° et
    l'anomalie de montage passait inaperçue.
    """
    # Diagonale d'un 60×40 tourné de 25° : R(25°) appliqué au vecteur (60, −40)
    theta = math.radians(25.0)
    dx = PRODUIT_W * math.cos(theta) + PRODUIT_H * math.sin(theta)
    dy = PRODUIT_W * math.sin(theta) - PRODUIT_H * math.cos(theta)

    _, rotation_deg, taille = _rectangle_from_diagonal(
        (0.0, 0.0), (dx, dy), PRODUIT_W, PRODUIT_H
    )

    assert rotation_deg == pytest.approx(25.0, abs=0.01), \
        "la rotation réelle doit être rendue telle quelle, pas ramenée à ~2°"
    assert taille == (PRODUIT_W, PRODUIT_H), "les côtés ne doivent pas être échangés"


# ------------------------------------------------------------------ warp_zone

def _zone_pour_warp(rotation_deg: float = 0.0) -> tuple:
    """Une image de plateau synthétique et la zone qui y est posée.

    L'image est fabriquée en dessinant le rectangle de la zone directement en pixels,
    puis en construisant l'homographie qui fait correspondre pixels et millimètres.
    """
    marqueurs = _marqueurs_synthetiques()
    vision = VisionProcessor(ARUCO_DICT_ID, ARUCO_MARKER_SIZE_MM)
    H = vision.compute_homography(marqueurs)

    # Une zone de 60 × 40 mm dont le coin haut-gauche est à 100 mm du bas du plateau,
    # éventuellement tournée. Position choisie pour que la zone tombe au milieu de
    # l'image source une fois le repère retourné.
    centres = _zone_centers(4, 40.0, 100.0, rotation_deg=rotation_deg)
    layout = detect_deposit_zones_mm(centres)
    return vision, H, layout.zones[0]


def test_warp_zone_dimensions_a_l_echelle_demandee() -> None:
    """L'image redressée doit faire exactement la taille de la zone × l'échelle."""
    vision, H, zone = _zone_pour_warp()
    image = np.full((400, 600, 3), 128, dtype=np.uint8)

    resultat = vision.warp_zone(image, zone, H, px_per_mm=4.0)

    # Zone de 60 × 40 mm à 4 px/mm → 240 × 160 px
    assert resultat.shape[:2] == (160, 240), f"obtenu {resultat.shape[:2]}"


def test_warp_zone_redresse_une_zone_tournee() -> None:
    """Le cœur de la fonction : une zone vissée de travers doit ressortir DROITE.

    Méthode : on peint une bande dans l'image source le long d'un côté de la zone
    inclinée. Après redressement, cette bande doit border proprement l'image de sortie
    — ce qui ne serait pas le cas si la rotation n'était pas compensée.

    ⚠️ La moitié « haute » de la zone est celle des grands y depuis le lot C2bis
    (origine du repère de zone au coin BAS-gauche), d'où le découpage hauteur/2 → hauteur.
    """
    vision, H, zone = _zone_pour_warp(rotation_deg=20.0)

    # Image source blanche, avec la moitié HAUTE de la zone peinte en noir. On dessine
    # dans le repère de la zone puis on reprojette en pixels, ce qui garantit que la
    # bande est bien inclinée de 20° dans l'image source.
    image = np.full((400, 600, 3), 255, dtype=np.uint8)
    largeur, hauteur = zone.size_mm
    coins_haut_mm = [
        zone.to_plateau_mm((0.0, hauteur)),
        zone.to_plateau_mm((largeur, hauteur)),
        zone.to_plateau_mm((largeur, hauteur / 2)),
        zone.to_plateau_mm((0.0, hauteur / 2)),
    ]
    polygone = np.array(vision.mm_to_pixels(coins_haut_mm, H), dtype=np.int32)
    cv2.fillPoly(image, [polygone], (0, 0, 0))

    resultat = vision.warp_zone(image, zone, H, px_per_mm=4.0)
    h_px = resultat.shape[0]

    moitie_haute = resultat[: h_px // 2 - 4].mean()
    moitie_basse = resultat[h_px // 2 + 4:].mean()

    assert moitie_haute < 40, (
        f"la moitié haute devrait être noire (moyenne {moitie_haute:.0f}) — "
        f"la rotation de la zone n'a pas été compensée"
    )
    assert moitie_basse > 215, (
        f"la moitié basse devrait être blanche (moyenne {moitie_basse:.0f})"
    )


def test_warp_zone_origine_du_repere_au_coin_bas_gauche() -> None:
    """Le point (0, 0) du repère de la zone doit être son coin BAS-gauche.

    C'est la convention posée au lot C2bis, et c'est elle qui permet de convertir un
    clic en millimètres par une simple division suivie d'un retournement de Y, sans
    repasser par l'homographie point par point (gui/screen_cordons.py::_position_mm).

    Le test pointe précisément le piège : avant le lot C2bis, un carré dessiné en
    (0, 0) ressortait en HAUT à gauche de l'image redressée. Il doit désormais
    ressortir en BAS à gauche — et surtout pas ailleurs, sinon les cordons d'un
    opérateur atterriraient à l'autre bout de la pièce.
    """
    vision, H, zone = _zone_pour_warp(rotation_deg=12.0)

    # Marquer un carré noir de 10 × 10 mm à l'ORIGINE du repère de la zone
    image = np.full((400, 600, 3), 255, dtype=np.uint8)
    coins_mm = [zone.to_plateau_mm(p) for p in
                ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0))]
    cv2.fillPoly(image, [np.array(vision.mm_to_pixels(coins_mm, H), dtype=np.int32)],
                 (0, 0, 0))

    px_per_mm = 4.0
    resultat = vision.warp_zone(image, zone, H, px_per_mm)
    hauteur_px = resultat.shape[0]

    # 10 mm × 4 px/mm = 40 px : le carré occupe les 40 dernières LIGNES, à gauche
    coin_bas = resultat[hauteur_px - 35:hauteur_px - 5, 5:35].mean()
    coin_haut = resultat[5:35, 5:35].mean()

    assert coin_bas < 40, (
        f"l'origine (0, 0) de la zone doit ressortir en BAS à gauche de l'image "
        f"(moyenne {coin_bas:.0f})"
    )
    assert coin_haut > 215, (
        f"le haut de l'image doit rester blanc (moyenne {coin_haut:.0f}) — s'il est "
        f"noir, le retournement de Y de warp_zone() n'a pas été appliqué"
    )


# ===========================================================================
# Sur image réelle — chaîne complète, matériel branché
# ===========================================================================
#
# Ces tests travaillent sur la PHOTO réellement prise par la caméra du projet (fixture
# plateau_capture, voir tests/conftest.py). Ils ne remplacent pas les tests synthétiques
# ci-dessus, qui restent la référence parce qu'ils sont déterministes : ils les
# complètent en vérifiant que la chaîne tient sur des données bruitées — flou, reflets,
# marqueurs vus de biais. Ils sont ignorés (`skip`) si le plateau n'est pas devant
# l'objectif.

def test_detection_reproductible_sur_image_reelle(
    vision: VisionProcessor, plateau_capture
) -> None:
    """Deux détections sur la MÊME image doivent donner exactement le même résultat.

    La détection ArUco est déterministe : si ce test échoue, c'est qu'un état est
    conservé d'un appel à l'autre dans le détecteur, ce qui rendrait tout le reste
    imprévisible.
    """
    premiere = vision.detect_markers(plateau_capture.image)
    seconde = vision.detect_markers(plateau_capture.image)

    assert set(premiere) == set(seconde)
    assert set(premiere) == set(plateau_capture.marker_ids), (
        "la détection doit retrouver les mêmes marqueurs que lors de la sélection"
    )


def test_coins_de_marqueur_bien_formes_sur_image_reelle(
    vision: VisionProcessor, plateau_capture
) -> None:
    """Chaque marqueur détecté sur une vraie photo doit avoir 4 coins situés dans les
    limites de l'image — un coin hors cadre signalerait une détection aberrante."""
    hauteur, largeur = plateau_capture.image.shape[:2]

    for marker_id, coins in vision.detect_markers(plateau_capture.image).items():
        assert coins.shape == (4, 2), f"marqueur {marker_id} : forme {coins.shape}"
        assert coins[:, 0].min() >= 0 and coins[:, 0].max() <= largeur
        assert coins[:, 1].min() >= 0 and coins[:, 1].max() <= hauteur


def test_homographie_sur_image_reelle(vision: VisionProcessor, plateau_capture) -> None:
    """Si assez de marqueurs de plateau sont visibles, l'homographie doit se calculer et
    convertir en millimètres plausibles.

    « Plausible » se juge sur l'ordre de grandeur : un point de l'image doit retomber
    dans une fourchette de quelques dizaines de centimètres autour du plateau. Une
    homographie dégénérée produirait des valeurs immenses ou NaN.
    """
    marqueurs = vision.detect_markers(plateau_capture.image)
    ids_plateau = {0, 1, 2, 3} & marqueurs.keys()

    if len(ids_plateau) < 2:
        pytest.skip(
            f"moins de 2 marqueurs de plateau visibles ({sorted(ids_plateau)}) — "
            f"impossible de calculer une homographie"
        )

    if len(ids_plateau) == 4:
        H = vision.compute_homography(marqueurs)
    else:
        H = vision.compute_homography_approx(marqueurs)

    # Convertir le centre de l'image, forcément situé sur le plateau ou tout près
    hauteur, largeur = plateau_capture.image.shape[:2]
    x_mm, y_mm = vision.pixel_to_mm(largeur / 2, hauteur / 2, H)

    assert math.isfinite(x_mm) and math.isfinite(y_mm), "homographie dégénérée"
    assert -500 < x_mm < 500 and -500 < y_mm < 500, (
        f"centre de l'image converti en ({x_mm:.0f}, {y_mm:.0f}) mm — hors de toute "
        f"plage plausible pour un plateau de 220 mm"
    )


def test_zones_de_depose_sur_image_reelle(
    vision: VisionProcessor, plateau_capture
) -> None:
    """Si des marqueurs de zone sont visibles, la reconstruction doit aboutir sans
    exception et produire des zones cohérentes avec le format déduit.

    Ce test ne présume PAS du nombre de zones réellement posées sur le plateau : il
    vérifie la cohérence interne du résultat, seule chose qui doive être vraie quelle
    que soit la scène.
    """
    marqueurs = vision.detect_markers(plateau_capture.image)
    ids_plateau = {0, 1, 2, 3} & marqueurs.keys()
    ids_zone = {i for i in marqueurs if i >= 4}

    if len(ids_plateau) < 2 or len(ids_zone) < 2:
        pytest.skip(
            f"pas de quoi reconstruire une zone (plateau {sorted(ids_plateau)}, "
            f"zone {sorted(ids_zone)})"
        )

    H = (vision.compute_homography(marqueurs) if len(ids_plateau) == 4
         else vision.compute_homography_approx(marqueurs))
    layout = vision.detect_deposit_zones(marqueurs, H)

    for zone in layout.zones:
        assert zone.id_bottom_right == zone.id_top_left + 1, "convention d'appariement"
        assert len(zone.corners_mm) == 4
        assert all(math.isfinite(c) for coin in zone.corners_mm for c in coin)

    if layout.product_size_mm is not None:
        largeur, hauteur = layout.product_size_mm
        assert largeur > 0 and hauteur > 0, "le format déduit doit être positif"


# ------------------------------------------------------------------ intégration

def test_detect_deposit_zones_depuis_des_marqueurs_pixels(vision: VisionProcessor) -> None:
    """Chaînage complet : marqueurs en pixels → homographie → zones en mm.

    Vérifie que la méthode de VisionProcessor fait bien le passage pixels → mm avant
    de déléguer à la fonction pure, et qu'elle ignore les marqueurs du plateau.
    """
    marqueurs = _marqueurs_synthetiques()   # les 4 coins du plateau, IDs 0-3
    H = vision.compute_homography(marqueurs)

    # Deux zones côte à côte SUR LA MÊME LIGNE, comme sur le croquis du plateau réel.
    # C'est le cas piégeux : la paire fantôme (5,6), formée du coin bas-droit de la
    # première et du coin haut-gauche de la seconde, a exactement la même LONGUEUR de
    # diagonale que les vraies zones — par symétrie, son vecteur est (100, +80) contre
    # (100, −80). Seul le tri par signe des composantes permet de l'écarter ; sans lui
    # elle invaliderait par conflit les deux zones réelles, dont elle emprunte les tags.
    marqueurs[4] = _coins_autour(150, 100)
    marqueurs[5] = _coins_autour(250, 180)
    marqueurs[6] = _coins_autour(350, 100)
    marqueurs[7] = _coins_autour(450, 180)

    layout = vision.detect_deposit_zones(marqueurs, H)

    paires = {(z.id_top_left, z.id_bottom_right) for z in layout.zones}
    assert paires == {(4, 5), (6, 7)}, \
        "les 2 zones doivent être trouvées, et les coins du plateau ignorés"
    assert len(layout.valid_zones) == 2
