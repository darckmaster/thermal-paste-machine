"""Démonstration Phase 2 Sessions 1 & 2 — détection ArUco + redressement homographique.

Vue gauche  : flux caméra original avec contours ArUco dessinés.
Vue droite  : image redressée (vue du dessus à l'échelle) dès que les 4 marqueurs sont visibles.

Utilisation : python tests/demo_vision.py
Fermer la fenêtre pour quitter.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cv2
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QLabel, QStatusBar,
)
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QImage, QPixmap

from modules.camera import Camera
from modules.vision import VisionProcessor
from modules.config import (
    ARUCO_DICT_ID,
    ARUCO_MARKER_SIZE_MM,
    WORK_AREA_WIDTH_MM,
    WORK_AREA_HEIGHT_MM,
)

# Résolution de l'image redressée : 2 pixels par mm
WARP_SCALE = 2
WARP_WIDTH  = int(WORK_AREA_WIDTH_MM  * WARP_SCALE)
WARP_HEIGHT = int(WORK_AREA_HEIGHT_MM * WARP_SCALE)


def _numpy_vers_pixmap(image_bgr: np.ndarray) -> QPixmap:
    """Convertit un tableau numpy BGR (OpenCV) en QPixmap (PyQt5)."""
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    h, w, c = image_rgb.shape
    qt_image = QImage(image_rgb.data, w, h, w * c, QImage.Format_RGB888)
    return QPixmap.fromImage(qt_image)


class FenetreDemoVision(QMainWindow):
    """Fenêtre principale : vue originale (gauche) + vue redressée (droite)."""

    def __init__(self, camera: Camera, vision: VisionProcessor) -> None:
        super().__init__()
        self._camera = camera
        self._vision = vision
        self._homography = None  # Calculée dès que les 4 marqueurs sont visibles

        self.setWindowTitle("Demo Vision — Phase 2")

        # Disposition horizontale : deux QLabel côte à côte
        conteneur = QWidget()
        layout = QHBoxLayout(conteneur)
        layout.setSpacing(4)

        # Vue gauche : image originale annotée
        self._label_original = QLabel("Vue originale")
        self._label_original.setFixedSize(640, 480)
        layout.addWidget(self._label_original)

        # Vue droite : image redressée (300×200 px = 150×100 mm à 2 px/mm)
        self._label_warp = QLabel("En attente des 4 marqueurs...")
        self._label_warp.setFixedSize(WARP_WIDTH, WARP_HEIGHT)
        self._label_warp.setStyleSheet("background-color: #222; color: white;")
        layout.addWidget(self._label_warp)

        self.setCentralWidget(conteneur)

        # Barre de statut
        self._status = QStatusBar()
        self.setStatusBar(self._status)

        # QTimer : mise à jour toutes les 33 ms (~30 fps)
        self._timer = QTimer()
        self._timer.timeout.connect(self._actualiser)
        self._timer.start(33)

    def _actualiser(self) -> None:
        """Capture, détecte, annote et affiche les deux vues."""
        frame = self._camera.capture()

        # Redimensionner pour l'affichage gauche (la caméra capture en 1280×960)
        frame_affichage = cv2.resize(frame, (640, 480))

        detected = self._vision.detect_markers(frame)

        if detected:
            # Dessiner les marqueurs détectés sur la vue originale redimensionnée
            # (on redétecte sur le frame réduit pour que les coordonnées correspondent)
            detected_affichage = self._vision.detect_markers(frame_affichage)
            if detected_affichage:
                coins_draw = [c.reshape(1, 4, 2).astype(np.float32) for c in detected_affichage.values()]
                ids_draw = np.array([[mid] for mid in detected_affichage.keys()])
                cv2.aruco.drawDetectedMarkers(frame_affichage, coins_draw, ids_draw)

            # Calculer ou mettre à jour l'homographie dès que les 4 marqueurs sont là
            if set(detected.keys()) == {0, 1, 2, 3}:
                try:
                    self._homography = self._vision.compute_homography(detected)
                except ValueError:
                    pass

            self._status.showMessage(f"Marqueurs détectés : {sorted(detected.keys())}")
        else:
            self._status.showMessage("Aucun marqueur détecté")

        # Vue gauche : original annoté
        self._label_original.setPixmap(_numpy_vers_pixmap(frame_affichage))

        # Vue droite : image redressée (uniquement si l'homographie est disponible)
        if self._homography is not None:
            image_warpee = self._vision.warp_image(frame, self._homography, (WARP_WIDTH, WARP_HEIGHT))
            self._label_warp.setPixmap(_numpy_vers_pixmap(image_warpee))

    def closeEvent(self, event) -> None:
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

    print(f"Zone de travail : {WORK_AREA_WIDTH_MM}×{WORK_AREA_HEIGHT_MM} mm")
    print(f"Image redressée : {WARP_WIDTH}×{WARP_HEIGHT} px ({WARP_SCALE} px/mm)")
    print("Fermer la fenêtre pour quitter.")

    fenetre = FenetreDemoVision(cam, vision)
    fenetre.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
