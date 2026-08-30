# Fenêtre principale de l'application PyQt5
# Gère la navigation entre les 4 écrans via un QStackedWidget

import numpy as np
from PyQt5.QtWidgets import QMainWindow, QStackedWidget, QMessageBox, QDialog
from PyQt5.QtCore import Qt

from gui.dialogs import PreparationPickerDialog
from modules.preparation import (
    list_autosaves,
    load_preparation,
    product_name_from_path,
)

from modules.config import (
    TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT,
    SERIAL_PORT, SERIAL_BAUDRATE,
    MACHINE_FEEDRATE_XY, MACHINE_FEEDRATE_Z, MACHINE_FEEDRATE_DISPENSE,
    CAMERA_INDEX,
)
from modules.camera import Camera
from modules.machine import Machine
from gui.screen_capture import ScreenCapture
from gui.screen_zone import ScreenZone
from gui.screen_run import ScreenRun
from gui.screen_report import ScreenReport
from gui.screen_calibration import ScreenCalibration
from gui.screen_plateau import ScreenPlateau
from gui.screen_cordons import ScreenCordons
from gui.screen_execution import ScreenExecution
from gui.screen_showroom import ScreenShowroom


# Feuille de style globale appliquée à toute l'application
# Définir ici plutôt que dans chaque écran → cohérence visuelle garantie
STYLESHEET = """
QWidget {
    background-color: #1e1e1e;
    color: #f0f0f0;
    font-size: 15px;
    font-family: sans-serif;
}
QPushButton {
    background-color: #2d5f8a;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 16px;
    font-weight: bold;
    min-height: 55px;
}
QPushButton:hover {
    background-color: #3a7cbf;
}
QPushButton:pressed {
    background-color: #1e4060;
}
QPushButton:disabled {
    background-color: #3a3a3a;
    color: #666;
}
QPushButton[role="success"] {
    background-color: #2d6b2d;
}
QPushButton[role="danger"] {
    background-color: #8b1a1a;
}
QPushButton[role="secondary"] {
    background-color: #4a4a4a;
}
QLabel[role="title"] {
    font-size: 17px;
    font-weight: bold;
    color: #7ec8e3;
    padding: 4px 0px;
}
QLabel[role="status"] {
    color: #888;
    font-size: 13px;
}
QLabel[role="camera"] {
    background-color: #111;
    border: 1px solid #333;
}
"""


