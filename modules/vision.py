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


def _plateau_corner_positions_mm() -> dict:
    """Positions mm connues des 4 marqueurs de coin du plateau, dans son propre repère
    (origine au marqueur 3, X vers ID0, Y vers ID2 — voir compute_homography).

    Disposition physique constatée le 2026-08-01 (remplace l'ancienne, où le
    marqueur 0 était en bas-gauche) :

        3 ─────── 0
        │         │
        2 ─────── 1

    Le repère mm a son origine sur le marqueur 3 (HAUT-GAUCHE) et son axe Y
    dirigé vers le BAS, exactement comme les lignes d'une image. Deux raisons :
      1. toutes les coordonnées du plateau restent positives (0 → WORK_AREA),
         ce qui évite les index négatifs et garde le clipping de screen_zone
         simple ;
      2. l'image produite par warp_image()/warp_region() s'affiche alors dans le
         bon sens. Avec l'ancien repère (Y vers le haut), le haut de la photo
         ressortait en bas de l'image redressée — miroir vertical présent depuis
         la Phase 2 et corrigé le 2026-08-01.

    Contrepartie : l'axe Y est désormais OPPOSÉ à l'axe Y machine (qui, lui,
    croît vers le fond). La conversion se fait en un seul endroit, dans
    gui/screen_run.py : machine_y = MACHINE_ORIGIN_Y - y_mm.

    Table partagée par compute_homography() (4 marqueurs, précis) et
    compute_homography_approx() (2-3 marqueurs, dégradé — repli caméra Geeetech,
    voir son docstring).
    """
    return {
        3: (0.0,                  0.0),                  # haut-gauche = origine
        0: (WORK_AREA_WIDTH_MM,   0.0),                  # haut-droit
        1: (WORK_AREA_WIDTH_MM,   WORK_AREA_HEIGHT_MM),  # bas-droit
        2: (0.0,                  WORK_AREA_HEIGHT_MM),  # bas-gauche
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

        Convention de placement des marqueurs dans la zone de travail
        (mise à jour le 2026-08-01 — voir _plateau_corner_positions_mm) :
            ID 3 → coin haut-gauche  (  0 mm,            0 mm              )
            ID 0 → coin haut-droit   (  WORK_AREA_WIDTH, 0 mm              )
            ID 1 → coin bas-droit    (  WORK_AREA_WIDTH, WORK_AREA_HEIGHT  )
            ID 2 → coin bas-gauche   (  0 mm,            WORK_AREA_HEIGHT  )
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
        # Repère ArUco : origine (0,0) au marqueur 3 (haut-gauche de l'image)
        #   X croît vers la droite (vers ID 0, haut-droit)
        #   Y croît vers le bas   (vers ID 2, bas-gauche) — comme les lignes d'une image
        # ⚠️ X est aligné avec l'axe X machine, mais Y est INVERSÉ par rapport à l'axe Y
        # machine (qui croît vers le fond) — l'inversion est faite dans gui/screen_run.py.
        corners = _plateau_corner_positions_mm()
        dst_pts = np.array([corners[0], corners[1], corners[2], corners[3]], dtype=np.float32)

        # getPerspectiveTransform calcule H exactement à partir de 4 paires de points
        # (contrairement à findHomography qui utilise RANSAC pour plus de robustesse,
        # mais ici 4 points bien définis suffisent)
        return cv2.getPerspectiveTransform(src_pts, dst_pts)

    def compute_homography_approx(self, detected_markers: dict) -> np.ndarray:
        """Calcule une homographie APPROXIMATIVE à partir de 2 ou 3 marqueurs du
        plateau seulement (parmi les IDs 0-3), au lieu des 4 exigés par
        compute_homography().

        Pourquoi cette méthode existe :
          Sur la Geeetech (PoC), la caméra est trop proche et trop peu mobile pour
          voir les 4 coins du plateau en même temps dès que celui-ci fait toute la
          taille du bâti (contrainte matérielle constatée le 2026-07-30, pas un bug
          logiciel). Seuls 2 marqueurs adjacents (ex. les 2 du haut) restent visibles.

        Différence avec compute_homography() — à bien comprendre avant d'utiliser
        cette méthode :
          compute_homography() calcule une vraie transformation PERSPECTIVE (4 points,
          8 degrés de liberté) : elle corrige le fait que la caméra n'est jamais
          parfaitement à la verticale (effet "trapèze"). Avec seulement 2 points, cette
          correction est impossible à déterminer — cette méthode calcule à la place une
          similitude (rotation + échelle uniforme + translation, 4 degrés de liberté,
          cv2.estimateAffinePartial2D) qui suppose une caméra quasi verticale. Résultat :
          moins précis que compute_homography(), avec une erreur qui grandit avec
          l'inclinaison réelle de la caméra. À réserver au PoC Geeetech ; la CNC cible,
          qui a la place pour reculer la caméra, doit utiliser compute_homography().

        Paramètres :
            detected_markers : dict {id: corners} — seuls les IDs 0-3 présents comptent,
                                les autres (ex. marqueurs de zone 4/5) sont ignorés.

        Retourne une matrice 3×3 (compatible pixel_to_mm/warp_image comme
        compute_homography(), mais sans terme de perspective).

        Lève ValueError si moins de 2 marqueurs parmi 0-3 sont présents.
        """
        corners = _plateau_corner_positions_mm()
        ids_disponibles = sorted(set(detected_markers.keys()) & corners.keys())

        if len(ids_disponibles) < 2:
            raise ValueError(
                f"Impossible d'approximer l'homographie — au moins 2 marqueurs du "
                f"plateau (IDs {sorted(corners.keys())}) sont nécessaires, "
                f"{len(ids_disponibles)} trouvé(s)"
            )

        src_pts = np.array(
            [detected_markers[i].mean(axis=0) for i in ids_disponibles], dtype=np.float32
        )
        dst_pts = np.array([corners[i] for i in ids_disponibles], dtype=np.float32)

        # estimateAffinePartial2D résout exactement avec 2 points (4 inconnues : rotation,
        # échelle, tx, ty ↔ 4 équations) ; avec 3 points, ajuste au mieux (moindres carrés)
        matrix_2x3, _inliers = cv2.estimateAffinePartial2D(src_pts, dst_pts)
        if matrix_2x3 is None:
            raise ValueError(
                "estimateAffinePartial2D n'a pas pu résoudre de transformation — "
                "vérifier que les marqueurs détectés ne sont pas confondus/alignés"
            )

        # Compléter en 3×3 (ligne [0, 0, 1]) pour rester compatible avec
        # cv2.perspectiveTransform (pixel_to_mm) et cv2.warpPerspective (warp_image),
        # qui acceptent une matrice purement affine sans terme de perspective
        return np.vstack([matrix_2x3, [0.0, 0.0, 1.0]])

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

    def warp_region(
        self,
        image: np.ndarray,
        homography: np.ndarray,
        origin_mm: tuple,
        px_per_mm: float,
        output_size: tuple,
    ) -> np.ndarray:
        """Redresse UNIQUEMENT une sous-région de l'image (ex. la zone de dépose),
        au lieu de tout le plateau (WORK_AREA) comme warp_image().

        Pourquoi cette méthode existe (et pas juste warp_image() + découpage) :
          warp_image() dimensionne toujours son image de sortie sur tout le
          WORK_AREA connu. Si la caméra n'a photographié qu'une partie du
          plateau (cas du repli 2-3 marqueurs, voir compute_homography_approx),
          les zones du canevas de sortie qui ne correspondent à aucun pixel de
          la photo source sont remplies en NOIR par warpPerspective. Si la
          sous-région qu'on veut afficher (la zone de dépose) tombe dans cette
          zone jamais photographiée, découper après-coup donne une image
          entièrement noire (bug constaté le 2026-07-30 avec le repli
          Geeetech). warp_region() redresse directement la sous-région voulue
          — il ne demande donc que des pixels réellement présents dans la
          photo, tant que la zone elle-même y est visible.

        Paramètres :
            origin_mm  : (x_min, y_min) du coin de la sous-région, dans le
                         repère du plateau (ex. le retour de deposit_zone_bounds_mm)
            px_per_mm  : échelle de sortie, identique en X et en Y
            output_size: (largeur_px, hauteur_px) de l'image de sortie
        """
        x0_mm, y0_mm = origin_mm

        # mm(plateau) → pixel(sous-région) : translater à l'origine de la zone
        # puis mettre à l'échelle — pas besoin de connaître WORK_AREA ici
        zone_matrix = np.array([
            [px_per_mm, 0,          -x0_mm * px_per_mm],
            [0,         px_per_mm,  -y0_mm * px_per_mm],
            [0,         0,          1                  ],
        ], dtype=np.float64)

        # H_zone = zone_matrix @ homography mappe pixels source → pixels de la sous-région
        H_zone = zone_matrix @ homography

        return cv2.warpPerspective(image, H_zone, output_size)

    def deposit_zone_bounds_mm(
        self,
        detected_markers: dict,
        homography: np.ndarray,
        id_a: int = 4,
        id_b: int = 5,
    ) -> tuple[float, float, float, float]:
        """Calcule les bornes en mm de la zone de dépose, délimitée par deux
        marqueurs ArUco placés à ses coins opposés (en diagonale).

        La zone est supposée alignée avec les axes du plateau (pas de rotation) :
        les deux marqueurs suffisent donc à définir un rectangle simple, sans
        recalculer une seconde homographie dédiée à la zone.

        Retourne (x_min, y_min, x_max, y_max) en mm, dans le repère du plateau
        (celui de compute_homography — origine au marqueur 0).

        Lève ValueError si l'un des deux marqueurs est absent.
        """
        ids_requis = {id_a, id_b}
        ids_manquants = ids_requis - set(detected_markers.keys())
        if ids_manquants:
            raise ValueError(
                f"Impossible de délimiter la zone de dépose — marqueurs manquants : {ids_manquants}"
            )

        # Centre de chaque marqueur en pixels, converti en mm via l'homographie du plateau
        cx_a, cy_a = detected_markers[id_a].mean(axis=0)
        x_a, y_a = self.pixel_to_mm(cx_a, cy_a, homography)

        cx_b, cy_b = detected_markers[id_b].mean(axis=0)
        x_b, y_b = self.pixel_to_mm(cx_b, cy_b, homography)

        # min/max plutôt que "a puis b" : peu importe lequel des deux marqueurs
        # est physiquement en haut-gauche ou bas-droit de la zone
        return (min(x_a, x_b), min(y_a, y_b), max(x_a, x_b), max(y_a, y_b))

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
