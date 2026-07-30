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

from modules.config import (
    CHARUCO_COLS, CHARUCO_ROWS, CHARUCO_SQUARE_MM, CHARUCO_MARKER_MM, CHARUCO_DICT_NAME,
    CHARUCO_LEGACY_PATTERN,
)


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


# ============================================================ ChArUco calibration

# Correspondance entre les noms de dictionnaires (utilisés dans local_config.json)
# et les constantes entières qu'OpenCV attend dans getPredefinedDictionary().
_ARUCO_DICT_MAP = {
    "DICT_4X4_50":         cv2.aruco.DICT_4X4_50,
    "DICT_4X4_100":        cv2.aruco.DICT_4X4_100,
    "DICT_4X4_250":        cv2.aruco.DICT_4X4_250,
    "DICT_4X4_1000":       cv2.aruco.DICT_4X4_1000,
    "DICT_5X5_50":         cv2.aruco.DICT_5X5_50,
    "DICT_5X5_100":        cv2.aruco.DICT_5X5_100,
    "DICT_5X5_250":        cv2.aruco.DICT_5X5_250,
    "DICT_6X6_50":         cv2.aruco.DICT_6X6_50,
    "DICT_6X6_100":        cv2.aruco.DICT_6X6_100,
    "DICT_7X7_50":         cv2.aruco.DICT_7X7_50,
    "DICT_ARUCO_ORIGINAL": cv2.aruco.DICT_ARUCO_ORIGINAL,
}

if CHARUCO_DICT_NAME not in _ARUCO_DICT_MAP:
    raise ValueError(
        f"Dictionnaire ChArUco inconnu dans local_config.json : '{CHARUCO_DICT_NAME}'. "
        f"Valeurs acceptees : {list(_ARUCO_DICT_MAP.keys())}"
    )

# Constante entiere OpenCV correspondant au dictionnaire configure
CHARUCO_DICT_ID = _ARUCO_DICT_MAP[CHARUCO_DICT_NAME]


def create_charuco_board():
    """Crée l'objet CharucoBoard et le détecteur associé pour la calibration.

    Le ChArUco (Chessboard + ArUco) combine :
    - L'échiquier : fournit des coins sub-pixel très précis pour la calibration
    - Les marqueurs ArUco : permettent d'identifier les coins même si la mire est partiellement visible

    IMPORTANT — legacy pattern : OpenCV a modifié la disposition des marqueurs en 4.6.
    Les générateurs externes (calib.io, kalibr...) utilisent l'ancien format. Activer
    setLegacyPattern(True) rend la détection compatible avec ces mires externes.

    Retourne : (board, detector)
    """
    dictionary = cv2.aruco.getPredefinedDictionary(CHARUCO_DICT_ID)
    board = cv2.aruco.CharucoBoard(
        (CHARUCO_COLS, CHARUCO_ROWS),
        CHARUCO_SQUARE_MM,
        CHARUCO_MARKER_MM,
        dictionary,
    )
    # Basculer sur l'ancien format de disposition des marqueurs si demandé (défaut = true)
    # Nécessaire pour détecter les mires générées par des outils externes.
    if CHARUCO_LEGACY_PATTERN:
        try:
            board.setLegacyPattern(True)
        except AttributeError:
            # setLegacyPattern n'existe pas dans OpenCV < 4.6 — pas de problème,
            # le format était nativement l'ancien à cette époque
            pass

    detector = cv2.aruco.CharucoDetector(board)
    return board, detector


def generate_charuco_image(output_path: str, px_per_mm: float = 8.0) -> None:
    """Génère et sauvegarde l'image de la mire ChArUco à imprimer.

    px_per_mm = 8.0 → résolution suffisante pour l'impression laser.
    Imprimer à taille réelle (sans zoom ni ajustement d'imprimante).
    La mire fait 4×4 carrés de 15 mm → 60×60 mm une fois imprimée.
    """
    board, _ = create_charuco_board()
    w = int(CHARUCO_COLS * CHARUCO_SQUARE_MM * px_per_mm)
    h = int(CHARUCO_ROWS * CHARUCO_SQUARE_MM * px_per_mm)
    # generateImage produit le PNG de la mire avec une bordure blanche de 10 px
    img = board.generateImage((w, h), marginSize=10)
    parent = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(parent, exist_ok=True)
    cv2.imwrite(output_path, img)


