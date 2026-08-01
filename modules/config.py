import json
import os
from typing import Optional

# Paramètres globaux — à ajuster selon le matériel réel

# Charger local_config.json si présent (fichier gitignore, propre à chaque machine)
# Ce fichier permet de surcharger certains paramètres sans modifier le code suivi par git.
_local_cfg_path = os.path.join(os.path.dirname(__file__), "..", "local_config.json")
_local_cfg: dict = {}
if os.path.exists(_local_cfg_path):
    with open(_local_cfg_path, "r", encoding="utf-8") as _f:
        _local_cfg = json.load(_f)

# Caméra
# None = détection automatique (prend la dernière caméra détectée — voir Camera._find_best_index)
# Surcharger dans local_config.json avec {"camera_index": 0} (RPi) ou {"camera_index": 1} (PC)
CAMERA_INDEX: Optional[int] = _local_cfg.get("camera_index", None)
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 960
CAMERA_HEIGHT_MM = 200.0  # Hauteur physique de la caméra au-dessus de la zone de travail (mm)

# ArUco
ARUCO_DICT_ID = "DICT_4X4_50"
ARUCO_MARKER_SIZE_MM = 28.0  # Taille réelle des marqueurs en mm (mesurée : 2.8 cm × 2.8 cm)

# Machine (Marlin 1.1.8 — Geeetech I3)
# Le port dépend du système : "/dev/ttyUSB0" sur le RPi (puce CH340, confirmé le
# 2026-07-01), mais "COM3" ou similaire sous Windows. Surchargeable dans
# local_config.json avec {"serial_port": "COM3"} pour démarrer directement sur le bon
# port, sans avoir à le choisir dans la liste déroulante de l'écran 1 à chaque lancement.
SERIAL_PORT: str = str(_local_cfg.get("serial_port", "/dev/ttyUSB0"))
# Vitesse de la liaison série, à faire correspondre au firmware de la carte : la Geeetech
# est configurée à 250000 (confirmé le 2026-07-01, valeur inhabituelle mais courante chez
# Marlin). La carte de la CNC cible pourra être compilée avec une autre valeur (115200 est
# l'autre grand classique) → surchargeable avec {"serial_baudrate": 115200}.
# Un baudrate faux ne provoque pas d'erreur d'ouverture : le port s'ouvre, mais Marlin ne
# répond que des caractères illisibles → la commande part en TimeoutError. C'est le premier
# paramètre à vérifier si la machine ne répond pas alors que le port est le bon.
SERIAL_BAUDRATE: int = int(_local_cfg.get("serial_baudrate", 250000))
MACHINE_FEEDRATE_XY = 3000         # mm/min, déplacements rapides XY (max Marlin : 24000)
MACHINE_FEEDRATE_Z = 100           # mm/min, déplacement Z — limité à 120 mm/min par M203
MACHINE_FEEDRATE_DISPENSE = 100    # mm/min, dépose pâte (axe E)

# Zone de travail (à calibrer)
# Redéfinie le 2026-07-30 : les 4 marqueurs du plateau sont désormais aux coins du bâti
# complet (plateau carré 220×220 mm, mesuré bord EXTÉRIEUR à bord extérieur des marqueurs),
# et non plus resserrés autour de la pièce comme avant cette date (151×104 mm, valeur
# conservée dans l'historique CLAUDE.md/CONCEPTION.md). La distance centre-à-centre
# utilisée par l'homographie se déduit en retranchant une largeur de marqueur
# (ARUCO_MARKER_SIZE_MM) à la mesure bord-à-bord : 220 - 28 = 192 mm.
# ⚠️ Conséquence à vérifier sur machine réelle : le marqueur 0 a physiquement changé de
# position (coin du bâti au lieu du coin de la pièce) → MACHINE_ORIGIN_X/Y ci-dessous,
# mesurés le 2026-07-01 pour l'ANCIENNE position du marqueur 0, sont probablement
# obsolètes et doivent être remesurés (M114 au-dessus du nouveau marqueur 0).
WORK_AREA_WIDTH_MM = 220.0 - ARUCO_MARKER_SIZE_MM   # 192.0 — plateau carré
WORK_AREA_HEIGHT_MM = 220.0 - ARUCO_MARKER_SIZE_MM  # 192.0 — idem (carré, même valeur)
DISPENSE_Z_HEIGHT_MM = 1.0      # Hauteur buse au-dessus de la pièce pendant la dépose
MACHINE_Z_TRAVEL_MM = 5.0      # Hauteur de transit entre les points (assez haut pour ne rien toucher)

# Origine du repère ArUco dans le repère machine (mesuré le 2026-07-01 via M114)
# = position machine (mm depuis G28) du marqueur 3, coin HAUT-GAUCHE de la zone de travail.
# La formule de conversion (appliquée dans gui/screen_run.py) est :
#     machine_x = aruco_x + MACHINE_ORIGIN_X   ← addition : les deux X vont vers la droite
#     machine_y = MACHINE_ORIGIN_Y - aruco_y   ← SOUSTRACTION : le Y ArUco descend (repère
#                                                image), le Y machine monte vers le fond
# ⚠️ À REMESURER, pour DEUX raisons cumulées :
#   1. les marqueurs ont été déplacés aux coins du bâti (voir note WORK_AREA ci-dessus) ;
#   2. la disposition des IDs relevée le 2026-08-01 place le marqueur **3** en haut-gauche
#      (0=haut-droit, 1=bas-droit, 2=bas-gauche — voir _plateau_corner_positions_mm).
# Le M114 doit donc être fait buse au-dessus du marqueur 3, plus du marqueur 0.
MACHINE_ORIGIN_X = 20.0   # X machine du marqueur 3 (haut-gauche) — obsolète, à remesurer
MACHINE_ORIGIN_Y = 50.0   # Y machine du marqueur 3 (haut-gauche) — obsolète, à remesurer

# Calibration caméra
# Nombre minimum d'images à capturer avant de pouvoir lancer la calibration
CALIBRATION_MIN_IMAGES: int = int(_local_cfg.get("calibration_min_images", 15))

# Paramètres de la mire ChArUco utilisée pour la calibration
# Ces valeurs DOIVENT correspondre exactement à la mire physique imprimée.
# Si vous utilisez une mire tierce (imprimée, achetée...), renseignez ses paramètres ici.
# Surcharger dans local_config.json, ex: {"charuco_cols": 7, "charuco_rows": 5, ...}
CHARUCO_COLS: int       = int(_local_cfg.get("charuco_cols", 4))
CHARUCO_ROWS: int       = int(_local_cfg.get("charuco_rows", 4))
CHARUCO_SQUARE_MM: float = float(_local_cfg.get("charuco_square_mm", 15.0))
CHARUCO_MARKER_MM: float = float(_local_cfg.get("charuco_marker_mm", 12.0))
CHARUCO_DICT_NAME: str  = str(_local_cfg.get("charuco_dict", "DICT_4X4_50"))
# Disposition legacy (avant OpenCV 4.6) : true = compatible avec calib.io, kalibr et la plupart
# des générateurs externes. Passer à false uniquement si la mire est générée par OpenCV 4.6+.
CHARUCO_LEGACY_PATTERN: bool = bool(_local_cfg.get("charuco_legacy_pattern", True))

# Interface
TOUCHSCREEN_WIDTH = 800
TOUCHSCREEN_HEIGHT = 480
