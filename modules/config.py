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
SERIAL_PORT = "/dev/ttyUSB0"       # Confirmé le 2026-07-01 (puce CH340)
SERIAL_BAUDRATE = 250000            # Confirmé le 2026-07-01 (Geeetech configurée à 250000)
MACHINE_FEEDRATE_XY = 3000         # mm/min, déplacements rapides XY (max Marlin : 24000)
MACHINE_FEEDRATE_Z = 100           # mm/min, déplacement Z — limité à 120 mm/min par M203
MACHINE_FEEDRATE_DISPENSE = 100    # mm/min, dépose pâte (axe E)

# Zone de travail (à calibrer)
WORK_AREA_WIDTH_MM = 151.0   # Mesuré le 2026-06-12 : distance centre-à-centre marqueurs 0↔1
WORK_AREA_HEIGHT_MM = 104.0  # Mesuré le 2026-06-12 : distance centre-à-centre marqueurs 0↔3
DISPENSE_Z_HEIGHT_MM = 1.0      # Hauteur buse au-dessus de la pièce pendant la dépose
MACHINE_Z_TRAVEL_MM = 5.0      # Hauteur de transit entre les points (assez haut pour ne rien toucher)

# Origine du repère ArUco dans le repère machine (confirmé le 2026-07-01 via M114)
# = position machine (mm depuis G28) du marqueur 0, coin bas-gauche de la zone de travail.
# La formule de conversion est : machine_x = aruco_x + MACHINE_ORIGIN_X
#                                 machine_y = aruco_y + MACHINE_ORIGIN_Y
MACHINE_ORIGIN_X = 20.0   # X machine du marqueur 0 (bas-gauche)
MACHINE_ORIGIN_Y = 50.0   # Y machine du marqueur 0 (bas-gauche)

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