class MainApp(QMainWindow):
    """Fenêtre principale — contient la pile d'écrans et gère la navigation.

    Navigation :
        ScreenCapture → ScreenZone → ScreenRun → ScreenReport → ScreenCapture
    Chaque écran émet un signal quand il a terminé son rôle.
    MainApp reçoit ce signal et bascule vers l'écran suivant.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Machine de Dépose de Pâte Thermique")

        # Créer l'objet Machine une seule fois — la connexion série est ouverte
        # dans le thread d'exécution (RunWorker) pour ne pas bloquer l'interface
        self._machine = Machine(
            port=SERIAL_PORT,
            baudrate=SERIAL_BAUDRATE,
            feedrate_xy=MACHINE_FEEDRATE_XY,
            feedrate_z=MACHINE_FEEDRATE_Z,
            feedrate_dispense=MACHINE_FEEDRATE_DISPENSE,
        )

        # Sur le RPi avec l'écran tactile, décommenter pour fixer la taille en production :
        # self.setFixedSize(TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT)

        # Appliquer le thème sombre global
        self.setStyleSheet(STYLESHEET)

        # QStackedWidget = pile de widgets — un seul visible à la fois
        # C'est le mécanisme standard PyQt5 pour naviguer entre des "pages"
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # Créer les 6 écrans dans l'ordre de navigation
        self._screen_capture = ScreenCapture()
        self._screen_zone = ScreenZone()
        self._screen_run = ScreenRun()
        self._screen_report = ScreenReport()
        self._screen_calibration = ScreenCalibration()
        self._screen_plateau = ScreenPlateau()
        self._screen_cordons = ScreenCordons()
        self._screen_execution = ScreenExecution()
        self._screen_showroom = ScreenShowroom()

        # Ajouter les écrans à la pile — l'index correspond à l'ordre d'ajout
        self._stack.addWidget(self._screen_capture)     # index 0
        self._stack.addWidget(self._screen_zone)        # index 1
        self._stack.addWidget(self._screen_run)         # index 2
        self._stack.addWidget(self._screen_report)      # index 3
        self._stack.addWidget(self._screen_calibration) # index 4
        self._stack.addWidget(self._screen_plateau)     # index 5
        self._stack.addWidget(self._screen_cordons)     # index 6
        self._stack.addWidget(self._screen_execution)   # index 7
        self._stack.addWidget(self._screen_showroom)    # index 8

        # Fournir la machine à screen_capture pour le bouton Homing
        self._screen_capture.set_machine(self._machine)
        # ... et à l'écran d'exécution, qui la pilote de bout en bout
        self._screen_execution.set_machine(self._machine)
        # ... et à la création de plateau, qui s'en sert pour se mettre en position de
        # prise de vue avant chaque photo (demandé le 2026-08-04)
        self._screen_plateau.set_machine(self._machine)
        # ... et au mode démonstration, qui rejoue le même cycle en boucle
        self._screen_showroom.set_machine(self._machine)

        # Caméra unique partagée entre screen_capture et screen_calibration
        # → évite un release+open de 1-2 s à chaque changement d'écran
        try:
            self._camera = Camera(CAMERA_INDEX)
        except RuntimeError as e:
            print(f"[MainApp] Camera non disponible : {e}")
            self._camera = None

        # Fournir la même référence caméra aux trois écrans qui en ont besoin
        self._screen_capture.set_camera(self._camera)
        self._screen_calibration.set_camera(self._camera)
        self._screen_plateau.set_camera(self._camera)
        self._screen_execution.set_camera(self._camera)
        self._screen_showroom.set_camera(self._camera)

        # Remplir les listes déroulantes de choix du matériel de l'écran 1. À faire APRÈS
        # set_machine() et set_camera() : les listes présélectionnent le port et la caméra
        # réellement en service, donc elles doivent les connaître.
        self._screen_capture.refresh_device_lists()

        # Données du cycle courant — stockées au fil de la navigation pour le rapport PDF
        self._captured_image = None   # photo de la pièce (numpy BGR)
        self._points_mm: list = []    # tracé de l'opérateur (coordonnées ArUco mm)
        self._quantity: float = 0.0   # quantité de pâte configurée (mm E / mm tracé)

        # Travail interrompu que l'opérateur a choisi de reprendre au démarrage. Gardé
        # ici jusqu'à ce qu'un plateau soit re-photographié : les cordons repris ne
        # peuvent être replacés qu'une fois les zones redétectées.
        self._preparation_reprise = None

        # Connecter les signaux de chaque écran à la méthode de navigation correspondante
        # Signal émis par l'écran → slot qui bascule vers l'écran suivant
        self._screen_capture.photo_validated.connect(self._go_to_zone)
        self._screen_zone.zone_configured.connect(self._go_to_run)
        self._screen_run.run_finished.connect(self._go_to_report)
        self._screen_report.new_piece_requested.connect(self._go_to_capture)
        self._screen_capture.calibration_requested.connect(self._go_to_calibration)
        self._screen_calibration.back_requested.connect(self._go_from_calibration_to_capture)
        self._screen_capture.plateau_requested.connect(self._go_to_plateau)
        self._screen_capture.preparation_load_requested.connect(self._go_to_load_preparation)
        self._screen_plateau.back_requested.connect(self._go_from_plateau_to_capture)
        self._screen_plateau.plateau_validated.connect(self._go_to_cordons)
        self._screen_cordons.back_requested.connect(self._go_from_cordons_to_plateau)
        self._screen_capture.deposit_requested.connect(self._go_to_execution)
        self._screen_execution.back_requested.connect(self._go_from_execution_to_capture)
        self._screen_capture.showroom_requested.connect(self._go_to_showroom)
        self._screen_showroom.back_requested.connect(self._go_from_showroom_to_capture)

        # Changements de matériel demandés depuis l'écran 1 — appliqués ici, car MainApp
        # est propriétaire de la Camera et de la Machine partagées par tous les écrans
        self._screen_capture.camera_selected.connect(self._on_camera_selected)
        self._screen_capture.machine_port_selected.connect(self._on_machine_port_selected)

        # Démarrer sur l'écran de capture
        self._go_to_capture()

    # ------------------------------------------------------------------ navigation

    def _go_to_capture(self) -> None:
        """Basculer vers l'écran de capture et démarrer la caméra."""
        self._screen_capture.start_camera()
        self._stack.setCurrentIndex(0)

    def _go_to_zone(self, image: np.ndarray) -> None:
        """Basculer vers l'écran de sélection de zone avec la photo capturée."""
        # Arrêter la caméra avant de quitter l'écran de capture — libère la ressource USB
        self._screen_capture.stop_camera()
        # Conserver l'image pour le rapport PDF généré à la fin du cycle
        self._captured_image = image
        self._screen_zone.set_image(image)
        self._stack.setCurrentIndex(1)

    def _go_to_run(self, points_mm: object, quantity: float) -> None:
        """Basculer vers l'écran d'exécution avec le tracé et la quantité configurés."""
        # Conserver le tracé et la quantité pour le rapport PDF
        self._points_mm = list(points_mm)
        self._quantity = quantity
        self._screen_run.start_run(self._machine, points_mm, quantity)
        self._stack.setCurrentIndex(2)

    def _go_to_report(self, status: str) -> None:
        """Basculer vers l'écran de rapport en lui transmettant toutes les données du cycle."""
        self._screen_report.set_result(
            self._captured_image,
            self._points_mm,
            self._quantity,
            status,
        )
        self._stack.setCurrentIndex(3)

    def _go_to_calibration(self) -> None:
        """Basculer vers l'écran de calibration caméra ChArUco."""
        # Arrêter la caméra de capture avant d'ouvrir celle de calibration
        # (une seule caméra physique — ne peut pas être ouverte deux fois simultanément)
        self._screen_capture.stop_camera()
        self._screen_calibration.start_camera()
        self._stack.setCurrentIndex(4)

    def _go_from_calibration_to_capture(self) -> None:
        """Retourner vers l'écran de capture depuis la calibration."""
        # Arrêter la caméra de calibration avant de relancer celle de capture
        self._screen_calibration.stop_camera()
        self._go_to_capture()

    def _go_to_plateau(self) -> None:
        """Basculer vers l'écran de création de plateau (nouveau processus multi-zones).

        Le nom du produit est demandé AVANT d'afficher l'écran : si l'opérateur annule
        la saisie, on reste où on est plutôt que d'ouvrir un écran sans identité.
        """
        if not self._screen_plateau.ask_product_name(self):
            return

        # Une seule caméra physique : couper l'aperçu de l'écran courant avant d'en
        # démarrer un autre
        self._screen_capture.stop_camera()
        self._screen_plateau.start_camera()
        self._stack.setCurrentIndex(5)

    def _go_from_plateau_to_capture(self) -> None:
        """Retourner vers l'écran de capture depuis la création de plateau."""
        self._screen_plateau.stop_camera()
        self._go_to_capture()

    def _go_to_cordons(self, donnees: object) -> None:
        """Basculer vers le tracé des cordons, une fois le plateau validé.

        Si un travail interrompu a été repris au démarrage, c'est ICI qu'il rejoint le
        plateau : les cordons repris ont besoin des zones de la photo qu'on vient de
        prendre pour être replacés. La reprise est consommée au passage — la rejouer
        écraserait le travail fait depuis.
        """
        # Le tracé travaille sur la photo figée : plus besoin de la caméra
        self._screen_plateau.stop_camera()
        self._screen_cordons.set_plateau(donnees, reprise=self._preparation_reprise)
        self._preparation_reprise = None
        self._stack.setCurrentIndex(6)

    def _go_from_cordons_to_plateau(self) -> None:
        """Revenir à la création de plateau — typiquement pour reprendre une photo."""
        self._screen_plateau.start_camera()
        self._stack.setCurrentIndex(5)

    def _go_to_execution(self) -> None:
        """Lancer le cycle de dépose multi-zones (lot D2).

        La caméra de l'écran d'accueil est arrêtée d'abord : le cycle va prendre sa
        propre photo, et deux lectures concurrentes sur le même flux se disputeraient les
        images. L'écran est affiché AVANT de démarrer le cycle, pour que l'opérateur voie
        la progression du homing plutôt qu'une interface figée.
        """
        self._screen_capture.stop_camera()
        self._stack.setCurrentIndex(7)
        self._screen_execution.start_cycle()

    def _go_from_execution_to_capture(self) -> None:
        """Retour à l'accueil à la fin du cycle, ou après une annulation."""
        self._go_to_capture()

    def _go_to_showroom(self) -> None:
        """Basculer vers le mode démonstration (cycle automatique en boucle).

        Même précaution que pour l'écran d'exécution : l'aperçu de l'accueil est coupé
        avant, car la boucle prend ses propres photos et deux lectures concurrentes sur
        le même flux se disputeraient les images.

        La liste des plateaux est rafraîchie à chaque entrée : un plateau enregistré
        entre-temps doit y figurer sans avoir à redémarrer l'application.
        """
        self._screen_capture.stop_camera()
        self._screen_showroom.refresh_preparations()
        self._stack.setCurrentIndex(8)

    def _go_from_showroom_to_capture(self) -> None:
        """Retour à l'accueil depuis le mode démonstration."""
        self._go_to_capture()

    # ------------------------------------------------------------------ reprise au démarrage

    def propose_resume(self, directory: str = None) -> bool:
        """Propose de reprendre un travail interrompu, s'il en existe un.

        Appelée par main.py **après** l'affichage de la fenêtre, et non depuis
        `__init__` : une boîte de dialogue modale pendant la construction bloquerait le
        démarrage avant que quoi que ce soit ne soit visible, et l'opérateur ferait face
        à un dialogue flottant sans contexte.

        Un fichier `.autosave.json` ne signale qu'une chose : un travail interrompu par
        un plantage ou une coupure. L'enregistrement définitif le supprime, donc sa
        seule présence est déjà l'information.

        Retourne True si une reprise a été acceptée.
        """
        autosaves = list_autosaves(directory)
        if not autosaves:
            return False

        # Le plus récemment modifié en premier (list_autosaves trie ainsi) : c'est le
        # travail que l'opérateur faisait quand l'application s'est arrêtée
        chemin = autosaves[0]
        nom = product_name_from_path(chemin)

        reponse = QMessageBox.question(
            self,
            "Reprendre un travail interrompu ?",
            f"Un travail non enregistré a été trouvé pour « {nom} ».\n\n"
            f"Le reprendre ? Les cordons déjà tracés seront restaurés — il faudra "
            f"reprendre une photo du plateau, ce qui ne fait perdre aucun tracé.\n\n"
            f"« Non » conserve le fichier : la question sera reposée au prochain "
            f"démarrage.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reponse != QMessageBox.Yes:
            return False

        return self._charger_preparation(chemin, titre_erreur="Reprise impossible")

    def _go_to_load_preparation(self) -> None:
        """Ouvre le sélecteur de plateaux enregistrés (bouton « Charger un plateau »).

        Distinct de `propose_resume()`, qui ne regarde que les travaux **interrompus**
        (`*.autosave.json`). Ici on rejoue une préparation **validée** — c'est le point 7
        du processus cible : les zones étant vissées à demeure, un plateau enregistré se
        rejoue autant de fois que nécessaire, sans rien retracer.
        """
        dialogue = PreparationPickerDialog(parent=self)
        if dialogue.exec_() != QDialog.Accepted:
            return

        chemin = dialogue.selected_path
        if chemin is None:
            return   # liste vide : le bouton « Charger » était déjà inactif

        self._charger_preparation(chemin, titre_erreur="Chargement impossible")

    def _charger_preparation(self, chemin: str, titre_erreur: str) -> bool:
        """Relit un fichier de préparation et amène l'opérateur à la prise de photo.

        Tronc commun à la reprise après plantage et au rechargement volontaire : les
        deux ne diffèrent que par la façon dont le fichier a été choisi. Factorisé pour
        que le comportement — pré-remplissage du nom, navigation, gestion d'erreur —
        ne puisse pas diverger entre les deux chemins.

        La préparation est mise de côté dans `_preparation_reprise` : elle ne rejoindra
        le plateau qu'une fois les zones redétectées, dans `_go_to_cordons()`.
        """
        try:
            self._preparation_reprise = load_preparation(chemin)
        except (OSError, ValueError, KeyError) as e:
            # Fichier tronqué, format inconnu, clé manquante : le dire et repartir
            # normalement plutôt que d'empêcher l'application de démarrer
            QMessageBox.warning(
                self, titre_erreur,
                f"Le fichier n'a pas pu être relu :\n{e}\n\n"
                f"L'application continue normalement."
            )
            self._preparation_reprise = None
            return False

        # Le nom du produit est déjà connu : le pré-remplir évite de le ressaisir, et
        # surtout évite qu'une faute de frappe crée un second fichier pour le même
        # plateau
        self._screen_plateau.set_product_name(self._preparation_reprise.product_name)

        # Aller directement à la capture du plateau : c'est la seule chose qui manque.
        # Les zones enregistrées sont des positions absolues, périmées dès que la caméra
        # bouge ; les cordons, eux, sont relatifs à la zone et survivent à la nouvelle photo.
        self._screen_capture.stop_camera()
        self._screen_plateau.start_camera()

        # La photo se déclenche seule dès que le plateau est reconnu. Sur un plateau
        # rechargé, le cadrage est toujours le même — caméra fixe, zones vissées à
        # demeure — donc demander un appui sur « Capturer » ne fait prendre aucune
        # décision à l'opérateur. Si le plateau n'est pas reconnu dans le délai imparti,
        # l'écran rend la main avec un message et le bouton reste disponible.
        self._screen_plateau.armer_capture_automatique()

        self._stack.setCurrentIndex(5)
        return True

    # ------------------------------------------------------------------ choix du matériel

    def _on_camera_selected(self, device_index: int) -> None:
        """Basculer sur une autre caméra, choisie dans la liste déroulante de l'écran 1.

        MainApp est le seul propriétaire de l'objet Camera (partagé avec l'écran de
        calibration) : c'est donc ici, et nulle part ailleurs, que l'ancienne est
        libérée et la nouvelle ouverte.
        """
        # Rien à faire si c'est déjà la caméra en service — éviter une fermeture puis
        # réouverture inutile, qui coûte 1 à 2 secondes
        if self._camera is not None and self._camera.index == device_index:
            return

        # Couper les deux aperçus AVANT de libérer : un timer qui lirait dans une caméra
        # déjà relâchée lèverait une RuntimeError en plein changement
        self._screen_capture.stop_camera()
        self._screen_calibration.stop_camera()

        if self._camera is not None:
            self._camera.release()
            self._camera = None

        try:
            self._camera = Camera(device_index)
            message = f"Camera {device_index} activee"
        except RuntimeError as e:
            # Caméra débranchée entre le scan et la sélection, ou occupée par un autre
            # logiciel : on reste sans caméra plutôt que de laisser un objet inutilisable
            self._camera = None
            message = f"Camera {device_index} indisponible : {e}"

        # Redistribuer la nouvelle référence (ou None) aux deux écrans concernés
        self._screen_capture.set_camera(self._camera)
        self._screen_calibration.set_camera(self._camera)

        # Relancer l'aperçu : on est forcément sur l'écran 1, seul écran à porter la liste
        self._screen_capture.start_camera()
        # Rafraîchir la liste pour remettre le suffixe "(en cours)" sur la bonne entrée
        self._screen_capture.refresh_device_lists()
        self._screen_capture.set_status(message)

    def _on_machine_port_selected(self, port: str) -> None:
        """Changer le port série de la machine, choisi dans la liste déroulante de l'écran 1.

        Aucune connexion n'est ouverte ici : la Machine ne se connecte qu'au moment du
        homing ou de la dépose, dans leur thread respectif. On ne fait donc que changer
        le port qui sera utilisé au prochain connect().
        """
        try:
            self._machine.set_port(port)
            self._screen_capture.set_status(f"Port machine : {port}")
        except RuntimeError as e:
            # set_port refuse pendant une connexion ouverte — le message vient de Machine
            self._screen_capture.set_status(str(e))
            # Remettre la liste sur le port réellement en service, pour ne pas laisser
            # croire que le changement a été pris en compte
            self._screen_capture.refresh_device_lists()

    # ------------------------------------------------------------------ cycle de vie

    def closeEvent(self, event) -> None:
        """Nettoyer les ressources avant de fermer la fenêtre."""
        # ⚠️ D'ABORD arrêter la boucle de démonstration, si elle tourne. Sans cela, le
        # thread de dépose survivrait à la fenêtre : la machine continuerait de bouger
        # alors que l'opérateur n'a plus aucun bouton d'arrêt sous la main.
        self._screen_showroom.shutdown()

        # Arrêter les timers d'aperçu des trois écrans qui utilisent la caméra
        self._screen_capture.stop_camera()
        self._screen_calibration.stop_camera()
        self._screen_plateau.stop_camera()
        # Libérer la caméra partagée (une seule fois, pas dans les écrans)
        if self._camera is not None:
            self._camera.release()
            self._camera = None
        event.accept()
