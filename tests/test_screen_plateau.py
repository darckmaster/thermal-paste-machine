# Tests automatiques de l'écran « Créer un plateau » (lot C1).
#
# Ces tests pilotent réellement les widgets PyQt5 via pytest-qt : ils construisent
# l'écran, lui injectent une image de synthèse et vérifient l'état de l'interface —
# libellés, boutons actifs ou non, signaux émis. Aucune caméra n'est nécessaire :
# `analyser()` est appelée directement, ce qui est précisément pourquoi elle est
# publique et séparée de `_on_capture()`.
#
# Ils ne remplacent pas les essais manuels de l'étudiant sur l'écran tactile : ils
# figent le COMPORTEMENT, pas l'ergonomie. Une cible tactile trop petite ou un texte
# illisible ne se voient qu'à l'œil.

import math

import cv2
import numpy as np
import pytest

from gui.screen_plateau import ScreenPlateau
from modules.vision import ANOMALIE_INVERSEE


# Le plateau de synthèse est dessiné dans une image 900×700 px. Les marqueurs sont de
# vrais ArUco générés par OpenCV : la détection réelle tourne donc bel et bien, ce qui
# fait de ces tests une vérification de la chaîne complète et pas d'un simple mock.
_LARGEUR = 900
_HAUTEUR = 700
_TAILLE_MARQUEUR = 60


def _coller_marqueur(image: np.ndarray, marker_id: int, cx: int, cy: int) -> None:
    """Colle un marqueur ArUco réel centré en (cx, cy) sur l'image."""
    dictionnaire = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    motif = cv2.aruco.generateImageMarker(dictionnaire, marker_id, _TAILLE_MARQUEUR)
    motif_bgr = cv2.cvtColor(motif, cv2.COLOR_GRAY2BGR)

    demi = _TAILLE_MARQUEUR // 2
    image[cy - demi:cy + demi, cx - demi:cx + demi] = motif_bgr


def _plateau_synthetique(zones: dict = None, coins_plateau: dict = None) -> np.ndarray:
    """Fabrique la photo d'un plateau : 4 coins + les zones demandées.

    zones : {id_haut_gauche: ((x1, y1), (x2, y2))} — positions pixel des 2 marqueurs
    coins_plateau : permet de retirer des coins pour tester les cas dégradés
    """
    image = np.full((_HAUTEUR, _LARGEUR, 3), 240, dtype=np.uint8)  # fond clair

    # Coins du plateau : 3 = haut-gauche, 0 = haut-droit, 1 = bas-droit, 2 = bas-gauche
    defaut_coins = {3: (80, 80), 0: (820, 80), 1: (820, 620), 2: (80, 620)}
    for marker_id, (cx, cy) in (coins_plateau if coins_plateau is not None
                                else defaut_coins).items():
        _coller_marqueur(image, marker_id, cx, cy)

    for id_tl, (p1, p2) in (zones or {}).items():
        _coller_marqueur(image, id_tl, p1[0], p1[1])
        _coller_marqueur(image, id_tl + 1, p2[0], p2[1])

    return image


def _deux_zones_saines() -> dict:
    """Deux zones de même format, décalées verticalement.

    Le décalage évite que la paire fantôme (5,6) — coin bas-droit de la première et
    coin haut-gauche de la seconde — ait par symétrie la même longueur de diagonale que
    les vraies zones.
    """
    return {
        4: ((200, 200), (360, 300)),
        6: ((500, 260), (660, 360)),
    }


@pytest.fixture
def ecran(qtbot) -> ScreenPlateau:
    """Un écran plateau construit et enregistré auprès de qtbot.

    qtbot assure la destruction propre du widget en fin de test — sans lui, les widgets
    s'accumuleraient d'un test à l'autre et Qt finirait par protester.
    """
    widget = ScreenPlateau()
    qtbot.addWidget(widget)
    widget.set_product_name("Produit test")
    return widget


# ------------------------------------------------------------------ nom du produit

