# Écran 2 — Sélection de zone de dépose
# L'utilisateur dessine un rectangle sur la photo ; on convertit en mm via l'homographie ArUco

import numpy as np
import cv2
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider
)
from PyQt5.QtCore import Qt, pyqtSignal, QRect, QPoint
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor

from modules.vision import VisionProcessor
from modules.config import (
    ARUCO_DICT_ID, ARUCO_MARKER_SIZE_MM,
    WORK_AREA_WIDTH_MM, WORK_AREA_HEIGHT_MM,
    DISPENSE_Z_HEIGHT_MM,
)


class ZoneSelector(QLabel):
    """QLabel interactif — l'utilisateur dessine un rectangle à la souris/au doigt.

    Émet rectangle_selected(QRect) quand le doigt/curseur est relâché.
    Le QRect est exprimé en coordonnées du label (pixels affichés).
    """

    rectangle_selected = pyqtSignal(QRect)

    def __init__(self) -> None:
        super().__init__()
        # Point de départ du rectangle (None si pas de dessin en cours)
        self._start: QPoint | None = None
        # Rectangle courant en cours de dessin (affiché en temps réel)
        self._rect: QRect | None = None
        # Dernier rectangle validé (affiché après relâchement)
        self._confirmed_rect: QRect | None = None

    def mousePressEvent(self, event) -> None:
        """Mémoriser le point de départ au clic/toucher."""
        if event.button() == Qt.LeftButton:
            self._start = event.pos()
            self._rect = QRect(self._start, self._start)
            self.update()  # Forcer un repaint pour afficher le rectangle naissant

    def mouseMoveEvent(self, event) -> None:
        """Mettre à jour le rectangle pendant le déplacement."""
        if self._start is not None:
            # normalized() garantit que top-left < bottom-right (même si on tire vers le haut)
            self._rect = QRect(self._start, event.pos()).normalized()
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        """Finaliser le rectangle et émettre le signal."""
        if event.button() == Qt.LeftButton and self._start is not None:
            self._rect = QRect(self._start, event.pos()).normalized()
            self._confirmed_rect = self._rect
            self._start = None
            self.rectangle_selected.emit(self._confirmed_rect)
            self.update()

    def paintEvent(self, event) -> None:
        """Dessiner l'image puis superposer le rectangle de sélection."""
        # Dessiner l'image de base (comportement normal du QLabel)
        super().paintEvent(event)

        # Dessiner le rectangle par-dessus si un est en cours ou confirmé
        rect_a_dessiner = self._rect or self._confirmed_rect
        if rect_a_dessiner and not rect_a_dessiner.isEmpty():
            painter = QPainter(self)
            # Contour orange vif (bien visible sur toutes les images)
            painter.setPen(QPen(QColor(255, 140, 0), 2, Qt.SolidLine))
            # Remplissage orange semi-transparent
            painter.setBrush(QColor(255, 140, 0, 50))
            painter.drawRect(rect_a_dessiner)
            painter.end()

    def clear_selection(self) -> None:
        """Effacer le rectangle sélectionné."""
        self._rect = None
        self._confirmed_rect = None
        self._start = None
        self.update()


