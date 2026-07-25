# Écran de calibration caméra — mire ChArUco
# Procédure guidée : capturer MIN_IMAGES positions → calibrer → sauvegarder

import os
import cv2
import numpy as np
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, QThread, QObject, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QImage, QPixmap

from modules.camera import Camera
from modules.config import CAMERA_INDEX, CALIBRATION_MIN_IMAGES
from modules.calibration import (
    create_charuco_board,
    detect_charuco,
    calibrate_charuco,
    save_calibration,
    generate_charuco_image,
)

CALIBRATION_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "assets", "camera_calibration.npz")
)
CHARUCO_IMAGE_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "assets", "charuco_calibration.png")
)


# ================================================================ thread détection

class DetectionThread(QThread):
    """Thread dédié à la détection ChArUco.

    Pourquoi un QThread subclass plutôt que worker+moveToThread ?
    - Plus simple : pas de setup de boucle d'événements Qt dans le thread
    - Isolation : le CharucoDetector est créé et utilisé uniquement dans ce thread
      (cv2.aruco.CharucoDetector n'est pas thread-safe si partagé entre threads)

    Fonctionnement :
      - Le thread principal dépose un frame via submit()
      - La boucle run() le récupère, fait la détection, émet result_ready
      - Si un nouveau frame arrive avant que le précédent soit traité, il est remplacé
        (on préfère la fraîcheur à l'exhaustivité pour un aperçu temps-réel)
    """

    result_ready = pyqtSignal(object, object, object)  # corners, ids, preview

    def __init__(self, board) -> None:
        super().__init__()
        # Le board est passé en paramètre mais le détecteur est créé dans run()
        # pour être certain qu'il vit entièrement dans ce thread
        self._board = board
        self._pending_frame: np.ndarray | None = None
        self._active: bool = True

    def submit(self, frame: np.ndarray) -> None:
        """Déposer un frame à analyser — remplace le précédent s'il n'a pas encore été traité."""
        self._pending_frame = frame

    def stop(self) -> None:
        """Signaler à la boucle de s'arrêter au prochain tour."""
        self._active = False

    def run(self) -> None:
        """Boucle principale — s'exécute dans le thread séparé."""
        # Créer le détecteur ICI, dans le contexte de ce thread
        # → jamais partagé avec le thread principal, pas de problème de thread-safety
        detector = cv2.aruco.CharucoDetector(self._board)

        while self._active:
            frame = self._pending_frame
            if frame is not None:
                self._pending_frame = None
                try:
                    corners, ids, preview = detect_charuco(frame, self._board, detector)
                    self.result_ready.emit(corners, ids, preview)
                except Exception:
                    # Ne jamais laisser une exception OpenCV tuer le thread silencieusement
                    pass
            # Attendre 20 ms avant de vérifier à nouveau — ~50 checks/s max, CPU limité
            self.msleep(20)


# ================================================================ worker calibration

class CalibrationWorker(QObject):
    """Exécute le calcul de calibration dans un thread séparé (peut prendre plusieurs secondes)."""

    finished = pyqtSignal(object, object, float)
    error_occurred = pyqtSignal(str)

    def __init__(self, all_corners: list, all_ids: list, board, image_size: tuple) -> None:
        super().__init__()
        self._all_corners = all_corners
        self._all_ids = all_ids
        self._board = board
        self._image_size = image_size

    @pyqtSlot()
    def run(self) -> None:
        try:
            camera_matrix, dist_coeffs, error = calibrate_charuco(
                self._all_corners, self._all_ids, self._board, self._image_size
            )
            self.finished.emit(camera_matrix, dist_coeffs, float(error))
        except Exception as e:
            self.error_occurred.emit(str(e))


# ================================================================ écran calibration

