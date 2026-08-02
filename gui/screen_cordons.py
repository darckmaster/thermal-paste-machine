# Écran « Cordons » — lot C2
#
# Deuxième étape du processus multi-zones. L'opérateur choisit une zone parmi celles que
# l'écran précédent a validées, l'IHM zoome dessus, il y trace ses cordons, puis revient
# à la vue d'ensemble où les cordons apparaissent sur TOUTES les zones.
#
# Un seul écran, deux modes — « plateau » (vue d'ensemble) et « zone » (zoom et tracé) —
# parce que l'aller-retour entre les deux est le geste central de cette étape : en faire
# deux écrans de la pile obligerait à recopier l'état de l'un à l'autre à chaque bascule.
#
# Les cordons sont mémorisés en mm RELATIFS à la zone. C'est ce qui permet de les
# reporter sur les autres zones sans rien recalculer, et c'est le format attendu par
# modules/preparation.py pour l'enregistrement (lot C3).

import cv2
import numpy as np
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QStackedLayout
)
from PyQt5.QtCore import Qt, QPoint, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QBrush, QColor

from modules.vision import VisionProcessor


# Résolution du zoom sur une zone. 8 px/mm donne environ 1 mm de précision de clic sur
# l'écran tactile sans alourdir l'affichage.
ZOOM_PX_PER_MM = 8.0

# Distance maximale, en pixels d'affichage, pour qu'un clic sélectionne un cordon
# existant. Assez large pour être atteignable au doigt, assez étroite pour ne pas
# capturer un clic destiné à démarrer un nouveau tracé.
_TOLERANCE_SELECTION_PX = 12.0

# Couleurs BGR pour le rendu de la vue d'ensemble (convention OpenCV)
_VERT = (60, 200, 60)
_ORANGE_BGR = (0, 160, 255)
_BLANC = (255, 255, 255)


def _label_vers_image(label: QLabel, image: np.ndarray, x: float, y: float) -> tuple:
    """Convertit des coordonnées du widget → pixels de l'image affichée.

    Qt affiche le pixmap centré et mis à l'échelle (KeepAspectRatio) : il faut donc
    retirer les marges de centrage puis diviser par le facteur d'échelle. Sans cette
    conversion, un clic tomberait à côté dès que le widget n'a pas exactement les
    proportions de l'image.
    """
    hauteur_img, largeur_img = image.shape[:2]
    ratio = min(label.width() / largeur_img, label.height() / hauteur_img)

    marge_x = (label.width() - largeur_img * ratio) / 2
    marge_y = (label.height() - hauteur_img * ratio) / 2

    return ((x - marge_x) / ratio, (y - marge_y) / ratio)


def _image_vers_label(label: QLabel, image: np.ndarray, x: float, y: float) -> tuple:
    """Conversion inverse de _label_vers_image, pour dessiner aux bonnes coordonnées."""
    hauteur_img, largeur_img = image.shape[:2]
    ratio = min(label.width() / largeur_img, label.height() / hauteur_img)

    marge_x = (label.width() - largeur_img * ratio) / 2
    marge_y = (label.height() - hauteur_img * ratio) / 2

    return (x * ratio + marge_x, y * ratio + marge_y)


def _distance_point_segment(p: tuple, a: tuple, b: tuple) -> float:
    """Distance d'un point au segment [a, b] — et non à la droite qui le porte.

    Nécessaire pour sélectionner un cordon en cliquant dessus : avec la distance à la
    droite, un clic loin au-delà d'une extrémité sélectionnerait quand même le segment.
    """
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    longueur_carree = dx * dx + dy * dy

    if longueur_carree == 0:
        # Segment dégénéré (deux points confondus) : la distance est celle au point
        return ((p[0] - ax) ** 2 + (p[1] - ay) ** 2) ** 0.5

    # Position du projeté sur le segment, bornée à [0, 1] pour rester ENTRE a et b
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / longueur_carree))
    proj_x, proj_y = ax + t * dx, ay + t * dy

    return ((p[0] - proj_x) ** 2 + (p[1] - proj_y) ** 2) ** 0.5


# ===========================================================================
# Vue d'ensemble — choix de la zone
# ===========================================================================

