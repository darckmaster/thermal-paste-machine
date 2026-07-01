# Écran 2 — Sélection de zone
# Affiche la photo capturée et permettra à l'utilisateur de définir la zone de dépose
# Phase 4 : placeholder — la sélection de zone sera implémentée en Phase 5

import numpy as np
import cv2
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap


class ScreenZone(QWidget):
    """Écran 2 : sélection de la zone de dépose et réglage de la quantité.

    Phase 4 (actuel) : placeholder — affiche la photo, bouton "Lancer" directement.
    Phase 5 : widget interactif pour dessiner un rectangle sur l'image.
    """

    # Signal émis quand l'utilisateur lance la dépose
    # Paramètres : zone (rectangle en mm — None pour l'instant) et quantité (mm d'axe E)
    zone_configured = pyqtSignal(object, float)

    def __init__(self) -> None:
        super().__init__()
        self._image: np.ndarray | None = None
        self._setup_ui()

    def set_image(self, image: np.ndarray) -> None:
        """Recevoir la photo validée depuis ScreenCapture et l'afficher."""
        self._image = image
        self._display_image(image)

    # ------------------------------------------------------------------ interface

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Titre
        title = QLabel("Selection de la zone de depose")
        title.setProperty("role", "title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Affichage de la photo capturée
        self._image_label = QLabel("Aucune image")
        self._image_label.setProperty("role", "camera")
        self._image_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._image_label, stretch=1)

        # Message placeholder — sera remplacé par le widget de dessin en Phase 5
        placeholder = QLabel(
            "Phase 5 : selection de zone a implémenter\n"
            "Pour l'instant : zone complete (toute la piece)"
        )
        placeholder.setProperty("role", "status")
        placeholder.setAlignment(Qt.AlignCenter)
        layout.addWidget(placeholder)

        # Slider pour régler la quantité de pâte (de 1 à 10 mm d'axe E)
        quantity_layout = QHBoxLayout()
        quantity_layout.addWidget(QLabel("Quantite :"))

        self._slider = QSlider(Qt.Horizontal)
        self._slider.setMinimum(1)   # 1 mm d'axe E minimum
        self._slider.setMaximum(10)  # 10 mm d'axe E maximum
        self._slider.setValue(3)     # valeur par défaut
        self._slider.setTickInterval(1)
        self._slider.setTickPosition(QSlider.TicksBelow)
        self._slider.valueChanged.connect(self._on_quantity_changed)
        quantity_layout.addWidget(self._slider, stretch=1)

        self._quantity_label = QLabel("3 mm")
        self._quantity_label.setMinimumWidth(60)
        quantity_layout.addWidget(self._quantity_label)
        layout.addLayout(quantity_layout)

        # Boutons de navigation
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        btn_back = QPushButton("Retour")
        btn_back.setProperty("role", "secondary")
        btn_back.clicked.connect(self._on_back)

        self._btn_launch = QPushButton("Lancer la depose")
        self._btn_launch.setProperty("role", "success")
        self._btn_launch.clicked.connect(self._on_launch)

        btn_layout.addWidget(btn_back)
        btn_layout.addWidget(self._btn_launch, stretch=2)
        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------ actions

    def _on_quantity_changed(self, value: int) -> None:
        """Mettre à jour l'affichage de la quantité quand le slider bouge."""
        self._quantity_label.setText(f"{value} mm")

    def _on_back(self) -> None:
        """Retour à l'écran de capture — déclenché par le signal new_piece_requested
        via un détour par MainApp, ou ici directement via la fenêtre parente."""
        # Remonter à la fenêtre principale pour déclencher la navigation
        parent = self.window()
        if hasattr(parent, '_go_to_capture'):
            parent._go_to_capture()

    def _on_launch(self) -> None:
        """Émettre le signal avec la zone (None pour l'instant) et la quantité."""
        quantity = float(self._slider.value())
        # zone = None en Phase 4 — sera un rectangle (x, y, w, h) en Phase 5
        self.zone_configured.emit(None, quantity)

    # ------------------------------------------------------------------ affichage

    def _display_image(self, frame: np.ndarray) -> None:
        """Afficher l'image numpy dans le label Qt."""
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
