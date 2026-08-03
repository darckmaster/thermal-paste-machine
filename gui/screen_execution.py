# Écran d'exécution multi-zones — lot D2
#
# C'est le nouveau point d'entrée de la dépose : un seul bouton depuis l'accueil, et
# l'opérateur est guidé jusqu'au bout du cycle. Il remplacera à terme le trio historique
# capture → tracé → dépose (retrait prévu au sous-lot D5, une fois celui-ci validé sur
# machine — d'ici là, l'ancien reste le seul chemin éprouvé jusqu'à la dépose réelle).
#
# Le cycle, tel que l'étudiant l'a spécifié le 2026-08-03 :
#
#   1. bouton « Lancer une dépose » sur l'accueil
#   2. homing
#   3. mise en position de prise de vue
#   4. choix du fichier de préparation
#   5. acquisition, puis affichage des zones valides et invalides
#   6. sélection des zones où il y a un produit (clic = sélectionne, re-clic = enlève)
#   7. acquitter, ou annuler et revenir à l'accueil
#   8. modale de confirmation (annuler = revenir à l'étape 6, pas à l'accueil)
#   9. nouveau homing, puis la dépose
#  10. modale de progression : avancement, zones faites, temps, pause, arrêt
#  11. bilan de fin  (la photo de fin et le rapport PDF arrivent au sous-lot D3)
#  12. acquittement, homing, retour à l'accueil
#
# Pourquoi tout ce qui touche la machine passe par un thread : une commande G-code bloque
# jusqu'au « ok » de Marlin, et un homing prend de 30 à 60 secondes. Exécutées dans le
# thread Qt, elles gèleraient l'interface — et donc le bouton d'arrêt, ce qui est un
# problème de sécurité et pas de confort.

import time

import cv2
import numpy as np
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QSizePolicy,
    QMessageBox,
)
from PyQt5.QtCore import Qt, QThread, QObject, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QImage, QPixmap

from gui.dialogs import (
    ConfirmDepositDialog,
    DepositProgressDialog,
    DepositSummaryDialog,
    PreparationPickerDialog,
)
from gui.screen_cordons import _label_vers_image
from gui.workers import PhotoPositionWorker
from modules.config import (
    DISPENSE_Z_HEIGHT_MM, MACHINE_Z_TRAVEL_MM,
    PHOTO_POSITION_X, PHOTO_POSITION_Y, PHOTO_POSITION_Z,
    MACHINE_TRAVEL_X_MAX_MM, MACHINE_TRAVEL_Y_MAX_MM, MACHINE_TRAVEL_Z_MAX_MM,
)
from modules.path_planner import (
    PathPlanner, check_machine_limits, format_limit_violations,
    sort_zones_for_deposit,
)
from modules.preparation import load_preparation
from modules.vision import VisionProcessor

# Couleurs BGR (convention OpenCV) des trois états d'une zone à l'écran.
# Trois états franchement distincts : l'opérateur doit pouvoir lire son plateau d'un
# coup d'œil, à bout de bras, sur un écran de 7 pouces.
_VERT = (60, 200, 60)        # sélectionnée — un produit s'y trouve
_GRIS = (170, 170, 170)      # valide mais non sélectionnée
_ROUGE = (60, 60, 220)       # invalide — non sélectionnable
_ORANGE = (0, 160, 255)      # cordons reportés
_BLANC = (255, 255, 255)

# Écart toléré entre la taille d'une zone vue et la taille du produit enregistré, en mm.
# Au-delà, la zone est refusée : les cordons ont été tracés pour CE format-là.
_TOLERANCE_FORMAT_MM = 5.0


# ===========================================================================
# Vue de sélection — la photo du plateau, zones cliquables
# ===========================================================================

