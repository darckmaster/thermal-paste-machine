# Écran « Créer un plateau » — lot C1
#
# Première étape du nouveau processus : l'opérateur nomme le produit, photographie le
# plateau, et le logiciel lui rend son diagnostic — quelles zones de dépose il a
# reconnues, et lesquelles présentent un défaut de montage.
#
# Cet écran ne trace rien : le tracé des cordons viendra au lot C2. Il s'arrête au
# moment où l'opérateur décide de continuer avec les zones saines, ou d'abandonner pour
# rectifier son plateau.

import cv2
import numpy as np
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QInputDialog, QLineEdit,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap

from modules.config import ARUCO_DICT_ID, ARUCO_MARKER_SIZE_MM
from modules.vision import (
    VisionProcessor,
    ANOMALIE_ANGLE,
    ANOMALIE_CONFLIT,
    ANOMALIE_DIAGONALE,
    ANOMALIE_FORMAT_INCONNU,
    ANOMALIE_INVERSEE,
)


# Couleurs de tracé, en BGR (convention OpenCV, pas RGB)
_VERT = (60, 200, 60)        # zone saine, exploitable
_ROUGE = (60, 60, 230)       # zone en anomalie
_ORANGE = (0, 160, 255)      # marqueur orphelin
_BLANC = (255, 255, 255)

# Libellés des anomalies affichés SUR la photo.
# Volontairement sans accents : cv2.putText n'utilise que les polices Hershey, qui ne
# connaissent que l'ASCII — un « é » y ressortirait en caractère parasite. Les messages
# de la barre de statut, eux, sont rendus par Qt et peuvent être accentués normalement.
_LIBELLES_IMAGE = {
    ANOMALIE_INVERSEE: "a l'envers",
    ANOMALIE_DIAGONALE: "format different",
    ANOMALIE_CONFLIT: "marqueurs ambigus",
    ANOMALIE_ANGLE: "trop inclinee",
    ANOMALIE_FORMAT_INCONNU: "format indeterminable",
}

# Nombre maximal de zones dont le défaut est détaillé dans la barre de statut. Au-delà,
# un simple décompte renvoie à l'image, où chaque zone porte son étiquette. Borne
# nécessaire : sur l'écran tactile 800×480, l'image ne dispose que d'environ 310 px de
# hauteur, qu'un message trop long réduirait encore.
_MAX_DEFAUTS_DETAILLES = 2

# Libellés accentués pour la barre de statut et les messages Qt
_LIBELLES_TEXTE = {
    ANOMALIE_INVERSEE: "montée à l'envers",
    ANOMALIE_DIAGONALE: "format différent des autres",
    ANOMALIE_CONFLIT: "marqueurs revendiqués par deux zones",
    ANOMALIE_ANGLE: "trop inclinée",
    ANOMALIE_FORMAT_INCONNU: "format du produit indéterminable",
}


