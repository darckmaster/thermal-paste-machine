# Tests du cycle de dépose multi-zones (lot D2) — gui/screen_execution.py
#
# Deux familles, volontairement séparées :
#
#   - le WORKER de dépose, éprouvé sans Qt ni matériel avec une machine simulée. C'est
#     lui qui pilote les actionneurs : sa logique de pause, d'arrêt et de suivi doit
#     être vérifiable sans rien allumer et sans boucle d'évènements.
#   - l'ÉCRAN, piloté par pytest-qt avec une image de synthèse. `analyser()` est publique
#     précisément pour ça — aucune caméra n'est nécessaire.
#
# Ce qu'ils ne remplacent pas : l'essai réel sur la machine. Un test peut dire que la
# trajectoire est juste, pas que la buse arrive au bon endroit — le sens réel des axes
# reste l'action M4.

import cv2
import numpy as np
import pytest
from PyQt5.QtWidgets import QLabel

from gui.dialogs import (
    ConfirmDepositDialog, DepositProgressDialog, DepositSummaryDialog,
)
from gui.screen_execution import DepositWorker, ScreenExecution
from modules.preparation import Cordon, Preparation, Settings
from modules.vision import DepositZone


# ------------------------------------------------------------------ plateau de synthèse

_LARGEUR = 900
_HAUTEUR = 700
_TAILLE_MARQUEUR = 60


def _coller_marqueur(image: np.ndarray, marker_id: int, cx: int, cy: int) -> None:
    """Colle un marqueur ArUco RÉEL centré en (cx, cy).

    De vrais marqueurs et non des mocks : la détection OpenCV tourne donc pour de bon,
    ce qui fait de ces tests une vérification de la chaîne complète.
    """
    dictionnaire = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    motif = cv2.aruco.generateImageMarker(dictionnaire, marker_id, _TAILLE_MARQUEUR)
    motif_bgr = cv2.cvtColor(motif, cv2.COLOR_GRAY2BGR)
    demi = _TAILLE_MARQUEUR // 2
    image[cy - demi:cy + demi, cx - demi:cx + demi] = motif_bgr


def _plateau_synthetique(zones: dict) -> np.ndarray:
    image = np.full((_HAUTEUR, _LARGEUR, 3), 240, dtype=np.uint8)
    for marker_id, (cx, cy) in {3: (80, 80), 0: (820, 80),
                                1: (820, 620), 2: (80, 620)}.items():
        _coller_marqueur(image, marker_id, cx, cy)
    for id_tl, (p1, p2) in zones.items():
        _coller_marqueur(image, id_tl, p1[0], p1[1])
        _coller_marqueur(image, id_tl + 1, p2[0], p2[1])
    return image


def _deux_zones() -> dict:
    return {
        4: ((200, 200), (360, 300)),
        6: ((500, 260), (660, 360)),
    }


def _preparation() -> Preparation:
    return Preparation(
        product_name="Calculateur test",
        cordons=[Cordon([(5.0, 5.0), (25.0, 5.0), (25.0, 15.0)])],
        settings=Settings(travel_speed_mm_min=1000.0, extrusion_speed_mm_min=100.0),
    )


# ===========================================================================
# Machine simulée
# ===========================================================================

class MachineSimulee:
    """Une machine qui note ce qu'on lui demande, au lieu de le faire.

    Suffit à éprouver le worker : ce qui nous intéresse est la SÉQUENCE d'appels et la
    façon dont la pause et l'arrêt l'interrompent, pas le G-code produit — celui-ci est
    déjà couvert par les tests de `machine.py`.
    """

    def __init__(self) -> None:
        self.appels: list = []
        self.connecte = False

    def connect(self) -> None:
        self.connecte = True
        self.appels.append(("connect",))

    def disconnect(self) -> None:
        self.connecte = False
        self.appels.append(("disconnect",))

    def is_connected(self) -> bool:
        return self.connecte

    def home(self) -> None:
        self.appels.append(("home",))

    def move_to(self, x, y, z) -> None:
        self.appels.append(("move_to", round(x, 3), round(y, 3), round(z, 3)))

    def move_z(self, z) -> None:
        self.appels.append(("move_z", round(z, 3)))

    def move_and_dispense(self, x, y, amount, feedrate=None) -> None:
        self.appels.append(("dispense", round(x, 3), round(y, 3), amount, feedrate))

    def dispense(self, amount, feedrate=None) -> None:
        self.appels.append(("prime", amount, feedrate))

    def emergency_stop(self) -> None:
        self.appels.append(("emergency_stop",))


