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

# Taille du plateau — mesure bord EXTÉRIEUR à bord extérieur des 4 marqueurs de coin.
# Redéfinie le 2026-07-30 : les 4 marqueurs sont aux coins du bâti complet (plateau carré
# supposé 220×220 mm), et non plus resserrés autour de la pièce comme avant cette date
# (151×104 mm, valeur conservée dans l'historique CLAUDE.md/CONCEPTION.md).
#
# ⚠️ ACTION M1 EN ATTENTE (voir CLAUDE.md § 7 bis) : les 220 mm ne sont PAS mesurés, ils
# sont supposés. Cette valeur est devenue un paramètre au lot C2bis précisément parce
# qu'elle sert de **repli quand les 4 tags ne sont pas détectés** — c'est-à-dire dans le
# mode NOMINAL de la Geeetech, où la caméra ne cadre que 2 tags et où l'origine du repère
# (marqueur 2) doit donc être extrapolée. Toute erreur ici décale alors TOUTE la dépose.
# Surcharger dans local_config.json dès que la mesure est faite : {"plateau_size_mm": 218.5}
PLATEAU_SIZE_MM: float = float(_local_cfg.get("plateau_size_mm", 220.0))
# Deux surcharges séparées pour un plateau non carré (la CNC cible, peut-être). Elles
# retombent par défaut sur la mesure carrée ci-dessus.
PLATEAU_WIDTH_MM: float = float(_local_cfg.get("plateau_width_mm", PLATEAU_SIZE_MM))
PLATEAU_HEIGHT_MM: float = float(_local_cfg.get("plateau_height_mm", PLATEAU_SIZE_MM))

# Zone de travail = distance CENTRE-À-CENTRE des marqueurs, seule grandeur qu'utilise
# l'homographie. Elle se déduit de la mesure bord-à-bord en retranchant une largeur de
# marqueur : 220 - 28 = 192 mm.
WORK_AREA_WIDTH_MM = PLATEAU_WIDTH_MM - ARUCO_MARKER_SIZE_MM   # 192.0 par défaut
WORK_AREA_HEIGHT_MM = PLATEAU_HEIGHT_MM - ARUCO_MARKER_SIZE_MM  # 192.0 par défaut
DISPENSE_Z_HEIGHT_MM = 1.0      # Hauteur buse au-dessus de la pièce pendant la dépose
MACHINE_Z_TRAVEL_MM = 5.0      # Hauteur de transit entre les points (assez haut pour ne rien toucher)