def test_bandeau_affiche_le_nom_du_produit(ecran: ScreenPlateau) -> None:
    """Le nom du produit doit rester visible en permanence : c'est ce qui permet de
    savoir sur quoi on travaille après plusieurs allers-retours entre écrans."""
    ecran.set_product_name("Calculateur XYZ")

    assert ecran.product_name == "Calculateur XYZ"
    assert "Calculateur XYZ" in ecran._banner.text()


# ------------------------------------------------------------------ cas nominal

def test_deux_zones_saines_activent_le_bouton_continuer(ecran: ScreenPlateau) -> None:
    """Sur un plateau conforme, les zones sont reconnues et l'opérateur peut continuer."""
    ecran.analyser(_plateau_synthetique(_deux_zones_saines()))

    assert ecran._layout is not None
    assert len(ecran._layout.valid_zones) == 2
    assert ecran._btn_continue.isEnabled()
    # Le nombre de zones apparaît sur le bouton : l'opérateur sait ce qu'il valide
    assert "2" in ecran._btn_continue.text()


def test_diagnostic_annonce_les_zones_et_le_format(ecran: ScreenPlateau) -> None:
    """La barre de statut doit dire combien de zones sont exploitables et quel format de
    produit a été déduit — sans quoi l'opérateur ne peut pas juger du résultat."""
    ecran.analyser(_plateau_synthetique(_deux_zones_saines()))
    statut = ecran._status_label.text()

    assert "2 zone(s) exploitable(s)" in statut
    assert "Format déduit" in statut


def test_image_affichee_apres_analyse(ecran: ScreenPlateau) -> None:
    """L'analyse doit produire un rendu visible : sans image, l'opérateur n'a aucun
    moyen de vérifier que le logiciel a bien vu ce qu'il croit avoir vu."""
    ecran.analyser(_plateau_synthetique(_deux_zones_saines()))

    assert ecran._image_label.pixmap() is not None
    assert not ecran._image_label.pixmap().isNull()


def test_analyse_ne_modifie_pas_la_photo_source(ecran: ScreenPlateau) -> None:
    """Le diagnostic est dessiné sur une COPIE : la photo d'origine doit rester intacte,
    puisque c'est elle qui sera transmise au tracé puis au rapport."""
    image = _plateau_synthetique(_deux_zones_saines())
    original = image.copy()

    ecran.analyser(image)

    assert np.array_equal(image, original), "la photo source a été annotée par erreur"


# ------------------------------------------------------------------ anomalies

def test_zone_inversee_signalee_et_exclue(ecran: ScreenPlateau) -> None:
    """Une zone montée à l'envers doit être signalée nommément, sans pour autant
    empêcher de travailler sur les zones saines."""
    zones = _deux_zones_saines()
    # Intervertir les deux marqueurs de la seconde zone : elle est montée à l'envers
    p1, p2 = zones[6]
    zones[6] = (p2, p1)

    ecran.analyser(_plateau_synthetique(zones))

    inversees = [z for z in ecran._layout.zones if ANOMALIE_INVERSEE in z.anomalies]
    assert len(inversees) == 1

    statut = ecran._status_label.text()
    assert "envers" in statut, f"le défaut doit être nommé dans le statut : {statut}"
    # Une anomalie n'invalide pas le plateau entier
    assert ecran._btn_continue.isEnabled()


def test_marqueur_orphelin_signale(ecran: ScreenPlateau) -> None:
    """Un marqueur de zone sans partenaire doit être signalé : c'est le symptôme d'un
    tag décollé, masqué, ou d'une zone au format aberrant."""
    zones = _deux_zones_saines()
    image = _plateau_synthetique(zones)
    # Ajouter un marqueur isolé, dont le voisin (21) n'existe pas
    _coller_marqueur(image, 20, 300, 550)

    ecran.analyser(image)

    assert 20 in ecran._layout.unpaired_ids
    assert "orphelin" in ecran._status_label.text().lower() or \
           "sans zone" in ecran._status_label.text().lower()