class ScreenPlateau(QWidget):
    """Écran 6 : création d'un plateau — capture, détection des zones, diagnostic.

    Cycle :
        1. À l'ouverture, l'opérateur saisit le nom du produit
        2. Flux vidéo en direct
        3. « Capturer » → l'image est figée et analysée, les zones sont matérialisées
        4. « Continuer » → le plateau validé est transmis à l'étape de tracé (lot C2)
           « Reprendre » → nouvelle photo, par exemple après avoir rectifié le montage
    """

    # Retour à l'écran d'accueil
    back_requested = pyqtSignal()

    # Plateau validé par l'opérateur — transporte (nom_produit, image, homographie, layout).
    # 'object' car PyQt5 ne connaît ni numpy ni nos classes métier.
    plateau_validated = pyqtSignal(object)

    def __init__(self) -> None:
        super().__init__()
        self._camera = None
        self._vision = VisionProcessor(ARUCO_DICT_ID, ARUCO_MARKER_SIZE_MM)

        # Nom du produit, saisi à l'ouverture de l'écran
        self._product_name: str = ""
        # Photo figée au moment du clic « Capturer » — None tant qu'on est en direct
        self._captured_image: np.ndarray | None = None
        # Résultats de la dernière analyse
        self._homography: np.ndarray | None = None
        self._layout = None

        # Timer d'aperçu — 10 fps, suffisant pour cadrer sans charger le RPi
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_frame)

        self._setup_ui()

    def set_camera(self, camera) -> None:
        """Reçoit la caméra partagée, créée et possédée par MainApp."""
        self._camera = camera

    # ------------------------------------------------------------------ interface

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Bandeau produit — reste visible en permanence pour qu'on sache toujours sur
        # quoi on travaille, y compris après plusieurs allers-retours entre écrans
        self._banner = QLabel("Plateau : (produit non defini)")
        self._banner.setProperty("role", "title")
        self._banner.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._banner)

        self._image_label = QLabel("Demarrage camera...")
        self._image_label.setProperty("role", "camera")
        self._image_label.setAlignment(Qt.AlignCenter)
        # Ignored : le label occupe l'espace que lui donne le layout sans grandir avec
        # son contenu — sinon chaque nouveau pixmap agrandirait la fenêtre
        self._image_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        layout.addWidget(self._image_label, stretch=1)

        self._status_label = QLabel("")
        self._status_label.setProperty("role", "status")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self._btn_back = QPushButton("Retour")
        self._btn_back.setProperty("role", "secondary")
        self._btn_back.clicked.connect(self.back_requested)

        self._btn_capture = QPushButton("Capturer")
        self._btn_capture.setEnabled(False)  # activé quand la caméra est prête
        self._btn_capture.clicked.connect(self._on_capture)

        self._btn_retake = QPushButton("Reprendre")
        self._btn_retake.setProperty("role", "secondary")
        self._btn_retake.setEnabled(False)
        self._btn_retake.clicked.connect(self._on_retake)

        self._btn_continue = QPushButton("Continuer")
        self._btn_continue.setProperty("role", "success")
        self._btn_continue.setEnabled(False)
        self._btn_continue.clicked.connect(self._on_continue)

        btn_layout.addWidget(self._btn_back)
        btn_layout.addWidget(self._btn_capture)
        btn_layout.addWidget(self._btn_retake)
        btn_layout.addWidget(self._btn_continue, stretch=2)
        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------ nom du produit

    def ask_product_name(self, parent=None) -> bool:
        """Demande le nom du produit. Retourne False si l'opérateur annule.

        Le nom sert à deux choses : il nomme le fichier de préparation, et il reste
        affiché en permanence dans le bandeau.

        Méthode publique et non appelée depuis __init__ : une boîte de dialogue modale
        au moment de la construction de l'écran bloquerait le démarrage de
        l'application, puisque tous les écrans sont créés d'un coup par MainApp.
        """
        # QInputDialog.getText() se dimensionne sur son contenu, ce qui donne une boîte
        # minuscule au titre tronqué — acceptable à la souris, inutilisable au doigt sur
        # l'écran 7 pouces. On construit donc le dialogue pour pouvoir l'agrandir.
        dialogue = QInputDialog(parent or self)
        dialogue.setWindowTitle("Nouveau plateau")
        dialogue.setLabelText("Référence du produit :")
        dialogue.setTextValue(self._product_name)
        dialogue.setInputMode(QInputDialog.TextInput)
        dialogue.setMinimumWidth(480)
        # Les boutons héritent de la feuille de style globale (hauteur mini 55 px), ce
        # qui suffit à en faire des cibles tactiles correctes

        if dialogue.exec_() != QInputDialog.Accepted:
            return False

        nom = dialogue.textValue().strip()
        if not nom:
            return False

        self.set_product_name(nom)
        return True

    def set_product_name(self, nom: str) -> None:
        """Fixe le nom du produit et met à jour le bandeau.

        Séparée de ask_product_name pour que les tests automatiques puissent définir un
        nom sans avoir à piloter une boîte de dialogue modale.
        """
        self._product_name = nom
        self._banner.setText(f"Plateau : {nom}")

    @property
    def product_name(self) -> str:
        return self._product_name

    # ------------------------------------------------------------------ caméra

    def start_camera(self) -> None:
        """Reprendre l'aperçu vidéo en direct."""
        self._captured_image = None
        self._layout = None
        self._btn_retake.setEnabled(False)
        self._btn_continue.setEnabled(False)

        if self._camera is None:
            self._image_label.setText("Camera non disponible\n\nVerifier le branchement USB")
            self._status_label.setText("Erreur caméra")
            self._btn_capture.setEnabled(False)
            return

        self._btn_capture.setEnabled(True)
        self._status_label.setText(
            "Cadrer le plateau entier, puis appuyer sur Capturer"
        )
        self._timer.start(100)

    def stop_camera(self) -> None:
        """Arrêter l'aperçu — sans libérer la caméra, qui est partagée."""
        self._timer.stop()

    def _update_frame(self) -> None:
        """Aperçu en direct, avec les marqueurs détectés en surimpression.

        L'overlay n'est pas décoratif : il permet à l'opérateur de vérifier son cadrage
        AVANT de déclencher, plutôt que de découvrir après coup qu'un marqueur manque.
        """
        if self._camera is None:
            return
        try:
            frame = self._camera.capture()
        except RuntimeError:
            self._timer.stop()
            self._image_label.setText("Camera deconnectee — rebrancher et relancer")
            self._btn_capture.setEnabled(False)
            return

        marqueurs = self._vision.detect_markers(frame)
        apercu = frame.copy()
        if marqueurs:
            coins = [c.reshape(1, 4, 2).astype(np.float32) for c in marqueurs.values()]
            ids = np.array([[mid] for mid in marqueurs.keys()])
            cv2.aruco.drawDetectedMarkers(apercu, coins, ids)

        self._status_label.setText(
            f"Marqueurs visibles : {sorted(marqueurs) if marqueurs else 'aucun'}"
        )
        self._display_image(apercu)

    # ------------------------------------------------------------------ analyse

    def _on_capture(self) -> None:
        """Figer l'image et lancer l'analyse du plateau."""
        if self._camera is None:
            return

        self._timer.stop()
        self._captured_image = self._camera.capture()
        self._btn_capture.setEnabled(False)
        self._btn_retake.setEnabled(True)

        self.analyser(self._captured_image)

    def analyser(self, image: np.ndarray) -> None:
        """Détecte les zones sur une photo et affiche le diagnostic.

        Méthode publique : les tests automatiques l'appellent directement avec une image
        de synthèse, sans passer par la caméra.
        """
        marqueurs = self._vision.detect_markers(image)
        ids_plateau = {0, 1, 2, 3} & marqueurs.keys()

        # Sans au moins 2 coins de plateau, aucune conversion pixels → mm n'est possible :
        # on ne peut donc rien dire des zones, même si leurs marqueurs sont bien vus
        if len(ids_plateau) < 4 and len(ids_plateau) >= 2:
            self._homography = self._vision.compute_homography_approx(marqueurs)
            precision_reduite = True
        elif len(ids_plateau) == 4:
            self._homography = self._vision.compute_homography(marqueurs)
            precision_reduite = False
        else:
            self._homography = None
            self._layout = None
            self._btn_continue.setEnabled(False)
            self._status_label.setText(
                f"Marqueurs du plateau insuffisants ({len(ids_plateau)}/4 détectés, "
                f"2 minimum) — impossible de situer les zones. Reprendre une photo."
            )
            self._display_image(image)
            return

        self._layout = self._vision.detect_deposit_zones(marqueurs, self._homography)

        apercu = self._dessiner_diagnostic(image, marqueurs)
        self._display_image(apercu)
        self._status_label.setText(self._texte_diagnostic(precision_reduite))

        # « Continuer » n'a de sens que s'il reste au moins une zone exploitable
        self._btn_continue.setEnabled(bool(self._layout.valid_zones))
        self._btn_continue.setText(
            f"Continuer ({len(self._layout.valid_zones)} zones)"
            if self._layout.valid_zones else "Continuer"
        )

    def _dessiner_diagnostic(self, image: np.ndarray, marqueurs: dict) -> np.ndarray:
        """Matérialise le diagnostic sur la photo : contours des zones et défauts.

        Le rendu se fait sur une COPIE : l'image d'origine doit rester intacte, c'est
        elle qui sera transmise à l'étape de tracé puis au rapport.
        """
        apercu = image.copy()

        for zone in self._layout.zones:
            # Les coins sont connus en mm : les reprojeter en pixels pour les dessiner
            coins_px = self._vision.mm_to_pixels(list(zone.corners_mm), self._homography)
            polygone = np.array(coins_px, dtype=np.int32)

            couleur = _VERT if zone.is_valid else _ROUGE
            cv2.polylines(apercu, [polygone], isClosed=True, color=couleur, thickness=3)

            # Étiquette au coin haut-gauche de la zone, décalée pour ne pas recouvrir
            # le marqueur lui-même
            x, y = int(coins_px[0][0]), int(coins_px[0][1])
            libelle = f"{zone.id_top_left}/{zone.id_bottom_right}"
            if not zone.is_valid:
                defauts = ", ".join(
                    _LIBELLES_IMAGE.get(a, a) for a in zone.anomalies
                )
                libelle = f"{libelle} : {defauts}"
            self._texte_lisible(apercu, libelle, (x + 6, y - 8), couleur)

        # Marqueurs orphelins : entourés en orange, ils signalent un partenaire manquant
        # ou une paire écartée pour cause de format aberrant
        for marker_id in self._layout.unpaired_ids:
            if marker_id not in marqueurs:
                continue
            cx, cy = marqueurs[marker_id].mean(axis=0)
            cv2.circle(apercu, (int(cx), int(cy)), 28, _ORANGE, 3)
            self._texte_lisible(
                apercu, f"{marker_id} orphelin", (int(cx) + 32, int(cy)), _ORANGE
            )

        return apercu

    @staticmethod
    def _texte_lisible(image, texte: str, position: tuple, couleur: tuple) -> None:
        """Écrit un texte lisible quel que soit le fond de la photo.

        Le texte est tracé deux fois : une passe épaisse en blanc, puis le texte en
        couleur par-dessus. Ce liseré garantit la lisibilité sur un plateau clair comme
        sur une pièce sombre, sans avoir à choisir une couleur de compromis.
        """
        cv2.putText(image, texte, position, cv2.FONT_HERSHEY_SIMPLEX, 0.6, _BLANC, 4)
        cv2.putText(image, texte, position, cv2.FONT_HERSHEY_SIMPLEX, 0.6, couleur, 2)

    def _texte_diagnostic(self, precision_reduite: bool) -> str:
        """Compose le message de la barre de statut à partir du résultat d'analyse."""
        parties = []

        if precision_reduite:
            parties.append(
                "⚠ Précision réduite (2-3 marqueurs plateau, pas de correction de "
                "perspective)"
            )

        valides = len(self._layout.valid_zones)
        total = len(self._layout.zones)

        if total == 0:
            parties.append("Aucune zone de dépose détectée")
        else:
            parties.append(f"{valides} zone(s) exploitable(s) sur {total} détectée(s)")

        # Détailler les défauts, mais SANS les énumérer tous : sur un plateau de 6 zones
        # dont plusieurs en anomalie, la barre de statut grandirait au point de manger la
        # place de l'image (mesuré sur 800×480, la résolution de l'écran tactile). Le
        # détail complet reste lisible AU BON ENDROIT — chaque rectangle porte son
        # étiquette sur la photo. La barre de statut, elle, reste un résumé.
        en_defaut = [z for z in self._layout.zones if not z.is_valid]
        for zone in en_defaut[:_MAX_DEFAUTS_DETAILLES]:
            defauts = ", ".join(_LIBELLES_TEXTE.get(a, a) for a in zone.anomalies)
            parties.append(f"Zone {zone.id_top_left}/{zone.id_bottom_right} : {defauts}")

        restantes = len(en_defaut) - _MAX_DEFAUTS_DETAILLES
        if restantes > 0:
            parties.append(f"et {restantes} autre(s) zone(s) en défaut — voir l'image")

        if self._layout.unpaired_ids:
            parties.append(
                f"Marqueurs sans zone : {self._layout.unpaired_ids} — partenaire absent "
                f"ou format incohérent"
            )

        if self._layout.product_size_mm is not None:
            largeur, hauteur = self._layout.product_size_mm
            parties.append(f"Format déduit : {largeur:.0f} × {hauteur:.0f} mm")

        return " · ".join(parties)

    # ------------------------------------------------------------------ actions

    def _on_retake(self) -> None:
        """Reprendre une photo — typiquement après avoir rectifié le montage."""
        self.start_camera()

    def _on_continue(self) -> None:
        """Valider le plateau et transmettre le résultat à l'étape de tracé.

        Seules les zones saines seront exploitables ; les zones en anomalie restent dans
        le layout pour rester affichées, mais l'opérateur a été averti et a choisi de
        continuer sans elles.
        """
        if self._layout is None or not self._layout.valid_zones:
            return

        self.plateau_validated.emit({
            "product_name": self._product_name,
            "image": self._captured_image,
            "homography": self._homography,
            "layout": self._layout,
        })

    # ------------------------------------------------------------------ affichage

    def _display_image(self, frame: np.ndarray) -> None:
        """Convertir une image OpenCV (BGR numpy) en QPixmap et l'afficher."""
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, channels = rgb.shape
        qimage = QImage(rgb.data, w, h, channels * w, QImage.Format_RGB888)
        self._image_label.setPixmap(
            QPixmap.fromImage(qimage).scaled(
                self._image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        )
