"""Tests unitaires pour modules/calibration.py — calibration ChArUco.

Pourquoi ce fichier existe :
  La session du 2026-07-29 a passé plusieurs heures à déboguer une calibration
  ChArUco cassée, dont une cause concrète et facile à faire régresser :
  cv2.aruco.calibrateCameraCharuco() a été supprimée dans OpenCV 5.0, et
  calibrate_charuco() a dû être réécrite pour utiliser board.matchImagePoints()
  + cv2.calibrateCamera() à la place (voir MANUEL_MAINTENANCE.md section 4.3).
  Ce genre de régression (upgrade OpenCV, refactor malencontreux) doit être
  détecté par `pytest`, pas par une session de calibration sur le terrain.

Toutes les images de mire utilisées ici sont générées par le code lui-même
(aucune caméra ni mire physique nécessaire), avec des paramètres de mire fixes
et écrits en dur dans ce fichier — volontairement indépendants de
local_config.json (qui varie d'une machine à l'autre, voir modules/config.py)
pour que ces tests donnent le même résultat sur n'importe quelle machine.
"""
import cv2
import numpy as np
import pytest

from modules.calibration import detect_charuco, calibrate_charuco


# Dictionnaire ArUco utilisé pour toutes les mires de test — identique au
# défaut du projet (DICT_4X4_50, voir modules/config.py::CHARUCO_DICT_NAME)
_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)


def _mire_board() -> object:
    """Construit une mire ChArUco 4×4 (15 mm/case, 12 mm/marqueur) pour les tests.

    legacy_pattern=False : c'est le réglage validé le 2026-07-29 pour une mire
    générée par ce projet lui-même (voir CLAUDE.md section 10 et
    MANUEL_MAINTENANCE.md section 4.4a) — celui qu'on veut protéger d'une
    régression, pas le défaut historique de local_config.json.example.
    """
    board = cv2.aruco.CharucoBoard((4, 4), 15.0, 12.0, _DICT)
    board.setLegacyPattern(False)
    return board


def _rendu_mire(board, px_per_mm: float = 8.0) -> np.ndarray:
    """Génère l'image BGR de la mire en mémoire (équivalent de generate_charuco_image,
    mais sans écrire de fichier — plus rapide pour des tests répétés).
    """
    taille_px = int(4 * 15.0 * px_per_mm)
    img_gris = board.generateImage((taille_px, taille_px), marginSize=10)
    return cv2.cvtColor(img_gris, cv2.COLOR_GRAY2BGR)


def _vues_synthetiques(image: np.ndarray) -> list:
    """Génère 12 vues déformées (homographies "keystone") de la mire de face.

    calibrate_charuco() a besoin de plusieurs points de vue différents pour
    résoudre un système non dégénéré (une seule vue frontale ne permet pas de
    séparer la focale de la caméra de sa distance à la mire — c'est le principe
    même de la calibration par mire planaire). On simule ça en resserrant un
    bord de l'image à la fois (haut/bas/gauche/droite), à 3 amplitudes
    croissantes : c'est équivalent à des photos prises avec des inclinaisons
    de caméra différentes. Décalages fixes (pas aléatoires) pour un test
    reproductible ; amplitudes modérées (≤ 15 %) validées empiriquement pour
    que la mire reste détectable après déformation.
    """
    h, w = image.shape[:2]
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])

    # Chaque fonction resserre un seul bord du quadrilatère de destination —
    # garantit un quadrilatère convexe (pas d'auto-intersection) quelle que
    # soit l'amplitude utilisée ci-dessous
    def narrow_top(a):
        return np.float32([[w * a, 0], [w * (1 - a), 0], [w, h], [0, h]])

    def narrow_bottom(a):
        return np.float32([[0, 0], [w, 0], [w * (1 - a), h], [w * a, h]])

    def narrow_left(a):
        return np.float32([[0, h * a], [w, 0], [w, h], [0, h * (1 - a)]])

    def narrow_right(a):
        return np.float32([[0, 0], [w, h * a], [w, h * (1 - a)], [0, h]])

    vues = []
    for amplitude in (0.05, 0.10, 0.15):
        for fn in (narrow_top, narrow_bottom, narrow_left, narrow_right):
            M = cv2.getPerspectiveTransform(src, fn(amplitude))
            # Fond blanc (pas noir) hors de la mire déformée — un bord noir
            # pourrait être pris pour un contour de marqueur par le détecteur
            vues.append(cv2.warpPerspective(image, M, (w, h), borderValue=(255, 255, 255)))
    return vues


