# Écran 2 — Tracé du chemin de dépose
# L'utilisateur clique/tape des points sur la photo pour dessiner son chemin.
# Les coordonnées sont converties en mm via l'homographie ArUco.

import numpy as np
import cv2
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QBrush, QColor

from modules.vision import VisionProcessor
from modules.config import (
    ARUCO_DICT_ID, ARUCO_MARKER_SIZE_MM,
    WORK_AREA_WIDTH_MM, WORK_AREA_HEIGHT_MM,
)


class LineSelector(QLabel):
    """QLabel interactif — chaque clic/toucher ajoute un point au tracé.

    Les points sont reliés par des lignes dessinées en temps réel.
    Émet point_added(QPoint) à chaque nouveau point.
    """

    point_added = pyqtSignal(QPoint)

    def __init__(self) -> None:
        super().__init__()
        # Liste des points du tracé en coordonnées label (pixels affichés)
        self._points: list[QPoint] = []

    def mousePressEvent(self, event) -> None:
        """Ajouter un point au clic/toucher."""
        if event.button() == Qt.LeftButton:
            self._points.append(event.pos())
            self.point_added.emit(event.pos())
            self.update()  # Déclencher un repaint pour afficher le nouveau point

    def paintEvent(self, event) -> None:
        """Dessiner l'image puis superposer le tracé par-dessus."""
        super().paintEvent(event)

        if len(self._points) == 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Dessiner les segments reliant les points
        if len(self._points) >= 2:
            pen = QPen(QColor(255, 80, 0), 3, Qt.SolidLine)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            for i in range(1, len(self._points)):
                painter.drawLine(self._points[i - 1], self._points[i])

        # Dessiner un cercle à chaque point (pour bien voir les waypoints)
        for i, pt in enumerate(self._points):
            if i == 0:
                # Premier point : vert (départ)
                painter.setBrush(QBrush(QColor(0, 200, 80)))
                painter.setPen(QPen(QColor(0, 120, 40), 2))
            elif i == len(self._points) - 1:
                # Dernier point : rouge (arrivée)
                painter.setBrush(QBrush(QColor(220, 50, 50)))
                painter.setPen(QPen(QColor(140, 20, 20), 2))
            else:
                # Points intermédiaires : orange
                painter.setBrush(QBrush(QColor(255, 140, 0)))
                painter.setPen(QPen(QColor(180, 90, 0), 2))
            painter.drawEllipse(pt, 8, 8)

        painter.end()

    def remove_last_point(self) -> None:
        """Supprimer le dernier point ajouté."""
        if self._points:
            self._points.pop()
            self.update()

    def clear_points(self) -> None:
        """Effacer tous les points."""
        self._points.clear()
        self.update()

    def get_points(self) -> list:
        """Retourner la liste des points (coordonnées label)."""
        return list(self._points)