class PlateauSelectionView(QLabel):
    """La photo du plateau avec ses zones, dans trois états, et le clic qui bascule.

    Distincte de `PlateauView` (screen_cordons) qui, elle, montre toutes les zones du
    même vert et y reporte les cordons sans notion de sélection. Fusionner les deux
    obligerait chacune à porter les cas de l'autre pour un gain nul.

    Les cordons ne sont dessinés que dans les zones **sélectionnées** : c'est le retour
    visuel demandé — l'opérateur voit exactement ce qui va être déposé, et où.
    """

    zone_toggled = pyqtSignal(object)   # DepositZone cliquée (valide uniquement)

    def __init__(self) -> None:
        super().__init__()
        self._image_source: np.ndarray | None = None   # la photo brute
        self._image_rendue: np.ndarray | None = None   # la photo annotée affichée
        self._zones: list = []
        self._selection: set = set()      # IDs des zones sélectionnées
        self._cordons: list = []
        self._homography = None
        self._vision = VisionProcessor()
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

    def set_plateau(self, image: np.ndarray, zones: list, homography,
                    cordons: list) -> None:
        self._image_source = image
        self._zones = zones
        self._homography = homography
        self._cordons = cordons
        self._selection = set()
        self._rendre()

    def set_selection(self, ids_selectionnes: set) -> None:
        self._selection = set(ids_selectionnes)
        self._rendre()

    # ------------------------------------------------------------------ rendu

    def _rendre(self) -> None:
        if self._image_source is None:
            return
        apercu = self._image_source.copy()

        for zone in self._zones:
            selectionnee = zone.id_top_left in self._selection
            if not zone.is_valid:
                couleur = _ROUGE
            elif selectionnee:
                couleur = _VERT
            else:
                couleur = _GRIS

            coins_px = self._vision.mm_to_pixels(
                list(zone.corners_mm), self._homography
            )
            # Une zone sélectionnée est tracée plus épais : la couleur seule ne suffit
            # pas si l'écran est vu de biais, ou par quelqu'un qui distingue mal le vert
            epaisseur = 5 if selectionnee else 2
            cv2.polylines(apercu, [np.array(coins_px, dtype=np.int32)],
                          isClosed=True, color=couleur, thickness=epaisseur)

            x, y = int(coins_px[0][0]), int(coins_px[0][1])
            etiquette = str(zone.id_top_left)
            if not zone.is_valid:
                etiquette = f"{etiquette} : ecartee"
            self._texte_lisible(apercu, etiquette, (x + 6, y - 8), couleur)

            # Les cordons, uniquement là où ils seront réellement déposés
            if selectionnee:
                for cordon in self._cordons:
                    if not cordon.is_valid:
                        continue
                    points_plateau = [
                        zone.to_plateau_mm(p) for p in cordon.points_mm
                    ]
                    points_px = self._vision.mm_to_pixels(
                        points_plateau, self._homography
                    )
                    cv2.polylines(apercu, [np.array(points_px, dtype=np.int32)],
                                  isClosed=False, color=_ORANGE, thickness=3)

        self._image_rendue = apercu
        self._rafraichir()

    @staticmethod
    def _texte_lisible(image, texte: str, position: tuple, couleur: tuple) -> None:
        """Texte doublé d'un liseré blanc, lisible sur un fond clair comme sombre."""
        cv2.putText(image, texte, position, cv2.FONT_HERSHEY_SIMPLEX, 0.7, _BLANC, 4)
        cv2.putText(image, texte, position, cv2.FONT_HERSHEY_SIMPLEX, 0.7, couleur, 2)

    def _rafraichir(self) -> None:
        if self._image_rendue is None:
            return
        rgb = cv2.cvtColor(self._image_rendue, cv2.COLOR_BGR2RGB)
        h, w, canaux = rgb.shape
        qimage = QImage(rgb.data, w, h, canaux * w, QImage.Format_RGB888)
        self.setPixmap(QPixmap.fromImage(qimage).scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._rafraichir()

    # ------------------------------------------------------------------ clic

    def mousePressEvent(self, event) -> None:
        """Bascule la zone sous le clic — un clic sélectionne, un autre désélectionne."""
        if self._image_rendue is None or event.button() != Qt.LeftButton:
            return

        px, py = _label_vers_image(
            self, self._image_rendue, event.pos().x(), event.pos().y()
        )
        zone = self.zone_at_pixel(px, py)
        if zone is not None:
            self.zone_toggled.emit(zone)

    def zone_at_pixel(self, px: float, py: float):
        """La zone VALIDE contenant ce pixel, ou None.

        Méthode publique pour que les tests puissent simuler un clic sans dépendre de la
        géométrie du widget à l'écran, qui n'a rien à voir avec ce qu'on veut vérifier.

        Les zones invalides sont volontairement ignorées : elles restent visibles, en
        rouge et avec leur motif, mais ne peuvent pas être sélectionnées.
        """
        if self._homography is None:
            return None
        x_mm, y_mm = self._vision.pixel_to_mm(px, py, self._homography)
        for zone in self._zones:
            if not zone.is_valid:
                continue
            # Ramener le point dans le repère de la zone : il est dedans si ses deux
            # coordonnées tombent entre 0 et les dimensions du produit. Fonctionne tel
            # quel sur une zone inclinée, là où une comparaison de bornes en coordonnées
            # plateau échouerait.
            zx, zy = zone.to_zone_mm((x_mm, y_mm))
            largeur, hauteur = zone.size_mm
            if 0 <= zx <= largeur and 0 <= zy <= hauteur:
                return zone
        return None


# ===========================================================================
# Threads machine
# ===========================================================================

class DepositWorker(QObject):
    """Étape 9 : homing, puis exécution de la liste de steps du plateau.

    Sait se mettre en pause et s'arrêter. La pause se prend **entre deux steps** : une
    commande G-code déjà envoyée va au bout, et Marlin a de surcroît quelques mouvements
    d'avance dans sa file. L'arrêt n'est donc jamais instantané au millimètre près —
    décidé le 2026-08-03 : on assume que la pâte s'écoule un peu, et on n'en tient pas
    compte à la reprise.
    """

    progress = pyqtSignal(float, int)      # (fraction parcourue, zones terminées)
    state_changed = pyqtSignal(str)
    zone_done = pyqtSignal(int)            # ID de zone terminée
    finished = pyqtSignal()
    stopped = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, machine, steps: list, travel_speed: float,
                 extrusion_speed: float, z_safe: float = None) -> None:
        super().__init__()
        self._machine = machine
        self._steps = steps
        self._travel_speed = travel_speed
        self._extrusion_speed = extrusion_speed
        # Hauteur à laquelle se dégager juste après le homing, avant tout déplacement
        # horizontal. Par défaut, celle du premier step — c'est la hauteur à laquelle le
        # parcours commence, donc celle qui convient.
        self._z_safe = z_safe if z_safe is not None else (
            steps[0]["z"] if steps else None
        )
        self._should_stop = False
        self._paused = False

    # ------------------------------------------------------------------ commandes

    def request_stop(self) -> None:
        self._should_stop = True
        # Lever aussi la pause. Ce n'est PAS ce qui fait sortir de la boucle d'attente —
        # sa condition teste déjà `_should_stop`, et c'est elle le vrai mécanisme. C'est
        # une ceinture de sécurité pour un chemin où l'enjeu est qu'une machine s'arrête :
        # si quelqu'un simplifiait un jour cette condition en `while self._paused`, le
        # bouton d'arrêt cesserait de répondre pendant une pause. La redondance est
        # signalée ici pour qu'on ne la prenne pas pour le mécanisme principal.
        self._paused = False

    def set_paused(self, en_pause: bool) -> None:
        self._paused = en_pause

    # ------------------------------------------------------------------ exécution

    @pyqtSlot()
    def run(self) -> None:
        # Poids de chaque step = distance XY réellement parcourue. La progression suit
        # donc le CHEMIN et non le nombre de steps : un tracé de 80 mm et un déplacement
        # de 2 mm ne peuvent pas compter pareil, sinon la barre avance par à-coups et
        # ment sur le temps restant.
        poids = self._poids_des_steps()
        total = sum(poids) or 1.0
        parcouru = 0.0
        zones_terminees = 0
        zone_courante = None

        try:
            self.state_changed.emit("Connexion a la machine...")
            self._machine.connect()

            self.state_changed.emit("Homing en cours (30-60 s)...")
            self._machine.home()

            # ⚠️ Se dégager en Z AVANT le premier déplacement horizontal.
            # `move_to()` envoie `G1 X Y` puis `G1 Z` : sans cette montée préalable, le
            # premier step du parcours traverserait tout le plateau à la hauteur du
            # homing avant de monter. Constaté sur la machine le 2026-08-04 — la pointe
            # y passe très près du dessus des zones.
            if self._z_safe is not None:
                self.state_changed.emit("Degagement en Z...")
                self._machine.move_z(self._z_safe)
        except Exception as e:
            self.error_occurred.emit(f"Machine indisponible : {e}")
            self._deconnecter()
            return

        try:
            self.state_changed.emit("Depose en cours")
            for index, step in enumerate(self._steps):
                # Pause : on attend ici, entre deux steps, sans rien envoyer
                while self._paused and not self._should_stop:
                    time.sleep(0.1)

                if self._should_stop:
                    break

                # Changement de zone : celle qu'on quitte est terminée
                if zone_courante is not None and step.get("zone") != zone_courante:
                    zones_terminees += 1
                    self.zone_done.emit(zone_courante)
                zone_courante = step.get("zone")

                self._executer(step)

                parcouru += poids[index]
                self.progress.emit(parcouru / total, zones_terminees)

            # La dernière zone n'a pas de successeur pour la déclarer terminée :
            # elle ne l'est que si la boucle est allée jusqu'au bout.
            if not self._should_stop and zone_courante is not None:
                self.zone_done.emit(zone_courante)

        except Exception as e:
            self.error_occurred.emit(f"Erreur pendant la depose : {e}")
            self._deconnecter()
            return

        self._deconnecter()
        self.stopped.emit() if self._should_stop else self.finished.emit()

    def _poids_des_steps(self) -> list:
        """Distance XY parcourue par chaque step, dans l'ordre."""
        poids = []
        precedent = None
        for step in self._steps:
            if precedent is None:
                poids.append(0.0)
            else:
                poids.append(
                    ((step["x"] - precedent["x"]) ** 2
                     + (step["y"] - precedent["y"]) ** 2) ** 0.5
                )
            precedent = step
        return poids

    def _executer(self, step: dict) -> None:
        type_step = step["type"]
        if type_step == "travel":
            self._machine.move_to(step["x"], step["y"], step["z"])
        elif type_step == "dispense":
            self._machine.move_and_dispense(
                step["x"], step["y"], step["amount"], feedrate=self._travel_speed
            )
        elif type_step == "prime":
            # Amorçage : on pousse la pâte sans bouger, le temps qu'elle arrive au bout
            self._machine.dispense(step["amount"], feedrate=self._extrusion_speed)

    def _deconnecter(self) -> None:
        try:
            self._machine.disconnect()
        except Exception:
            pass   # une erreur de déconnexion ne doit pas masquer le résultat du cycle


