# Mode démonstration (« showroom ») — release spéciale de soutenance
#
# Pourquoi cet écran existe
# -------------------------
# Pendant une soutenance, l'orateur parle et répond au jury : il ne peut pas en même
# temps conduire la machine écran par écran. Ce mode enchaîne donc TOUT SEUL, en boucle,
# le cycle que `screen_execution.py` fait dérouler à l'opérateur :
#
#     homing → position de prise de vue → photo → détection des zones →
#     sélection automatique des zones valides → dépose → photo de fin → pause → …
#
# Ce n'est PAS un second moteur de dépose. Tout ce qui touche la machine et la vision est
# repris tel quel du cycle manuel — le worker de dépose, la mise en position, le contrôle
# de format, le contrôle de course. Un deuxième moteur divergerait du premier, et c'est
# celui qu'on ne relit pas qui finit par être faux : ce projet l'a déjà vécu avec le choix
# d'homographie dupliqué entre deux écrans (lot C2bis).
#
# La seule chose que cet écran remplace, ce sont les DÉCISIONS de l'opérateur :
#
#   | Étape du cycle manuel        | Ici                                              |
#   |------------------------------|--------------------------------------------------|
#   | choix du fichier             | choisi une fois avant de démarrer (AIVC par défaut)|
#   | sélection des zones au doigt | toutes les zones valides, automatiquement          |
#   | modale de confirmation       | supprimée — elle attendrait un clic               |
#   | modale de progression        | remplacée par la barre intégrée à l'écran         |
#   | modale de bilan              | remplacée par le bandeau d'état                   |
#
# ⚠️ Pourquoi AUCUNE fenêtre modale ici : une modale attend un clic. En boucle
# automatique, elle arrêterait la démonstration à la première itération, exactement quand
# l'orateur a le dos tourné. C'est la contrainte qui a dicté toute la structure de ce
# fichier : un seul écran, tout l'état visible dessus, et des transitions déclenchées par
# des signaux plutôt que par des `exec_()`.
#
# ⚠️ Sûreté : le mode s'arrête de lui-même dans trois cas — un ARRÊT IMMÉDIAT (`M112`
# laisse Marlin hors service jusqu'au redémarrage : continuer la boucle n'aurait aucun
# sens), trois échecs consécutifs (une machine qui bat de l'aile devant un jury doit
# s'immobiliser, pas insister), et l'arrêt en douceur demandé par l'orateur.

import time

from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox,
    QSpinBox, QCheckBox, QProgressBar, QMessageBox,
)
from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal, pyqtSlot

from gui.screen_execution import (
    DepositWorker, PlateauSelectionView, controler_format_des_zones,
)
from gui.workers import PhotoPositionRunner
from modules.config import (
    DISPENSE_Z_HEIGHT_MM, MACHINE_Z_TRAVEL_MM,
    PHOTO_POSITION_X, PHOTO_POSITION_Y, PHOTO_POSITION_Z,
    MACHINE_TRAVEL_X_MAX_MM, MACHINE_TRAVEL_Y_MAX_MM, MACHINE_TRAVEL_Z_MAX_MM,
)
from modules.path_planner import (
    PathPlanner, check_machine_limits, format_limit_violations,
    sort_zones_for_deposit,
)
from modules.preparation import (
    list_preparations, load_preparation, product_name_from_path,
)
from modules.vision import VisionProcessor

# --- États de la boucle ---------------------------------------------------------------
# Un automate explicite plutôt qu'une poignée de booléens : à tout instant, une seule
# chose est en cours, et c'est cette valeur qui le dit. Les booléens indépendants
# (« en train de photographier » + « en train de déposer ») autorisent des combinaisons
# impossibles, et c'est là que se logent les doubles lancements sur le port série.
ETAT_ARRET = "arret"            # rien ne tourne — configuration modifiable
ETAT_POSITION = "position"      # homing + mise en position de prise de vue
ETAT_ANALYSE = "analyse"        # photo et détection des zones
ETAT_DEPOSE = "depose"          # la machine parcourt le plateau
ETAT_PHOTO_FIN = "photo_fin"    # retour en position de prise de vue et photo de fin
ETAT_ATTENTE = "attente"        # compte à rebours entre deux cycles