# Origine du repère plateau dans le repère machine (mesuré le 2026-08-03)
# = position machine (mm depuis G28) du marqueur **2**, coin BAS-GAUCHE du plateau.
# La formule de conversion (appliquée dans gui/screen_run.py) est :
#     machine_x = plateau_x + MACHINE_ORIGIN_X   ← addition, les deux X vont vers la droite
#     machine_y = plateau_y + MACHINE_ORIGIN_Y   ← addition AUSSI depuis le lot C2bis : le
#                                                  repère plateau monte comme l'axe machine
#
# ✅ MESURÉ le 2026-08-03 sur la Geeetech, dispositif de seringue MONTÉ (action M2 bis).
# Le relevé est pris dans l'autre sens que celui du 2026-08-02, et c'est plus commode : au
# lieu d'amener la buse sur le marqueur puis de lire M114, on lit où tombe la pointe quand
# la machine est au homing. Relevé d'Erwann :
#
#   Au homing, la POINTE DE SERINGUE est au point (-6.0, +2.0) du repère plateau.
#
# On en déduit l'origine par simple inversion. La conversion ci-dessus se relit
# `plateau = machine - ORIGIN` ; appliquée au homing, où `machine = (0, 0)` :
#     -6 = 0 - MACHINE_ORIGIN_X   →   MACHINE_ORIGIN_X = +6.0
#     +2 = 0 - MACHINE_ORIGIN_Y   →   MACHINE_ORIGIN_Y = -2.0
#
# Ce relevé vise la POINTE et non la buse : il absorbe l'action M2 ter, qui devait mesurer
# séparément le décalage entre les deux. Recoupement avec la mesure du 2026-08-02 (qui
# visait la buse, sans seringue montée) : l'écart buse↔pointe ressort à (-1, +2) mm, un
# ordre de grandeur crédible pour un support de seringue. Les deux mesures se confirment.
#
# 🔎 CE QUE CETTE MESURE A TRANCHÉ. Le relevé du 2026-08-02 donnait Y = 0.00 avec un
# compteur de pas à 0 EXACT : l'axe Y n'avait donc pas bougé d'un pas depuis le homing, et
# la valeur avait été enregistrée sous réserve — soit le marqueur 2 tombait déjà sous la
# buse, soit le plateau BUTAIT sur la fin de course et 0 était une limite, pas une mesure.
# La nouvelle valeur, NÉGATIVE, tranche pour la seconde lecture : c'était bien une butée.
# Leçon à garder : une grandeur relevée à 0 exact, sur un axe dont le compteur de pas est
# lui aussi à 0 exact, est presque toujours une butée et non une mesure.
#
# ⚠️ CONSÉQUENCE PHYSIQUE À NE PAS OUBLIER — une bande de 2 mm en bas du plateau est HORS
# COURSE. Atteindre `plateau_y = 0` demanderait `machine_y = -2`, en deçà de la fin de
# course : seul `plateau_y >= 2` est réellement atteignable. Un cordon tracé plus bas ne
# fera PAS échouer Marlin, qui rogne les coordonnées hors course EN SILENCE — la dépose
# sortirait déformée et passerait pour une erreur de vision. D'où le contrôle de course
# décidé pour le lot D1 (décision D12, CLAUDE.md section 8), à faire AVANT le premier
# mouvement et à signaler en nommant la zone fautive.
#
# ⚠️ Le SENS des axes machine (action M4) reste à établir en interactif, machine sous
# tension. Le relevé ci-dessus est COHÉRENT avec les deux additions, mais il ne les prouve
# pas : il a été pris en se plaçant déjà dans cette convention. C'est le passage visible au
# zéro de chaque zone (décision D8 du lot D) qui le validera, à l'œil, pendant D2.
#
# 📜 Historique des valeurs : 20/50 (2026-07-01, deux conventions de repère en arrière),
# puis 5.0/0.0 (2026-08-02, buse sans seringue, réserve sur Y), puis les valeurs actuelles.
MACHINE_ORIGIN_X = 6.0    # X machine du marqueur 2 (bas-gauche) — pointe, 2026-08-03
MACHINE_ORIGIN_Y = -2.0   # Y machine du marqueur 2 — NÉGATIF : bas du plateau hors course

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

# Préparations (plateaux enregistrés : zones + cordons + paramètres)
# Dossier où sont écrits les fichiers JSON de travail, à la racine du projet.
# Chemin absolu calculé depuis l'emplacement de ce fichier : le dossier doit être
# trouvé quel que soit le répertoire courant depuis lequel l'application est lancée.
PREPARATIONS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "preparations")
)

# Paramètres de dépose par défaut, repris dans chaque nouvelle préparation.
# Ils déterminent ensemble la quantité de pâte déposée : plus la buse avance lentement
# pour une vitesse d'extrusion donnée, plus le cordon est épais.
DEFAULT_TRAVEL_SPEED_MM_MIN = float(
    _local_cfg.get("default_travel_speed_mm_min", MACHINE_FEEDRATE_XY)
)
DEFAULT_EXTRUSION_SPEED_MM_MIN = float(
    _local_cfg.get("default_extrusion_speed_mm_min", MACHINE_FEEDRATE_DISPENSE)
)

# Interface
TOUCHSCREEN_WIDTH = 800
TOUCHSCREEN_HEIGHT = 480
