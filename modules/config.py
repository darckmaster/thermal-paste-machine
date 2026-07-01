# Paramètres globaux — à ajuster selon le matériel réel

# Caméra
CAMERA_INDEX = 0
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
DISPENSE_Z_HEIGHT_MM = 1.0      # Hauteur buse au-dessus de la pièce

# Interface
TOUCHSCREEN_WIDTH = 800
TOUCHSCREEN_HEIGHT = 480
