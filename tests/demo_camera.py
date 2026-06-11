"""Démonstration Phase 1 — affiche le flux caméra en temps réel via PyQt5.

Utilisation : python tests/demo_camera.py
Fermer la fenêtre pour quitter.
"""
import sys
import os

# Ajouter le répertoire racine au chemin Python pour pouvoir importer 'modules'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cv2
from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QImage, QPixmap

from modules.camera import Camera


class FenetreDemoCamera(QMainWindow):
    """Fenêtre de démonstration : affiche le flux caméra en continu."""

    def __init__(self, camera: Camera) -> None:
        super().__init__()
        self._camera = camera

        self.setWindowTitle(f"Demo Camera — Phase 1  ({camera.width}×{camera.height})")

        # QLabel : widget PyQt5 capable d'afficher une image (QPixmap)
        self._label = QLabel(self)
        self._label.setFixedSize(camera.width, camera.height)
        self.setCentralWidget(self._label)
        self.adjustSize()

        # QTimer : appelle _actualiser() toutes les 33 ms → environ 30 images par seconde
        # C'est l'équivalent PyQt5 du "while True" + waitKey(33) d'OpenCV
        self._timer = QTimer()
        self._timer.timeout.connect(self._actualiser)
        self._timer.start(33)

    def _actualiser(self) -> None:
        """Capture une image et l'affiche dans le QLabel."""
        frame = self._camera.capture()

        # Convertir BGR (ordre OpenCV) → RGB (ordre attendu par Qt)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        hauteur, largeur, canaux = frame_rgb.shape

        # Construire un QImage depuis le tableau numpy
        # stride = nombre d'octets par ligne = largeur × nombre de canaux
        stride = largeur * canaux
        qt_image = QImage(frame_rgb.data, largeur, hauteur, stride, QImage.Format_RGB888)

        # Convertir QImage → QPixmap et l'afficher dans le QLabel
        self._label.setPixmap(QPixmap.fromImage(qt_image))

    def closeEvent(self, event) -> None:
        """Arrête le timer et libère la caméra à la fermeture de la fenêtre."""
        self._timer.stop()
        self._camera.release()
        event.accept()


def main() -> None:
    # QApplication : point d'entrée obligatoire pour toute application PyQt5
    # sys.argv transmet les arguments de ligne de commande à Qt (utile pour --style, etc.)
    app = QApplication(sys.argv)

    try:
        cam = Camera(device_index=0)
    except RuntimeError as e:
        print(f"Erreur : {e}")
        sys.exit(1)

    print(f"Caméra ouverte — résolution : {cam.width}×{cam.height}")
    print("Fermer la fenêtre pour quitter.")

    fenetre = FenetreDemoCamera(cam)
    fenetre.show()

    # app.exec_() démarre la boucle d'événements Qt — bloque jusqu'à la fermeture de la fenêtre
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
