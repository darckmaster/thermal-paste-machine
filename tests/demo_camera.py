"""Démonstration Phase 1 — affiche le flux caméra en temps réel via PyQt5.

Utilisation : python tests/demo_camera.py
Fermer la fenêtre pour quitter.

Mode réglage de la mise au point (caméras avec autofocus, ex. FIT0729 DFRobot) :
    python tests/demo_camera.py --focus
Désactive l'autofocus et affiche la valeur courante dans le titre de la fenêtre.
Flèches Haut/Bas (ou +/-) pour l'ajuster, à la distance de capture réelle de la machine —
il n'y a pas de formule, seule l'observation à l'écran dit quand c'est net. Noter la valeur
retenue dans local_config.json : {"camera_autofocus_off": true, "camera_focus_value": <valeur>}.
"""
import sys
import os

# Ajouter le répertoire racine au chemin Python pour pouvoir importer 'modules'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cv2
from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap

from modules.camera import Camera

# Pas d'incrément par pression de flèche en mode --focus. L'échelle du pilote est inconnue
# à l'avance (parfois 0-255, parfois 0-1023) : un pas de 5 permet d'affiner sans que
# chaque pression ne saute une plage utile de valeurs sur un petit intervalle.
_PAS_FOCUS = 5


class FenetreDemoCamera(QMainWindow):
    """Fenêtre de démonstration : affiche le flux caméra en continu.

    En mode réglage (`mode_focus=True`), les flèches Haut/Bas pilotent en direct la mise
    au point manuelle de la caméra — la valeur courante s'affiche dans le titre pour ne
    pas empiéter sur l'image, déjà à sa taille réelle en 1280×960.
    """

    def __init__(self, camera: Camera, mode_focus: bool = False) -> None:
        super().__init__()
        self._camera = camera
        self._mode_focus = mode_focus
        self._valeur_focus = 0

        if self._mode_focus:
            # Couper l'autofocus pour que les réglages manuels ci-dessous prennent effet —
            # sans ça, le pilote reprend la main entre deux pressions de flèche.
            self._camera.set_autofocus(False)
            self._camera.set_focus(self._valeur_focus)

        self._mettre_a_jour_titre()

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

    def _mettre_a_jour_titre(self) -> None:
        base = f"Demo Camera — Phase 1  ({self._camera.width}×{self._camera.height})"
        if self._mode_focus:
            base += f"  —  FOCUS = {self._valeur_focus}  (Haut/Bas pour ajuster)"
        self.setWindowTitle(base)

    def keyPressEvent(self, event) -> None:
        """Flèches Haut/Bas : ajuste la mise au point manuelle en mode --focus."""
        if not self._mode_focus:
            return

        if event.key() == Qt.Key_Up:
            self._valeur_focus += _PAS_FOCUS
        elif event.key() == Qt.Key_Down:
            self._valeur_focus = max(0, self._valeur_focus - _PAS_FOCUS)
        else:
            return

        self._camera.set_focus(self._valeur_focus)
        self._mettre_a_jour_titre()

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
    mode_focus = "--focus" in sys.argv[1:]

    # QApplication : point d'entrée obligatoire pour toute application PyQt5
    # sys.argv transmet les arguments de ligne de commande à Qt (utile pour --style, etc.)
    app = QApplication(sys.argv)

    try:
        cam = Camera(device_index=0)
    except RuntimeError as e:
        print(f"Erreur : {e}")
        sys.exit(1)

    print(f"Caméra ouverte — résolution : {cam.width}×{cam.height}")
    if mode_focus:
        print("Mode réglage focus : flèches Haut/Bas pour ajuster, à la distance de "
              "capture réelle. Noter la valeur retenue dans local_config.json.")
    print("Fermer la fenêtre pour quitter.")

    fenetre = FenetreDemoCamera(cam, mode_focus=mode_focus)
    fenetre.show()

    # app.exec_() démarre la boucle d'événements Qt — bloque jusqu'à la fermeture de la fenêtre
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
