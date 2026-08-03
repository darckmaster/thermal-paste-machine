# Écran 1 — Capture photo
# Affiche le flux caméra en temps réel, permet de capturer et valider une photo

import numpy as np
import cv2
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QComboBox,
    QMessageBox,
)
from PyQt5.QtCore import Qt, QTimer, QThread, QObject, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QImage, QPixmap

from gui.workers import PhotoPositionRunner
from modules.camera import Camera
from modules.machine import Machine
from modules.vision import VisionProcessor
from modules.config import (
    CAMERA_INDEX, ARUCO_DICT_ID, ARUCO_MARKER_SIZE_MM,
    PHOTO_POSITION_X, PHOTO_POSITION_Y, PHOTO_POSITION_Z,
)


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

    # Signal émis quand l'opérateur veut créer un plateau (nouveau processus, lot C)
    plateau_requested = pyqtSignal()

    # Demande de rechargement d'un plateau déjà enregistré. C'est MainApp qui ouvre le
    # sélecteur et applique le chargement : lui seul possède les écrans à alimenter.
    preparation_load_requested = pyqtSignal()

    # Demande de lancement d'un cycle de dépose multi-zones (lot D2). L'écran d'exécution
    # se charge ensuite de tout : homing, prise de vue, choix du fichier, sélection des
    # zones, dépose, bilan, retour ici.
    deposit_requested = pyqtSignal()

    # Signaux de changement de matériel. L'écran ne remplace PAS lui-même la caméra ou
    # le port : les objets Camera et Machine appartiennent à MainApp (qui les partage
    # avec les autres écrans), donc seul MainApp peut les échanger proprement. L'écran
    # se contente de dire ce que l'opérateur a choisi.
    camera_selected = pyqtSignal(int)          # index OpenCV de la caméra choisie
    machine_port_selected = pyqtSignal(str)    # nom du port série choisi (ex. "COM3")

    def __init__(self) -> None:
        super().__init__()
        # Objet caméra — créé au premier start_camera(), détruit à stop_camera()
        self._camera: Camera | None = None
        # Détecteur ArUco réutilisé à chaque frame — sert uniquement à l'aperçu (debug visuel
        # des 4 marqueurs du plateau) ; la détection "officielle" pour le tracé se fait dans
        # screen_zone.py sur la photo validée
        self._vision = VisionProcessor(
            aruco_dict_id=ARUCO_DICT_ID, marker_real_size_mm=ARUCO_MARKER_SIZE_MM
        )
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

        # Mise en position de prise de vue avant chaque photo — voir _on_capture()
        self._runner = PhotoPositionRunner(self)
        self._runner.done.connect(self._on_position_prete)

        self._setup_ui()
        self._runner.progress.connect(self._status_label.setText)

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

        # Ligne "matériel" — choix du port machine et de la caméra.
        # Placée sur l'écran 1 parce que c'est le premier écran affiché : l'opérateur
        # règle son matériel avant toute action, sans avoir à éditer local_config.json.
        device_layout = QHBoxLayout()
        device_layout.setSpacing(8)

        device_layout.addWidget(QLabel("Machine :"))
        self._combo_port = QComboBox()
        # 44 px = taille minimale d'une cible tactile confortable sur l'écran 7"
        self._combo_port.setMinimumHeight(44)
        # "activated" plutôt que "currentIndexChanged" : activated n'est émis que sur une
        # action de l'opérateur, alors que currentIndexChanged se déclenche AUSSI quand on
        # remplit la liste par code → cela provoquerait un changement de port fantôme à
        # chaque rafraîchissement de la liste.
        self._combo_port.activated.connect(self._on_port_selected)
        device_layout.addWidget(self._combo_port, stretch=1)

        device_layout.addWidget(QLabel("Caméra :"))
        self._combo_camera = QComboBox()
        self._combo_camera.setMinimumHeight(44)
        self._combo_camera.activated.connect(self._on_camera_selected)
        device_layout.addWidget(self._combo_camera, stretch=1)

        # Rafraîchir : re-scanner le matériel sans relancer l'application — utile quand
        # on branche la carte ou la caméra après le démarrage
        self._btn_refresh = QPushButton("Rafraichir")
        self._btn_refresh.setProperty("role", "secondary")
        self._btn_refresh.clicked.connect(self.refresh_device_lists)
        device_layout.addWidget(self._btn_refresh)

        layout.addLayout(device_layout)

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

        # Accès au nouveau processus multi-zones. Cohabite volontairement avec le cycle
        # historique (capture → tracé → dépose) tant que celui-ci reste le seul à mener
        # jusqu'à la dépose réelle : on ne casse pas ce qui fonctionne pour une démo.
        self._btn_plateau = QPushButton("Créer un plateau")
        self._btn_plateau.setProperty("role", "secondary")
        self._btn_plateau.clicked.connect(self.plateau_requested)
        homing_layout.addWidget(self._btn_plateau)

        # Rejouer un plateau déjà enregistré, sans rien retracer — point 7 du processus
        # cible. Bouton distinct de « Créer un plateau » : créer et recharger sont deux
        # intentions différentes, et les confondre dans un même bouton ferait risquer
        # d'écraser un plateau existant en croyant en ouvrir un nouveau.
        self._btn_charger = QPushButton("Charger un plateau")
        self._btn_charger.setProperty("role", "secondary")
        self._btn_charger.clicked.connect(self.preparation_load_requested)
        homing_layout.addWidget(self._btn_charger)

        # Point d'entrée du cycle de dépose multi-zones (lot D2). Bouton mis en avant
        # (role "success") car c'est l'action normale au quotidien : les deux boutons
        # précédents servent à PRÉPARER un plateau, celui-ci à l'exécuter.
        self._btn_depose = QPushButton("Lancer une dépose")
        self._btn_depose.setProperty("role", "success")
        self._btn_depose.clicked.connect(self.deposit_requested)
        homing_layout.addWidget(self._btn_depose)

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

    # ------------------------------------------------------------------ choix du matériel

    def refresh_device_lists(self) -> None:
        """(Re)remplir les deux listes déroulantes en scannant le matériel présent.

        Appelée une fois au démarrage par app.py (après set_machine/set_camera), puis à
        chaque clic sur "Rafraichir".
        """
        self._refresh_port_list()
        self._refresh_camera_list()

    def _refresh_port_list(self) -> None:
        """Remplir la liste des ports série et y présélectionner le port courant."""
        # Retenir le port actuellement configuré AVANT de vider la liste
        port_courant = self._machine.port if self._machine is not None else None

        self._combo_port.clear()
        ports = Machine.list_ports()

        for device, libelle in ports:
            # Le texte affiché est le libellé lisible, mais la donnée associée
            # (userData) est le vrai nom de device — c'est lui qu'on émettra
            self._combo_port.addItem(libelle, device)

        if not ports:
            # Aucun port : afficher une entrée explicite plutôt qu'une liste vide muette
            self._combo_port.addItem("Aucun port detecte", None)
            self._combo_port.setEnabled(False)
            return

        self._combo_port.setEnabled(True)

        if port_courant is not None:
            position = self._combo_port.findData(port_courant)
            if position >= 0:
                self._combo_port.setCurrentIndex(position)
            else:
                # Cas courant en développement : config.py contient "/dev/ttyUSB0" alors
                # qu'on travaille sous Windows. On ajoute quand même l'entrée, marquée
                # "absent", pour que la liste reflète honnêtement ce qui est configuré.
                self._combo_port.addItem(f"{port_courant} (absent)", port_courant)
                self._combo_port.setCurrentIndex(self._combo_port.count() - 1)

    def _refresh_camera_list(self) -> None:
        """Remplir la liste des caméras et y présélectionner celle en cours d'usage."""
        index_courant = self._camera.index if self._camera is not None else None

        # Le scan ouvre et referme chaque index. Si l'aperçu tourne en même temps, le
        # timer lit dans la caméra pendant que le scan la sollicite → frames perdues et
        # scan peu fiable. On suspend l'aperçu le temps du scan, puis on le rétablit
        # seulement s'il était actif (ne pas relancer un aperçu sur photo figée).
        apercu_actif = self._timer.isActive()
        self._timer.stop()
        try:
            # Exclure la caméra en service : la sonder ouvrirait un second handle sur le
            # même périphérique, dont la fermeture couperait le flux en cours (voir le
            # docstring de Camera.list_devices). C'est ce qui cassait l'aperçu au démarrage
            # et après chaque changement de caméra (constaté le 2026-08-01).
            indices = Camera.list_devices(
                exclude={index_courant} if index_courant is not None else None
            )
        finally:
            if apercu_actif:
                self._timer.start(100)

        # La caméra en service ayant été volontairement écartée du scan, elle doit être
        # réintégrée à la main pour figurer dans la liste proposée à l'opérateur
        if index_courant is not None and index_courant not in indices:
            indices.append(index_courant)
        indices.sort()

        self._combo_camera.clear()

        if not indices:
            self._combo_camera.addItem("Aucune camera detectee", None)
            self._combo_camera.setEnabled(False)
            return

        self._combo_camera.setEnabled(True)
        for i in indices:
            # Suffixe "(en cours)" pour que l'opérateur repère celle qui alimente l'aperçu
            suffixe = " (en cours)" if i == index_courant else ""
            self._combo_camera.addItem(f"Camera {i}{suffixe}", i)

        if index_courant is not None:
            position = self._combo_camera.findData(index_courant)
            if position >= 0:
                self._combo_camera.setCurrentIndex(position)

    def _on_port_selected(self, position: int) -> None:
        """L'opérateur a choisi un port — prévenir MainApp, qui seul détient la Machine."""
        device = self._combo_port.itemData(position)
        if device:
            self.machine_port_selected.emit(device)

    def _on_camera_selected(self, position: int) -> None:
        """L'opérateur a choisi une caméra — prévenir MainApp, qui seul détient la Camera."""
        index = self._combo_camera.itemData(position)
        if index is not None:
            self.camera_selected.emit(int(index))

    def set_status(self, message: str) -> None:
        """Afficher un message dans la barre de statut de cet écran.

        Permet à MainApp de rendre compte à l'opérateur du résultat d'un changement de
        matériel (succès, ou refus parce que la machine est connectée).
        """
        self._status_label.setText(message)

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
        """Appelé toutes les 100 ms par le timer — capture, détecte les ArUco et affiche."""
        if self._camera is None:
            return
        try:
            frame = self._camera.capture()
            self._display_image_with_markers(frame)
        except RuntimeError:
            # La caméra a été débranchée en cours de route
            self._timer.stop()
            self._image_label.setText("Camera deconnectee — rebrancher et relancer")
            self._btn_capture.setEnabled(False)

    def _display_image_with_markers(self, frame: np.ndarray) -> None:
        """Détecte les marqueurs ArUco du plateau et les affiche en surimpression.

        Aide au positionnement de la pièce/du plateau : l'opérateur voit tout de suite
        quels marqueurs (parmi les IDs 0-3 attendus) sont vus par la caméra, sans avoir
        à capturer une photo pour le savoir.
        """
        detected = self._vision.detect_markers(frame)

        if detected:
            # Dessiner sur une copie — ne jamais modifier "frame" (utilisé tel quel par
            # _on_capture pour la photo réellement transmise à l'écran suivant)
            preview = frame.copy()
            coins = [c.reshape(1, 4, 2).astype(np.float32) for c in detected.values()]
            ids = np.array([[mid] for mid in detected.keys()])
            cv2.aruco.drawDetectedMarkers(preview, coins, ids)
            self._status_label.setText(f"Marqueurs détectés : {sorted(detected.keys())}")
            self._display_image(preview)
        else:
            self._status_label.setText("Aucun marqueur ArUco détecté")
            self._display_image(frame)

    # ------------------------------------------------------------------ actions boutons

    def _on_capture(self) -> None:
        """Amener la machine en position de prise de vue, puis figer l'image.

        Demandé par l'étudiant le 2026-08-04 : toute photo du plateau est prise depuis la
        même position machine. Sur le PoC le plateau est solidaire du lit qui bouge en Y,
        donc photographier là où la machine se trouve donne un cadrage variable.
        """
        if self._camera is None:
            return
        if self._runner.busy:
            return   # mise en position déjà en cours — ignorer le double appui

        if self._machine is None:
            if not self._confirmer_sans_machine("Aucune machine n'est configuree."):
                return
            self._capturer_maintenant()
            return

        self._btn_capture.setEnabled(False)
        self._runner.start(
            self._machine, (PHOTO_POSITION_X, PHOTO_POSITION_Y, PHOTO_POSITION_Z)
        )

    def _on_position_prete(self, reussi: bool) -> None:
        """La machine est en position, ou n'a pas pu y aller."""
        if not reussi and not self._confirmer_sans_machine(
            f"Mise en position impossible : {self._runner.last_error}"
        ):
            self._btn_capture.setEnabled(True)
            self._status_label.setText("Capture annulee.")
            return
        self._capturer_maintenant()

    def _confirmer_sans_machine(self, motif: str) -> bool:
        """Photographier quand même, sans garantie de cadrage ? « Non » par défaut.

        On ne bloque pas : travailler sans machine reste légitime (mise au point sur le
        PC de développement). Mais la photo sera prise là où la machine se trouve, et le
        dire vaut mieux que de le taire.
        """
        reponse = QMessageBox.question(
            self, "Photographier sans mise en position ?",
            f"{motif}\n\n"
            "La photo sera prise a la position actuelle de la machine. Sur le PoC, le "
            "plateau bouge avec le lit : le cadrage peut differer d'une photo a "
            "l'autre.\n\nPhotographier quand meme ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return reponse == QMessageBox.Yes

    def _capturer_maintenant(self) -> None:
        """La capture proprement dite, une fois la question de la position réglée."""
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
