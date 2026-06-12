"""Calibration de l'objectif de la caméra (correction de la distorsion barrel).

Pourquoi ce module ?
  Les objectifs de webcam bon marché déforment l'image : les objets au centre
  paraissent plus grands qu'ils ne le sont (barrel distortion). L'homographie
  corrige la perspective mais pas cette distorsion → erreur de ~10 % sur les
  mesures intérieures à la zone de travail.

  Ce module calcule les coefficients de distorsion une seule fois (calibration),
  puis les applique à chaque image (undistort) avant tout traitement.

Procédure (une seule fois) :
  1. Imprimer assets/chessboard_calibration.png sur A4 paysage (25 mm / carré)
  2. Lancer tests/demo_calibration.py
  3. Présenter l'échiquier à la caméra sous 15+ angles/positions différents
  4. Appuyer sur ESPACE pour valider chaque position détectée
  5. Les coefficients sont sauvegardés dans assets/camera_calibration.npz

Fonctions publiques :
  generate_chessboard_image(path)              → crée le PNG à imprimer
  calibrate(images)                            → calcule les coefficients
  undistort(image, camera_matrix, dist_coeffs) → corrige une image
  save_calibration(path, ...)                  → sauvegarde dans .npz
  load_calibration(path)                       → charge depuis .npz
"""
import os
import cv2
import numpy as np


# Dimensions de l'échiquier de calibration : nombre de COINS INTERNES (pas de carrés)
# Un échiquier 10×7 carrés a 9×6 coins internes
CHESSBOARD_SIZE = (9, 6)

# Taille physique d'un carré imprimé (en mm) — dépend du fichier assets/chessboard_calibration.png
SQUARE_SIZE_MM = 25.0


def generate_chessboard_image(
    output_path: str,
    board_cols: int = 10,
    board_rows: int = 7,
    square_px: int = 80,
) -> None:
    """Génère et sauvegarde l'image de l'échiquier à imprimer.

    board_cols × board_rows : nombre de carrés (colonnes × lignes)
    square_px               : taille d'un carré en pixels dans l'image
    Résultat                : PNG 800×560 px → imprimer en taille réelle sur A4 paysage
                              → carrés de ~25 mm chacun
    """
    h = board_rows * square_px
    w = board_cols * square_px

    # Créer une image blanche (fond)
    img = np.ones((h, w), dtype=np.uint8) * 255

    # Remplir les cases noires : règle du damier — (ligne + colonne) pair = noir
    for row in range(board_rows):
        for col in range(board_cols):
            if (row + col) % 2 == 0:
                y0, x0 = row * square_px, col * square_px
                img[y0:y0 + square_px, x0:x0 + square_px] = 0

    # Créer le dossier parent si nécessaire
    parent = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(parent, exist_ok=True)

    cv2.imwrite(output_path, img)


def calibrate(
    images: list,
    chessboard_size: tuple = CHESSBOARD_SIZE,
    square_size_mm: float = SQUARE_SIZE_MM,
) -> tuple:
    """Calcule les paramètres de distorsion de la caméra.

    Paramètres :
        images         : liste d'images BGR (numpy arrays) montrant l'échiquier
        chessboard_size: (nb_coins_x, nb_coins_y) — coins internes, pas les carrés
        square_size_mm : taille physique d'un carré en mm

    Retourne :
        (camera_matrix, dist_coeffs, reprojection_error)
        reprojection_error < 1.0 = bonne calibration, < 0.5 = excellente

    Lève ValueError si moins de 10 images ont l'échiquier correctement détecté.
    """
    # Points 3D de l'échiquier dans son propre repère (plan Z=0)
    # Chaque coin est séparé de square_size_mm des voisins
    objp = np.zeros((chessboard_size[0] * chessboard_size[1], 3), np.float32)
    objp[:, :2] = (
        np.mgrid[0:chessboard_size[0], 0:chessboard_size[1]]
        .T.reshape(-1, 2) * square_size_mm
    )

    objpoints = []  # Coordonnées 3D réelles pour chaque image valide
    imgpoints = []  # Coordonnées 2D détectées dans l'image pour chaque image valide

    # Critère d'arrêt pour cornerSubPix : précision 0.001 px ou 30 itérations max
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

    for img in images:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Chercher les coins internes de l'échiquier dans l'image
        found, corners = cv2.findChessboardCorners(gray, chessboard_size, None)

        if found:
            objpoints.append(objp)

            # Affiner la position des coins au niveau sub-pixel pour plus de précision
            # fenêtre de recherche 11×11 px autour de chaque coin détecté
            corners_refined = cv2.cornerSubPix(
                gray, corners,
                winSize=(11, 11),
                zeroZone=(-1, -1),
                criteria=criteria,
            )
            imgpoints.append(corners_refined)

    if len(objpoints) < 10:
        raise ValueError(
            f"Calibration impossible : seulement {len(objpoints)} images valides "
            f"sur {len(images)} fournies (minimum requis : 10). "
            f"Vérifier que l'échiquier est bien visible et bien éclairé."
        )

    h, w = images[0].shape[:2]

    # Calculer la matrice intrinsèque et les coefficients de distorsion
    # calibrateCamera retourne aussi les vecteurs de rotation/translation (non utilisés ici)
    ret, camera_matrix, dist_coeffs, _rvecs, _tvecs = cv2.calibrateCamera(
        objpoints, imgpoints, (w, h), None, None
    )

    # ret = erreur de reprojection en pixels (écart moyen entre coins détectés et recalculés)
    return camera_matrix, dist_coeffs, ret


def undistort(
    image: np.ndarray,
    camera_matrix: np.ndarray,
    dist_coeffs: np.ndarray,
) -> np.ndarray:
    """Corrige la distorsion de l'objectif sur une image.

    Utilise la même matrice caméra en entrée et en sortie → les dimensions et
    le système de coordonnées pixel restent identiques à l'image d'origine.
    Les pixels aux bords (hors zone valide) deviennent noirs, mais la zone
    centrale (où se trouvent les marqueurs et la pièce) est correctement corrigée.
    """
    # undistort avec newCameraMatrix = camera_matrix conserve le repère pixel d'origine
    return cv2.undistort(image, camera_matrix, dist_coeffs, None, camera_matrix)


def save_calibration(
    path: str,
    camera_matrix: np.ndarray,
    dist_coeffs: np.ndarray,
) -> None:
    """Sauvegarde la matrice caméra et les coefficients de distorsion dans un .npz."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    np.savez(path, camera_matrix=camera_matrix, dist_coeffs=dist_coeffs)


def load_calibration(path: str) -> tuple:
    """Charge les coefficients de calibration depuis un fichier .npz.

    Retourne (camera_matrix, dist_coeffs) si le fichier existe,
    (None, None) sinon — le code appelant peut alors travailler sans calibration.
    """
    if not os.path.exists(path):
        return None, None

    data = np.load(path)
    return data['camera_matrix'], data['dist_coeffs']