# ===========================================================================
# L'écran
# ===========================================================================

class ScreenExecution(QWidget):
    """Le cycle de dépose complet, de l'accueil à l'accueil."""

    back_requested = pyqtSignal()      # retour à l'écran d'accueil

    def __init__(self) -> None:
        super().__init__()
        self._machine = None
        self._camera = None
        self._vision = VisionProcessor()

        self._preparation = None
        self._zones: list = []
        self._homography = None
        self._selection: set = set()
        self._motifs_refus: dict = {}   # id de zone → pourquoi elle est non sélectionnable

        # Deux paires thread/worker DISTINCTES, et non une paire réutilisée. Réaffecter
        # `self._thread` remplacerait la référence du premier QThread alors que son
        # `deleteLater()` n'a pas encore été traité : le ramasse-miettes de Python
        # détruirait l'objet pendant que le thread système tourne encore. Ce projet a
        # déjà connu ce défaut une fois, sur le worker de homing (2026-07-01).
        self._thread_prep: QThread | None = None
        self._worker_prep = None
        self._thread_depose: QThread | None = None
        self._worker_depose = None

        self._dialogue_progression = None
        self._depart = 0.0
        self._chrono = QTimer(self)
        self._chrono.setInterval(1000)
        self._chrono.timeout.connect(self._tick)
        self._zones_faites: list = []
        self._zones_prevues: list = []
        self._dry_run = True

        self._setup_ui()

    def set_machine(self, machine) -> None:
        self._machine = machine

    def set_camera(self, camera) -> None:
        self._camera = camera

    # ------------------------------------------------------------------ interface

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        self._titre = QLabel("Lancer une depose")
        self._titre.setProperty("role", "title")
        self._titre.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._titre)

        self._vue = PlateauSelectionView()
        self._vue.zone_toggled.connect(self._on_zone_toggled)
        layout.addWidget(self._vue, stretch=1)

        self._status = QLabel("")
        self._status.setProperty("role", "status")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        boutons = QHBoxLayout()
        boutons.setSpacing(8)

        self._btn_tout = QPushButton("Tout selectionner")
        self._btn_tout.setProperty("role", "secondary")
        self._btn_tout.clicked.connect(self._on_tout_selectionner)
        boutons.addWidget(self._btn_tout)

        self._btn_valider = QPushButton("Valider la selection")
        self._btn_valider.setProperty("role", "success")
        self._btn_valider.setEnabled(False)
        self._btn_valider.clicked.connect(self._on_valider)
        boutons.addWidget(self._btn_valider)

        self._btn_annuler = QPushButton("Annuler")
        self._btn_annuler.setProperty("role", "secondary")
        self._btn_annuler.clicked.connect(self.back_requested)
        boutons.addWidget(self._btn_annuler)

        layout.addLayout(boutons)

    def _activer_boutons_selection(self, actif: bool) -> None:
        self._btn_tout.setEnabled(actif)
        self._btn_valider.setEnabled(actif and bool(self._selection))

    # ------------------------------------------------------------------ étapes 2-3

    def start_cycle(self) -> None:
        """Point d'entrée : lance le homing et la mise en position de prise de vue."""
        self._preparation = None
        self._zones = []
        self._selection = set()
        self._zones_faites = []
        self._activer_boutons_selection(False)
        self._status.setText("Preparation de la machine...")

        if self._machine is None:
            self._echec("Aucune machine configuree.")
            return

        self._thread_prep = QThread()
        self._worker_prep = PhotoPositionWorker(
            self._machine, (PHOTO_POSITION_X, PHOTO_POSITION_Y, PHOTO_POSITION_Z)
        )
        self._worker_prep.moveToThread(self._thread_prep)
        self._thread_prep.started.connect(self._worker_prep.run)
        self._worker_prep.progress.connect(self._status.setText)
        self._worker_prep.error_occurred.connect(self._echec)
        self._worker_prep.finished.connect(self._marquer_prep_reussie)
        self._worker_prep.finished.connect(self._thread_prep.quit)
        self._worker_prep.error_occurred.connect(self._thread_prep.quit)
        # Brancher la suite du cycle sur la fin du THREAD et non sur celle du worker :
        # ce slot ouvre une fenêtre modale, donc une boucle d'évènements imbriquée qui
        # ne rendra la main qu'après la sélection des zones. Sur le signal du worker, le
        # `quit()` du thread attendrait tout ce temps derrière elle.
        #
        # Contrepartie : `finished` d'un QThread se déclenche aussi quand c'est une
        # ERREUR qui a demandé le `quit()`. D'où le drapeau — sans lui, une machine
        # injoignable enchaînerait quand même sur le choix du fichier.
        self._prep_reussie = False
        self._thread_prep.finished.connect(self._on_position_atteinte)
        self._thread_prep.start()

    @pyqtSlot()
    def _marquer_prep_reussie(self) -> None:
        self._prep_reussie = True

    @pyqtSlot()
    def _on_position_atteinte(self) -> None:
        """Étapes 4 et 5 : choisir le fichier, puis photographier et analyser."""
        if not self._prep_reussie:
            return   # une erreur machine a déjà été signalée et a ramené à l'accueil

        self._status.setText("Machine en position. Choisir la preparation a executer.")
        if not self._choisir_preparation():
            self.back_requested.emit()
            return
        self._capturer_et_analyser()

    def _choisir_preparation(self) -> bool:
        dialogue = PreparationPickerDialog(parent=self)
        if dialogue.exec_() != dialogue.Accepted:
            return False

        chemin = dialogue.selected_path
        if chemin is None:
            return False

        # Le chargement peut échouer sur un fichier tronqué ou d'un format futur. Le
        # dire et revenir à l'accueil vaut mieux que de partir avec une préparation à
        # moitié lue — ce sont des coordonnées de dépose.
        try:
            self._preparation = load_preparation(chemin)
        except (OSError, ValueError, KeyError) as e:
            self._avertir(f"Preparation illisible : {e}")
            return False

        if not [c for c in self._preparation.cordons if c.is_valid]:
            self._avertir(
                "Cette preparation ne contient aucun cordon tracable : il n'y a rien "
                "a deposer."
            )
            return False
        return True

    # ------------------------------------------------------------------ étape 5

    def _capturer_et_analyser(self) -> None:
        if self._camera is None:
            self._echec("Aucune camera disponible.")
            return
        try:
            image = self._camera.capture()
        except Exception as e:
            self._echec(f"Capture impossible : {e}")
            return
        self.analyser(image)

    def analyser(self, image: np.ndarray) -> None:
        """Détecte les zones sur une photo et prépare la sélection.

        Méthode publique : les tests l'appellent directement avec une image de synthèse,
        sans caméra ni machine.
        """
        marqueurs = self._vision.detect_markers(image)
        try:
            reference = self._vision.compute_plateau_reference(marqueurs)
        except ValueError:
            self._homography = None
            self._zones = []
            self._activer_boutons_selection(False)
            self._status.setText(
                "Marqueurs du plateau insuffisants (2 minimum) : impossible de situer "
                "les zones. Verifier le cadrage, puis relancer."
            )
            return

        self._homography = reference.homography
        layout = self._vision.detect_deposit_zones(marqueurs, self._homography)
        self._zones = layout.zones
        self._motifs_refus = self._controler_format(layout.zones)
        self._selection = set()

        self._vue.set_plateau(
            image, self._zones, self._homography, self._preparation.cordons
        )
        self._activer_boutons_selection(True)
        self._status.setText(self._texte_selection())

    def _controler_format(self, zones: list) -> dict:
        """Écarte les zones dont le format ne correspond pas au produit enregistré.

        La photo fait foi pour la GÉOMÉTRIE — le plateau a pu bouger ou être remonté
        depuis l'enregistrement, et c'est la position vue maintenant qui compte. Mais les
        cordons ont été tracés pour CE produit-là : sur une zone d'un autre format, ils
        déborderaient. Le contrôle porte donc sur la taille, pas sur la position.
        """
        reference = self._preparation.reference_zone if self._preparation else None
        if reference is None:
            return {}

        largeur_ref, hauteur_ref = reference.size_mm
        motifs = {}
        for zone in zones:
            if not zone.is_valid:
                continue
            ecart = max(abs(zone.size_mm[0] - largeur_ref),
                        abs(zone.size_mm[1] - hauteur_ref))
            if ecart > _TOLERANCE_FORMAT_MM:
                motifs[zone.id_top_left] = (
                    f"format {zone.size_mm[0]:.0f}x{zone.size_mm[1]:.0f} mm, "
                    f"attendu {largeur_ref:.0f}x{hauteur_ref:.0f} mm"
                )
                # Marquer la zone comme non sélectionnable en la sortant des valides :
                # l'anomalie est ajoutée à la zone elle-même pour que l'affichage la
                # montre en rouge, comme les autres défauts, sans cas particulier.
                zone.anomalies.append("format_incompatible")
        return motifs

    def _zones_selectionnables(self) -> list:
        return [z for z in self._zones if z.is_valid]

    def _texte_selection(self) -> str:
        selectionnables = self._zones_selectionnables()
        texte = (
            f"{len(selectionnables)} zone(s) exploitable(s) sur {len(self._zones)} "
            f"detectee(s). Toucher une zone pour indiquer qu'un produit s'y trouve, "
            f"la retoucher pour l'enlever."
        )
        if self._motifs_refus:
            details = " ; ".join(
                f"zone {zid} ({motif})" for zid, motif in self._motifs_refus.items()
            )
            texte += f"\nEcartees pour format incompatible : {details}."
        if self._selection:
            texte += f"\n{len(self._selection)} zone(s) selectionnee(s)."
        return texte

    # ------------------------------------------------------------------ étape 6

    def _on_zone_toggled(self, zone) -> None:
        if zone.id_top_left in self._selection:
            self._selection.discard(zone.id_top_left)
        else:
            self._selection.add(zone.id_top_left)
        self._vue.set_selection(self._selection)
        self._btn_valider.setEnabled(bool(self._selection))
        self._status.setText(self._texte_selection())

    def _on_tout_selectionner(self) -> None:
        """Raccourci : tout prendre, ou tout enlever si tout est déjà pris.

        La sélection reste vide par défaut — déposer sur une zone sans produit gaspille
        de la pâte et salit le plateau. Mais sur un plateau plein, six appuis pour dire
        « tout » serait une corvée : ce bouton est le compromis.
        """
        selectionnables = self._zones_selectionnables()
        if len(self._selection) == len(selectionnables):
            self._selection = set()
        else:
            self._selection = {z.id_top_left for z in selectionnables}
        self._vue.set_selection(self._selection)
        self._btn_valider.setEnabled(bool(self._selection))
        self._status.setText(self._texte_selection())

    # ------------------------------------------------------------------ étapes 8-9

    def _on_valider(self) -> None:
        zones = [z for z in self._zones if z.id_top_left in self._selection]
        if not zones:
            return

        dialogue = ConfirmDepositDialog(
            self._preparation.product_name, len(zones), parent=self
        )
        if dialogue.exec_() != dialogue.Accepted:
            # Retour à la SÉLECTION, pas à l'accueil : se tromper d'une zone est
            # l'erreur la plus probable ici, refaire tout le cycle serait décourageant.
            return

        self._dry_run = dialogue.dry_run
        steps = self._construire_steps(zones)
        if steps is None:
            return
        self._lancer_depose(steps, zones)

    def _construire_steps(self, zones: list):
        """Calcule la trajectoire et vérifie qu'elle tient dans la course de la machine.

        Retourne None si le contrôle de course échoue — auquel cas rien n'a bougé.
        """
        settings = self._preparation.settings
        planner = PathPlanner.from_settings(
            settings,
            z_dispense_mm=DISPENSE_Z_HEIGHT_MM,
            z_travel_mm=MACHINE_Z_TRAVEL_MM,
            dry_run=self._dry_run,
        )
        steps = planner.generate_plateau_path(
            zones, self._preparation.cordons, settings.row_tolerance_mm
        )

        # ⚠️ AVANT le premier mouvement, jamais pendant. Marlin ne refuse pas une
        # coordonnée hors course : il la rogne EN SILENCE, et la dépose sortirait
        # déformée en passant pour une erreur de vision.
        violations = check_machine_limits(
            steps,
            x_max=MACHINE_TRAVEL_X_MAX_MM,
            y_max=MACHINE_TRAVEL_Y_MAX_MM,
            z_max=MACHINE_TRAVEL_Z_MAX_MM,
        )
        if violations:
            QMessageBox.critical(
                self, "Depose hors course", format_limit_violations(violations)
            )
            return None
        return steps

    def _lancer_depose(self, steps: list, zones: list) -> None:
        self._zones_faites = []
        self._zones_prevues = [z.id_top_left for z in sort_zones_for_deposit(zones)]
        settings = self._preparation.settings

        self._dialogue_progression = DepositProgressDialog(parent=self)
        self._dialogue_progression.set_progress(0.0, 0, len(self._zones_prevues))
        self._dialogue_progression.pause_toggled.connect(self._on_pause)
        self._dialogue_progression.stop_requested.connect(self._on_stop)

        self._thread_depose = QThread()
        self._worker_depose = DepositWorker(
            self._machine, steps,
            travel_speed=settings.travel_speed_mm_min,
            extrusion_speed=settings.extrusion_speed_mm_min,
        )
        self._worker_depose.moveToThread(self._thread_depose)
        self._thread_depose.started.connect(self._worker_depose.run)
        self._worker_depose.progress.connect(self._on_progress)
        self._worker_depose.state_changed.connect(
            self._dialogue_progression.set_state_text)
        self._worker_depose.zone_done.connect(self._zones_faites.append)
        self._worker_depose.finished.connect(lambda: self._fin_de_depose(False))
        self._worker_depose.stopped.connect(lambda: self._fin_de_depose(True))
        self._worker_depose.error_occurred.connect(self._on_erreur_depose)
        self._worker_depose.finished.connect(self._thread_depose.quit)
        self._worker_depose.stopped.connect(self._thread_depose.quit)
        self._worker_depose.error_occurred.connect(self._thread_depose.quit)

        self._depart = time.monotonic()
        self._chrono.start()
        self._thread_depose.start()
        self._dialogue_progression.exec_()

    # ------------------------------------------------------------------ étape 10

    def _on_progress(self, fraction: float, zones_terminees: int) -> None:
        if self._dialogue_progression is not None:
            self._dialogue_progression.set_progress(
                fraction, zones_terminees, len(self._zones_prevues)
            )

    def _tick(self) -> None:
        if self._dialogue_progression is not None:
            self._dialogue_progression.set_elapsed(
                int(time.monotonic() - self._depart)
            )

    def _on_pause(self, en_pause: bool) -> None:
        if self._worker_depose is not None:
            self._worker_depose.set_paused(en_pause)
        if self._dialogue_progression is not None:
            self._dialogue_progression.set_state_text(
                "EN PAUSE — la pate peut continuer de s'ecouler legerement."
                if en_pause else "Depose en cours"
            )

    def _on_stop(self) -> None:
        """Arrêt : coupe les actionneurs immédiatement, puis arrête le thread.

        `emergency_stop()` est appelé **hors du thread** parce qu'il écrit directement
        sur le port série sans attendre de « ok » : passer par le worker le ferait
        attendre la fin du step en cours, ce qui n'est pas un arrêt.
        """
        if self._machine is not None and self._machine.is_connected():
            try:
                self._machine.emergency_stop()
            except Exception:
                pass
        if self._worker_depose is not None:
            self._worker_depose.request_stop()

    def _on_erreur_depose(self, message: str) -> None:
        self._chrono.stop()
        if self._dialogue_progression is not None:
            self._dialogue_progression.set_finished(message)
            self._dialogue_progression.accept()
            self._dialogue_progression = None
        QMessageBox.critical(self, "Erreur pendant la depose", message)
        self.back_requested.emit()

    # ------------------------------------------------------------------ étapes 11-12

    def _fin_de_depose(self, interrompu: bool) -> None:
        self._chrono.stop()
        secondes = int(time.monotonic() - self._depart)

        if self._dialogue_progression is not None:
            self._dialogue_progression.accept()
            self._dialogue_progression = None

        bilan = DepositSummaryDialog(
            product_name=self._preparation.product_name,
            zones_faites=self._zones_faites,
            zones_prevues=self._zones_prevues,
            secondes=secondes,
            interrompu=interrompu,
            dry_run=self._dry_run,
            parent=self,
        )
        bilan.exec_()
        self.back_requested.emit()

    # ------------------------------------------------------------------ erreurs

    def _avertir(self, message: str) -> None:
        """Signaler un problème SANS quitter l'écran.

        Séparé de `_echec` pour que le retour à l'accueil soit émis par un seul endroit :
        un appelant qui signale puis rend la main à un appelant qui quitte émettrait
        `back_requested` deux fois, et l'écran d'accueil serait rechargé deux fois.
        """
        self._status.setText(message)
        QMessageBox.critical(self, "Cycle de depose", message)

    def _echec(self, message: str) -> None:
        self._avertir(message)
        self.back_requested.emit()