class PlateauView(QLabel):
    """La photo du plateau, avec ses zones cliquables et les cordons reportés."""

    zone_clicked = pyqtSignal(object)   # DepositZone sur laquelle on a cliqué

    def __init__(self) -> None:
        super().__init__()
        self._image: np.ndarray | None = None   # image annotée affichée
        self._zones: list = []
        self._homography = None
        self._vision = VisionProcessor()
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

    def set_plateau(self, image, zones: list, homography, cordons: list) -> None:
        """Recalcule le rendu : contours des zones + cordons reportés sur chacune."""
        self._zones = zones
        self._homography = homography
        self._image = self._rendre(image, cordons)
        self._rafraichir()

    def _rendre(self, image: np.ndarray, cordons: list) -> np.ndarray:
        """Dessine les zones et les cordons sur une copie de la photo."""
        apercu = image.copy()

        for zone in self._zones:
            coins_px = self._vision.mm_to_pixels(list(zone.corners_mm), self._homography)
            cv2.polylines(apercu, [np.array(coins_px, dtype=np.int32)],
                          isClosed=True, color=_VERT, thickness=3)

            x, y = int(coins_px[0][0]), int(coins_px[0][1])
            etiquette = f"{zone.id_top_left}/{zone.id_bottom_right}"
            cv2.putText(apercu, etiquette, (x + 6, y - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, _BLANC, 4)
            cv2.putText(apercu, etiquette, (x + 6, y - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, _VERT, 2)

            # Les mêmes cordons, replacés dans le repère de CHAQUE zone : c'est ici que
            # se voit concrètement « tracé une fois, appliqué partout »
            for cordon in cordons:
                if len(cordon) < 2:
                    continue
                points_plateau = [zone.to_plateau_mm(p) for p in cordon]
                points_px = self._vision.mm_to_pixels(points_plateau, self._homography)
                cv2.polylines(apercu, [np.array(points_px, dtype=np.int32)],
                              isClosed=False, color=_ORANGE_BGR, thickness=3)

        return apercu

    def mousePressEvent(self, event) -> None:
        """Sélectionner la zone sous le clic, s'il y en a une."""
        if self._image is None or event.button() != Qt.LeftButton:
            return

        px, py = _label_vers_image(self, self._image, event.pos().x(), event.pos().y())
        x_mm, y_mm = self._vision.pixel_to_mm(px, py, self._homography)

        for zone in self._zones:
            # Ramener le point dans le repère de la zone : il est à l'intérieur si ses
            # deux coordonnées tombent entre 0 et les dimensions du produit. Cette
            # méthode fonctionne telle quelle sur une zone inclinée, là où une
            # comparaison de bornes en coordonnées plateau échouerait.
            zx, zy = zone.to_zone_mm((x_mm, y_mm))
            largeur, hauteur = zone.size_mm
            if 0 <= zx <= largeur and 0 <= zy <= hauteur:
                self.zone_clicked.emit(zone)
                return

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._rafraichir()

    def _rafraichir(self) -> None:
        if self._image is None:
            return
        rgb = cv2.cvtColor(self._image, cv2.COLOR_BGR2RGB)
        h, w, canaux = rgb.shape
        qimage = QImage(rgb.data, w, h, canaux * w, QImage.Format_RGB888)
        self.setPixmap(QPixmap.fromImage(qimage).scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))


# ===========================================================================
# Zoom sur une zone — tracé des cordons
# ===========================================================================

class CordonEditor(QLabel):
    """La zone redressée, sur laquelle l'opérateur trace ses cordons.

    Règle d'interaction, à connaître pour lire le code :
      - un tracé EST en cours → chaque clic ajoute un point, le double-clic le termine ;
      - aucun tracé en cours → un clic près d'un cordon existant le sélectionne, un clic
        ailleurs démarre un nouveau tracé.

    Les points sont mémorisés en mm relatifs à la zone. L'image affichée étant redressée
    à échelle fixe, la conversion pixel → mm est une simple division.
    """

    cordons_modified = pyqtSignal()   # le jeu de cordons a changé (pour l'autosave, lot C3)
    selection_changed = pyqtSignal()  # la sélection a changé (état des boutons)

    def __init__(self) -> None:
        super().__init__()
        self._image: np.ndarray | None = None
        # Cordons terminés, chacun une liste de (x_mm, y_mm) relatifs à la zone
        self._cordons: list = []
        # Tracé en cours — volontairement à part : il ne doit ni être enregistré par
        # l'autosave, ni compter comme un cordon tant qu'il n'est pas clos
        self._en_cours: list = []
        self._selection: int | None = None
        # Position du curseur en mm, pour le trait élastique. None au doigt : un écran
        # tactile n'a pas de survol, donc pas de position entre deux appuis.
        self._curseur_mm: tuple | None = None

        # Undo/redo de profondeur 1 : une seule action mémorisée de chaque côté
        self._derniere_action: dict | None = None
        self._action_refaisable: dict | None = None

        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        # Nécessaire pour recevoir les mouvements de souris sans bouton enfoncé
        self.setMouseTracking(True)

    # ------------------------------------------------------------------ état

    def set_zone_image(self, image: np.ndarray, cordons: list) -> None:
        """Charge l'image redressée de la zone et les cordons déjà tracés."""
        self._image = image
        self._cordons = [list(c) for c in cordons]
        self._en_cours = []
        self._selection = None
        self._derniere_action = None
        self._action_refaisable = None
        self._rafraichir()

    @property
    def cordons(self) -> list:
        """Les cordons TERMINÉS uniquement — le tracé en cours en est exclu."""
        return [list(c) for c in self._cordons]

    @property
    def a_un_trace_en_cours(self) -> bool:
        return bool(self._en_cours)

    @property
    def selection(self) -> int | None:
        return self._selection

    def peut_annuler(self) -> bool:
        return self._derniere_action is not None

    def peut_refaire(self) -> bool:
        return self._action_refaisable is not None

    # ------------------------------------------------------------------ actions

    def _enregistrer_action(self, action: dict) -> None:
        """Mémorise l'action annulable et invalide le « refaire » disponible.

        Toute nouvelle action rend caduque la branche qu'on aurait pu refaire : c'est le
        comportement attendu de n'importe quel éditeur.
        """
        self._derniere_action = action
        self._action_refaisable = None

    def annuler(self) -> None:
        """Annule la dernière action. Profondeur 1 : une seule, pas d'historique."""
        action = self._derniere_action
        if action is None:
            return

        if action["type"] == "point":
            self._en_cours.pop()
        elif action["type"] == "cloture":
            # Rouvrir le cordon : il redevient le tracé en cours
            self._en_cours = self._cordons.pop()
        elif action["type"] == "suppression":
            self._cordons.insert(action["index"], action["points"])

        self._derniere_action = None
        self._action_refaisable = action
        self._selection = None
        self._notifier()

    def refaire(self) -> None:
        """Rejoue l'action annulée."""
        action = self._action_refaisable
        if action is None:
            return

        if action["type"] == "point":
            self._en_cours.append(action["point"])
        elif action["type"] == "cloture":
            self._cordons.append(self._en_cours)
            self._en_cours = []
        elif action["type"] == "suppression":
            self._cordons.pop(action["index"])

        self._action_refaisable = None
        self._derniere_action = action
        self._selection = None
        self._notifier()

    def supprimer_selection(self) -> None:
        """Supprime le cordon sélectionné."""
        if self._selection is None:
            return

        index = self._selection
        points = self._cordons.pop(index)
        self._enregistrer_action({"type": "suppression", "index": index, "points": points})
        self._selection = None
        self._notifier()

    def _cloturer(self) -> None:
        """Termine le tracé en cours et le range parmi les cordons.

        Un tracé de moins de 2 points est abandonné : il n'a aucun segment, donc rien à
        déposer. On ne l'enregistre pas comme action annulable, il n'a jamais existé.
        """
        if len(self._en_cours) < 2:
            self._en_cours = []
            self._rafraichir()
            return

        self._cordons.append(self._en_cours)
        self._en_cours = []
        self._enregistrer_action({"type": "cloture"})
        self._notifier()

    def _notifier(self) -> None:
        self._rafraichir()
        self.cordons_modified.emit()
        self.selection_changed.emit()

    # ------------------------------------------------------------------ souris

    def _position_mm(self, pos: QPoint) -> tuple:
        """Convertit une position du widget en mm relatifs à la zone.

        L'image affichée est redressée à échelle fixe (ZOOM_PX_PER_MM) par
        VisionProcessor.warp_zone(). En X la conversion se réduit à une division ; en
        Y il faut RETOURNER, parce que l'origine du repère de la zone est son coin
        BAS-gauche (lot C2bis) alors que la ligne 0 de l'image est son coin haut.

        C'est la réciproque exacte de _mm_vers_label() : les deux doivent être
        modifiées ensemble, sans quoi les cordons s'afficheraient ailleurs qu'où on
        les a posés.
        """
        px, py = _label_vers_image(self, self._image, pos.x(), pos.y())
        hauteur_px = self._image.shape[0]
        return (px / ZOOM_PX_PER_MM, (hauteur_px - py) / ZOOM_PX_PER_MM)

    def mousePressEvent(self, event) -> None:
        if self._image is None or event.button() != Qt.LeftButton:
            return

        point_mm = self._position_mm(event.pos())

        if self._en_cours:
            # Tracé en cours : le clic ajoute un point
            self._en_cours.append(point_mm)
            self._enregistrer_action({"type": "point", "point": point_mm})
            self._notifier()
            return

        # Aucun tracé en cours : sélectionner un cordon existant, ou en démarrer un
        index = self._cordon_sous_le_curseur(event.pos())
        if index is not None:
            self._selection = index
            self._rafraichir()
            self.selection_changed.emit()
            return

        self._selection = None
        self._en_cours = [point_mm]
        self._enregistrer_action({"type": "point", "point": point_mm})
        self._notifier()

    def mouseDoubleClickEvent(self, event) -> None:
        """Le double-clic pose le dernier point et clôt le tracé.

        Le point n'est ajouté que s'il n'est pas DÉJÀ le dernier. Cette précaution rend
        le comportement indépendant de la séquence d'événements de Qt : en usage réel, un
        mousePressEvent précède le double-clic et a donc déjà posé le point, alors que
        QTest.mouseDClick n'envoie que l'événement de double-clic. Sans ce garde-fou, le
        point serait dupliqué dans un cas et absent dans l'autre — et le test ne
        vérifierait pas ce que fait vraiment l'application.
        """
        if event.button() != Qt.LeftButton or self._image is None:
            return

        point_mm = self._position_mm(event.pos())
        if not self._en_cours or not self._memes_points(self._en_cours[-1], point_mm):
            self._en_cours.append(point_mm)

        self._cloturer()

    @staticmethod
    def _memes_points(a: tuple, b: tuple, tolerance_mm: float = 0.5) -> bool:
        """Deux positions désignent-elles le même point ?

        Tolérance et non égalité stricte : les coordonnées viennent d'une conversion
        depuis des pixels entiers, deux clics au même endroit peuvent différer d'un
        centième de millimètre.
        """
        return abs(a[0] - b[0]) <= tolerance_mm and abs(a[1] - b[1]) <= tolerance_mm

    def mouseMoveEvent(self, event) -> None:
        """Suit le curseur pour le trait élastique.

        Confort réservé à la souris : un écran tactile n'ayant pas de survol, le trait
        n'apparaîtra pas au doigt. Assumé — le tracé reste utilisable sans lui.
        """
        if self._image is None or not self._en_cours:
            return
        self._curseur_mm = self._position_mm(event.pos())
        self.update()

    def leaveEvent(self, event) -> None:
        """Curseur sorti du widget : plus de trait élastique à afficher."""
        self._curseur_mm = None
        self.update()

    def _cordon_sous_le_curseur(self, pos: QPoint) -> int | None:
        """Index du cordon situé sous la position donnée, ou None."""
        for index, cordon in enumerate(self._cordons):
            for i in range(1, len(cordon)):
                a = self._mm_vers_label(cordon[i - 1])
                b = self._mm_vers_label(cordon[i])
                if _distance_point_segment((pos.x(), pos.y()), a, b) <= _TOLERANCE_SELECTION_PX:
                    return index
        return None

    # ------------------------------------------------------------------ rendu

    def _mm_vers_label(self, point_mm: tuple) -> tuple:
        """mm relatifs à la zone → coordonnées du widget, pour le dessin.

        Réciproque de _position_mm() : même retournement de Y, dans l'autre sens.
        """
        hauteur_px = self._image.shape[0]
        return _image_vers_label(
            self, self._image,
            point_mm[0] * ZOOM_PX_PER_MM,
            hauteur_px - point_mm[1] * ZOOM_PX_PER_MM,
        )

    def _rafraichir(self) -> None:
        if self._image is None:
            return
        rgb = cv2.cvtColor(self._image, cv2.COLOR_BGR2RGB)
        h, w, canaux = rgb.shape
        qimage = QImage(rgb.data, w, h, canaux * w, QImage.Format_RGB888)
        self.setPixmap(QPixmap.fromImage(qimage).scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._rafraichir()

    def paintEvent(self, event) -> None:
        """Dessine les cordons par-dessus l'image de la zone."""
        super().paintEvent(event)
        if self._image is None:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Cordons terminés — le sélectionné ressort en jaune épais
        for index, cordon in enumerate(self._cordons):
            selectionne = (index == self._selection)
            couleur = QColor(255, 220, 0) if selectionne else QColor(255, 120, 0)
            painter.setPen(QPen(couleur, 5 if selectionne else 3,
                                Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            self._tracer_polyline(painter, cordon)

        # Tracé en cours — en vert, pour le distinguer des cordons acquis
        if self._en_cours:
            painter.setPen(QPen(QColor(0, 220, 100), 3,
                                Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            self._tracer_polyline(painter, self._en_cours)

            # Trait élastique : segment pointillé du dernier point vers le curseur
            if self._curseur_mm is not None:
                painter.setPen(QPen(QColor(0, 220, 100), 2, Qt.DashLine))
                dernier = self._mm_vers_label(self._en_cours[-1])
                curseur = self._mm_vers_label(self._curseur_mm)
                painter.drawLine(int(dernier[0]), int(dernier[1]),
                                 int(curseur[0]), int(curseur[1]))

            # Points du tracé en cours, pour viser précisément
            painter.setBrush(QBrush(QColor(0, 220, 100)))
            painter.setPen(QPen(QColor(0, 120, 50), 2))
            for point in self._en_cours:
                x, y = self._mm_vers_label(point)
                painter.drawEllipse(QPoint(int(x), int(y)), 6, 6)

        painter.end()

    def _tracer_polyline(self, painter: QPainter, points: list) -> None:
        for i in range(1, len(points)):
            a = self._mm_vers_label(points[i - 1])
            b = self._mm_vers_label(points[i])
            painter.drawLine(int(a[0]), int(a[1]), int(b[0]), int(b[1]))


# ===========================================================================
# L'écran
# ===========================================================================

class ScreenCordons(QWidget):
    """Écran 7 : choix d'une zone, tracé des cordons, report sur tout le plateau."""

    back_requested = pyqtSignal()
    # Émis à chaque modification du jeu de cordons — le lot C3 y branchera l'autosave
    cordons_modified = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._vision = VisionProcessor()
        self._product_name = ""
        self._image = None
        self._homography = None
        self._layout_plateau = None
        # Zone sur laquelle les cordons sont tracés — celle qui fera référence
        self._zone_reference = None
        self._setup_ui()

    # ------------------------------------------------------------------ interface

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        self._banner = QLabel("Cordons")
        self._banner.setProperty("role", "title")
        self._banner.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._banner)

        # Les deux modes se superposent dans une pile : basculer de l'un à l'autre ne
        # déplace rien à l'écran, seule la vue change
        self._vues = QStackedLayout()
        self._vue_plateau = PlateauView()
        self._vue_plateau.setProperty("role", "camera")
        self._vue_plateau.zone_clicked.connect(self._ouvrir_zone)
        self._editeur = CordonEditor()
        self._editeur.setProperty("role", "camera")
        self._editeur.cordons_modified.connect(self._on_cordons_modified)
        self._editeur.selection_changed.connect(self._maj_boutons)
        self._vues.addWidget(self._vue_plateau)   # index 0
        self._vues.addWidget(self._editeur)       # index 1
        layout.addLayout(self._vues, stretch=1)

        self._status = QLabel("")
        self._status.setProperty("role", "status")
        self._status.setAlignment(Qt.AlignCenter)
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        # Barre du mode « plateau »
        self._barre_plateau = QHBoxLayout()
        self._btn_back = QPushButton("Retour")
        self._btn_back.setProperty("role", "secondary")
        self._btn_back.clicked.connect(self.back_requested)
        self._btn_editer = QPushButton("Modifier les cordons")
        self._btn_editer.clicked.connect(self._rouvrir_zone_reference)
        self._barre_plateau.addWidget(self._btn_back)
        self._barre_plateau.addWidget(self._btn_editer, stretch=2)

        # Barre du mode « zone »
        self._barre_zone = QHBoxLayout()
        self._btn_annuler = QPushButton("Annuler")
        self._btn_annuler.setProperty("role", "secondary")
        self._btn_annuler.clicked.connect(self._on_annuler)
        self._btn_refaire = QPushButton("Refaire")
        self._btn_refaire.setProperty("role", "secondary")
        self._btn_refaire.clicked.connect(self._on_refaire)
        self._btn_supprimer = QPushButton("Supprimer")
        self._btn_supprimer.setProperty("role", "danger")
        self._btn_supprimer.clicked.connect(self._on_supprimer)
        self._btn_valider = QPushButton("Valider")
        self._btn_valider.setProperty("role", "success")
        self._btn_valider.clicked.connect(self._valider_trace)
        for bouton in (self._btn_annuler, self._btn_refaire,
                       self._btn_supprimer, self._btn_valider):
            self._barre_zone.addWidget(bouton)

        # Les deux barres cohabitent dans un conteneur ; on masque celle qui ne sert pas
        self._conteneur_plateau = QWidget()
        self._conteneur_plateau.setLayout(self._barre_plateau)
        self._conteneur_zone = QWidget()
        self._conteneur_zone.setLayout(self._barre_zone)
        layout.addWidget(self._conteneur_plateau)
        layout.addWidget(self._conteneur_zone)

    # ------------------------------------------------------------------ entrée

    def set_plateau(self, donnees: dict) -> None:
        """Reçoit le plateau validé par l'écran précédent et affiche la vue d'ensemble."""
        self._product_name = donnees["product_name"]
        self._image = donnees["image"]
        self._homography = donnees["homography"]
        self._layout_plateau = donnees["layout"]
        self._zone_reference = None
        self._editeur.set_zone_image(np.zeros((1, 1, 3), dtype=np.uint8), [])
        self._banner.setText(f"Cordons — {self._product_name}")
        self._afficher_plateau()

    @property
    def cordons(self) -> list:
        """Cordons terminés, en mm relatifs à la zone de référence."""
        return self._editeur.cordons

    @property
    def zone_reference(self):
        return self._zone_reference

    # ------------------------------------------------------------------ mode plateau

    def _afficher_plateau(self) -> None:
        """Bascule sur la vue d'ensemble, cordons reportés sur toutes les zones."""
        zones = self._layout_plateau.valid_zones
        self._vue_plateau.set_plateau(self._image, zones, self._homography, self.cordons)
        self._vues.setCurrentIndex(0)
        self._conteneur_plateau.setVisible(True)
        self._conteneur_zone.setVisible(False)

        nb = len(self.cordons)
        if nb == 0:
            self._status.setText(
                f"{len(zones)} zone(s) — appuyer sur une zone pour y tracer les cordons"
            )
        else:
            self._status.setText(
                f"{nb} cordon(s) appliqué(s) aux {len(zones)} zone(s) du plateau"
            )
        self._btn_editer.setEnabled(self._zone_reference is not None)

    def _rouvrir_zone_reference(self) -> None:
        """Retourne à la zone déjà utilisée, pour compléter ou corriger le tracé."""
        if self._zone_reference is not None:
            self._ouvrir_zone(self._zone_reference)

    # ------------------------------------------------------------------ mode zone

    def _ouvrir_zone(self, zone) -> None:
        """Zoome sur une zone et passe en mode tracé.

        La première zone ouverte devient la zone de RÉFÉRENCE : c'est dans son repère que
        les cordons sont mémorisés. En rouvrir une autre ensuite reviendrait à changer de
        repère et déplacerait les cordons déjà tracés — on garde donc la première.
        """
        if self._zone_reference is None:
            self._zone_reference = zone
        zone = self._zone_reference

        image_zone = self._vision.warp_zone(
            self._image, zone, self._homography, ZOOM_PX_PER_MM
        )
        self._editeur.set_zone_image(image_zone, self.cordons)

        self._vues.setCurrentIndex(1)
        self._conteneur_plateau.setVisible(False)
        self._conteneur_zone.setVisible(True)

        largeur, hauteur = zone.size_mm
        self._status.setText(
            f"Zone {zone.id_top_left}/{zone.id_bottom_right} — {largeur:.0f} × "
            f"{hauteur:.0f} mm · appuyer pour poser un point, double-appui pour terminer"
        )
        self._maj_boutons()

    def _valider_trace(self) -> None:
        """Termine le tracé et revient à la vue d'ensemble."""
        self._afficher_plateau()

    def _on_annuler(self) -> None:
        self._editeur.annuler()

    def _on_refaire(self) -> None:
        self._editeur.refaire()

    def _on_supprimer(self) -> None:
        self._editeur.supprimer_selection()

    def _on_cordons_modified(self) -> None:
        self._maj_boutons()
        self.cordons_modified.emit()

    def _maj_boutons(self) -> None:
        """Active ou non les boutons selon ce qui est réellement possible."""
        self._btn_annuler.setEnabled(self._editeur.peut_annuler())
        self._btn_refaire.setEnabled(self._editeur.peut_refaire())
        self._btn_supprimer.setEnabled(self._editeur.selection is not None)
        # Terminer un tracé en cours avant de valider éviterait de le perdre en silence
        self._btn_valider.setEnabled(not self._editeur.a_un_trace_en_cours)