def detect_charuco(image: np.ndarray, board, detector) -> tuple:
    """Détecte les coins ChArUco dans une image et retourne le résultat annoté.

    Paramètres :
        image    : image BGR (numpy array)
        board    : objet CharucoBoard (créé par create_charuco_board)
        detector : objet CharucoDetector (réutilisé à chaque frame pour éviter de le recréer)

    Retourne :
        (corners, ids, preview, marker_count)
        corners, ids : None si moins de 4 coins ChArUco détectés (insuffisant pour calibrer)
        preview      : copie de l'image avec marqueurs ArUco bruts + coins ChArUco (si trouvés)
        marker_count : nombre de marqueurs ArUco bruts vus, même quand le board échoue —
                       permet de distinguer "aucun tag vu" de "tags vus mais mire non reconstruite"
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    preview = image.copy()

    # detectBoard retourne les coins ChArUco (intersections des cases), leurs IDs,
    # les coins bruts des marqueurs ArUco et leurs IDs
    charuco_corners, charuco_ids, marker_corners, marker_ids = detector.detectBoard(gray)

    # Dessiner les marqueurs ArUco bruts (carrés colorés avec leur ID)
    # Fait AVANT de savoir si le board se reconstruit — utile pour diagnostiquer :
    # si ça ne s'affiche jamais, le problème est dans la détection de base, pas dans le board
    marker_count = 0
    if marker_ids is not None and marker_corners is not None and len(marker_ids) > 0:
        marker_count = len(marker_ids)
        # Enrobé dans un try/except : le format retourné par detectBoard varie selon la version OpenCV
        try:
            cv2.aruco.drawDetectedMarkers(preview, marker_corners, marker_ids)
        except Exception:
            pass

    # 4 coins ChArUco minimum : en dessous la contribution à la calibration est trop faible
    if charuco_ids is not None and charuco_corners is not None and len(charuco_ids) >= 4:
        try:
            cv2.aruco.drawDetectedCornersCharuco(preview, charuco_corners, charuco_ids)
        except Exception:
            pass
        return charuco_corners, charuco_ids, preview, marker_count

    return None, None, preview, marker_count


def calibrate_charuco(
    all_corners: list,
    all_ids: list,
    board,
    image_size: tuple,
) -> tuple:
    """Calcule les paramètres de distorsion de la caméra depuis les captures ChArUco.

    Paramètres :
        all_corners : liste de tableaux de coins ChArUco (un tableau par image valide)
        all_ids     : liste de tableaux d'IDs correspondants
        board       : objet CharucoBoard
        image_size  : (largeur, hauteur) de l'image en pixels

    Retourne :
        (camera_matrix, dist_coeffs, reprojection_error)
        reprojection_error en pixels — < 1.0 = bonne calibration, < 0.5 = excellente

    Lève ValueError si moins de 10 images valides.
    """
    if len(all_corners) < 10:
        raise ValueError(
            f"Calibration impossible : seulement {len(all_corners)} images valides "
            f"(minimum requis : 10)"
        )

    # cv2.aruco.calibrateCameraCharuco() a été supprimée dans OpenCV 5.0 (API ChArUco "legacy").
    # Remplacement recommandé par OpenCV : board.matchImagePoints() convertit chaque pose
    # (coins ChArUco 2D + IDs détectés) en paires points-objet 3D / points-image 2D, à partir
    # des positions 3D connues des coins de la mire — puis on calibre avec la fonction
    # générique cv2.calibrateCamera() (la même que pour l'échiquier simple plus haut).
    objpoints = []
    imgpoints = []
    for corners, ids in zip(all_corners, all_ids):
        obj_pts, img_pts = board.matchImagePoints(corners, ids)
        objpoints.append(obj_pts)
        imgpoints.append(img_pts)

    ret, camera_matrix, dist_coeffs, _rvecs, _tvecs = cv2.calibrateCamera(
        objpoints, imgpoints, image_size, None, None
    )

    return camera_matrix, dist_coeffs, ret


# ============================================================ pose de la mire (distance)

def estimate_board_pose(
    corners: np.ndarray, ids: np.ndarray, board, camera_matrix: np.ndarray, dist_coeffs: np.ndarray
) -> tuple:
    """Estime la pose (rotation, translation) de la mire par rapport à la caméra.

    Réutilise board.matchImagePoints() (même mécanisme que calibrate_charuco) pour
    associer les coins ChArUco détectés à leurs positions 3D connues dans le repère de
    la mire, puis résout la pose caméra↔mire par solvePnP à partir de ces correspondances.

    Retourne (rvec, tvec), ou (None, None) si la pose n'a pas pu être résolue
    (moins de 4 coins détectés, ou configuration géométrique dégénérée).
    """
    if corners is None or ids is None or len(ids) < 4:
        return None, None

    obj_pts, img_pts = board.matchImagePoints(corners, ids)
    if obj_pts is None or len(obj_pts) < 4:
        return None, None

    ok, rvec, tvec = cv2.solvePnP(obj_pts, img_pts, camera_matrix, dist_coeffs)
    if not ok:
        return None, None
    return rvec, tvec


def distance_to_board_normal_mm(rvec: np.ndarray, tvec: np.ndarray) -> float:
    """Distance (mm) entre le centre optique de la caméra et le PLAN de la mire, mesurée
    perpendiculairement à ce plan (le long de sa normale) — pas la distance "à vol d'oiseau"
    jusqu'à l'origine de la mire, qui varierait selon l'inclinaison de la mire.

    Dans le repère de la mire, tous les coins ont Z=0 : sa normale est donc l'axe +Z de ce
    repère. rvec/tvec (issus de solvePnP) transforment le repère mire vers le repère caméra :
    R = Rodrigues(rvec) donne l'orientation de la mire dans le repère caméra, donc
    normal_cam = R @ [0, 0, 1] est la normale de la mire exprimée dans le repère caméra
    (vecteur unitaire, car R est une rotation). Le plan de la mire passe par le point tvec
    (son origine, dans le repère caméra) — la distance du centre caméra (origine du repère
    caméra) à ce plan est alors simplement normal_cam · tvec (produit scalaire, simplifié
    car normal_cam est unitaire).
    """
    rotation_matrix, _ = cv2.Rodrigues(rvec)
    normal_cam = rotation_matrix @ np.array([0.0, 0.0, 1.0])
    return abs(float(np.dot(normal_cam, tvec.flatten())))