def _steps(nb_zones: int = 2) -> list:
    """Une trajectoire minimale mais réaliste : par zone, un passage au zéro et un tracé."""
    steps = []
    for index in range(nb_zones):
        zone_id = 4 + 2 * index
        base = 100.0 * index
        steps.append({"type": "travel", "x": base, "y": 0.0, "z": 5.0,
                      "amount": 0.0, "zone": zone_id})
        steps.append({"type": "travel", "x": base, "y": 0.0, "z": 1.0,
                      "amount": 0.0, "zone": zone_id})
        steps.append({"type": "dispense", "x": base + 20.0, "y": 0.0, "z": 1.0,
                      "amount": 2.0, "zone": zone_id})
        steps.append({"type": "travel", "x": base + 20.0, "y": 0.0, "z": 5.0,
                      "amount": 0.0, "zone": zone_id})
    return steps


def _worker(machine, steps=None) -> DepositWorker:
    return DepositWorker(machine, steps if steps is not None else _steps(),
                         travel_speed=1000.0, extrusion_speed=100.0)


# ===========================================================================
# Le worker de dépose
# ===========================================================================

def test_le_worker_se_connecte_home_puis_execute_dans_cet_ordre():
    """Le homing précède toujours la dépose : sans lui, la position est inconnue."""
    machine = MachineSimulee()
    worker = _worker(machine)
    worker.run()

    types = [appel[0] for appel in machine.appels]
    assert types[0] == "connect"
    assert types[1] == "home"
    assert "dispense" in types
    assert types[-1] == "disconnect"


def test_le_worker_se_degage_en_z_avant_tout_deplacement_horizontal():
    """Constaté sur la machine le 2026-08-04 — et c'est un défaut, pas un réglage.

    `Machine.move_to()` envoie `G1 X Y` PUIS `G1 Z`. Juste après un homing, la buse est
    à la hauteur du homing : sans montée préalable, le premier step du parcours
    traverserait tout le plateau à cette hauteur avant de monter. En dépose à blanc la
    marge est trop faible, et en dépose réelle la buse balaierait à Z=0 avant de monter
    à la hauteur de transit.

    Le test vérifie l'ORDRE : aucun déplacement horizontal ne doit précéder la montée.
    """
    machine = MachineSimulee()
    worker = _worker(machine)
    worker.run()

    types = [appel[0] for appel in machine.appels]
    index_montee = types.index("move_z")
    index_premier_xy = min(
        i for i, t in enumerate(types) if t in ("move_to", "dispense")
    )

    assert types.index("home") < index_montee, "se degager avant le homing n'a pas de sens"
    assert index_montee < index_premier_xy, (
        "la buse s'est deplacee horizontalement avant de se degager en Z"
    )
    # La montée vise bien la hauteur à laquelle le parcours commence
    assert machine.appels[index_montee] == ("move_z", 5.0)


def test_le_worker_declare_chaque_zone_terminee_une_fois():
    """Le bilan de fin repose là-dessus : une zone comptée deux fois le fausserait."""
    machine = MachineSimulee()
    worker = _worker(machine)
    faites = []
    worker.zone_done.connect(faites.append)

    worker.run()

    assert faites == [4, 6]


def test_la_progression_croit_et_atteint_le_maximum():
    """La barre ne doit ni reculer, ni s'arrêter avant la fin."""
    machine = MachineSimulee()
    worker = _worker(machine)
    fractions = []
    worker.progress.connect(lambda f, z: fractions.append(f))

    worker.run()

    assert fractions == sorted(fractions), "la progression ne doit jamais reculer"
    assert fractions[-1] == pytest.approx(1.0)


