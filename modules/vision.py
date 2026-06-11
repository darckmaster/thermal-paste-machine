import cv2
import numpy as np

from modules.config import ARUCO_DICT_ID, ARUCO_MARKER_SIZE_MM


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

        # Taille physique d'un côté du marqueur en mm — servira en Session 2 pour pixel → mm
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
