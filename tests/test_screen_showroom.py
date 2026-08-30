# Tests du mode démonstration en boucle — gui/screen_showroom.py
#
# Ce que ces tests couvrent, et pourquoi ce sont ceux-là :
#
#   - la SÉLECTION AUTOMATIQUE des zones, qui est la seule décision d'opérateur que ce
#     mode remplace vraiment. Si elle retenait une zone qu'un opérateur aurait refusée,
#     la machine déposerait au mauvais endroit sans que personne ne regarde l'écran ;
#   - l'ENCHAÎNEMENT complet, éprouvé de bout en bout avec une machine et une caméra
#     simulées : c'est la propriété qui fait tout l'intérêt du mode, et la seule qu'un
#     test unitaire de méthode isolée ne montrerait pas ;
#   - les trois ARRÊTS (nombre de cycles atteint, échecs répétés, arrêt immédiat), parce
#     qu'une boucle automatique qui ne sait pas s'arrêter est un danger, pas une démo ;
#   - l'invariant de la DÉPOSE À BLANC sur ce chemin-là. L'invariant I5 est déjà vérifié
#     sur le planner ; ici on vérifie que le chemin showroom l'emprunte réellement,
#     puisqu'il court-circuite la modale de confirmation qui portait ce choix.
#
# Ce qu'ils ne remplacent pas : l'essai réel. Un test dit que la séquence est juste, pas
# que la buse arrive au bon endroit.

import cv2
import numpy as np
import pytest

from gui.screen_showroom import (
    ETAT_ARRET, ETAT_ATTENTE, ETAT_DEPOSE, MAX_ECHECS_CONSECUTIFS, ScreenShowroom,
)
from modules.config import (
    DISPENSE_Z_HEIGHT_MM, DRY_RUN_Z_CLEARANCE_MM, MACHINE_Z_HOME_MM,
    MACHINE_Z_TRAVEL_MM,
)
from modules.preparation import Cordon, Preparation, Settings, save_preparation
from modules.vision import DepositZone


# ===========================================================================
# Plateau de synthèse — de VRAIS marqueurs ArUco, pas des mocks
# ===========================================================================

_LARGEUR = 900
_HAUTEUR = 700
_TAILLE_MARQUEUR = 60


def _coller_marqueur(image: np.ndarray, marker_id: int, cx: int, cy: int) -> None:
    """Colle un marqueur ArUco réel centré en (cx, cy).

    Générer de vrais marqueurs fait tourner la détection OpenCV pour de bon : ces tests
    éprouvent donc la chaîne complète vision → zones → trajectoire, et pas seulement le
    câblage de l'écran.
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
        product_name="AIVC",
        cordons=[Cordon([(5.0, 5.0), (25.0, 5.0), (25.0, 15.0)])],
        settings=Settings(travel_speed_mm_min=1000.0, extrusion_speed_mm_min=100.0),
    )


# ===========================================================================
# Matériel simulé
# ===========================================================================

class MachineSimulee:
    """Note ce qu'on lui demande au lieu de le faire.

    Suffit ici : ce qu'on veut vérifier est la SÉQUENCE des commandes et la façon dont la
    boucle les enchaîne, pas le G-code produit — déjà couvert par `test_machine.py`.
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


class CameraSimulee:
    """Rend toujours la même photo de plateau, et compte les prises de vue."""

    def __init__(self, image: np.ndarray) -> None:
        self._image = image
        self.captures = 0

    def capture(self) -> np.ndarray:
        self.captures += 1
        return self._image.copy()


class CameraEnPanne:
    """Lève à chaque capture — sert à éprouver le compteur d'échecs."""

    def capture(self):
        raise RuntimeError("camera deconnectee")


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def ecran(qtbot) -> ScreenShowroom:
    widget = ScreenShowroom()
    qtbot.addWidget(widget)
    widget._preparation = _preparation()
    return widget


@pytest.fixture
def plateau() -> np.ndarray:
    return _plateau_synthetique(_deux_zones())


def _armer(ecran, qtbot, tmp_path, machine, camera, cycles: int = 1,
           pause: int = 0) -> None:
    """Prépare l'écran pour une boucle réelle : matériel simulé et plateau sur disque.

    Le fichier est écrit dans un dossier temporaire et poussé dans la liste déroulante à
    la main : `demarrer()` relit le fichier choisi, on veut donc éprouver ce chemin-là et
    non un objet déjà en mémoire.
    """
    chemin = save_preparation(_preparation(), directory=str(tmp_path))
    ecran._combo.addItem("AIVC", chemin)
    ecran._combo.setCurrentIndex(ecran._combo.count() - 1)
    ecran.set_machine(machine)
    ecran.set_camera(camera)
    ecran._spin_cycles.setValue(cycles)
    ecran._spin_pause.setValue(pause)