def test_la_progression_suit_le_chemin_et_non_le_nombre_de_steps():
    """DÉCISION D13 — un tracé de 80 mm et un déplacement de 2 mm ne comptent pas pareil.

    Une progression en nombre de steps avancerait par à-coups et mentirait sur le temps
    restant. Ici, un long segment doit faire bondir la barre bien plus qu'un court.
    """
    steps = [
        {"type": "travel", "x": 0.0, "y": 0.0, "z": 5.0, "amount": 0.0, "zone": 4},
        {"type": "travel", "x": 2.0, "y": 0.0, "z": 5.0, "amount": 0.0, "zone": 4},
        {"type": "dispense", "x": 82.0, "y": 0.0, "z": 1.0, "amount": 8.0, "zone": 4},
    ]
    worker = _worker(MachineSimulee(), steps)
    fractions = []
    worker.progress.connect(lambda f, z: fractions.append(f))

    worker.run()

    # 2 mm puis 80 mm : après le petit déplacement, on est loin sous la moitié
    assert fractions[1] == pytest.approx(2.0 / 82.0)
    assert fractions[2] == pytest.approx(1.0)


def test_l_arret_interrompt_la_sequence_et_ne_declare_pas_la_zone_finie():
    """Une zone interrompue ne doit PAS figurer comme déposée dans le bilan.

    C'est tout l'intérêt du bilan après arrêt : dire quelles pièces ont réellement reçu
    de la pâte. La compter comme faite serait pire que de ne rien dire.
    """
    machine = MachineSimulee()
    worker = _worker(machine)
    faites = []
    worker.zone_done.connect(faites.append)
    arrete = []
    worker.stopped.connect(lambda: arrete.append(True))
    fini = []
    worker.finished.connect(lambda: fini.append(True))

    # Arrêter dès le premier step exécuté
    worker.progress.connect(lambda f, z: worker.request_stop())
    worker.run()

    assert arrete == [True], "l'arret doit emettre stopped, pas finished"
    assert fini == []
    assert 6 not in faites, "la zone jamais atteinte ne peut pas etre declaree faite"


def test_l_arret_pendant_une_pause_prend_effet():
    """Cas réel : l'opérateur met en pause, constate un problème, puis arrête.

    Le test porte sur le COMPORTEMENT — le worker doit sortir sans rien déposer — et non
    sur la ligne qui le produit. C'est délibéré : le mécanisme réel est la condition de
    la boucle d'attente, pas la levée de pause dans `request_stop()` qui n'en est qu'une
    redondance. Un test qui viserait cette ligne-là passerait au vert en laissant la
    protection tomber si la boucle changeait.

    Ce test ne doit surtout pas boucler indéfiniment : sur une machine qui bouge, un
    bouton d'arrêt qui ne répond pas est un problème de sécurité, pas de confort.
    """
    machine = MachineSimulee()
    worker = _worker(machine)
    worker.set_paused(True)
    worker.request_stop()

    worker.run()   # ne doit pas boucler indéfiniment

    types = [appel[0] for appel in machine.appels]
    assert "dispense" not in types


def test_la_vitesse_de_deplacement_de_la_preparation_atteint_la_machine():
    """Les deux vitesses de Settings doivent arriver jusqu'au G-code.

    Sans cela, elles ne serviraient qu'au calcul de la quantité : la buse avancerait à la
    vitesse configurée pour la machine, et le cordon n'aurait pas l'épaisseur demandée —
    puisque celle-ci vient du RAPPORT des deux vitesses.
    """
    machine = MachineSimulee()
    worker = DepositWorker(machine, _steps(1), travel_speed=777.0,
                           extrusion_speed=88.0)
    worker.run()

    deposes = [a for a in machine.appels if a[0] == "dispense"]
    assert deposes, "la sequence de test contient une depose"
    assert all(a[4] == 777.0 for a in deposes)


def test_l_amorcage_passe_par_une_extrusion_sans_deplacement():
    steps = [
        {"type": "travel", "x": 0.0, "y": 0.0, "z": 1.0, "amount": 0.0, "zone": 4},
        {"type": "prime", "x": 0.0, "y": 0.0, "z": 1.0, "amount": 2.5, "zone": 4},
    ]
    machine = MachineSimulee()
    worker = DepositWorker(machine, steps, travel_speed=1000.0, extrusion_speed=60.0)
    worker.run()

    assert ("prime", 2.5, 60.0) in machine.appels


