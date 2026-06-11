import cv2
import numpy as np
import pytest

from modules.vision import VisionProcessor
from modules.config import ARUCO_DICT_ID, ARUCO_MARKER_SIZE_MM


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