# ===========================================================================
# Sélection automatique des zones
# ===========================================================================

def test_toutes_les_zones_valides_sont_selectionnees_automatiquement(
    ecran, plateau,
) -> None:
    """La substitution à l'opérateur : ce qu'il aurait coché, la boucle le coche."""
    zones = ecran.analyser(plateau)

    assert len(zones) == 2
    assert all(z.is_valid for z in zones)
    # La vue doit montrer exactement la même chose que ce qui sera déposé : c'est elle que
    # le jury regarde, et un écart entre les deux ferait mentir la démonstration.
    assert ecran._vue._selection == {z.id_top_left for z in zones}


def test_une_zone_au_mauvais_format_est_ecartee_sans_intervention(
    ecran, plateau,
) -> None:
    """Le contrôle de format du cycle manuel s'applique aussi en automatique.

    Sans lui, la boucle déposerait des cordons tracés pour un produit sur une zone d'un
    autre format : ils déborderaient de la pièce.
    """
    # Une zone de référence délibérément trop grande : les zones vues s'en écartent de
    # bien plus que la tolérance de 5 mm. `reference_zone` étant une propriété calculée,
    # on la constitue comme le ferait un vrai fichier — une zone dans la liste, et son
    # ID désigné comme référence.
    ecran._preparation.zones = [DepositZone(
        id_top_left=4, id_bottom_right=5,
        corners_mm=((0.0, 20.0), (150.0, 20.0), (150.0, 0.0), (0.0, 0.0)),
        rotation_deg=0.0, diagonal_mm=151.3, size_mm=(150.0, 20.0), anomalies=[],
    )]
    ecran._preparation.reference_zone_id = 4

    zones = ecran.analyser(plateau)

    assert zones == []
    assert ecran._vue._selection == set()


def test_les_reglages_par_defaut_sont_ceux_de_la_soutenance(ecran) -> None:
    """Les valeurs affichées à l'ouverture de l'écran, avant toute saisie.

    Les nombres sont écrits en dur et non repris des constantes du module : un test qui
    relit la même constante que le code passerait quelle que soit sa valeur, et ne dirait
    donc rien. Ici, changer un défaut doit faire échouer ce test — c'est le but.
    """
    assert ecran._spin_cycles.value() == 1      # un seul plateau, pas de boucle sans fin
    assert ecran._spin_pause.value() == 2       # 2 s entre deux cycles
    assert ecran._case_a_blanc.isChecked()      # aucune extrusion tant que M3 n'est pas faite


def test_marqueurs_insuffisants_ne_selectionne_rien(ecran) -> None:
    """Une photo sans marqueur ne doit pas produire de trajectoire, mais un message."""
    image_vide = np.full((_HAUTEUR, _LARGEUR, 3), 240, dtype=np.uint8)

    assert ecran.analyser(image_vide) == []
    assert "insuffisants" in ecran._status.text()


# ===========================================================================
# Refus au démarrage
# ===========================================================================

def test_demarrer_sans_machine_ne_lance_rien(ecran, plateau) -> None:
    ecran.set_camera(CameraSimulee(plateau))

    ecran.demarrer()

    assert ecran._etat == ETAT_ARRET
    assert "machine" in ecran._status.text().lower()
    # La configuration doit rester modifiable : rien n'a démarré
    assert ecran._combo.isEnabled()


def test_demarrer_sans_camera_ne_lance_rien(ecran) -> None:
    ecran.set_machine(MachineSimulee())

    ecran.demarrer()

    assert ecran._etat == ETAT_ARRET
    assert "camera" in ecran._status.text().lower()


def test_un_plateau_sans_cordon_tracable_est_refuse(
    ecran, qtbot, tmp_path, plateau,
) -> None:
    """Un plateau sans cordon ferait tourner la machine pour ne rien déposer."""
    vide = Preparation(product_name="VIDE", cordons=[Cordon([(1.0, 1.0)])])
    chemin = save_preparation(vide, directory=str(tmp_path))
    ecran._combo.addItem("VIDE", chemin)
    ecran.set_machine(MachineSimulee())
    ecran.set_camera(CameraSimulee(plateau))

    ecran.demarrer()

    assert ecran._etat == ETAT_ARRET
    assert "rien a deposer" in ecran._status.text()


# ===========================================================================
# La boucle elle-même
# ===========================================================================