def test_la_machine_est_deconnectee_meme_si_un_step_echoue():
    """Laisser le port ouvert après une erreur bloquerait le cycle suivant."""
    class MachineQuiCasse(MachineSimulee):
        def move_to(self, x, y, z):
            raise RuntimeError("cable debranche")

    machine = MachineQuiCasse()
    worker = _worker(machine)
    erreurs = []
    worker.error_occurred.connect(erreurs.append)

    worker.run()

    assert erreurs, "l'erreur doit etre remontee a l'interface"
    assert ("disconnect",) in machine.appels
    assert not machine.connecte


def test_une_machine_injoignable_ne_fait_pas_planter_le_cycle():
    class MachineAbsente(MachineSimulee):
        def connect(self):
            raise RuntimeError("port introuvable")

    worker = _worker(MachineAbsente())
    erreurs = []
    worker.error_occurred.connect(erreurs.append)

    worker.run()

    assert len(erreurs) == 1
    assert "injoignable" in erreurs[0] or "indisponible" in erreurs[0]


# ===========================================================================
# La vue de sélection
# ===========================================================================

@pytest.fixture
def ecran(qtbot) -> ScreenExecution:
    widget = ScreenExecution()
    qtbot.addWidget(widget)
    widget._preparation = _preparation()
    return widget


def test_les_zones_sont_detectees_et_rien_n_est_selectionne_au_depart(ecran) -> None:
    """DÉCISION D10 — la sélection est un acte délibéré.

    Déposer sur une zone vide gaspille de la pâte et salit le plateau : présélectionner
    ferait de l'oubli de décocher une erreur silencieuse.
    """
    ecran.analyser(_plateau_synthetique(_deux_zones()))

    assert len(ecran._zones) == 2
    assert ecran._selection == set()
    assert not ecran._btn_valider.isEnabled()


def test_un_clic_selectionne_un_second_deselectionne(ecran) -> None:
    ecran.analyser(_plateau_synthetique(_deux_zones()))
    zone = ecran._zones[0]

    ecran._on_zone_toggled(zone)
    assert ecran._selection == {zone.id_top_left}
    assert ecran._btn_valider.isEnabled()

    ecran._on_zone_toggled(zone)
    assert ecran._selection == set()
    assert not ecran._btn_valider.isEnabled()


def test_tout_selectionner_puis_tout_enlever(ecran) -> None:
    ecran.analyser(_plateau_synthetique(_deux_zones()))

    ecran._on_tout_selectionner()
    assert len(ecran._selection) == 2

    ecran._on_tout_selectionner()
    assert ecran._selection == set()


def test_les_cordons_n_apparaissent_que_dans_les_zones_selectionnees(ecran) -> None:
    """Test de l'EFFET VISIBLE, pas seulement de la cause.

    L'opérateur doit voir ce qui va être déposé, et où. On compte donc les pixels
    orange — la couleur des cordons — avant et après sélection. Vérifier l'état interne
    ne dirait rien de ce qu'il y a réellement à l'écran.
    """
    ecran.analyser(_plateau_synthetique(_deux_zones()))
    vue = ecran._vue

    def pixels_orange(image) -> int:
        # Orange BGR (0, 160, 255) : bleu faible, rouge fort
        return int(np.sum(
            (image[:, :, 0] < 80) & (image[:, :, 1] > 110)
            & (image[:, :, 1] < 210) & (image[:, :, 2] > 200)
        ))

    avant = pixels_orange(vue._image_rendue)
    ecran._on_zone_toggled(ecran._zones[0])
    apres = pixels_orange(vue._image_rendue)

    assert avant == 0, "aucun cordon ne doit s'afficher tant que rien n'est selectionne"
    assert apres > 0, "les cordons de la zone selectionnee doivent apparaitre"


def test_un_clic_hors_zone_ne_selectionne_rien(ecran) -> None:
    ecran.analyser(_plateau_synthetique(_deux_zones()))

    # Un coin de l'image, loin de toute zone
    assert ecran._vue.zone_at_pixel(10.0, 10.0) is None


