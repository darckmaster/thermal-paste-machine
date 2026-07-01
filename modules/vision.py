import cv2
import numpy as np

from modules.config import (
    ARUCO_DICT_ID,
    ARUCO_MARKER_SIZE_MM,
    WORK_AREA_WIDTH_MM,
    WORK_AREA_HEIGHT_MM,
)


# Correspondance entre le nom de dictionnaire (string de config.py) et la constante interne OpenCV
_ARUCO_DICTS = {
    "DICT_4X4_50": cv2.aruco.DICT_4X4_50,
    "DICT_4X4_100": cv2.aruco.DICT_4X4_100,
    "DICT_5X5_50": cv2.aruco.DICT_5X5_50,
}


class VisionProcessor:
    """Détection de marqueurs ArUco et calibrage géométrique (Phase 2)."""

    def __init__(
        self,
        aruco_dict_id: str = ARUCO_DICT_ID,
        marker_real_size_mm: float = ARUCO_MARKER_SIZE_MM,
    ) -> None:
        # Vérifier que le nom de dictionnaire passé en config est bien supporté
        if aruco_dict_id not in _ARUCO_DICTS:
            raise ValueError(
                f"Dictionnaire ArUco inconnu : '{aruco_dict_id}'. "
                f"Valeurs acceptées : {list(_ARUCO_DICTS)}"
            )

        # Charger le dictionnaire ArUco — ensemble de motifs binaires que le détecteur reconnaît
        aruco_dict = cv2.aruco.getPredefinedDictionary(_ARUCO_DICTS[aruco_dict_id])

        # Paramètres de détection par défaut — fonctionnent bien pour une webcam USB standard
        aruco_params = cv2.aruco.DetectorParameters()

        # Créer le détecteur ArUco (API OpenCV >= 4.7 — remplace l'ancienne fonction cv2.aruco.detectMarkers)
        self._detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)

        # Taille physique d'un côté du marqueur en mm
        self.marker_real_size_mm: float = marker_real_size_mm

    def detect_markers(self, image: np.ndarray) -> dict:
        """Détecte les marqueurs ArUco dans l'image.

        Retourne un dict {id: corners} où :
        - id    : entier (ex. 0, 1, 2, 3)
        - corners : tableau numpy (4, 2) des coins du marqueur en pixels (x, y)

        Retourne un dict vide si aucun marqueur n'est trouvé.
        """
        # Lancer la détection — OpenCV retourne :
        #   corners : liste de tableaux de forme (1, 4, 2)
        #   ids     : tableau de forme (N, 1), ou None si rien n'est détecté
        corners, ids, _ = self._detector.detectMarkers(image)

        result = {}

        # ids vaut None quand aucun marqueur n'est visible dans l'image
        if ids is not None:
            for i, marker_id in enumerate(ids.flatten()):
                # corners[i] a la forme (1, 4, 2) — on retire la première dimension avec [0]
                # pour obtenir (4, 2) : les 4 coins dans l'ordre haut-gauche, haut-droit,
                # bas-droit, bas-gauche (sens horaire, convention OpenCV)
                result[int(marker_id)] = corners[i][0]

        return result

    def compute_homography(self, detected_markers: dict) -> np.ndarray:
        """Calcule la matrice d'homographie H (3×3) à partir des 4 marqueurs détectés.

        H mappe les coordonnées pixel de l'image source vers les coordonnées réelles en mm.
        Les 4 marqueurs IDs 0, 1, 2, 3 doivent être présents.

        Convention de placement des marqueurs dans la zone de travail :
            ID 0 → coin bas-gauche   (  0 mm,            0 mm              )
            ID 1 → coin haut-gauche  (  0 mm,            WORK_AREA_HEIGHT  )
            ID 2 → coin haut-droit   (  WORK_AREA_WIDTH, WORK_AREA_HEIGHT  )
            ID 3 → coin bas-droit    (  WORK_AREA_WIDTH, 0 mm              )
        """
        ids_requis = {0, 1, 2, 3}
        ids_manquants = ids_requis - set(detected_markers.keys())
        if ids_manquants:
            raise ValueError(
                f"Impossible de calculer l'homographie — marqueurs manquants : {ids_manquants}"
            )

        # Centres des 4 marqueurs dans l'image (moyenne des 4 coins de chaque marqueur)
        # mean(axis=0) sur un tableau (4, 2) retourne le point central (x_moy, y_moy)
        src_pts = np.array([
            detected_markers[0].mean(axis=0),  # centre du marqueur 0 en pixels
            detected_markers[1].mean(axis=0),  # centre du marqueur 1 en pixels
            detected_markers[2].mean(axis=0),  # centre du marqueur 2 en pixels
            detected_markers[3].mean(axis=0),  # centre du marqueur 3 en pixels
        ], dtype=np.float32)

        # Positions réelles des 4 marqueurs dans la zone de travail (en mm)
        # Repère ArUco : origine (0,0) au marqueur 0 (bas-gauche de l'image)
        #   X croît vers la droite (vers ID 3, bas-droit)
        #   Y croît vers le haut  (vers ID 1, haut-gauche)
        # Ce repère est aligné avec le repère machine : X+ = buse à droite, Y+ = plateau arrière.
        # Placement physique confirmé le 2026-07-01 :
        #   ID 0 → bas-gauche  (0,       0      )
        #   ID 1 → haut-gauche (0,       104 mm )
        #   ID 2 → haut-droit  (151 mm,  104 mm )
        #   ID 3 → bas-droit   (151 mm,  0      )
        dst_pts = np.array([
            [0,                  0                   ],  # ID 0 bas-gauche → origine
            [0,                  WORK_AREA_HEIGHT_MM ],  # ID 1 haut-gauche → Y max
            [WORK_AREA_WIDTH_MM, WORK_AREA_HEIGHT_MM ],  # ID 2 haut-droit  → X max, Y max
            [WORK_AREA_WIDTH_MM, 0                   ],  # ID 3 bas-droit   → X max
        ], dtype=np.float32)

        # getPerspectiveTransform calcule H exactement à partir de 4 paires de points
        # (contrairement à findHomography qui utilise RANSAC pour plus de robustesse,
        # mais ici 4 points bien définis suffisent)
        return cv2.getPerspectiveTransform(src_pts, dst_pts)

    def warp_image(
        self, image: np.ndarray, homography: np.ndarray, output_size: tuple
    ) -> np.ndarray:
        """Redresse l'image en vue du dessus, à l'échelle de la zone de travail.

        homography  : matrice H pixel→mm issue de compute_homography()
        output_size : (largeur_px, hauteur_px) de l'image de sortie
                      ex. (300, 200) pour 2 px/mm sur une zone 150×100 mm

        L'image retournée représente la zone de travail vue du dessus,
        où chaque pixel correspond à output_size / WORK_AREA mm.
        """
        output_width, output_height = output_size

        # Facteurs d'échelle : convertissent mm → pixels de l'image de sortie
        scale_x = output_width  / WORK_AREA_WIDTH_MM
        scale_y = output_height / WORK_AREA_HEIGHT_MM

        # Matrice d'échelle 3×3 pour passer de l'espace mm vers les pixels de sortie
        scale_matrix = np.array([
            [scale_x, 0,       0],
            [0,       scale_y, 0],
            [0,       0,       1],
        ], dtype=np.float64)

        # H_warp = scale_matrix @ H mappe pixels source → pixels de sortie
        # warpPerspective utilise H_warp^{-1} pour retrouver, pour chaque pixel
        # de sortie, le pixel correspondant dans l'image source
        H_warp = scale_matrix @ homography

        return cv2.warpPerspective(image, H_warp, output_size)

    def pixel_to_mm(
        self, px: float, py: float, homography: np.ndarray
    ) -> tuple[float, float]:
        """Convertit des coordonnées pixel (image source) en coordonnées réelles (mm).

        Utilise la matrice H issue de compute_homography() qui mappe pixel→mm.
        Retourne (x_mm, y_mm) dans le repère de la zone de travail.
        """
        # perspectiveTransform attend un tableau de forme (1, N, 2)
        # on enveloppe le point unique dans les deux niveaux de tableau requis
        pt = np.array([[[px, py]]], dtype=np.float32)
        pt_mm = cv2.perspectiveTransform(pt, homography)

        # pt_mm a la forme (1, 1, 2) — on extrait les deux coordonnées
        return float(pt_mm[0][0][0]), float(pt_mm[0][0][1])
