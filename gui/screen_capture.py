# Écran 1 — Capture photo
# Affiche le flux caméra en temps réel, permet de capturer et valider une photo

import numpy as np
import cv2
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, QThread, QObject, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QImage, QPixmap

from modules.camera import Camera
from modules.machine import Machine
from modules.config import CAMERA_INDEX


# ================================================================ worker homing

class HomingWorker(QObject):
    """Exécute le homing (G28) dans un thread séparé pour ne pas bloquer l'interface.

    Même principe que RunWorker : les commandes G-code bloquent jusqu'à la réponse
    de Marlin (G28 peut prendre 30-60 s). Sans thread, l'interface serait gelée.
    """

    finished = pyqtSignal()        # Homing terminé avec succès
    error_occurred = pyqtSignal(str)  # Erreur machine

    def __init__(self, machine: Machine) -> None:
        super().__init__()
        self._machine = machine

    @pyqtSlot()
    def run(self) -> None:
        """Connexion → G28 → déconnexion."""
        try:
            self._machine.connect()
            self._machine.home()
            self._machine.disconnect()
            self.finished.emit()
        except Exception as e:
            try:
                self._machine.disconnect()
            except Exception:
                pass
            self.error_occurred.emit(str(e))


class ScreenCapture(QWidget):
    """Écran 1 : flux vidéo en direct + capture + validation.

    Cycle :
        1. Flux vidéo en direct (QTimer → capture() toutes les 100 ms)
        2. Clic "Capturer" → flux figé, image sauvegardée
        3. Clic "Valider" → signal photo_validated émis → navigation vers ScreenZone
        4. Clic "Reprendre" → flux relancé, retour à l'étape 1
    """

    # Signal émis quand l'utilisateur valide la photo
    # Le paramètre est l'image numpy BGR — 'object' car PyQt5 ne connaît pas numpy
    photo_validated = pyqtSignal(object)

    # Signal émis quand l'opérateur veut accéder à l'écran de calibration caméra
    calibration_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        # Objet caméra — créé au premier start_camera(), détruit à stop_camera()
        self._camera: Camera | None = None
        # Image figée au moment du clic "Capturer" — None si flux en direct
        self._captured_image: np.ndarray | None = None
        # Référence machine pour le homing — fournie par app.py via set_machine()
        self._machine: Machine | None = None
        # Thread et worker de homing — stockés en attributs pour éviter le garbage collection
        # Si on les laissait en variables locales, Python les détruirait dès la fin de
        # _on_homing() et le thread s'arrêterait silencieusement avant d'avoir rien fait.
        self._homing_thread: QThread | None = None
        self._homing_worker: HomingWorker | None = None

        # Timer qui déclenche une capture toutes les 100 ms (~10 fps)
        # 10 fps est suffisant pour un aperçu — moins de charge CPU sur RPi 3B+
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_frame)

        self._setup_ui()

    def set_machine(self, machine: Machine) -> None:
        """Fournit la référence machine pour le bouton Homing.

        Appelé par app.py après la création de l'écran.
        Sans machine, le bouton Homing reste désactivé.
        """
        self._machine = machine
        self._btn_homing.setEnabled(True)

    def set_camera(self, camera) -> None:
        """Reçoit la référence caméra partagée (créée et possédée par MainApp).

        L'écran n'ouvre plus la caméra lui-même — la même instance est partagée
        avec screen_calibration pour éviter les fermetures/réouvertures lentes
        (1-2s à chaque changement d'écran).
        """
        self._camera = camera

    # ------------------------------------------------------------------ interface

    def _setup_ui(self) -> None:
        """Construire la mise en page : zone image (haut) + boutons (bas)."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Titre de l'écran
        title = QLabel("Capture de la piece")
        title.setProperty("role", "title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Zone d'affichage de l'image — occupe tout l'espace disponible
        self._image_label = QLabel("Demarrage camera...")
        self._image_label.setProperty("role", "camera")
        self._image_label.setAlignment(Qt.AlignCenter)
        # Ignored = le label prend l'espace alloué par le layout sans grandir selon son contenu
        # Sans ça, chaque nouveau pixmap agrandit le label → boucle infinie d'agrandissement
        self._image_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        layout.addWidget(self._image_label, stretch=1)

        # Ligne de statut (nombre de pixels, résolution, messages d'erreur)
        self._status_label = QLabel("")
        self._status_label.setProperty("role", "status")
        self._status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._status_label)

        # Bouton Homing — ligne séparée au-dessus des boutons de capture
        homing_layout = QHBoxLayout()
        homing_layout.setSpacing(8)

        self._btn_homing = QPushButton("Homing (G28)")
        self._btn_homing.setProperty("role", "secondary")
        self._btn_homing.setEnabled(False)  # Activé par set_machine() quand la machine est connue
        self._btn_homing.clicked.connect(self._on_homing)
        homing_layout.addWidget(self._btn_homing)

        # Bouton d'accès à l'écran de calibration caméra (ChArUco)
        self._btn_calibration = QPushButton("Calibration caméra")
        self._btn_calibration.setProperty("role", "secondary")
        self._btn_calibration.clicked.connect(self.calibration_requested)
        homing_layout.addWidget(self._btn_calibration)

        layout.addLayout(homing_layout)

        # Barre de boutons capture — 3 boutons côte à côte
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self._btn_capture = QPushButton("Capturer")
        self._btn_capture.setEnabled(False)  # Activé seulement quand la caméra est prête
        self._btn_capture.clicked.connect(self._on_capture)

        self._btn_validate = QPushButton("Valider")
        self._btn_validate.setProperty("role", "success")
        self._btn_validate.setEnabled(False)  # Activé après une capture
        self._btn_validate.clicked.connect(self._on_validate)

        self._btn_retake = QPushButton("Reprendre")
        self._btn_retake.setProperty("role", "secondary")
        self._btn_retake.setEnabled(False)  # Activé après une capture
        self._btn_retake.clicked.connect(self._on_retake)

        btn_layout.addWidget(self._btn_capture)
        btn_layout.addWidget(self._btn_validate)
        btn_layout.addWidget(self._btn_retake)
        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------ caméra

    def start_camera(self) -> None:
        """Démarrer l'aperçu vidéo — la caméra est déjà ouverte par MainApp via set_camera()."""
        self._captured_image = None
        self._btn_validate.setEnabled(False)
        self._btn_retake.setEnabled(False)

        if self._camera is None:
            self._image_label.setText(
                "Camera non disponible\n\nVerifier le branchement USB"
            )
            self._status_label.setText("Erreur camera")
            self._btn_capture.setEnabled(False)
            return

        self._btn_capture.setEnabled(True)
        self._status_label.setText(
            f"Camera prete — {self._camera.width}x{self._camera.height} px"
        )
        # Démarrer le timer → _update_frame() appelé toutes les 100 ms
        self._timer.start(100)

    def stop_camera(self) -> None:
        """Arrêter le timer d'aperçu — ne pas libérer la caméra (partagée avec calibration)."""
        self._timer.stop()

    def _update_frame(self) -> None:
        """Appelé toutes les 100 ms par le timer — capture et affiche une image."""
        if self._camera is None:
            return
        try:
            frame = self._camera.capture()
            self._display_image(frame)
        except RuntimeError:
            # La caméra a été débranchée en cours de route
            self._timer.stop()
            self._image_label.setText("Camera deconnectee — rebrancher et relancer")
            self._btn_capture.setEnabled(False)

    # ------------------------------------------------------------------ actions boutons

    def _on_capture(self) -> None:
        """Figer l'image et passer en mode validation."""
        if self._camera is None:
            return

        # Arrêter le flux pour figer l'image
        self._timer.stop()

        # Capturer l'image définitive et l'afficher
        self._captured_image = self._camera.capture()
        self._display_image(self._captured_image)

        # Basculer les boutons : on est maintenant en mode "photo figée"
        self._btn_capture.setEnabled(False)
        self._btn_validate.setEnabled(True)
        self._btn_retake.setEnabled(True)
        self._status_label.setText("Photo prise — valider ou reprendre")

    def _on_validate(self) -> None:
        """Émettre le signal avec l'image capturée → navigation vers ScreenZone."""
        if self._captured_image is not None:
            # photo_validated déclenche MainApp._go_to_zone() qui appelle stop_camera()
            self.photo_validated.emit(self._captured_image)

    def _on_retake(self) -> None:
        """Reprendre le flux vidéo — annuler la photo figée."""
        self._captured_image = None
        self._btn_capture.setEnabled(True)
        self._btn_validate.setEnabled(False)
        self._btn_retake.setEnabled(False)
        self._status_label.setText(
            f"Camera prete — {self._camera.width}x{self._camera.height} px"
        )
        # Relancer le flux
        self._timer.start(100)

    # ------------------------------------------------------------------ homing

    def _on_homing(self) -> None:
        """Lancer le homing G28 dans un thread séparé."""
        if self._machine is None:
            return

        # Désactiver tous les boutons pendant le homing pour éviter les actions parallèles
        self._btn_homing.setEnabled(False)
        self._btn_capture.setEnabled(False)
        self._status_label.setText("Homing en cours (30-60 s)...")

        # Créer le thread et le worker — stockés en attributs (pas en variables locales)
        # pour éviter que Python les détruise avant la fin du thread
        self._homing_thread = QThread()
        self._homing_worker = HomingWorker(self._machine)
        self._homing_worker.moveToThread(self._homing_thread)

        self._homing_thread.started.connect(self._homing_worker.run)
        self._homing_worker.finished.connect(self._on_homing_finished)
        self._homing_worker.error_occurred.connect(self._on_homing_error)

        # Nettoyer le thread après la fin (succès ou erreur)
        self._homing_worker.finished.connect(self._homing_thread.quit)
        self._homing_worker.finished.connect(self._homing_worker.deleteLater)
        self._homing_worker.error_occurred.connect(self._homing_thread.quit)
        self._homing_worker.error_occurred.connect(self._homing_worker.deleteLater)
        self._homing_thread.finished.connect(self._homing_thread.deleteLater)

        self._homing_thread.start()

    @pyqtSlot()
    def _on_homing_finished(self) -> None:
        """Homing terminé avec succès — réactiver les boutons."""
        self._btn_homing.setEnabled(True)
        self._btn_capture.setEnabled(self._camera is not None)
        self._status_label.setText("Homing termine — machine prete")

    @pyqtSlot(str)
    def _on_homing_error(self, message: str) -> None:
        """Erreur pendant le homing — afficher le message et réactiver le bouton."""
        self._btn_homing.setEnabled(True)
        self._btn_capture.setEnabled(self._camera is not None)
        self._status_label.setText(f"Erreur homing : {message}")

    # ------------------------------------------------------------------ affichage

    def _display_image(self, frame: np.ndarray) -> None:
        """Convertir une image OpenCV (BGR numpy) en QPixmap et l'afficher."""
        # OpenCV utilise l'ordre BGR ; Qt attend RGB → inversion des canaux
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, channels = rgb.shape

        # Créer un QImage à partir des données numpy (sans copie mémoire inutile)
        # Le stride (bytes_per_line) évite les artefacts si la largeur n'est pas alignée
        bytes_per_line = channels * w
        qimage = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)

        # Redimensionner pour tenir dans le label tout en gardant le ratio d'aspect
        pixmap = QPixmap.fromImage(qimage).scaled(
            self._image_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self._image_label.setPixmap(pixmap)
