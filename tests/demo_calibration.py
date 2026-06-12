"""Outil de calibration de l'objectif — Phase 2 Session 3.

Objectif : calculer et sauvegarder les coefficients de distorsion de la webcam.
Ces coefficients seront ensuite appliqués à chaque image avant le traitement ArUco.

Matériel nécessaire :
  - Échiquier imprimé depuis assets/chessboard_calibration.png (A4 paysage)
  - Caméra branchée en USB

Procédure :
  1. Lancer ce script : python tests/demo_calibration.py
  2. Présenter l'échiquier dans le champ de la caméra
  3. Quand les coins verts apparaissent sur l'échiquier → appuyer ESPACE pour capturer
  4. Répéter en changeant l'angle et la position (15 captures minimum)
  5. Quand le compteur atteint 15, la calibration est calculée automatiquement
  6. Le résultat est sauvegardé dans assets/camera_calibration.npz

Conseil : varier les angles (inclinaison gauche/droite/haut/bas), les distances
et les positions dans l'image pour une meilleure calibration.

Utilisation : python tests/demo_calibration.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Supprimer le warning Qt "wrong permissions on runtime directory /run/user/1000"
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.application=false")

import cv2
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QLabel, QStatusBar,
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap, QFont, QColor

from modules.camera import Camera
from modules.calibration import (
    CHESSBOARD_SIZE,
    SQUARE_SIZE_MM,
    generate_chessboard_image,
    calibrate,
    save_calibration,
)

# Chemins des fichiers
CHESSBOARD_PNG_PATH  = os.path.join(
    os.path.dirname(__file__), "..", "assets", "chessboard_calibration.png"
)
CALIBRATION_NPZ_PATH = os.path.join(
    os.path.dirname(__file__), "..", "assets", "camera_calibration.npz"
)

# Nombre de captures nécessaires avant de déclencher la calibration
MIN_CAPTURES = 15

# Résolution d'affichage
DISPLAY_WIDTH  = 800
DISPLAY_HEIGHT = 600


def _numpy_vers_pixmap(image_bgr: np.ndarray) -> QPixmap:
    """Convertit un tableau numpy BGR (OpenCV) en QPixmap (PyQt5)."""
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    h, w, c = image_rgb.shape
    qt_image = QImage(image_rgb.data, w, h, w * c, QImage.Format_RGB888)
    return QPixmap.fromImage(qt_image)


class FenetreCalibration(QMainWindow):
    """Fenêtre d'acquisition pour la calibration de l'objectif.

    Affiche le flux caméra avec les coins de l'échiquier détectés.
    ESPACE pour capturer un frame, calibration automatique à MIN_CAPTURES frames.
    """

    def __init__(self, camera: Camera) -> None:
        super().__init__()
        self._camera   = camera
        self._captures = []       # Images capturées avec échiquier détecté
        self._last_corners = None # Coins détectés dans le dernier frame
        self._done = False        # True après calibration réussie

        self.setWindowTitle("Calibration objectif — Phase 2 Session 3")

        # ── Layout ──────────────────────────────────────────────────────────
        conteneur = QWidget()
        layout = QVBoxLayout(conteneur)

        # Étiquette principale : flux caméra
        self._label_image = QLabel("En attente de la caméra...")
        self._label_image.setFixedSize(DISPLAY_WIDTH, DISPLAY_HEIGHT)
        self._label_image.setAlignment(Qt.AlignCenter)
        self._label_image.setStyleSheet("background-color: #111; color: white;")
        layout.addWidget(self._label_image)

        # Étiquette d'instruction / résultat
        self._label_info = QLabel(
            f"Présenter l'échiquier → coins verts → ESPACE pour capturer  "
            f"(0 / {MIN_CAPTURES})"
        )
        self._label_info.setFont(QFont("Monospace", 10))
        self._label_info.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._label_info)

        self.setCentralWidget(conteneur)

        self._status = QStatusBar()
        self.setStatusBar(self._status)

        # QTimer : mise à jour toutes les 33 ms ≈ 30 fps
        self._timer = QTimer()
        self._timer.timeout.connect(self._actualiser)
        self._timer.start(33)

    def keyPressEvent(self, event) -> None:
        """ESPACE : capturer le frame courant si l'échiquier est détecté."""
        if event.key() == Qt.Key_Space and not self._done:
            self._capturer()

    def _capturer(self) -> None:
        """Capture le frame courant si l'échiquier y est bien détecté."""
        if self._last_frame is None or self._last_corners is None:
            self._status.showMessage("Échiquier non détecté — repositionner")
            return

        self._captures.append(self._last_frame.copy())
        n = len(self._captures)
        self._label_info.setText(
            f"Capture {n} / {MIN_CAPTURES} enregistrée ✓   "
            f"{'→ calcul en cours...' if n >= MIN_CAPTURES else 'Changer l\'angle et recapturer'}"
        )
        self._status.showMessage(f"{n} capture(s) enregistrée(s)")

        # Déclencher la calibration automatiquement dès que le minimum est atteint
        if n >= MIN_CAPTURES:
            self._calculer_calibration()

    def _calculer_calibration(self) -> None:
        """Calcule la calibration à partir des frames capturés et sauvegarde."""
        self._timer.stop()
        self._label_info.setText("Calcul de la calibration en cours...")
        QApplication.processEvents()  # Forcer le rafraîchissement de l'affichage

        try:
            camera_matrix, dist_coeffs, reprojection_error = calibrate(
                self._captures,
                chessboard_size=CHESSBOARD_SIZE,
                square_size_mm=SQUARE_SIZE_MM,
            )
            save_calibration(CALIBRATION_NPZ_PATH, camera_matrix, dist_coeffs)
            self._done = True

            # Afficher le résultat — erreur de reprojection < 1.0 = acceptable, < 0.5 = excellent
            qualite = "excellent" if reprojection_error < 0.5 else (
                "acceptable" if reprojection_error < 1.0 else "insuffisant (refaire)"
            )
            self._label_info.setText(
                f"Calibration sauvegardée ✓   "
                f"Erreur de reprojection : {reprojection_error:.3f} px ({qualite})"
            )
            self._status.showMessage(
                f"Fichier sauvegardé : {os.path.abspath(CALIBRATION_NPZ_PATH)}"
            )
            print(f"\nCalibration réussie !")
            print(f"  Erreur de reprojection : {reprojection_error:.3f} px ({qualite})")
            print(f"  Fichier : {os.path.abspath(CALIBRATION_NPZ_PATH)}")
            print("  Vous pouvez fermer la fenêtre.")

        except ValueError as e:
            self._label_info.setText(f"Erreur : {e}")
            self._timer.start(33)  # Reprendre le flux pour continuer les captures

    def _actualiser(self) -> None:
        """Capture un frame, détecte l'échiquier et l'affiche avec les coins annotés."""
        frame = self._camera.capture()
        self._last_frame = frame.copy()
        self._last_corners = None

        # Redimensionner pour l'affichage
        frame_affichage = cv2.resize(frame, (DISPLAY_WIDTH, DISPLAY_HEIGHT))
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Chercher les coins de l'échiquier dans l'image pleine résolution
        found, corners = cv2.findChessboardCorners(gray, CHESSBOARD_SIZE, None)

        if found:
            self._last_corners = corners

            # Calculer le facteur d'échelle pour afficher les coins sur le frame réduit
            scale_x = DISPLAY_WIDTH  / frame.shape[1]
            scale_y = DISPLAY_HEIGHT / frame.shape[0]
            corners_display = corners.copy()
            corners_display[:, :, 0] *= scale_x
            corners_display[:, :, 1] *= scale_y

            # Dessiner les coins en vert sur la vue d'affichage
            cv2.drawChessboardCorners(frame_affichage, CHESSBOARD_SIZE, corners_display, found)
            self._status.showMessage(
                f"Échiquier détecté ({CHESSBOARD_SIZE[0]}×{CHESSBOARD_SIZE[1]} coins) "
                f"— ESPACE pour capturer"
            )
        else:
            self._status.showMessage(
                "Échiquier non détecté — ajuster l'angle, la distance ou l'éclairage"
            )

        self._label_image.setPixmap(_numpy_vers_pixmap(frame_affichage))

    def closeEvent(self, event) -> None:
        """Arrêter le timer et libérer la caméra à la fermeture."""
        self._timer.stop()
        self._camera.release()
        event.accept()


def main() -> None:
    # Générer l'échiquier à imprimer s'il n'existe pas encore
    chessboard_path = os.path.abspath(CHESSBOARD_PNG_PATH)
    if not os.path.exists(chessboard_path):
        generate_chessboard_image(chessboard_path)
        print(f"Échiquier généré : {chessboard_path}")
        print(f"→ Imprimer ce fichier sur A4 PAYSAGE en taille réelle (25 mm / carré)")
    else:
        print(f"Échiquier existant : {chessboard_path}")

    print(f"\nProcédure :")
    print(f"  1. Présenter l'échiquier imprimé devant la caméra")
    print(f"  2. Quand les coins verts apparaissent → appuyer ESPACE")
    print(f"  3. Répéter {MIN_CAPTURES}+ fois en changeant l'angle et la position")
    print(f"  4. La calibration se calcule automatiquement à {MIN_CAPTURES} captures")

    app = QApplication(sys.argv)

    try:
        cam = Camera(device_index=0)
    except RuntimeError as e:
        print(f"Erreur caméra : {e}")
        sys.exit(1)

    fenetre = FenetreCalibration(cam)
    fenetre.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