def test_detect_charuco_detecte_sa_propre_mire() -> None:
    """Une mire générée par board.generateImage() doit être détectable par un
    CharucoDetector construit sur ce même board — condition de base pour que
    la calibration soit seulement utilisable en pratique.
    """
    board = _mire_board()
    detector = cv2.aruco.CharucoDetector(board)
    image = _rendu_mire(board)

    corners, ids, preview, marker_count = detect_charuco(image, board, detector)

    assert marker_count > 0, "Au moins un marqueur ArUco doit être vu sur la mire générée"
    assert ids is not None, "La mire générée par l'app doit être détectable (voir MANUEL_MAINTENANCE.md §4.4a)"
    assert len(ids) >= 4, "Au moins 4 coins ChArUco nécessaires pour contribuer à une calibration"
    assert preview.shape == image.shape, "preview doit être une image annotée de mêmes dimensions"


def test_detect_charuco_image_vide_ne_detecte_rien() -> None:
    """Sur une image blanche sans mire, aucun marqueur ni coin ne doit être détecté."""
    board = _mire_board()
    detector = cv2.aruco.CharucoDetector(board)
    image_vide = np.ones((300, 300, 3), dtype=np.uint8) * 255

    corners, ids, preview, marker_count = detect_charuco(image_vide, board, detector)

    assert marker_count == 0
    assert ids is None


def test_calibrate_charuco_retourne_une_calibration_valide() -> None:
    """calibrate_charuco() doit calculer une calibration à partir de plusieurs
    vues ChArUco valides, en passant par board.matchImagePoints() +
    cv2.calibrateCamera() — PAS par cv2.aruco.calibrateCameraCharuco(), qui
    n'existe plus depuis OpenCV 5.0 (AttributeError sinon).
    """
    board = _mire_board()
    detector = cv2.aruco.CharucoDetector(board)
    mire = _rendu_mire(board)
    image_size = (mire.shape[1], mire.shape[0])

    all_corners, all_ids = [], []
    for vue in _vues_synthetiques(mire):
        corners, ids, _preview, _count = detect_charuco(vue, board, detector)
        if ids is not None:
            all_corners.append(corners)
            all_ids.append(ids)

    assert len(all_corners) >= 10, (
        f"Seulement {len(all_corners)} vues synthétiques détectées sur "
        f"{len(_vues_synthetiques(mire))} générées — vérifier _vues_synthetiques()"
    )

    camera_matrix, dist_coeffs, error = calibrate_charuco(all_corners, all_ids, board, image_size)

    assert camera_matrix.shape == (3, 3), f"camera_matrix doit être 3×3, obtenu {camera_matrix.shape}"
    assert dist_coeffs.size >= 4, "dist_coeffs doit contenir au moins 4 coefficients de distorsion"
    assert error >= 0, "L'erreur de reprojection doit être un nombre positif ou nul"


def test_calibrate_charuco_leve_erreur_si_pas_assez_de_vues() -> None:
    """calibrate_charuco() doit refuser de calibrer avec moins de 10 vues valides
    plutôt que de produire silencieusement une calibration peu fiable — le seuil
    est vérifié avant tout calcul, donc de fausses données suffisent ici.
    """
    faux_corners = [np.zeros((4, 1, 2), dtype=np.float32)] * 5
    faux_ids = [np.zeros((4, 1), dtype=np.int32)] * 5

    with pytest.raises(ValueError):
        calibrate_charuco(faux_corners, faux_ids, _mire_board(), (100, 100))