def test_un_clic_dans_une_zone_rend_cette_zone(ecran) -> None:
    """La correspondance clic → zone doit marcher, sinon rien n'est sélectionnable."""
    ecran.analyser(_plateau_synthetique(_deux_zones()))

    # Centre de la première zone, reprojeté en pixels depuis les mm
    zone = ecran._zones[0]
    centre_px = ecran._vue._vision.mm_to_pixels(
        [zone.center_mm], ecran._homography
    )[0]

    trouvee = ecran._vue.zone_at_pixel(centre_px[0], centre_px[1])
    assert trouvee is not None
    assert trouvee.id_top_left == zone.id_top_left


def test_un_plateau_sans_assez_de_marqueurs_desactive_la_validation(ecran) -> None:
    """Sans 2 coins, aucune conversion pixels → mm n'est possible : on ne peut rien dire."""
    image = np.full((_HAUTEUR, _LARGEUR, 3), 240, dtype=np.uint8)
    _coller_marqueur(image, 3, 80, 80)   # un seul coin

    ecran.analyser(image)

    assert ecran._zones == []
    assert not ecran._btn_valider.isEnabled()
    assert "insuffisants" in ecran._status.text()


# ------------------------------------------------------------------ contrôle de format

def test_une_zone_d_un_autre_format_est_ecartee_avec_son_motif(ecran) -> None:
    """DÉCISION D7 — la photo fait foi pour la géométrie, avec contrôle de taille.

    Le plateau a pu bouger ou être remonté : c'est la position vue MAINTENANT qui
    compte. Mais les cordons ont été tracés pour CE produit — sur une zone d'un autre
    format, ils déborderaient.
    """
    ecran.analyser(_plateau_synthetique(_deux_zones()))
    # La zone de référence de la préparation est calée sur la première zone vue
    reference = ecran._zones[0]
    ecran._preparation.zones = [reference]
    ecran._preparation.reference_zone_id = reference.id_top_left

    # Une seconde zone volontairement bien plus petite que la référence
    petite = DepositZone(
        id_top_left=8, id_bottom_right=9,
        corners_mm=((0, 20), (20, 20), (20, 0), (0, 0)),
        rotation_deg=0.0, diagonal_mm=28.0,
        size_mm=(reference.size_mm[0] - 40.0, reference.size_mm[1] - 40.0),
        anomalies=[],
    )
    motifs = ecran._controler_format([reference, petite])

    assert 8 in motifs
    assert not petite.is_valid, "la zone ecartee doit devenir non selectionnable"
    assert reference.is_valid, "la zone au bon format reste utilisable"


# ------------------------------------------------------------------ contrôle de course

def test_une_trajectoire_hors_course_bloque_le_lancement(ecran, monkeypatch) -> None:
    """INVARIANT I7 vu depuis l'écran — rien ne doit bouger si la course est dépassée.

    Marlin rognerait les coordonnées en silence. Le test vérifie que `_construire_steps`
    rend None, donc qu'aucun thread de dépose n'est démarré.
    """
    messages = []
    monkeypatch.setattr(
        "gui.screen_execution.QMessageBox.critical",
        lambda *args, **kwargs: messages.append(args[2]),
    )
    # Une zone volontairement placée en coordonnées plateau négatives : hors course
    zone = DepositZone(
        id_top_left=4, id_bottom_right=5,
        corners_mm=((-500, -400), (-440, -400), (-440, -440), (-500, -440)),
        rotation_deg=0.0, diagonal_mm=72.0, size_mm=(60.0, 40.0), anomalies=[],
    )
    ecran._dry_run = True

    assert ecran._construire_steps([zone]) is None
    assert messages, "l'operateur doit etre averti"
    assert "annule" in messages[0].lower()


def test_une_trajectoire_dans_la_course_produit_des_steps(ecran) -> None:
    zone = DepositZone(
        id_top_left=4, id_bottom_right=5,
        corners_mm=((20, 60), (80, 60), (80, 20), (20, 20)),
        rotation_deg=0.0, diagonal_mm=72.0, size_mm=(60.0, 40.0), anomalies=[],
    )
    ecran._dry_run = True

    steps = ecran._construire_steps([zone])
    assert steps
    assert all(s["amount"] == 0.0 for s in steps), "en depose a blanc, aucune extrusion"


