# Fenêtre principale de l'application PyQt5
# Gère la navigation entre les 4 écrans via un QStackedWidget

import numpy as np
from PyQt5.QtWidgets import QMainWindow, QStackedWidget
from PyQt5.QtCore import Qt

from modules.config import (
    TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT,
    SERIAL_PORT, SERIAL_BAUDRATE,
    MACHINE_FEEDRATE_XY, MACHINE_FEEDRATE_Z, MACHINE_FEEDRATE_DISPENSE,
    CAMERA_INDEX,
)
from modules.camera import Camera
from modules.machine import Machine
from gui.screen_capture import ScreenCapture
from gui.screen_zone import ScreenZone
from gui.screen_run import ScreenRun
from gui.screen_report import ScreenReport
from gui.screen_calibration import ScreenCalibration
from gui.screen_plateau import ScreenPlateau
from gui.screen_cordons import ScreenCordons


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

        # Sur le RPi avec l'écran tactile, décommenter pour fixer la taille en production :
        # self.setFixedSize(TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT)

        # Appliquer le thème sombre global
        self.setStyleSheet(STYLESHEET)

        # QStackedWidget = pile de widgets — un seul visible à la fois
        # C'est le mécanisme standard PyQt5 pour naviguer entre des "pages"
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # Créer les 6 écrans dans l'ordre de navigation
        self._screen_capture = ScreenCapture()
        self._screen_zone = ScreenZone()
        self._screen_run = ScreenRun()
        self._screen_report = ScreenReport()
        self._screen_calibration = ScreenCalibration()
        self._screen_plateau = ScreenPlateau()
        self._screen_cordons = ScreenCordons()

        # Ajouter les écrans à la pile — l'index correspond à l'ordre d'ajout
        self._stack.addWidget(self._screen_capture)     # index 0
        self._stack.addWidget(self._screen_zone)        # index 1
        self._stack.addWidget(self._screen_run)         # index 2
        self._stack.addWidget(self._screen_report)      # index 3
        self._stack.addWidget(self._screen_calibration) # index 4
        self._stack.addWidget(self._screen_plateau)     # index 5
        self._stack.addWidget(self._screen_cordons)     # index 6

        # Fournir la machine à screen_capture pour le bouton Homing
        self._screen_capture.set_machine(self._machine)

        # Caméra unique partagée entre screen_capture et screen_calibration
        # → évite un release+open de 1-2 s à chaque changement d'écran
        try:
            self._camera = Camera(CAMERA_INDEX)
        except RuntimeError as e:
            print(f"[MainApp] Camera non disponible : {e}")
            self._camera = None

        # Fournir la même référence caméra aux trois écrans qui en ont besoin
        self._screen_capture.set_camera(self._camera)
        self._screen_calibration.set_camera(self._camera)
        self._screen_plateau.set_camera(self._camera)

        # Remplir les listes déroulantes de choix du matériel de l'écran 1. À faire APRÈS
        # set_machine() et set_camera() : les listes présélectionnent le port et la caméra
        # réellement en service, donc elles doivent les connaître.
        self._screen_capture.refresh_device_lists()

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
        self._screen_capture.calibration_requested.connect(self._go_to_calibration)
        self._screen_calibration.back_requested.connect(self._go_from_calibration_to_capture)
        self._screen_capture.plateau_requested.connect(self._go_to_plateau)
        self._screen_plateau.back_requested.connect(self._go_from_plateau_to_capture)
        self._screen_plateau.plateau_validated.connect(self._go_to_cordons)
        self._screen_cordons.back_requested.connect(self._go_from_cordons_to_plateau)

        # Changements de matériel demandés depuis l'écran 1 — appliqués ici, car MainApp
        # est propriétaire de la Camera et de la Machine partagées par tous les écrans
        self._screen_capture.camera_selected.connect(self._on_camera_selected)
        self._screen_capture.machine_port_selected.connect(self._on_machine_port_selected)

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

    def _go_to_calibration(self) -> None:
        """Basculer vers l'écran de calibration caméra ChArUco."""
        # Arrêter la caméra de capture avant d'ouvrir celle de calibration
        # (une seule caméra physique — ne peut pas être ouverte deux fois simultanément)
        self._screen_capture.stop_camera()
        self._screen_calibration.start_camera()
        self._stack.setCurrentIndex(4)

    def _go_from_calibration_to_capture(self) -> None:
        """Retourner vers l'écran de capture depuis la calibration."""
        # Arrêter la caméra de calibration avant de relancer celle de capture
        self._screen_calibration.stop_camera()
        self._go_to_capture()

    def _go_to_plateau(self) -> None:
        """Basculer vers l'écran de création de plateau (nouveau processus multi-zones).

        Le nom du produit est demandé AVANT d'afficher l'écran : si l'opérateur annule
        la saisie, on reste où on est plutôt que d'ouvrir un écran sans identité.
        """
        if not self._screen_plateau.ask_product_name(self):
            return

        # Une seule caméra physique : couper l'aperçu de l'écran courant avant d'en
        # démarrer un autre
        self._screen_capture.stop_camera()
        self._screen_plateau.start_camera()
        self._stack.setCurrentIndex(5)

    def _go_from_plateau_to_capture(self) -> None:
        """Retourner vers l'écran de capture depuis la création de plateau."""
        self._screen_plateau.stop_camera()
        self._go_to_capture()

    def _go_to_cordons(self, donnees: object) -> None:
        """Basculer vers le tracé des cordons, une fois le plateau validé."""
        # Le tracé travaille sur la photo figée : plus besoin de la caméra
        self._screen_plateau.stop_camera()
        self._screen_cordons.set_plateau(donnees)
        self._stack.setCurrentIndex(6)

    def _go_from_cordons_to_plateau(self) -> None:
        """Revenir à la création de plateau — typiquement pour reprendre une photo."""
        self._screen_plateau.start_camera()
        self._stack.setCurrentIndex(5)

    # ------------------------------------------------------------------ choix du matériel

    def _on_camera_selected(self, device_index: int) -> None:
        """Basculer sur une autre caméra, choisie dans la liste déroulante de l'écran 1.

        MainApp est le seul propriétaire de l'objet Camera (partagé avec l'écran de
        calibration) : c'est donc ici, et nulle part ailleurs, que l'ancienne est
        libérée et la nouvelle ouverte.
        """
        # Rien à faire si c'est déjà la caméra en service — éviter une fermeture puis
        # réouverture inutile, qui coûte 1 à 2 secondes
        if self._camera is not None and self._camera.index == device_index:
            return

        # Couper les deux aperçus AVANT de libérer : un timer qui lirait dans une caméra
        # déjà relâchée lèverait une RuntimeError en plein changement
        self._screen_capture.stop_camera()
        self._screen_calibration.stop_camera()

        if self._camera is not None:
            self._camera.release()
            self._camera = None

        try:
            self._camera = Camera(device_index)
            message = f"Camera {device_index} activee"
        except RuntimeError as e:
            # Caméra débranchée entre le scan et la sélection, ou occupée par un autre
            # logiciel : on reste sans caméra plutôt que de laisser un objet inutilisable
            self._camera = None
            message = f"Camera {device_index} indisponible : {e}"

        # Redistribuer la nouvelle référence (ou None) aux deux écrans concernés
        self._screen_capture.set_camera(self._camera)
        self._screen_calibration.set_camera(self._camera)

        # Relancer l'aperçu : on est forcément sur l'écran 1, seul écran à porter la liste
        self._screen_capture.start_camera()
        # Rafraîchir la liste pour remettre le suffixe "(en cours)" sur la bonne entrée
        self._screen_capture.refresh_device_lists()
        self._screen_capture.set_status(message)

    def _on_machine_port_selected(self, port: str) -> None:
        """Changer le port série de la machine, choisi dans la liste déroulante de l'écran 1.

        Aucune connexion n'est ouverte ici : la Machine ne se connecte qu'au moment du
        homing ou de la dépose, dans leur thread respectif. On ne fait donc que changer
        le port qui sera utilisé au prochain connect().
        """
        try:
            self._machine.set_port(port)
            self._screen_capture.set_status(f"Port machine : {port}")
        except RuntimeError as e:
            # set_port refuse pendant une connexion ouverte — le message vient de Machine
            self._screen_capture.set_status(str(e))
            # Remettre la liste sur le port réellement en service, pour ne pas laisser
            # croire que le changement a été pris en compte
            self._screen_capture.refresh_device_lists()

    # ------------------------------------------------------------------ cycle de vie

    def closeEvent(self, event) -> None:
        """Nettoyer les ressources avant de fermer la fenêtre."""
        # Arrêter les timers d'aperçu des trois écrans qui utilisent la caméra
        self._screen_capture.stop_camera()
        self._screen_calibration.stop_camera()
        self._screen_plateau.stop_camera()
        # Libérer la caméra partagée (une seule fois, pas dans les écrans)
        if self._camera is not None:
            self._camera.release()
            self._camera = None
        event.accept()
