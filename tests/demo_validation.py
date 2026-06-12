"""Démonstration Phase 2 Session 3 — Validation métrologique de pixel_to_mm().

Protocole de test :
  1. Poser une règle dans la zone de travail (entre les 4 marqueurs ArUco).
  2. Dès que les 4 marqueurs sont détectés, cliquer sur deux repères séparés
     d'une distance connue sur la règle (ex : 0 mm et 100 mm).
  3. Le script affiche la distance calculée en mm — comparer avec la valeur physique.
  4. Cliquer "Réinitialiser" pour effectuer une nouvelle mesure.

Critère de validation : écart ≤ 2 mm sur une distance de 100 mm.

Utilisation : python tests/demo_validation.py
Fermer la fenêtre pour quitter.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Supprimer le warning Qt "wrong permissions on runtime directory /run/user/1000"
# Qt réclame les droits 0700 sur ce dossier ; systemd le crée parfois en 0770.
# Cette variable désactive uniquement cette catégorie de log, sans effet sur le reste.
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.application=false")

import cv2
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QHBoxLayout, QVBoxLayout,
    QLabel, QStatusBar, QPushButton,
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QFont

from modules.camera import Camera
from modules.vision import VisionProcessor
from modules.calibration import load_calibration, undistort as undistort_image
from modules.config import (
    ARUCO_DICT_ID,
    ARUCO_MARKER_SIZE_MM,
    WORK_AREA_WIDTH_MM,
    WORK_AREA_HEIGHT_MM,
)

# Chemin vers les coefficients de calibration (générés par tests/demo_calibration.py)
CALIBRATION_PATH = os.path.join(
    os.path.dirname(__file__), "..", "assets", "camera_calibration.npz"
)

# Résolution d'affichage de la vue originale dans le QLabel
DISPLAY_WIDTH  = 640
DISPLAY_HEIGHT = 480

# Résolution de l'image redressée : 2 pixels par mm
WARP_SCALE  = 2
WARP_WIDTH  = int(WORK_AREA_WIDTH_MM  * WARP_SCALE)
WARP_HEIGHT = int(WORK_AREA_HEIGHT_MM * WARP_SCALE)


def _numpy_vers_pixmap(image_bgr: np.ndarray) -> QPixmap:
    """Convertit un tableau numpy BGR (OpenCV) en QPixmap (PyQt5)."""
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    h, w, c = image_rgb.shape
    qt_image = QImage(image_rgb.data, w, h, w * c, QImage.Format_RGB888)
    return QPixmap.fromImage(qt_image)


class LabelCliquable(QLabel):
    """QLabel qui transmet les clics gauche à un callback externe.

    Le callback reçoit (x, y) en pixels dans le repère du QLabel affiché.
    """

    def __init__(self, callback_clic, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._callback_clic = callback_clic

    def mousePressEvent(self, event) -> None:
        # N'envoyer que les clics gauche — ignorer le clic droit et le clic molette
        if event.button() == Qt.LeftButton:
            self._callback_clic(event.x(), event.y())


class FenetreValidation(QMainWindow):
    """Fenêtre de validation métrologique.

    Vue gauche (cliquable) : flux caméra original avec marqueurs annotés.
    Vue droite             : image redressée (vue du dessus).
    Zone basse             : résultat de la mesure + bouton reset.
    """

    def __init__(
        self,
        camera: Camera,
        vision: VisionProcessor,
        camera_matrix=None,
        dist_coeffs=None,
    ) -> None:
        super().__init__()
        self._camera        = camera
        self._vision        = vision
        self._camera_matrix = camera_matrix  # None si pas de calibration disponible
        self._dist_coeffs   = dist_coeffs
        self._homography    = None  # Disponible dès que les 4 marqueurs sont détectés
        self._points_px     = []   # Points cliqués en coordonnées du QLabel (640×480)
        self._points_mm     = []   # Mêmes points convertis en mm via pixel_to_mm()

        self.setWindowTitle("Validation métrologique — Phase 2 Session 3")

        # ── Layout principal (vertical) ──────────────────────────────────────
        conteneur = QWidget()
        layout_principal = QVBoxLayout(conteneur)

        # ── Ligne du haut : deux vues côte à côte ────────────────────────────
        layout_vues = QHBoxLayout()
        layout_principal.addLayout(layout_vues)

        # Vue gauche : image originale, cliquable
        self._label_original = LabelCliquable(
            self._sur_clic,
            "En attente de la caméra...",
        )
        self._label_original.setFixedSize(DISPLAY_WIDTH, DISPLAY_HEIGHT)
        self._label_original.setStyleSheet("background-color: #111; color: white;")
        layout_vues.addWidget(self._label_original)

        # Vue droite : image redressée (référence visuelle)
        self._label_warp = QLabel("En attente des 4 marqueurs...")
        self._label_warp.setFixedSize(WARP_WIDTH, WARP_HEIGHT)
        self._label_warp.setStyleSheet("background-color: #222; color: white;")
        layout_vues.addWidget(self._label_warp)

        # ── Ligne du bas : résultat + bouton reset ───────────────────────────
        layout_bas = QHBoxLayout()
        layout_principal.addLayout(layout_bas)

        self._label_resultat = QLabel(
            "Attendre les 4 marqueurs, puis cliquer 2 points dans la vue gauche"
        )
        font = QFont("Monospace", 11)
        self._label_resultat.setFont(font)
        self._label_resultat.setAlignment(Qt.AlignCenter)
        layout_bas.addWidget(self._label_resultat)

        bouton_reset = QPushButton("Réinitialiser les points")
        bouton_reset.clicked.connect(self._reset_points)
        bouton_reset.setFixedWidth(220)
        layout_bas.addWidget(bouton_reset)

        self.setCentralWidget(conteneur)

        # Barre de statut (bas de fenêtre) : infos de détection en temps réel
        self._status = QStatusBar()
        self.setStatusBar(self._status)

        # QTimer : déclenche _actualiser() toutes les 33 ms ≈ 30 fps
        self._timer = QTimer()
        self._timer.timeout.connect(self._actualiser)
        self._timer.start(33)

    # ── Gestion des clics ────────────────────────────────────────────────────

    def _sur_clic(self, x_label: int, y_label: int) -> None:
        """Traite un clic gauche sur la vue originale.

        x_label, y_label : coordonnées dans le QLabel affiché (640×480).
        On les remet à l'échelle de la résolution capteur (1280×960)
        avant d'appeler pixel_to_mm(), qui travaille sur l'image originale.
        """
        if self._homography is None:
            self._label_resultat.setText(
                "Attendre que les 4 marqueurs soient visibles avant de cliquer"
            )
            return

        # On n'accepte que 2 points — ignorer les clics supplémentaires
        if len(self._points_px) >= 2:
            return

        # Remettre à l'échelle : DISPLAY_WIDTH×HEIGHT → résolution capteur réelle
        scale_x = self._camera.width  / DISPLAY_WIDTH
        scale_y = self._camera.height / DISPLAY_HEIGHT
        x_orig = x_label * scale_x
        y_orig = y_label * scale_y

        # Convertir en mm dans le repère de la zone de travail
        x_mm, y_mm = self._vision.pixel_to_mm(x_orig, y_orig, self._homography)

        self._points_px.append((x_label, y_label))
        self._points_mm.append((x_mm, y_mm))

        if len(self._points_mm) == 1:
            self._label_resultat.setText(
                f"P1 : ({x_mm:.1f}, {y_mm:.1f}) mm  —  cliquer le point 2"
            )

        elif len(self._points_mm) == 2:
            # Distance euclidienne entre les deux points dans l'espace mm
            dx = self._points_mm[1][0] - self._points_mm[0][0]
            dy = self._points_mm[1][1] - self._points_mm[0][1]
            distance_mm = np.sqrt(dx ** 2 + dy ** 2)

            self._label_resultat.setText(
                f"Distance : {distance_mm:.1f} mm   "
                f"(Δx = {dx:.1f} mm,  Δy = {dy:.1f} mm)   "
                f"— tolérance attendue : ± 2 mm"
            )

    def _reset_points(self) -> None:
        """Efface les points cliqués pour commencer une nouvelle mesure."""
        self._points_px.clear()
        self._points_mm.clear()
        self._label_resultat.setText(
            "Points réinitialisés — cliquer 2 points dans la vue gauche"
        )

    # ── Boucle d'affichage ───────────────────────────────────────────────────

    def _actualiser(self) -> None:
        """Capture une image, détecte les marqueurs, met à jour les deux vues."""
        frame = self._camera.capture()

        # Corriger la distorsion de l'objectif si la calibration est disponible
        # Cette étape améliore la précision des mesures de ~10 % à ~1-2 %
        if self._camera_matrix is not None:
            frame = undistort_image(frame, self._camera_matrix, self._dist_coeffs)

        # Réduire pour l'affichage gauche (la caméra capture en haute résolution)
        frame_affichage = cv2.resize(frame, (DISPLAY_WIDTH, DISPLAY_HEIGHT))

        # Détecter les marqueurs sur l'image pleine résolution (meilleure précision)
        detected = self._vision.detect_markers(frame)

        if detected:
            # Annoter la vue réduite (redétection pour que les coordonnées correspondent)
            detected_affichage = self._vision.detect_markers(frame_affichage)
            if detected_affichage:
                coins_draw = [
                    c.reshape(1, 4, 2).astype(np.float32)
                    for c in detected_affichage.values()
                ]
                ids_draw = np.array([[mid] for mid in detected_affichage.keys()])
                cv2.aruco.drawDetectedMarkers(frame_affichage, coins_draw, ids_draw)

            # Recalculer l'homographie à chaque frame (la caméra peut légèrement bouger)
            if set(detected.keys()) == {0, 1, 2, 3}:
                try:
                    self._homography = self._vision.compute_homography(detected)
                except ValueError:
                    pass

            self._status.showMessage(
                f"Marqueurs détectés : {sorted(detected.keys())}  —  cliquer dans la vue gauche"
            )
        else:
            # Si les marqueurs disparaissent, on invalide l'homographie
            self._homography = None
            self._status.showMessage("Aucun marqueur détecté — repositionner la caméra")

        # Dessiner les points cliqués par l'utilisateur sur la vue gauche
        pixmap = _numpy_vers_pixmap(frame_affichage)
        if self._points_px:
            painter = QPainter(pixmap)

            for i, (px, py) in enumerate(self._points_px):
                # Point 1 en rouge, point 2 en vert
                couleur = QColor(255, 80, 80) if i == 0 else QColor(80, 220, 80)
                painter.setPen(QPen(couleur, 2))
                # Croix centrée sur le point cliqué
                painter.drawLine(px - 12, py, px + 12, py)
                painter.drawLine(px, py - 12, px, py + 12)
                # Étiquette à droite de la croix
                painter.setFont(QFont("Monospace", 9))
                if i < len(self._points_mm):
                    x_mm, y_mm = self._points_mm[i]
                    painter.drawText(px + 14, py + 4, f"P{i+1} ({x_mm:.0f},{y_mm:.0f})mm")
                else:
                    painter.drawText(px + 14, py + 4, f"P{i+1}")

            # Ligne jaune reliant les deux points si les deux sont posés
            if len(self._points_px) == 2:
                painter.setPen(QPen(QColor(255, 220, 0), 1, Qt.DashLine))
                p1, p2 = self._points_px
                painter.drawLine(p1[0], p1[1], p2[0], p2[1])

            painter.end()

        self._label_original.setPixmap(pixmap)

        # Vue droite : image redressée (uniquement si l'homographie est disponible)
        if self._homography is not None:
            image_warpee = self._vision.warp_image(
                frame, self._homography, (WARP_WIDTH, WARP_HEIGHT)
            )
            self._label_warp.setPixmap(_numpy_vers_pixmap(image_warpee))

    def closeEvent(self, event) -> None:
        """Arrêter le timer et libérer la caméra à la fermeture de la fenêtre."""
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

    vision = VisionProcessor(
        aruco_dict_id=ARUCO_DICT_ID,
        marker_real_size_mm=ARUCO_MARKER_SIZE_MM,
    )

    # Charger la calibration si elle a déjà été faite (assets/camera_calibration.npz)
    camera_matrix, dist_coeffs = load_calibration(CALIBRATION_PATH)
    if camera_matrix is not None:
        print("Calibration objectif chargée ✓ — undistortion activée")
    else:
        print("Calibration objectif non trouvée — lancer tests/demo_calibration.py")
        print("  → précision réduite (~10 % d'erreur sur les mesures intérieures)")

    print(f"Zone de travail : {WORK_AREA_WIDTH_MM} × {WORK_AREA_HEIGHT_MM} mm")
    print(f"Image redressée : {WARP_WIDTH} × {WARP_HEIGHT} px  ({WARP_SCALE} px/mm)")
    print("Protocole : poser une règle dans la zone, cliquer 2 repères, lire la distance.")
    print("Fermer la fenêtre pour quitter.")

    fenetre = FenetreValidation(cam, vision, camera_matrix, dist_coeffs)
    fenetre.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
