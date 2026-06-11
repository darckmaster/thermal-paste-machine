# Paramètres globaux — à ajuster selon le matériel réel

# Caméra
CAMERA_INDEX = 0
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 960

# ArUco
ARUCO_DICT_ID = "DICT_4X4_50"
ARUCO_MARKER_SIZE_MM = 28.0  # Taille réelle des marqueurs en mm (mesurée : 2.8 cm × 2.8 cm)

# Machine (Marlin)
SERIAL_PORT = "/dev/ttyUSB0"    # Ou /dev/ttyACM0 selon branchement
SERIAL_BAUDRATE = 115200
MACHINE_FEEDRATE_MOVE = 3000    # mm/min, déplacements rapides
MACHINE_FEEDRATE_DISPENSE = 100 # mm/min, dépose pâte

# Zone de travail (à calibrer)
WORK_AREA_WIDTH_MM = 152.0   # Mesuré le 2026-06-11 : distance centre-à-centre marqueurs 0↔1
WORK_AREA_HEIGHT_MM = 106.0  # Mesuré le 2026-06-11 : distance centre-à-centre marqueurs 0↔3
DISPENSE_Z_HEIGHT_MM = 1.0      # Hauteur buse au-dessus de la pièce

# Interface
TOUCHSCREEN_WIDTH = 800
TOUCHSCREEN_HEIGHT = 480