def test_la_boucle_enchaine_le_nombre_de_cycles_demande(
    ecran, qtbot, tmp_path, plateau,
) -> None:
    """Le cœur du mode : deux cycles complets s'enchaînent sans un seul clic.

    Chaque cycle comporte trois séquences machine — mise en position, dépose, retour en
    position pour la photo de fin — donc trois homings. Les compter est la façon la plus
    directe de vérifier que le cycle est parcouru en entier et pas court-circuité.
    """
    machine = MachineSimulee()
    camera = CameraSimulee(plateau)
    _armer(ecran, qtbot, tmp_path, machine, camera, cycles=2, pause=0)

    ecran.demarrer()

    # Pendant que ça tourne, la configuration est verrouillée : la changer en route ne
    # serait pris en compte qu'au cycle suivant, l'écran mentirait sur ce que fait la
    # machine à l'instant où on le lit.
    assert ecran._combo.isEnabled() is False
    assert ecran._btn_arret_dur.isEnabled() is True

    qtbot.waitUntil(lambda: ecran._etat == ETAT_ARRET, timeout=20000)

    assert ecran._cycles_reussis == 2
    assert ecran._cycles_lances == 2
    assert machine.appels.count(("home",)) == 6      # 3 homings × 2 cycles
    assert camera.captures == 4                      # 1 photo de debut + 1 de fin, × 2
    assert "Nombre de cycles" in ecran._status.text()
    # Et la configuration est rendue à l'opérateur
    assert ecran._combo.isEnabled()


def test_en_depose_a_blanc_la_boucle_n_extrude_pas_et_ne_descend_pas(
    ecran, qtbot, tmp_path, plateau,
) -> None:
    """Invariant I5, vérifié sur le chemin showroom.

    Il est déjà éprouvé sur le planner, mais ce mode-ci court-circuite la modale de
    confirmation qui portait le choix de la dépose à blanc : rien ne garantirait sans ce
    test que la case de l'écran arrive bien jusqu'au planner.
    """
    machine = MachineSimulee()
    _armer(ecran, qtbot, tmp_path, machine, CameraSimulee(plateau), cycles=1, pause=0)
    assert ecran._case_a_blanc.isChecked()   # coché par défaut — voir le commentaire de l'écran

    ecran.demarrer()
    qtbot.waitUntil(lambda: ecran._etat == ETAT_ARRET, timeout=20000)

    # Aucune extrusion, ni en cours de tracé ni à l'amorçage
    assert all(appel[3] == 0.0 for appel in machine.appels if appel[0] == "dispense")
    assert all(appel[1] == 0.0 for appel in machine.appels if appel[0] == "prime")

    # Aucune des hauteurs de la dépose réelle n'a été demandée : la trajectoire est
    # restée à la hauteur unique du mode à blanc.
    hauteurs = {appel[3] for appel in machine.appels if appel[0] == "move_to"}
    hauteurs |= {appel[1] for appel in machine.appels if appel[0] == "move_z"}
    assert DISPENSE_Z_HEIGHT_MM not in hauteurs
    assert MACHINE_Z_TRAVEL_MM not in hauteurs
    assert MACHINE_Z_HOME_MM + DRY_RUN_Z_CLEARANCE_MM in hauteurs


# ===========================================================================
# Les trois façons de s'arrêter
# ===========================================================================

def test_trois_echecs_consecutifs_arretent_la_boucle(ecran) -> None:
    """Une machine qui échoue en boucle devant un jury doit s'immobiliser, pas insister."""
    ecran._spin_pause.setValue(60)   # pause longue : la boucle reste en attente entre deux
    ecran._verrouiller_configuration(True)

    for _ in range(MAX_ECHECS_CONSECUTIFS - 1):
        ecran._echec("panne simulee")
        assert ecran._etat == ETAT_ATTENTE

    ecran._echec("panne simulee")

    assert ecran._etat == ETAT_ARRET
    assert "boucle arretee" in ecran._status.text().lower()
    assert ecran._attente.isActive() is False
    assert ecran._combo.isEnabled()     # la configuration est rendue


def test_un_cycle_reussi_remet_le_compteur_d_echecs_a_zero(ecran, monkeypatch) -> None:
    """Sinon, trois incidents espacés d'une heure finiraient par arrêter la boucle.

    Le compteur est armé puis la fin de dépose est appelée directement, sans repasser par
    `demarrer()` — qui remet lui-même le compteur à zéro et rendrait le test inerte. Ce
    piège a été trouvé en vérifiant les tests par mutation : la première version restait
    verte alors que la remise à zéro avait été supprimée du code.
    """
    # La photo de fin n'a rien à voir avec ce qu'on vérifie ici : la neutraliser évite de
    # faire tourner un thread machine pour rien.
    monkeypatch.setattr(ecran._runner_fin, "start", lambda machine, position: None)
    ecran._echecs_consecutifs = MAX_ECHECS_CONSECUTIFS - 1
    ecran._etat = ETAT_DEPOSE
    ecran._noter_resultat("ok", "")

    ecran._on_thread_depose_fini()

    assert ecran._cycles_reussis == 1
    assert ecran._echecs_consecutifs == 0