class ScreenCalibration(QWidget):
    """Écran de calibration caméra guidée avec mire ChArUco."""

    back_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()

        self._camera: Camera | None = None
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_frame)

        # Créer uniquement le board ici — le détecteur sera créé dans DetectionThread.run()
        self._board, _ = create_charuco_board()

        self._all_corners: list = []
        self._all_ids: list = []
        self._image_size: tuple = (0, 0)

        self._camera_matrix = None
        self._dist_coeffs = None

        # Thread de détection — créé dans start_camera(), arrêté dans stop_camera()
        self._detection_thread: DetectionThread | None = None
        # Flag pour ne pas soumettre un frame si le précédent est encore en traitement
        self._detection_busy: bool = False
        self._charuco_detected: bool = False

        # Thread de calibration (calcul final)
        self._calib_thread: QThread | None = None
        self._calib_worker: CalibrationWorker | None = None

        self._setup_ui()

    # ------------------------------------------------------------------ interface

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(8)

        left_layout = QVBoxLayout()
        left_layout.setSpacing(4)

        title = QLabel("Calibration caméra — mire ChArUco 4×4")
        title.setProperty("role", "title")
        title.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(title)

        self._image_label = QLabel("Démarrage caméra...")
        self._image_label.setProperty("role", "camera")
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        left_layout.addWidget(self._image_label, stretch=1)

        self._status_label = QLabel("")
        self._status_label.setProperty("role", "status")
        self._status_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self._status_label)

        main_layout.addLayout(left_layout, stretch=3)

        right_layout = QVBoxLayout()
        right_layout.setSpacing(8)

        self._lbl_count = QLabel(f"Images\n0 / {CALIBRATION_MIN_IMAGES}")
        self._lbl_count.setAlignment(Qt.AlignCenter)
        self._lbl_count.setStyleSheet("font-size: 18px; font-weight: bold; color: #f0f0f0;")
        right_layout.addWidget(self._lbl_count)

        self._lbl_detection = QLabel("Détection\n—")
        self._lbl_detection.setAlignment(Qt.AlignCenter)
        self._lbl_detection.setStyleSheet("font-size: 13px; color: #888;")
        right_layout.addWidget(self._lbl_detection)

        self._lbl_error = QLabel("Erreur\n—")
        self._lbl_error.setAlignment(Qt.AlignCenter)
        self._lbl_error.setStyleSheet("font-size: 13px; color: #888;")
        right_layout.addWidget(self._lbl_error)

        right_layout.addStretch()

        self._btn_generate = QPushButton("Générer\nla mire")
        self._btn_generate.setProperty("role", "secondary")
        self._btn_generate.clicked.connect(self._on_generate)
        right_layout.addWidget(self._btn_generate)

        self._btn_capture = QPushButton("Capturer\ncette pose")
        self._btn_capture.setEnabled(False)
        self._btn_capture.clicked.connect(self._on_capture)
        right_layout.addWidget(self._btn_capture)

        self._btn_calibrate = QPushButton("Calibrer")
        self._btn_calibrate.setProperty("role", "secondary")
        self._btn_calibrate.setEnabled(False)
        self._btn_calibrate.clicked.connect(self._on_calibrate)
        right_layout.addWidget(self._btn_calibrate)

        self._btn_save = QPushButton("Sauvegarder")
        self._btn_save.setProperty("role", "success")
        self._btn_save.setEnabled(False)
        self._btn_save.clicked.connect(self._on_save)
        right_layout.addWidget(self._btn_save)

        self._btn_reset = QPushButton("Recommencer")
        self._btn_reset.setProperty("role", "secondary")
        self._btn_reset.clicked.connect(self._on_reset)
        right_layout.addWidget(self._btn_reset)

        self._btn_back = QPushButton("← Retour")
        self._btn_back.setProperty("role", "secondary")
        self._btn_back.clicked.connect(self.back_requested)
        right_layout.addWidget(self._btn_back)

        main_layout.addLayout(right_layout, stretch=1)

    # ------------------------------------------------------------------ caméra & thread

    def set_camera(self, camera) -> None:
        """Reçoit la référence caméra partagée (créée et possédée par MainApp)."""
        self._camera = camera
        if camera is not None:
            self._image_size = (camera.width, camera.height)

    def start_camera(self) -> None:
        """Démarrer l'aperçu et le thread de détection — la caméra est déjà ouverte."""
        if self._camera is None:
            self._image_label.setText("Caméra non disponible")
            self._status_label.setText("Erreur caméra")
            return

        # Créer et démarrer le thread de détection
        self._detection_thread = DetectionThread(self._board)
        self._detection_thread.result_ready.connect(self._on_detection_result)
        self._detection_thread.start()
        self._detection_busy = False

        self._status_label.setText(
            f"Caméra prête — {self._camera.width}×{self._camera.height} px"
        )
        self._timer.start(150)

    def stop_camera(self) -> None:
        """Arrêter le timer et le thread de détection — ne pas libérer la caméra (partagée)."""
        self._timer.stop()

        if self._detection_thread is not None:
            self._detection_thread.stop()   # Sortir de la boucle while
            self._detection_thread.wait(2000)
            self._detection_thread = None

        self._detection_busy = False

    # ------------------------------------------------------------------ flux vidéo

    def _update_frame(self) -> None:
        """Capturer un frame, l'afficher, et le soumettre au thread de détection."""
        if self._camera is None:
            return
        try:
            frame = self._camera.capture()
        except RuntimeError:
            self._timer.stop()
            self._image_label.setText("Caméra déconnectée — rebrancher et relancer")
            return

        # Afficher le frame brut immédiatement (sans attendre la détection)
        self._display_image(frame)

        # Soumettre au thread de détection seulement si disponible
        if not self._detection_busy and self._detection_thread is not None:
            self._detection_busy = True
            # copy() obligatoire : évite que le prochain capture() modifie le tableau
            # pendant que le thread de détection l'analyse
            self._detection_thread.submit(frame.copy())

    # ------------------------------------------------------------------ résultat détection

    @pyqtSlot(object, object, object)
    def _on_detection_result(self, corners, ids, preview: np.ndarray) -> None:
        """Reçu depuis DetectionThread quand la détection d'un frame est terminée.

        Qt route automatiquement ce signal dans le thread principal (connexion queued)
        car DetectionThread émet depuis un thread différent → accès aux widgets sans risque.
        """
        self._detection_busy = False
        self._charuco_detected = corners is not None

        if self._charuco_detected:
            self._lbl_detection.setText(f"Détection\n✓ {len(ids)} coins")
            self._lbl_detection.setStyleSheet("font-size: 13px; color: #4CAF50;")
            self._btn_capture.setEnabled(True)
            self._display_image(preview)
        else:
            self._lbl_detection.setText("Détection\n✗ —")
            self._lbl_detection.setStyleSheet("font-size: 13px; color: #f44336;")
            self._btn_capture.setEnabled(False)

    # ------------------------------------------------------------------ actions

    def _on_capture(self) -> None:
        """Capturer la pose courante et l'ajouter aux données de calibration."""
        if self._camera is None or not self._charuco_detected:
            return

        try:
            frame = self._camera.capture()
        except RuntimeError:
            return

        # Créer un détecteur local pour cette capture synchrone
        # (ne pas réutiliser celui du DetectionThread qui tourne en parallèle)
        detector = cv2.aruco.CharucoDetector(self._board)
        corners, ids, _ = detect_charuco(frame, self._board, detector)

        if corners is None:
            self._status_label.setText("Détection perdue au moment de la capture — réessayer")
            return

        self._all_corners.append(corners)
        self._all_ids.append(ids)

        count = len(self._all_corners)
        self._lbl_count.setText(f"Images\n{count} / {CALIBRATION_MIN_IMAGES}")

        if count >= CALIBRATION_MIN_IMAGES:
            self._btn_calibrate.setEnabled(True)
            self._status_label.setText(
                f"{count} images — prêt à calibrer (ou continuer pour plus de précision)"
            )
        else:
            self._status_label.setText(
                f"{count} / {CALIBRATION_MIN_IMAGES} — "
                f"changer la position et l'inclinaison de la mire "
                f"({CALIBRATION_MIN_IMAGES - count} restantes)"
            )

    def _on_calibrate(self) -> None:
        """Lancer le calcul de calibration dans un thread séparé."""
        self._btn_calibrate.setEnabled(False)
        self._btn_capture.setEnabled(False)
        self._btn_save.setEnabled(False)
        self._status_label.setText("Calibration en cours — veuillez patienter...")

        self._calib_thread = QThread()
        self._calib_worker = CalibrationWorker(
            self._all_corners, self._all_ids, self._board, self._image_size
        )
        self._calib_worker.moveToThread(self._calib_thread)

        self._calib_thread.started.connect(self._calib_worker.run)
        self._calib_worker.finished.connect(self._on_calibration_done)
        self._calib_worker.error_occurred.connect(self._on_calibration_error)
        self._calib_worker.finished.connect(self._calib_thread.quit)
        self._calib_worker.finished.connect(self._calib_worker.deleteLater)
        self._calib_worker.error_occurred.connect(self._calib_thread.quit)
        self._calib_worker.error_occurred.connect(self._calib_worker.deleteLater)
        self._calib_thread.finished.connect(self._calib_thread.deleteLater)

        self._calib_thread.start()

    @pyqtSlot(object, object, float)
    def _on_calibration_done(self, camera_matrix, dist_coeffs, error: float) -> None:
        self._camera_matrix = camera_matrix
        self._dist_coeffs = dist_coeffs

        if error < 1.0:
            color, qualite = "#4CAF50", "excellente"
        elif error < 2.0:
            color, qualite = "#FF9800", "acceptable"
        else:
            color, qualite = "#f44336", "insuffisante — recommencer avec plus d'images"

        self._lbl_error.setText(f"Erreur\n{error:.2f} px")
        self._lbl_error.setStyleSheet(f"font-size: 13px; color: {color};")
        self._status_label.setText(f"Calibration terminée — erreur {error:.2f} px ({qualite})")
        self._btn_calibrate.setEnabled(True)
        self._btn_save.setEnabled(error < 2.0)

    @pyqtSlot(str)
    def _on_calibration_error(self, message: str) -> None:
        self._status_label.setText(f"Erreur : {message}")
        self._btn_calibrate.setEnabled(True)

    def _on_save(self) -> None:
        if self._camera_matrix is None:
            return
        save_calibration(CALIBRATION_PATH, self._camera_matrix, self._dist_coeffs)
        self._btn_save.setEnabled(False)
        self._status_label.setText(
            f"Coefficients sauvegardés → {os.path.basename(CALIBRATION_PATH)}"
        )

    def _on_reset(self) -> None:
        self._all_corners.clear()
        self._all_ids.clear()
        self._camera_matrix = None
        self._dist_coeffs = None
        self._lbl_count.setText(f"Images\n0 / {CALIBRATION_MIN_IMAGES}")
        self._lbl_error.setText("Erreur\n—")
        self._lbl_error.setStyleSheet("font-size: 13px; color: #888;")
        self._btn_calibrate.setEnabled(False)
        self._btn_save.setEnabled(False)
        self._status_label.setText("Remise à zéro — présentez la mire sous différents angles")

    def _on_generate(self) -> None:
        generate_charuco_image(CHARUCO_IMAGE_PATH)
        self._status_label.setText(
            "Mire générée : assets/charuco_calibration.png — imprimer à taille réelle"
        )

    # ------------------------------------------------------------------ affichage

    def _display_image(self, frame: np.ndarray) -> None:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, channels = rgb.shape
        bytes_per_line = channels * w
        qimage = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimage).scaled(
            self._image_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self._image_label.setPixmap(pixmap)
