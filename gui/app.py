# Fenêtre principale de l'application PyQt5
# Gère la navigation entre les 4 écrans via un QStackedWidget

import numpy as np
from PyQt5.QtWidgets import QMainWindow, QStackedWidget
from PyQt5.QtCore import Qt

from modules.config import (
    TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT,
    SERIAL_PORT, SERIAL_BAUDRATE,
    MACHINE_FEEDRATE_XY, MACHINE_FEEDRATE_Z, MACHINE_FEEDRATE_DISPENSE,
)
from modules.machine import Machine
from gui.screen_capture import ScreenCapture
from gui.screen_zone import ScreenZone
from gui.screen_run import ScreenRun
from gui.screen_report import ScreenReport


# Feuille de style globale appliquée à toute l'application
# Définir ici plutôt que dans chaque écran → cohérence visuelle garantie
STYLESHEET = """
QWidget {
    background-color: #1e1e1e;
    color: #f0f0f0;
    font-size: 15px;
    font-family: sans-serif;
}
QPushButton {
    background-color: #2d5f8a;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 16px;
    font-weight: bold;
    min-height: 55px;
}
QPushButton:hover {
    background-color: #3a7cbf;
}
QPushButton:pressed {
    background-color: #1e4060;
}
QPushButton:disabled {
    background-color: #3a3a3a;
    color: #666;
}
QPushButton[role="success"] {
    background-color: #2d6b2d;
}
QPushButton[role="danger"] {
    background-color: #8b1a1a;
}
QPushButton[role="secondary"] {
    background-color: #4a4a4a;
}
QLabel[role="title"] {
    font-size: 17px;
    font-weight: bold;
    color: #7ec8e3;
    padding: 4px 0px;
}
QLabel[role="status"] {
    color: #888;
    font-size: 13px;
}
QLabel[role="camera"] {
    background-color: #111;
    border: 1px solid #333;
}
"""


class MainApp(QMainWindow):
    """Fenêtre principale — contient la pile d'écrans et gère la navigation.

    Navigation :
        ScreenCapture → ScreenZone → ScreenRun → ScreenReport → ScreenCapture
    Chaque écran émet un signal quand il a terminé son rôle.
    MainApp reçoit ce signal et bascule vers l'écran suivant.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Machine de Dépose de Pâte Thermique")

        # Créer l'objet Machine une seule fois — la connexion série est ouverte
        # dans le thread d'exécution (RunWorker) pour ne pas bloquer l'interface
        self._machine = Machine(
            port=SERIAL_PORT,
            baudrate=SERIAL_BAUDRATE,
            feedrate_xy=MACHINE_FEEDRATE_XY,
            feedrate_z=MACHINE_FEEDRATE_Z,
            feedrate_dispense=MACHINE_FEEDRATE_DISPENSE,
        )

        # Fixer la taille à la résolution de l'écran tactile — pas de barre de titre en prod
        self.setFixedSize(TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT)

        # Appliquer le thème sombre global
        self.setStyleSheet(STYLESHEET)

        # QStackedWidget = pile de widgets — un seul visible à la fois
        # C'est le mécanisme standard PyQt5 pour naviguer entre des "pages"
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # Créer les 4 écrans dans l'ordre de navigation
        self._screen_capture = ScreenCapture()
        self._screen_zone = ScreenZone()
        self._screen_run = ScreenRun()
        self._screen_report = ScreenReport()

        # Ajouter les écrans à la pile — l'index correspond à l'ordre d'ajout
        self._stack.addWidget(self._screen_capture)   # index 0
        self._stack.addWidget(self._screen_zone)       # index 1
        self._stack.addWidget(self._screen_run)        # index 2
        self._stack.addWidget(self._screen_report)     # index 3

        # Données du cycle courant — stockées au fil de la navigation pour le rapport PDF
        self._captured_image = None   # photo de la pièce (numpy BGR)
        self._points_mm: list = []    # tracé de l'opérateur (coordonnées ArUco mm)
        self._quantity: float = 0.0   # quantité de pâte configurée (mm E / mm tracé)

        # Connecter les signaux de chaque écran à la méthode de navigation correspondante
        # Signal émis par l'écran → slot qui bascule vers l'écran suivant
        self._screen_capture.photo_validated.connect(self._go_to_zone)
        self._screen_zone.zone_configured.connect(self._go_to_run)
        self._screen_run.run_finished.connect(self._go_to_report)
        self._screen_report.new_piece_requested.connect(self._go_to_capture)

        # Démarrer sur l'écran de capture
        self._go_to_capture()

    # ------------------------------------------------------------------ navigation

    def _go_to_capture(self) -> None:
        """Basculer vers l'écran de capture et démarrer la caméra."""
        self._screen_capture.start_camera()
        self._stack.setCurrentIndex(0)

    def _go_to_zone(self, image: np.ndarray) -> None:
        """Basculer vers l'écran de sélection de zone avec la photo capturée."""
        # Arrêter la caméra avant de quitter l'écran de capture — libère la ressource USB
        self._screen_capture.stop_camera()
        # Conserver l'image pour le rapport PDF généré à la fin du cycle
        self._captured_image = image
        self._screen_zone.set_image(image)
        self._stack.setCurrentIndex(1)

    def _go_to_run(self, points_mm: object, quantity: float) -> None:
        """Basculer vers l'écran d'exécution avec le tracé et la quantité configurés."""
        # Conserver le tracé et la quantité pour le rapport PDF
        self._points_mm = list(points_mm)
        self._quantity = quantity
        self._screen_run.start_run(self._machine, points_mm, quantity)
        self._stack.setCurrentIndex(2)

    def _go_to_report(self, status: str) -> None:
        """Basculer vers l'écran de rapport en lui transmettant toutes les données du cycle."""
        self._screen_report.set_result(
            self._captured_image,
            self._points_mm,
            self._quantity,
            status,
        )
        self._stack.setCurrentIndex(3)

    # ------------------------------------------------------------------ cycle de vie

    def closeEvent(self, event) -> None:
        """Nettoyer les ressources avant de fermer la fenêtre."""
        # Toujours libérer la caméra proprement — sinon le flux reste bloqué
        self._screen_capture.stop_camera()
        event.accept()