# ===========================================================================
# Les modales
# ===========================================================================

def test_la_depose_a_blanc_est_cochee_par_defaut(qtbot) -> None:
    """Tant que l'extrusion n'est pas réglée (sous-lot D4), le défaut sûr est à blanc.

    Se tromper dans ce sens ne coûte qu'un cycle pour rien ; dans l'autre, cela sort de
    la pâte avec des tempos jamais réglés, sur une hauteur Z jamais mesurée.
    """
    dialogue = ConfirmDepositDialog("Produit", 3)
    qtbot.addWidget(dialogue)

    assert dialogue.dry_run is True


def _textes_des_labels(dialogue) -> str:
    """Concatène le texte de tous les QLabel d'un dialogue.

    Explicitement des QLabel, et non une introspection sur `children()` : viser un type
    déduit à l'exécution donne un test qui passe pour de mauvaises raisons le jour où
    l'ordre des enfants change.
    """
    return " ".join(label.text() for label in dialogue.findChildren(QLabel))


def test_la_confirmation_rappelle_le_produit_et_le_nombre_de_zones(qtbot) -> None:
    dialogue = ConfirmDepositDialog("Calculateur ABC", 4)
    qtbot.addWidget(dialogue)

    textes = _textes_des_labels(dialogue)
    assert "Calculateur ABC" in textes
    assert "4" in textes


def test_la_fenetre_de_progression_ne_se_ferme_pas_a_l_echap(qtbot) -> None:
    """Tant que la machine bouge, la seule sortie est le bouton d'arrêt.

    Échap déclencherait `reject()` — une fermeture masquée qui laisserait le thread
    tourner en retirant à l'opérateur l'accès à l'arrêt. C'est exactement le trou de
    sécurité relevé sur `app.py::closeEvent` (dette L2), qu'on ne reproduit pas ici.
    """
    from PyQt5.QtCore import Qt as _Qt
    from PyQt5.QtGui import QKeyEvent
    from PyQt5.QtCore import QEvent

    dialogue = DepositProgressDialog()
    qtbot.addWidget(dialogue)
    dialogue.show()

    dialogue.keyPressEvent(
        QKeyEvent(QEvent.KeyPress, _Qt.Key_Escape, _Qt.NoModifier)
    )

    assert dialogue.isVisible(), "Echap ne doit pas fermer la fenetre"


def test_la_progression_se_borne_entre_0_et_100(qtbot) -> None:
    """Une fraction aberrante ne doit pas produire une barre hors de ses bornes."""
    dialogue = DepositProgressDialog()
    qtbot.addWidget(dialogue)

    dialogue.set_progress(1.7, 3, 3)
    assert dialogue._barre.value() == 1000

    dialogue.set_progress(-0.4, 0, 3)
    assert dialogue._barre.value() == 0


def test_le_bilan_nominal_ne_detaille_pas_les_zones(qtbot) -> None:
    """DÉCISION D9 — un tableau dont toutes les lignes disent « fait » noie l'information."""
    dialogue = DepositSummaryDialog(
        "Produit", zones_faites=[4, 6], zones_prevues=[4, 6],
        secondes=90, interrompu=False, dry_run=False,
    )
    qtbot.addWidget(dialogue)

    textes = _textes_des_labels(dialogue)
    assert "2 / 2" in textes
    assert "NON deposee" not in textes


def test_le_bilan_interrompu_dit_quelles_zones_n_ont_pas_ete_faites(qtbot) -> None:
    """Après un arrêt, c'est le seul renseignement qui compte pour la traçabilité."""
    dialogue = DepositSummaryDialog(
        "Produit", zones_faites=[4], zones_prevues=[4, 6, 8],
        secondes=42, interrompu=True, dry_run=False,
    )
    qtbot.addWidget(dialogue)

    textes = _textes_des_labels(dialogue)
    assert "1 / 3" in textes
    assert "Zone 6 : NON deposee" in textes
    assert "Zone 8 : NON deposee" in textes
    assert "Zone 4 : deposee" in textes