class ScreenZone(QWidget):
    """Écran 2 : tracé libre du chemin de dépose sur la photo.

    L'utilisateur tape une série de points sur la photo.
    Les points sont convertis en mm via l'homographie ArUco et transmis
    au PathPlanner pour générer la trajectoire G-code.
    """

    # points_mm = liste de (x_mm, y_mm) définissant le tracé
    # quantity = mm d'axe E par mm de déplacement (slider)
    zone_configured = pyqtSignal(object, float)

    def __init__(self) -> None:
        super().__init__()
        self._image: np.ndarray | None = None
        self._homography: np.ndarray | None = None
        self._vision = VisionProcessor(ARUCO_DICT_ID, ARUCO_MARKER_SIZE_MM)
        self._setup_ui()

    def set_image(self, image: np.ndarray) -> None:
        """Recevoir la photo de ScreenCapture, détecter les ArUco, afficher."""
        self._image = image
        self._selector.clear_points()
        self._btn_launch.setEnabled(False)
        self._btn_undo.setEnabled(False)
        self._n_points_label.setText("0 point(s)")

        self._detect_homography(image)
        self._display_image(image)

    # ------------------------------------------------------------------ interface

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Titre
        title = QLabel("Tracer le chemin de depose")
        title.setProperty("role", "title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Sélecteur de tracé interactif
        self._selector = LineSelector()
        self._selector.setProperty("role", "camera")
        self._selector.setAlignment(Qt.AlignCenter)
        self._selector.point_added.connect(self._on_point_added)
        layout.addWidget(self._selector, stretch=1)

        # Barre de statut
        self._status_label = QLabel("Appuyer sur la photo pour ajouter des points")
        self._status_label.setProperty("role", "status")
        self._status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._status_label)

        # Ligne : compteur de points + slider quantité
        info_layout = QHBoxLayout()

        self._n_points_label = QLabel("0 point(s)")
        self._n_points_label.setProperty("role", "status")
        info_layout.addWidget(self._n_points_label)

        info_layout.addStretch(1)
        info_layout.addWidget(QLabel("Quantite :"))

        self._slider = QSlider(Qt.Horizontal)
        self._slider.setMinimum(1)    # 0.01 mm/mm
        self._slider.setMaximum(10)   # 0.10 mm/mm
        self._slider.setValue(3)      # 0.03 mm/mm par défaut
        self._slider.setTickInterval(1)
        self._slider.setTickPosition(QSlider.TicksBelow)
        self._slider.valueChanged.connect(self._on_quantity_changed)
        info_layout.addWidget(self._slider)

        self._qty_label = QLabel("0.03 mm/mm")
        self._qty_label.setMinimumWidth(80)
        info_layout.addWidget(self._qty_label)
        layout.addLayout(info_layout)

        # Boutons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        btn_back = QPushButton("Retour")
        btn_back.setProperty("role", "secondary")
        btn_back.clicked.connect(self._on_back)

        self._btn_undo = QPushButton("Annuler dernier")
        self._btn_undo.setProperty("role", "secondary")
        self._btn_undo.setEnabled(False)
        self._btn_undo.clicked.connect(self._on_undo)

        btn_clear = QPushButton("Effacer tout")
        btn_clear.setProperty("role", "secondary")
        btn_clear.clicked.connect(self._on_clear)

        self._btn_launch = QPushButton("Lancer")
        self._btn_launch.setProperty("role", "success")
        self._btn_launch.setEnabled(False)  # Activé dès 2 points
        self._btn_launch.clicked.connect(self._on_launch)

        btn_layout.addWidget(btn_back)
        btn_layout.addWidget(self._btn_undo)
        btn_layout.addWidget(btn_clear)
        btn_layout.addWidget(self._btn_launch, stretch=2)
        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------ détection ArUco

    def _detect_homography(self, image: np.ndarray) -> None:
        """Détecter les marqueurs ArUco et calculer l'homographie."""
        markers = self._vision.detect_markers(image)
        if len(markers) == 4:
            self._homography = self._vision.compute_homography(markers)
            self._status_label.setText(
                "4 marqueurs detectes — appuyer sur la photo pour tracer le chemin"
            )
        else:
            self._homography = None
            self._status_label.setText(
                f"Attention : {len(markers)}/4 marqueurs detectes — "
                f"conversion pixels→mm indisponible"
            )

    # ------------------------------------------------------------------ conversion coordonnées

    def _label_to_image_coords(self, lx: int, ly: int) -> tuple:
        """Convertir coordonnées label (pixels affichés) → pixels de l'image originale."""
        if self._image is None:
            return lx, ly

        lw = self._selector.width()
        lh = self._selector.height()
        ih, iw = self._image.shape[:2]

        # Facteur de zoom appliqué par Qt (KeepAspectRatio)
        ratio = min(lw / iw, lh / ih)
        disp_w = iw * ratio
        disp_h = ih * ratio

        # Offset de centrage (marges noires)
        off_x = (lw - disp_w) / 2
        off_y = (lh - disp_h) / 2

        ix = max(0.0, min((lx - off_x) / ratio, iw - 1))
        iy = max(0.0, min((ly - off_y) / ratio, ih - 1))
        return int(ix), int(iy)

    def _point_to_mm(self, pt: QPoint) -> tuple | None:
        """Convertir un point label → (x_mm, y_mm) via l'homographie.

        Retourne None si l'homographie n'est pas disponible ou si le point
        est hors de la zone de travail.
        """
        if self._homography is None:
            return None

        ix, iy = self._label_to_image_coords(pt.x(), pt.y())
        x_mm, y_mm = self._vision.pixel_to_mm(ix, iy, self._homography)

        # Clipper à la zone de travail physique
        x_mm = max(0.0, min(x_mm, WORK_AREA_WIDTH_MM))
        y_mm = max(0.0, min(y_mm, WORK_AREA_HEIGHT_MM))

        return (round(x_mm, 1), round(y_mm, 1))

    # ------------------------------------------------------------------ actions

    def _on_point_added(self, pt: QPoint) -> None:
        """Mettre à jour le compteur et l'état des boutons après ajout d'un point."""
        n = len(self._selector.get_points())
        self._n_points_label.setText(f"{n} point(s)")
        self._btn_undo.setEnabled(True)

        # "Lancer" activé dès qu'on a au moins 2 points (= 1 segment)
        self._btn_launch.setEnabled(n >= 2)

        if n >= 2:
            self._status_label.setText(
                f"{n} points — continuer le trace ou appuyer sur Lancer"
            )

    def _on_undo(self) -> None:
        """Supprimer le dernier point."""
        self._selector.remove_last_point()
        n = len(self._selector.get_points())
        self._n_points_label.setText(f"{n} point(s)")
        self._btn_undo.setEnabled(n > 0)
        self._btn_launch.setEnabled(n >= 2)
        if n == 0:
            self._status_label.setText("Appuyer sur la photo pour ajouter des points")

    def _on_clear(self) -> None:
        """Effacer tous les points."""
        self._selector.clear_points()
        self._n_points_label.setText("0 point(s)")
        self._btn_undo.setEnabled(False)
        self._btn_launch.setEnabled(False)
        self._status_label.setText("Appuyer sur la photo pour ajouter des points")

    def _on_quantity_changed(self, value: int) -> None:
        self._qty_label.setText(f"{value * 0.01:.2f} mm/mm")

    def _on_back(self) -> None:
        parent = self.window()
        if hasattr(parent, '_go_to_capture'):
            parent._go_to_capture()

    def _on_launch(self) -> None:
        """Convertir tous les points en mm et émettre le signal."""
        label_points = self._selector.get_points()
        if len(label_points) < 2:
            return

        # Convertir chaque point label → mm
        points_mm = []
        for pt in label_points:
            coords = self._point_to_mm(pt)
            if coords is not None:
                points_mm.append(coords)

        if len(points_mm) < 2:
            self._status_label.setText(
                "Impossible de convertir le trace en mm — "
                "vérifier que les marqueurs ArUco sont visibles."
            )
            return

        quantity = self._slider.value() * 0.01
        self.zone_configured.emit(points_mm, quantity)

    # ------------------------------------------------------------------ affichage

    def _display_image(self, frame: np.ndarray) -> None:
        """Afficher l'image dans le LineSelector."""
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