def test_l_arret_immediat_coupe_les_actionneurs_et_stoppe_la_boucle(ecran) -> None:
    """`M112` met Marlin hors service : la boucle ne doit surtout pas repartir.

    Éprouvé sans thread : l'état de dépose est mis en place à la main, ce qui rend le
    test déterministe là où une vraie course entre threads ne le serait pas.
    """
    machine = MachineSimulee()
    machine.connect()
    ecran.set_machine(machine)
    ecran._etat = ETAT_DEPOSE
    ecran._verrouiller_configuration(True)

    class WorkerEspion:
        def __init__(self) -> None:
            self.arret_demande = False

        def request_stop(self) -> None:
            self.arret_demande = True

    ecran._worker_depose = WorkerEspion()

    ecran.arret_immediat()

    # L'arrêt d'urgence part TOUT DE SUITE, hors du thread : le faire faire au worker
    # reviendrait à attendre la fin du step en cours, ce qui n'est pas un arrêt.
    assert ("emergency_stop",) in machine.appels
    assert ecran._worker_depose.arret_demande is True

    # Puis le thread rend la main avec le statut « stop » : la boucle se termine en
    # disant qu'il faut redémarrer la machine, au lieu d'enchaîner un cycle voué à échouer.
    ecran._noter_resultat("stop", "")
    ecran._on_thread_depose_fini()

    assert ecran._etat == ETAT_ARRET
    assert "redemarree" in ecran._status.text()


def test_l_arret_en_douceur_pendant_l_attente_termine_tout_de_suite(ecran) -> None:
    """Rien ne tourne pendant le compte à rebours : inutile de le laisser s'écouler."""
    ecran._spin_pause.setValue(60)
    ecran._verrouiller_configuration(True)
    ecran._attendre_puis_recommencer("cycle termine")
    assert ecran._etat == ETAT_ATTENTE

    ecran.arret_en_douceur()

    assert ecran._etat == ETAT_ARRET
    assert ecran._attente.isActive() is False


def test_l_arret_en_douceur_pendant_une_depose_laisse_finir_le_cycle(ecran) -> None:
    """L'arrêt normal de fin de démonstration ne coupe rien en pleine pièce."""
    machine = MachineSimulee()
    machine.connect()
    ecran.set_machine(machine)
    ecran._etat = ETAT_DEPOSE
    ecran._verrouiller_configuration(True)

    ecran.arret_en_douceur()

    assert ecran._etat == ETAT_DEPOSE            # la dépose en cours continue
    assert ("emergency_stop",) not in machine.appels
    assert ecran._arret_demande is True


def test_une_camera_en_panne_ne_lance_aucun_mouvement_de_depose(
    ecran, qtbot, tmp_path,
) -> None:
    """Un échec de capture doit arrêter le cycle avant la trajectoire, pas après."""
    machine = MachineSimulee()
    _armer(ecran, qtbot, tmp_path, machine, CameraEnPanne(), cycles=1, pause=0)

    ecran.demarrer()
    qtbot.waitUntil(lambda: ecran._etat == ETAT_ARRET, timeout=20000)

    assert ecran._cycles_reussis == 0
    # Aucune dépose : seules les mises en position ont eu lieu
    assert not [a for a in machine.appels if a[0] in ("dispense", "prime")]


def test_shutdown_arrete_la_boucle(ecran) -> None:
    """Fermer l'application pendant la boucle ne doit pas laisser la machine seule.

    C'est le trou de sécurité connu du projet (dette L2 #1) : un thread de dépose qui
    survit à la fenêtre retire à l'opérateur l'accès au bouton d'arrêt.
    """
    machine = MachineSimulee()
    machine.connect()
    ecran.set_machine(machine)
    ecran._etat = ETAT_ATTENTE
    ecran._verrouiller_configuration(True)

    ecran.shutdown()

    assert ecran._etat == ETAT_ARRET
    assert ("emergency_stop",) in machine.appels


def test_shutdown_ne_fait_rien_si_la_boucle_est_a_l_arret(ecran) -> None:
    """Fermer l'application sans avoir rien lancé ne doit pas envoyer d'arrêt d'urgence."""
    machine = MachineSimulee()
    machine.connect()
    ecran.set_machine(machine)

    ecran.shutdown()

    assert ("emergency_stop",) not in machine.appels