# Nombre d'échecs de suite au-delà duquel la boucle s'arrête d'elle-même.
# Un seul échec ne prouve rien (une main devant la caméra suffit) ; trois d'affilée
# signalent un problème que la boucle ne réglera pas en insistant.
MAX_ECHECS_CONSECUTIFS = 3

# Pause par défaut entre deux cycles, en secondes. Assez pour qu'un spectateur voie la
# photo de fin et que l'orateur puisse commenter, assez court pour ne pas créer un blanc.
PAUSE_DEFAUT_S = 10

# Produit présélectionné à l'ouverture de l'écran, s'il existe dans les préparations.
PRODUIT_PAR_DEFAUT = "AIVC"


class ScreenShowroom(QWidget):
    """Boucle de démonstration autonome : un bouton, puis plus rien à toucher."""

    back_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._machine = None
        self._camera = None
        self._vision = VisionProcessor()

        self._preparation = None
        self._etat = ETAT_ARRET
        # Arrêt « en douceur » : la boucle va au bout du cycle en cours puis s'arrête.
        # Distinct de l'arrêt immédiat, qui coupe les actionneurs — les deux existent
        # parce qu'ils répondent à deux situations opposées : « c'est fini, merci » et
        # « la machine part dans le décor ».
        self._arret_demande = False

        self._cycles_lances = 0
        self._cycles_reussis = 0
        self._echecs_consecutifs = 0
        self._depart_session = 0.0
        self._depart_cycle = 0.0
        self._zones_prevues: list = []

        # Deux runners distincts pour la mise en position de début et celle de fin.
        # Ils ne se croisent jamais, mais partager l'objet obligerait à débrancher puis
        # rebrancher son signal `done` entre les deux usages — la bascule qu'on oublie.
        self._runner_debut = PhotoPositionRunner(self)
        self._runner_debut.progress.connect(self._afficher_etat)
        self._runner_debut.done.connect(self._on_position_debut)
        self._runner_fin = PhotoPositionRunner(self)
        self._runner_fin.progress.connect(self._afficher_etat)
        self._runner_fin.done.connect(self._on_position_fin)

        self._thread_depose: QThread | None = None
        self._worker_depose = None
        # Résultat de la dépose, renseigné par les slots des signaux du worker et LU
        # seulement quand le thread est terminé. Voir `_on_thread_depose_fini`.
        self._resultat_depose: tuple = ("ok", "")

        self._chrono = QTimer(self)
        self._chrono.setInterval(1000)
        self._chrono.timeout.connect(self._tick_chrono)

        self._attente = QTimer(self)
        self._attente.setInterval(1000)
        self._attente.timeout.connect(self._tick_attente)
        self._secondes_restantes = 0
        self._message_attente = ""

        self._setup_ui()

    def set_machine(self, machine) -> None:
        self._machine = machine

    def set_camera(self, camera) -> None:
        self._camera = camera

    # ------------------------------------------------------------------ interface

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        titre = QLabel("Mode demonstration — cycle automatique en boucle")
        titre.setProperty("role", "title")
        titre.setAlignment(Qt.AlignCenter)
        layout.addWidget(titre)

        # --- Ligne de configuration (verrouillée pendant la boucle) ---
        config = QHBoxLayout()
        config.setSpacing(8)

        config.addWidget(QLabel("Plateau :"))
        self._combo = QComboBox()
        self._combo.setMinimumHeight(44)   # cible tactile de l'écran 7 pouces
        config.addWidget(self._combo, stretch=1)

        config.addWidget(QLabel("Pause (s) :"))
        self._spin_pause = QSpinBox()
        self._spin_pause.setRange(0, 300)
        self._spin_pause.setValue(PAUSE_DEFAUT_S)
        self._spin_pause.setMinimumHeight(44)
        config.addWidget(self._spin_pause)

        config.addWidget(QLabel("Cycles (0 = sans fin) :"))
        self._spin_cycles = QSpinBox()
        self._spin_cycles.setRange(0, 999)
        self._spin_cycles.setValue(0)
        self._spin_cycles.setMinimumHeight(44)
        config.addWidget(self._spin_cycles)

        layout.addLayout(config)

        # La dépose à blanc est cochée PAR DÉFAUT et c'est délibéré : la hauteur Z de la
        # pointe de seringue n'est toujours pas mesurée (action M3), donc une dépose
        # réelle en boucle, sans surveillance, planterait la buse dans les pièces.
        self._case_a_blanc = QCheckBox(
            "Depose a blanc (aucune extrusion, aucun mouvement en Z)"
        )
        self._case_a_blanc.setChecked(True)
        self._case_a_blanc.setMinimumHeight(36)
        layout.addWidget(self._case_a_blanc)

        # --- Vue du plateau ---
        # Le même widget que le cycle manuel : zones en vert, cordons reportés en orange.
        # Le clic n'est volontairement PAS branché — en démonstration, une sélection
        # modifiée par mégarde (ou par un membre du jury venu voir l'écran tactile de
        # près) changerait ce que la machine fait au cycle suivant.
        self._vue = PlateauSelectionView()
        layout.addWidget(self._vue, stretch=1)

        # --- Progression ---
        self._barre = QProgressBar()
        self._barre.setMinimum(0)
        self._barre.setMaximum(1000)   # en millièmes : la progression est une fraction
        self._barre.setValue(0)
        self._barre.setMinimumHeight(30)
        self._barre.setFormat("%p%")
        layout.addWidget(self._barre)

        self._compteurs = QLabel("")
        layout.addWidget(self._compteurs)

        self._status = QLabel("Choisir le plateau, puis demarrer.")
        self._status.setProperty("role", "status")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        # --- Boutons ---
        boutons = QHBoxLayout()
        boutons.setSpacing(8)

        self._btn_demarrer = QPushButton("Demarrer la boucle")
        self._btn_demarrer.setProperty("role", "success")
        self._btn_demarrer.clicked.connect(self.demarrer)
        boutons.addWidget(self._btn_demarrer)

        self._btn_arret_doux = QPushButton("Arreter apres ce cycle")
        self._btn_arret_doux.setProperty("role", "secondary")
        self._btn_arret_doux.setEnabled(False)
        self._btn_arret_doux.clicked.connect(self.arret_en_douceur)
        boutons.addWidget(self._btn_arret_doux)

        self._btn_arret_dur = QPushButton("ARRET IMMEDIAT")
        self._btn_arret_dur.setProperty("role", "danger")
        self._btn_arret_dur.setEnabled(False)
        self._btn_arret_dur.clicked.connect(self._on_arret_immediat)
        boutons.addWidget(self._btn_arret_dur)

        self._btn_retour = QPushButton("Retour")
        self._btn_retour.setProperty("role", "secondary")
        self._btn_retour.clicked.connect(self.back_requested)
        boutons.addWidget(self._btn_retour)

        layout.addLayout(boutons)

    def refresh_preparations(self) -> None:
        """Remplir la liste des plateaux, en présélectionnant le produit de démonstration.

        Appelée à chaque entrée sur l'écran plutôt qu'une fois pour toutes : un plateau
        peut avoir été enregistré depuis, et découvrir la veille au soir que la liste est
        figée serait une mauvaise surprise.
        """
        self._combo.clear()
        for chemin in list_preparations():
            self._combo.addItem(product_name_from_path(chemin), chemin)

        if self._combo.count() == 0:
            self._status.setText(
                "Aucun plateau enregistre. Creer et enregistrer un plateau d'abord."
            )
            self._btn_demarrer.setEnabled(False)
            return

        self._btn_demarrer.setEnabled(True)
        # Présélection du produit de démonstration s'il existe, sinon la première entrée.
        # Recherche insensible à la casse : le nom du produit est saisi à la main.
        for index in range(self._combo.count()):
            if self._combo.itemText(index).upper() == PRODUIT_PAR_DEFAUT.upper():
                self._combo.setCurrentIndex(index)
                break

    def _verrouiller_configuration(self, en_marche: bool) -> None:
        """Griser ce qui ne doit plus bouger pendant que la boucle tourne.

        Changer de plateau ou décocher la dépose à blanc en cours de route ne serait pris
        en compte qu'au cycle suivant : l'écran mentirait sur ce que fait la machine à
        l'instant où on le lit.
        """
        for widget in (self._combo, self._spin_pause, self._spin_cycles,
                       self._case_a_blanc, self._btn_demarrer, self._btn_retour):
            widget.setEnabled(not en_marche)
        self._btn_arret_doux.setEnabled(en_marche)
        self._btn_arret_dur.setEnabled(en_marche)

    # ------------------------------------------------------------------ démarrage

    def demarrer(self) -> None:
        """Vérifie que tout est en place, puis lance le premier cycle."""
        if self._etat != ETAT_ARRET:
            return   # déjà en marche : un double appui ne doit pas lancer deux boucles

        if self._machine is None:
            self._status.setText("Aucune machine configuree : boucle impossible.")
            return
        if self._camera is None:
            self._status.setText("Aucune camera disponible : boucle impossible.")
            return
        if self._combo.count() == 0:
            self._status.setText("Aucun plateau enregistre.")
            return

        chemin = self._combo.currentData()
        try:
            self._preparation = load_preparation(chemin)
        except (OSError, ValueError, KeyError) as e:
            # Un fichier illisible se dit et n'empêche pas de réessayer avec un autre :
            # ce sont des coordonnées de dépose, on ne part pas avec une lecture partielle.
            self._status.setText(f"Plateau illisible : {e}")
            return

        if not [c for c in self._preparation.cordons if c.is_valid]:
            self._status.setText(
                "Ce plateau ne contient aucun cordon tracable : il n'y a rien a deposer."
            )
            return

        self._arret_demande = False
        self._cycles_lances = 0
        self._cycles_reussis = 0
        self._echecs_consecutifs = 0
        self._depart_session = time.monotonic()
        self._verrouiller_configuration(True)
        self._chrono.start()
        self._cycle_suivant()

    def _cycle_suivant(self) -> None:
        """Étape 1 d'un cycle : homing et mise en position de prise de vue."""
        if self._arret_demande:
            self._terminer("Boucle arretee a la demande de l'operateur.")
            return

        maximum = self._spin_cycles.value()
        if maximum and self._cycles_lances >= maximum:
            self._terminer(f"Nombre de cycles demande atteint ({maximum}).")
            return

        # Garde-fou anti-blocage : `PhotoPositionRunner.start()` ne fait RIEN si son
        # thread précédent tourne encore, et le ferait en silence — la boucle attendrait
        # alors un signal qui n'arrivera jamais. En temps normal les deux runners sont au
        # repos ici ; on réessaie plutôt que de lancer dans le vide.
        if self._runner_debut.busy or self._runner_fin.busy:
            self._afficher_etat("Mise en position precedente encore en cours...")
            QTimer.singleShot(1000, self._cycle_suivant)
            return

        self._cycles_lances += 1
        self._depart_cycle = time.monotonic()
        self._etat = ETAT_POSITION
        self._barre.setValue(0)
        self._afficher_etat("Homing et mise en position de prise de vue (30-60 s)...")
        self._runner_debut.start(
            self._machine, (PHOTO_POSITION_X, PHOTO_POSITION_Y, PHOTO_POSITION_Z)
        )

    # ------------------------------------------------------------------ photo et analyse

    @pyqtSlot(bool)
    def _on_position_debut(self, reussi: bool) -> None:
        if self._etat != ETAT_POSITION:
            return   # arrêt demandé pendant la mise en position : ne pas enchaîner
        if not reussi:
            self._echec(f"Mise en position impossible : {self._runner_debut.last_error}")
            return

        self._etat = ETAT_ANALYSE
        self._afficher_etat("Capture et analyse du plateau...")

        try:
            image = self._camera.capture()
        except Exception as e:
            self._echec(f"Capture impossible : {e}")
            return

        zones = self.analyser(image)
        if not zones:
            # Pas un plantage : un plateau vide, mal cadré ou masqué donne ce résultat.
            # On le dit, on attend, et on retente — c'est ce que ferait l'opérateur.
            self._echec("Aucune zone exploitable sur cette photo.")
            return

        self._lancer_depose(zones)

    def analyser(self, image) -> list:
        """Détecte les zones sur une photo et retient celles qui sont déposables.

        Méthode publique et rendant la liste retenue : c'est le point d'entrée des tests,
        qui l'appellent avec une image de synthèse, sans caméra ni machine.

        La sélection est ici AUTOMATIQUE — toutes les zones valides — là où le cycle
        manuel la laisse à l'opérateur, qui seul sait où il a posé un produit. En
        démonstration, l'hypothèse assumée est que le plateau est garni avant de lancer
        la boucle ; une zone vide ne fait perdre que du temps, la dépose à blanc
        n'extrudant rien.
        """
        marqueurs = self._vision.detect_markers(image)
        try:
            reference = self._vision.compute_plateau_reference(marqueurs)
        except ValueError:
            self._vue.set_plateau(image, [], None, [])
            self._afficher_etat(
                "Marqueurs du plateau insuffisants (2 minimum) : cadrage a verifier."
            )
            return []

        homography = reference.homography
        layout = self._vision.detect_deposit_zones(marqueurs, homography)
        # Même contrôle de format que le cycle manuel : les cordons ont été tracés pour
        # un produit d'une taille donnée, ils déborderaient sur un autre format.
        controler_format_des_zones(
            layout.zones,
            self._preparation.reference_zone if self._preparation else None,
        )
        zones_retenues = [z for z in layout.zones if z.is_valid]

        cordons = self._preparation.cordons if self._preparation else []
        self._vue.set_plateau(image, layout.zones, homography, cordons)
        self._vue.set_selection({z.id_top_left for z in zones_retenues})
        return zones_retenues

    # ------------------------------------------------------------------ dépose

    def _lancer_depose(self, zones: list) -> None:
        """Étape 2 d'un cycle : calcul de la trajectoire, contrôle de course, exécution."""
        settings = self._preparation.settings
        planner = PathPlanner.from_settings(
            settings,
            z_dispense_mm=DISPENSE_Z_HEIGHT_MM,
            z_travel_mm=MACHINE_Z_TRAVEL_MM,
            dry_run=self._case_a_blanc.isChecked(),
        )
        steps = planner.generate_plateau_path(
            zones, self._preparation.cordons, settings.row_tolerance_mm
        )

        # ⚠️ AVANT le premier mouvement. Marlin ne refuse pas une coordonnée hors course :
        # il la rogne EN SILENCE. En démonstration, personne ne surveille l'écran — une
        # dépose déformée passerait pour le résultat normal du logiciel.
        violations = check_machine_limits(
            steps,
            x_max=MACHINE_TRAVEL_X_MAX_MM,
            y_max=MACHINE_TRAVEL_Y_MAX_MM,
            z_max=MACHINE_TRAVEL_Z_MAX_MM,
        )
        if violations:
            self._echec(format_limit_violations(violations))
            return

        self._zones_prevues = [z.id_top_left for z in sort_zones_for_deposit(zones)]
        self._etat = ETAT_DEPOSE
        self._afficher_etat(f"Depose de {len(self._zones_prevues)} zone(s)...")

        # ⚠️ Spécifique à la boucle : un thread de dépose est créé à CHAQUE cycle, et
        # remplacer `self._thread_depose` lâche la dernière référence Python sur le
        # précédent. S'il n'était pas complètement sorti, le ramasse-miettes détruirait
        # un QThread encore vivant — le défaut déjà rencontré sur le worker de homing le
        # 2026-07-01, ici multiplié par le nombre de cycles. `wait()` sur un thread déjà
        # terminé rend la main immédiatement : le coût est nul, la garantie est réelle.
        if self._thread_depose is not None:
            self._thread_depose.wait(5000)

        self._thread_depose = QThread()
        self._worker_depose = DepositWorker(
            self._machine, steps,
            travel_speed=settings.travel_speed_mm_min,
            extrusion_speed=settings.extrusion_speed_mm_min,
        )
        self._worker_depose.moveToThread(self._thread_depose)
        self._thread_depose.started.connect(self._worker_depose.run)
        self._worker_depose.progress.connect(self._on_progress)
        self._worker_depose.state_changed.connect(self._afficher_etat)
        self._worker_depose.finished.connect(lambda: self._noter_resultat("ok", ""))
        self._worker_depose.stopped.connect(lambda: self._noter_resultat("stop", ""))
        self._worker_depose.error_occurred.connect(
            lambda msg: self._noter_resultat("erreur", msg)
        )
        self._worker_depose.finished.connect(self._thread_depose.quit)
        self._worker_depose.stopped.connect(self._thread_depose.quit)
        self._worker_depose.error_occurred.connect(self._thread_depose.quit)
        # La suite est branchée sur la fin du THREAD et non sur celle du worker : au
        # moment où le worker émet, son thread tourne encore, et enchaîner sur une
        # nouvelle connexion série depuis là ouvrirait le port pendant que l'ancien
        # propriétaire le referme.
        self._thread_depose.finished.connect(self._on_thread_depose_fini)
        self._thread_depose.start()

    def _noter_resultat(self, statut: str, message: str) -> None:
        self._resultat_depose = (statut, message)

    def _on_progress(self, fraction: float, zones_terminees: int) -> None:
        self._barre.setValue(int(max(0.0, min(1.0, fraction)) * 1000))
        self._afficher_etat(
            f"Depose : zone {min(zones_terminees + 1, len(self._zones_prevues))} "
            f"sur {len(self._zones_prevues)}"
        )

    @pyqtSlot()
    def _on_thread_depose_fini(self) -> None:
        """La dépose est terminée — bien, mal, ou interrompue."""
        statut, message = self._resultat_depose

        if statut == "erreur":
            self._echec(f"Erreur pendant la depose : {message}")
            return

        if statut == "stop":
            # `emergency_stop()` a envoyé `M112` : Marlin est hors service tant qu'il n'a
            # pas été redémarré. Relancer un cycle échouerait à coup sûr, et l'écran
            # afficherait une cascade d'erreurs devant le jury.
            self._terminer(
                "ARRET IMMEDIAT : la machine doit etre redemarree avant tout nouveau "
                "cycle."
            )
            return

        self._cycles_reussis += 1
        self._echecs_consecutifs = 0
        self._barre.setValue(1000)

        # Photo de fin, comme au sous-lot D3 : la machine revient en position de prise de
        # vue pour que la vue de fin soit cadrée comme celle du début.
        self._etat = ETAT_PHOTO_FIN
        self._afficher_etat("Retour en position de prise de vue...")
        self._runner_fin.start(
            self._machine, (PHOTO_POSITION_X, PHOTO_POSITION_Y, PHOTO_POSITION_Z)
        )

    @pyqtSlot(bool)
    def _on_position_fin(self, reussi: bool) -> None:
        """Photo de fin puis enchaînement — un échec ici n'invalide pas le cycle."""
        if self._etat != ETAT_PHOTO_FIN:
            return

        if reussi and self._camera is not None:
            try:
                # Affichée sans habillage : les zones dessinées seraient celles de la
                # photo PRÉCÉDENTE, donc un repère qui n'est pas celui de cette image.
                self._vue.set_plateau(self._camera.capture(), [], None, [])
            except Exception:
                pass   # une photo ratée ne doit pas interrompre la démonstration

        self._attendre_puis_recommencer(
            f"Cycle {self._cycles_lances} termine."
        )

    # ------------------------------------------------------------------ enchaînement

    def _attendre_puis_recommencer(self, message: str) -> None:
        """Pause entre deux cycles, avec compte à rebours visible."""
        if self._arret_demande:
            self._terminer("Boucle arretee a la demande de l'operateur.")
            return

        self._etat = ETAT_ATTENTE
        self._secondes_restantes = self._spin_pause.value()
        self._message_attente = message

        if self._secondes_restantes <= 0:
            # Enchaînement immédiat, mais en repassant par la boucle d'évènements Qt
            # (`singleShot(0)`) plutôt qu'en appelant directement : un appel direct
            # empilerait les cycles dans la pile d'appels de Python, qui finirait par
            # déborder après quelques centaines d'itérations — soit après une nuit de
            # démonstration.
            QTimer.singleShot(0, self._cycle_suivant)
            return

        self._afficher_etat(f"{message} Prochain cycle dans {self._secondes_restantes} s.")
        self._attente.start()

    def _tick_attente(self) -> None:
        self._secondes_restantes -= 1
        if self._secondes_restantes <= 0:
            self._attente.stop()
            self._cycle_suivant()
            return
        self._afficher_etat(
            f"{self._message_attente} Prochain cycle dans {self._secondes_restantes} s."
        )

    def _echec(self, message: str) -> None:
        """Un cycle a échoué : on compte, on prévient, et on retente — jusqu'à un point.

        Retenter est le bon comportement pour les causes passagères, qui sont les plus
        fréquentes en salle : quelqu'un passe devant la caméra, un reflet, un plateau
        décalé. Mais insister indéfiniment sur une cause durable — machine débranchée,
        seringue absente — donnerait une machine qui s'agite en vain devant un jury.
        """
        self._echecs_consecutifs += 1
        if self._echecs_consecutifs >= MAX_ECHECS_CONSECUTIFS:
            self._terminer(
                f"{message}\n{MAX_ECHECS_CONSECUTIFS} cycles de suite ont echoue : "
                f"boucle arretee. Verifier la machine, la camera et le plateau."
            )
            return
        self._attendre_puis_recommencer(
            f"Cycle {self._cycles_lances} abandonne — {message}"
        )

    # ------------------------------------------------------------------ arrêts

    def arret_en_douceur(self) -> None:
        """Terminer proprement : le cycle en cours va à son terme, puis la boucle s'arrête.

        C'est l'arrêt normal en fin de démonstration. Il ne touche pas aux actionneurs,
        donc la machine reste utilisable ensuite — contrairement à l'arrêt immédiat.
        """
        self._arret_demande = True
        self._btn_arret_doux.setEnabled(False)

        if self._etat == ETAT_ATTENTE:
            # Rien ne tourne : inutile de faire patienter jusqu'au bout du compte à rebours
            self._attente.stop()
            self._terminer("Boucle arretee a la demande de l'operateur.")
            return

        self._afficher_etat(
            "Arret demande : la boucle s'arretera a la fin du cycle en cours."
        )

    def _on_arret_immediat(self) -> None:
        """Bouton rouge : demande confirmation, car l'arrêt est irréversible."""
        reponse = QMessageBox.question(
            self, "Arret immediat ?",
            "Cela coupe tous les actionneurs et interrompt le plateau en cours.\n"
            "La machine devra etre REDEMARREE avant le prochain cycle.\n\n"
            "Pour terminer proprement, utiliser plutot « Arreter apres ce cycle ».\n\n"
            "Arreter vraiment ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reponse == QMessageBox.Yes:
            self.arret_immediat()

    def arret_immediat(self) -> None:
        """Coupe les actionneurs tout de suite, puis arrête la boucle.

        `emergency_stop()` est appelé **hors du thread de dépose** parce qu'il écrit
        directement sur le port série sans attendre de « ok » : le faire faire au worker
        reviendrait à attendre la fin du step en cours, ce qui n'est pas un arrêt.
        """
        self._arret_demande = True

        if self._machine is not None and self._machine.is_connected():
            try:
                self._machine.emergency_stop()
            except Exception:
                pass   # une machine déjà muette ne doit pas masquer l'arrêt de la boucle

        if self._worker_depose is not None and self._etat == ETAT_DEPOSE:
            # La suite est prise en charge par `_on_thread_depose_fini`, qui verra le
            # statut « stop » et terminera la boucle avec le bon message.
            self._worker_depose.request_stop()
            return

        self._attente.stop()
        self._terminer(
            "ARRET IMMEDIAT : la machine doit etre redemarree avant tout nouveau cycle."
        )

    def shutdown(self) -> None:
        """Tout arrêter sans rien demander — appelé à la fermeture de l'application.

        Fermer la fenêtre pendant que la boucle tourne laisserait le thread de dépose
        continuer, en retirant à l'opérateur l'accès au bouton d'arrêt : c'est le trou de
        sécurité connu du projet (dette L2, trou #1), qu'on ne va pas rouvrir ici.
        """
        if self._etat == ETAT_ARRET:
            return
        self.arret_immediat()
        # Attendre la fin effective du thread : sans cela, l'interpréteur Python peut
        # détruire le worker pendant que le thread système tourne encore.
        if self._thread_depose is not None and self._thread_depose.isRunning():
            self._thread_depose.quit()
            self._thread_depose.wait(5000)

    def _terminer(self, raison: str) -> None:
        """Fin de boucle, quelle qu'en soit la cause : tout remettre en état de repos."""
        self._attente.stop()
        self._chrono.stop()
        self._etat = ETAT_ARRET
        self._verrouiller_configuration(False)
        duree = int(time.monotonic() - self._depart_session)
        self._afficher_etat(
            f"{raison}\nBilan : {self._cycles_reussis} cycle(s) reussi(s) sur "
            f"{self._cycles_lances} lance(s), en {duree // 60} min {duree % 60:02d} s."
        )

    # ------------------------------------------------------------------ affichage

    def _afficher_etat(self, message: str) -> None:
        self._status.setText(message)
        self._rafraichir_compteurs()

    def _tick_chrono(self) -> None:
        self._rafraichir_compteurs()

    def _rafraichir_compteurs(self) -> None:
        """Bandeau permanent : où en est-on, depuis combien de temps.

        C'est la ligne que l'orateur regarde d'un coup d'œil en parlant, et celle qu'un
        membre du jury lit sans explication. Elle est donc mise à jour à chaque seconde
        et à chaque changement d'état, pas seulement en fin de cycle.
        """
        if self._etat == ETAT_ARRET:
            self._compteurs.setText(
                f"En attente — {self._cycles_reussis} cycle(s) reussi(s)."
            )
            return
        cycle = int(time.monotonic() - self._depart_cycle)
        total = int(time.monotonic() - self._depart_session)
        self._compteurs.setText(
            f"Cycle {self._cycles_lances} · {self._cycles_reussis} reussi(s) · "
            f"cycle en cours {cycle // 60}:{cycle % 60:02d} · "
            f"total {total // 60}:{total % 60:02d}"
        )