def test_message_de_diagnostic_borne_en_longueur(ecran: ScreenPlateau, qtbot) -> None:
    """Le message ne doit pas énumérer tous les défauts d'un plateau très dégradé.

    Sur l'écran tactile 800×480, l'image ne dispose que d'environ 310 px de hauteur : un
    message qui listerait les six zones d'un plateau entièrement mal monté la réduirait
    encore. Au-delà de deux zones détaillées, un décompte renvoie à l'image, où chaque
    rectangle porte déjà son étiquette.
    """
    # Quatre zones de même format, toutes montées à l'envers : chaque paire a ses deux
    # marqueurs intervertis, donc (bas-droit, haut-gauche) au lieu de l'inverse
    zones = {}
    for i, id_tl in enumerate((4, 6, 8, 10)):
        x = 180 + (i % 2) * 340
        y = 180 + (i // 2) * 240
        zones[id_tl] = ((x + 160, y + 100), (x, y))

    ecran.analyser(_plateau_synthetique(zones))

    en_defaut = [z for z in ecran._layout.zones if not z.is_valid]
    assert len(en_defaut) >= 3, "prérequis : il faut plus de 2 zones en défaut"

    statut = ecran._status_label.text()
    assert "autre(s) zone(s) en défaut" in statut, (
        f"le message doit être résumé au-delà de 2 zones :\n{statut}"
    )
    # Borne concrète : au-delà, le message déborde sur la place de l'image
    assert len(statut) < 320, f"message trop long ({len(statut)} caractères) :\n{statut}"


def test_aucune_zone_desactive_continuer(ecran: ScreenPlateau) -> None:
    """Sans zone exploitable, « Continuer » n'a aucun sens et doit rester inactif."""
    ecran.analyser(_plateau_synthetique(zones={}))

    assert ecran._layout is not None
    assert ecran._layout.valid_zones == []
    assert not ecran._btn_continue.isEnabled()
    assert "Aucune zone" in ecran._status_label.text()


# ------------------------------------------------------------------ cas dégradés

def test_plateau_insuffisant_refuse_l_analyse(ecran: ScreenPlateau) -> None:
    """Avec moins de 2 coins de plateau, aucune conversion pixels → mm n'est possible :
    il faut le dire clairement plutôt que de produire des zones fantaisistes."""
    image = _plateau_synthetique(_deux_zones_saines(), coins_plateau={3: (80, 80)})

    ecran.analyser(image)

    assert ecran._layout is None
    assert not ecran._btn_continue.isEnabled()
    assert "insuffisants" in ecran._status_label.text()


def test_repli_deux_marqueurs_avertit_de_la_precision(ecran: ScreenPlateau) -> None:
    """Avec seulement 2 coins de plateau — le cas NOMINAL sur la Geeetech — le tracé
    reste possible mais l'opérateur doit être averti de la précision dégradée."""
    image = _plateau_synthetique(
        _deux_zones_saines(), coins_plateau={3: (80, 80), 0: (820, 80)}
    )

    ecran.analyser(image)

    assert "Précision réduite" in ecran._status_label.text()
    assert ecran._layout is not None


# ------------------------------------------------------- capture automatique (2026-08-02)

class _CameraFactice:
    """Une caméra qui rend toujours la même image de synthèse."""

    def __init__(self, image: np.ndarray) -> None:
        self._image = image
        self.appels = 0

    def capture(self) -> np.ndarray:
        self.appels += 1
        return self._image.copy()


def test_capture_automatique_declenche_des_que_le_plateau_est_vu(
    ecran: ScreenPlateau,
) -> None:
    """Au rechargement d'un plateau, la photo doit se prendre seule.

    La caméra est fixe sur le bâti et les zones sont vissées à demeure : le cadrage est
    toujours le même, donc l'appui sur « Capturer » ne fait prendre aucune décision à
    l'opérateur — c'est un geste de plus sur un écran tactile, rien d'autre.
    """
    ecran.set_camera(_CameraFactice(_plateau_synthetique(_deux_zones_saines())))
    ecran.armer_capture_automatique()

    # Une image d'aperçu suffit : les marqueurs y sont visibles dès la première
    ecran._update_frame()

    assert ecran._layout is not None, "l'analyse devait être déclenchée sans action"
    assert len(ecran._layout.valid_zones) == 2
    assert ecran._btn_continue.isEnabled()


def test_capture_automatique_attend_de_voir_le_plateau(ecran: ScreenPlateau) -> None:
    """Tant que le plateau n'est pas reconnaissable, on n'appuie pas sur la détente.

    Une temporisation aveugle déclencherait sur la première image venue — main encore
    dans le champ, exposition pas stabilisée — et produirait un diagnostic raté qu'il
    faudrait de toute façon reprendre.
    """
    # Un seul coin de plateau : en dessous du minimum de 2 exigé par l'homographie
    image = _plateau_synthetique(_deux_zones_saines(), coins_plateau={3: (80, 80)})
    ecran.set_camera(_CameraFactice(image))
    ecran.armer_capture_automatique()

    ecran._update_frame()

    assert ecran._layout is None, "aucune analyse ne devait être lancée"
    assert ecran._capture_auto_armee, "la capture doit rester armée, en attente"
    assert "recherche du plateau" in ecran._status_label.text()


def test_capture_automatique_rend_la_main_apres_le_garde_temps(
    ecran: ScreenPlateau,
) -> None:
    """Passé le délai, l'opérateur reprend la main avec un message qui dit quoi faire.

    Mieux vaut ça qu'un écran qui attend sans fin, où l'on finit par se demander si
    l'application est bloquée.
    """
    # Aucun marqueur de plateau visible : la capture automatique ne peut pas aboutir
    ecran.set_camera(_CameraFactice(_plateau_synthetique(zones={}, coins_plateau={})))
    # Même enchaînement que MainApp au rechargement : on démarre l'aperçu, PUIS on arme
    ecran.start_camera()
    ecran.armer_capture_automatique()

    ecran._abandonner_capture_automatique()   # simule l'expiration du garde-temps

    assert not ecran._capture_auto_armee
    assert ecran._btn_capture.isEnabled(), "le bouton manuel doit rester disponible"
    assert "Capturer" in ecran._status_label.text()
    ecran.stop_camera()   # ne pas laisser le timer d'aperçu battre après le test


def test_reprendre_desarme_la_capture_automatique(ecran: ScreenPlateau) -> None:
    """Après un « Reprendre », c'est l'opérateur qui décide du moment.

    Il vient de constater un défaut de montage : redéclencher tout seul le renverrait
    au même diagnostic avant qu'il ait eu le temps de rectifier quoi que ce soit.
    """
    ecran.set_camera(_CameraFactice(_plateau_synthetique(_deux_zones_saines())))
    ecran.armer_capture_automatique()
    assert ecran._capture_auto_armee

    ecran.start_camera()   # ce que fait le bouton « Reprendre »

    assert not ecran._capture_auto_armee


# ------------------------------------------------------------------ signal de sortie

def test_continuer_emet_le_plateau_valide(ecran: ScreenPlateau, qtbot) -> None:
    """Le clic sur « Continuer » doit transmettre tout ce dont l'étape de tracé aura
    besoin : le produit, la photo, l'homographie et les zones."""
    image = _plateau_synthetique(_deux_zones_saines())
    ecran._captured_image = image
    ecran.analyser(image)

    with qtbot.waitSignal(ecran.plateau_validated, timeout=1000) as capture:
        ecran._btn_continue.click()

    charge = capture.args[0]
    assert charge["product_name"] == "Produit test"
    assert charge["image"] is image
    assert charge["homography"] is not None
    assert len(charge["layout"].valid_zones) == 2


def test_continuer_sans_zone_n_emet_rien(ecran: ScreenPlateau, qtbot) -> None:
    """Garde-fou : même appelé directement, le passage à l'étape suivante doit être
    impossible sans zone exploitable."""
    ecran.analyser(_plateau_synthetique(zones={}))

    with qtbot.assertNotEmitted(ecran.plateau_validated):
        ecran._on_continue()


def test_retour_emet_back_requested(ecran: ScreenPlateau, qtbot) -> None:
    """Le bouton Retour doit ramener à l'écran d'accueil."""
    with qtbot.waitSignal(ecran.back_requested, timeout=1000):
        ecran._btn_back.click()
