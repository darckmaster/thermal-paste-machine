"""Démonstration Phase 2 Session 1 — détection ArUco en temps réel via PyQt5.

Placer les marqueurs DICT_4X4_50 (IDs 0, 1, 2, 3) devant la caméra.
Les marqueurs détectés sont encadrés en vert avec leur ID affiché.

Utilisation : python tests/demo_vision.py
Fermer la fenêtre pour quitter.
"""
import sys
import os

# Ajouter le répertoire racine au chemin Python pour pouvoir importer 'modules'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cv2
import numpy as np
from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow, QStatusBar
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QImage, QPixmap

from modules.camera import Camera
from modules.vision import VisionProcessor
from modules.config import ARUCO_DICT_ID, ARUCO_MARKER_SIZE_MM


class FenetreDemoVision(QMainWindow):
    """Fenêtre de démonstration : flux caméra avec détection ArUco en temps réel."""

    def __init__(self, camera: Camera, vision: VisionProcessor) -> None:
        super().__init__()
        self._camera = camera
        self._vision = vision

        self.setWindowTitle("Demo Vision — Phase 2 Session 1")

        # QLabel pour afficher le flux vidéo annoté
        self._label = QLabel(self)
        self._label.setFixedSize(camera.width, camera.height)
        self.setCentralWidget(self._label)

        # Barre de statut en bas de la fenêtre — affiche les IDs détectés
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("En attente de marqueurs...")

        self.adjustSize()

        # QTimer : mise à jour toutes les 33 ms (~30 fps)
        self._timer = QTimer()
        self._timer.timeout.connect(self._actualiser)
        self._timer.start(33)

    def _actualiser(self) -> None:
        """Capture une image, détecte les marqueurs, annote et affiche."""
        frame = self._camera.capture()

        # Détecter les marqueurs ArUco dans l'image courante
        detected = self._vision.detect_markers(frame)

        if detected:
            # Reformater pour cv2.aruco.drawDetectedMarkers :
            #   - liste de tableaux (1, 4, 2) pour les coins
            #   - tableau (N, 1) pour les IDs
            corners_draw = [c.reshape(1, 4, 2).astype(np.float32) for c in detected.values()]
            ids_draw = np.array([[mid] for mid in detected.keys()])

            # Dessiner les contours verts et les IDs sur l'image (modifie frame en place)
            cv2.aruco.drawDetectedMarkers(frame, corners_draw, ids_draw)

            self._status.showMessage(f"Marqueurs détectés : {sorted(detected.keys())}")
        else:
            self._status.showMessage("Aucun marqueur détecté")

        # Convertir BGR (OpenCV) → RGB (Qt), puis afficher dans le QLabel
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        hauteur, largeur, canaux = frame_rgb.shape
        stride = largeur * canaux
        qt_image = QImage(frame_rgb.data, largeur, hauteur, stride, QImage.Format_RGB888)
        self._label.setPixmap(QPixmap.fromImage(qt_image))

    def closeEvent(self, event) -> None:
        """Arrête le timer et libère la caméra à la fermeture de la fenêtre."""
        self._timer.stop()
        self._camera.release()
        event.accept()


def main() -> None:
    app = QApplication(sys.argv)

    try:
        cam = Camera(device_index=0)
    except RuntimeError as e:
        print(f"Erreur caméra : {e}")
        sys.exit(1)

    vision = VisionProcessor(aruco_dict_id=ARUCO_DICT_ID, marker_real_size_mm=ARUCO_MARKER_SIZE_MM)

    print(f"Prêt — dictionnaire {ARUCO_DICT_ID}, taille marqueur {ARUCO_MARKER_SIZE_MM} mm")
    print("Fermer la fenêtre pour quitter.")

    fenetre = FenetreDemoVision(cam, vision)
    fenetre.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