class ScreenZone(QWidget):
    """Écran 2 : sélection de la zone de dépose sur la photo capturée.

    L'utilisateur dessine un rectangle sur la photo.
    On détecte les marqueurs ArUco pour convertir le rectangle pixels → mm.
    On émet zone_configured(zone_mm, quantite) pour passer à l'exécution.
    """

    # zone_mm = (x, y, largeur, hauteur) en mm dans le repère machine
    # quantite = mm d'axe E à pousser par mm de déplacement (réglé par le slider)
    zone_configured = pyqtSignal(object, float)

    def __init__(self) -> None:
        super().__init__()
        self._image: np.ndarray | None = None          # photo brute reçue de ScreenCapture
        self._homography: np.ndarray | None = None     # matrice H calculée depuis les ArUco
        self._vision = VisionProcessor(ARUCO_DICT_ID, ARUCO_MARKER_SIZE_MM)
        self._zone_mm: tuple | None = None              # zone sélectionnée en mm
        self._setup_ui()

    def set_image(self, image: np.ndarray) -> None:
        """Recevoir la photo de ScreenCapture, détecter les ArUco, afficher."""
        self._image = image
        self._zone_mm = None
        self._selector.clear_selection()
        self._btn_launch.setEnabled(False)

        # Tenter de détecter les 4 marqueurs et calculer l'homographie
        self._detect_and_setup_homography(image)

        # Afficher la photo dans le sélecteur
        self._display_image(image)

    # ------------------------------------------------------------------ interface

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Titre
        title = QLabel("Selectionner la zone de depose")
        title.setProperty("role", "title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Zone de sélection interactive (image + dessin rectangle)
        self._selector = ZoneSelector()
        self._selector.setProperty("role", "camera")
        self._selector.setAlignment(Qt.AlignCenter)
        # Activer le suivi souris même sans clic enfoncé (utile pour le tactile)
        self._selector.setMouseTracking(True)
        self._selector.rectangle_selected.connect(self._on_rectangle_drawn)
        layout.addWidget(self._selector, stretch=1)

        # Message d'état (indique si les ArUco sont détectés, la zone sélectionnée, etc.)
        self._status_label = QLabel("Dessiner un rectangle sur la photo")
        self._status_label.setProperty("role", "status")
        self._status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._status_label)

        # Slider : quantité de pâte (mm d'axe E par mm de déplacement)
        # Valeur × 0.01 pour avoir de 0.01 à 0.10 mm/mm (résolution 0.01)
        qty_layout = QHBoxLayout()
        qty_layout.addWidget(QLabel("Quantite :"))

        self._slider = QSlider(Qt.Horizontal)
        self._slider.setMinimum(1)    # 0.01 mm/mm
        self._slider.setMaximum(10)   # 0.10 mm/mm
        self._slider.setValue(3)      # 0.03 mm/mm par défaut
        self._slider.setTickInterval(1)
        self._slider.setTickPosition(QSlider.TicksBelow)
        self._slider.valueChanged.connect(self._on_quantity_changed)
        qty_layout.addWidget(self._slider, stretch=1)

        self._qty_label = QLabel("0.03 mm/mm")
        self._qty_label.setMinimumWidth(80)
        qty_layout.addWidget(self._qty_label)
        layout.addLayout(qty_layout)

        # Boutons de navigation
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        btn_back = QPushButton("Retour")
        btn_back.setProperty("role", "secondary")
        btn_back.clicked.connect(self._on_back)

        btn_reset = QPushButton("Effacer")
        btn_reset.setProperty("role", "secondary")
        btn_reset.clicked.connect(self._on_reset)

        self._btn_launch = QPushButton("Lancer la depose")
        self._btn_launch.setProperty("role", "success")
        self._btn_launch.setEnabled(False)  # Activé seulement quand une zone est sélectionnée
        self._btn_launch.clicked.connect(self._on_launch)

        btn_layout.addWidget(btn_back)
        btn_layout.addWidget(btn_reset)
        btn_layout.addWidget(self._btn_launch, stretch=2)
        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------ détection ArUco

    def _detect_and_setup_homography(self, image: np.ndarray) -> None:
        """Détecter les 4 marqueurs ArUco et calculer l'homographie pixel→mm."""
        markers = self._vision.detect_markers(image)

        if len(markers) == 4:
            # Les 4 marqueurs sont détectés → on peut convertir pixels en mm
            self._homography = self._vision.compute_homography(markers)
            self._status_label.setText(
                "4 marqueurs ArUco detectes — dessiner un rectangle sur la zone"
            )
        else:
            # Pas assez de marqueurs → on ne peut pas convertir en mm
            self._homography = None
            self._status_label.setText(
                f"Attention : {len(markers)}/4 marqueurs detectes — "
                f"la conversion pixels→mm ne sera pas possible"
            )

    # ------------------------------------------------------------------ conversion coordonnées

    def _label_to_image_coords(self, lx: int, ly: int) -> tuple:
        """Convertir des coordonnées du label (pixels affichés) en pixels de l'image originale.

        Le label affiche l'image redimensionnée avec Qt.KeepAspectRatio, ce qui crée
        des marges noires (letterboxing). On doit corriger ces offsets pour retrouver
        les coordonnées dans l'image originale.
        """
        if self._image is None:
            return lx, ly

        lw = self._selector.width()
        lh = self._selector.height()
        ih, iw = self._image.shape[:2]

        # Calculer le facteur de zoom appliqué par Qt (KeepAspectRatio)
        ratio = min(lw / iw, lh / ih)
        disp_w = iw * ratio
        disp_h = ih * ratio

        # Calculer l'offset dû au centrage de l'image dans le label
        off_x = (lw - disp_w) / 2
        off_y = (lh - disp_h) / 2

        # Convertir et clipper aux limites de l'image
        ix = (lx - off_x) / ratio
        iy = (ly - off_y) / ratio
        ix = max(0.0, min(ix, iw - 1))
        iy = max(0.0, min(iy, ih - 1))

        return int(ix), int(iy)

    def _rect_to_zone_mm(self, rect: QRect) -> tuple | None:
        """Convertir un rectangle (en coordonnées label) en zone en mm.

        Retourne (x_mm, y_mm, width_mm, height_mm) ou None si impossible.
        """
        if self._homography is None or self._image is None:
            return None

        # Convertir les 4 coins du rectangle de label → pixels image
        tl = self._label_to_image_coords(rect.left(), rect.top())
        br = self._label_to_image_coords(rect.right(), rect.bottom())

        # Convertir les pixels image → coordonnées mm via l'homographie ArUco
        x1_mm, y1_mm = self._vision.pixel_to_mm(tl[0], tl[1], self._homography)
        x2_mm, y2_mm = self._vision.pixel_to_mm(br[0], br[1], self._homography)

        # Calculer la zone (x_min, y_min, largeur, hauteur) en mm
        x_mm = min(x1_mm, x2_mm)
        y_mm = min(y1_mm, y2_mm)
        w_mm = abs(x2_mm - x1_mm)
        h_mm = abs(y2_mm - y1_mm)

        # Clipper à la zone de travail physique
        x_mm = max(0.0, min(x_mm, WORK_AREA_WIDTH_MM))
        y_mm = max(0.0, min(y_mm, WORK_AREA_HEIGHT_MM))
        w_mm = min(w_mm, WORK_AREA_WIDTH_MM - x_mm)
        h_mm = min(h_mm, WORK_AREA_HEIGHT_MM - y_mm)

        # Rejeter les zones trop petites (rectangle accidentel = un simple clic)
        if w_mm < 1.0 or h_mm < 1.0:
            return None

        return (round(x_mm, 1), round(y_mm, 1), round(w_mm, 1), round(h_mm, 1))

    # ------------------------------------------------------------------ actions

    def _on_rectangle_drawn(self, rect: QRect) -> None:
        """Réaction quand l'utilisateur a fini de dessiner le rectangle."""
        zone_mm = self._rect_to_zone_mm(rect)

        if zone_mm is None and self._homography is None:
            # Pas d'ArUco — on ne peut pas convertir
            self._status_label.setText(
                "Impossible de convertir en mm : marqueurs ArUco non detectes.\n"
                "Reprendre une photo avec les marqueurs visibles."
            )
            self._btn_launch.setEnabled(False)
            return

        if zone_mm is None:
            # Zone trop petite (simple clic)
            self._status_label.setText("Zone trop petite — dessiner un rectangle plus grand")
            self._btn_launch.setEnabled(False)
            return

        self._zone_mm = zone_mm
        x, y, w, h = zone_mm
        self._status_label.setText(
            f"Zone selectionnee : {w:.1f} × {h:.1f} mm  "
            f"(origine X={x:.1f} Y={y:.1f} mm)"
        )
        self._btn_launch.setEnabled(True)

    def _on_quantity_changed(self, value: int) -> None:
        """Mettre à jour l'affichage de la quantité quand le slider bouge."""
        qty = value * 0.01
        self._qty_label.setText(f"{qty:.2f} mm/mm")

    def _on_reset(self) -> None:
        """Effacer la sélection et recommencer."""
        self._selector.clear_selection()
        self._zone_mm = None
        self._btn_launch.setEnabled(False)
        self._status_label.setText("Dessiner un rectangle sur la photo")

    def _on_back(self) -> None:
        """Retour à l'écran de capture."""
        parent = self.window()
        if hasattr(parent, '_go_to_capture'):
            parent._go_to_capture()

    def _on_launch(self) -> None:
        """Émettre le signal avec la zone mm et la quantité configurée."""
        if self._zone_mm is None:
            return
        quantity = self._slider.value() * 0.01  # Convertir slider → mm/mm
        self.zone_configured.emit(self._zone_mm, quantity)

    # ------------------------------------------------------------------ affichage

    def _display_image(self, frame: np.ndarray) -> None:
        """Afficher l'image dans le ZoneSelector."""
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, channels = rgb.shape
        bytes_per_line = channels * w
        qimage = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimage).scaled(
            self._selector.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self._selector.setPixmap(pixmap)
