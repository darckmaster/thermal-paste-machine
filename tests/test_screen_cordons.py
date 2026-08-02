# Tests automatiques de l'écran de tracé des cordons (lot C2).
#
# Les interactions sont pilotées par qtbot, qui envoie de VRAIS événements souris aux
# widgets : les tests exercent donc le même chemin de code qu'un opérateur, y compris la
# conversion des coordonnées d'affichage en millimètres.
#
# Ils figent le comportement, pas l'ergonomie : la lisibilité du trait ou la taille des
# cibles tactiles ne se jugent qu'à l'œil sur l'écran réel.

import math

import numpy as np
import pytest
from PyQt5.QtCore import QPoint, Qt

from gui.screen_cordons import (
    ZOOM_PX_PER_MM,
    CordonEditor,
    ScreenCordons,
    _distance_point_segment,
    _image_vers_label,
)
from modules.vision import DepositZone, VisionProcessor
from tests.test_vision import _marqueurs_synthetiques


ZONE_W = 60.0
ZONE_H = 40.0


def _zone(id_tl: int = 4, x: float = 40.0, y: float = 60.0,
          rotation_deg: float = 0.0) -> DepositZone:
    """Une zone dont le coin BAS-GAUCHE — son origine — est en (x, y).

    Ancrée sur l'origine du repère de la zone depuis le lot C2bis (c'était le coin
    haut-gauche avant) : c'est le point auquel se rapportent les cordons.
    """
    theta = math.radians(rotation_deg)
    u = (math.cos(theta), math.sin(theta))       # le long de la largeur
    n = (-math.sin(theta), math.cos(theta))      # le long de la hauteur, vers le HAUT

    bl = (x, y)
    br = (x + ZONE_W * u[0], y + ZONE_W * u[1])
    tl = (x + ZONE_H * n[0], y + ZONE_H * n[1])
    tr = (tl[0] + ZONE_W * u[0], tl[1] + ZONE_W * u[1])

    return DepositZone(id_tl, id_tl + 1, (tl, tr, br, bl), rotation_deg,
                       math.hypot(ZONE_W, ZONE_H), (ZONE_W, ZONE_H), [])


class _LayoutFactice:
    """Un PlateauLayout réduit à ce dont l'écran a besoin."""

    def __init__(self, zones: list) -> None:
        self.zones = zones

    @property
    def valid_zones(self) -> list:
        return self.zones


def _donnees_plateau(zones: list = None) -> dict:
    """La charge utile transmise par l'écran de création de plateau."""
    vision = VisionProcessor()
    H = vision.compute_homography(_marqueurs_synthetiques())
    return {
        "product_name": "Produit test",
        "image": np.full((400, 600, 3), 200, dtype=np.uint8),
        "homography": H,
        "layout": _LayoutFactice(zones if zones is not None else [_zone()]),
    }


@pytest.fixture
def editeur(qtbot) -> CordonEditor:
    """Un éditeur prêt à tracer, sur une zone de 60 × 40 mm.

    La taille du widget est fixée à celle exacte de l'image redressée : le facteur
    d'échelle vaut alors 1 et les coordonnées de clic correspondent aux pixels de
    l'image, ce qui rend les positions attendues lisibles dans les tests.
    """
    widget = CordonEditor()
    qtbot.addWidget(widget)
    largeur = int(ZONE_W * ZOOM_PX_PER_MM)
    hauteur = int(ZONE_H * ZOOM_PX_PER_MM)
    widget.resize(largeur, hauteur)
    widget.set_zone_image(np.full((hauteur, largeur, 3), 220, dtype=np.uint8), [])
    return widget


def _pixel_du_mm(x_mm: float, y_mm: float) -> QPoint:
    """mm de zone → pixel du widget, avec le RETOURNEMENT de Y du lot C2bis.

    L'origine du repère de la zone est son coin bas-gauche, alors que la ligne 0 de
    l'image est son coin HAUT : un point à y = 0 mm se clique donc sur la dernière
    ligne. Les tests conservent ainsi des coordonnées en millimètres lisibles, et
    c'est ce helper — et lui seul — qui porte la conversion.

    La fixture `editeur` dimensionne le widget à la taille exacte de l'image, donc
    l'échelle vaut 1 et un millimètre vaut ZOOM_PX_PER_MM pixels.
    """
    hauteur_px = int(ZONE_H * ZOOM_PX_PER_MM)
    return QPoint(int(x_mm * ZOOM_PX_PER_MM), int(hauteur_px - y_mm * ZOOM_PX_PER_MM))


def _clic(qtbot, widget, x_mm: float, y_mm: float) -> None:
    """Simule un appui à la position donnée, exprimée en mm de zone."""
    qtbot.mouseClick(widget, Qt.LeftButton, pos=_pixel_du_mm(x_mm, y_mm))


def _double_clic(qtbot, widget, x_mm: float, y_mm: float) -> None:
    """Simule un double-appui, qui clôt le tracé en cours."""
    qtbot.mouseDClick(widget, Qt.LeftButton, pos=_pixel_du_mm(x_mm, y_mm))


# ------------------------------------------------------------------ utilitaire

def test_distance_a_un_segment_et_non_a_sa_droite() -> None:
    """La sélection d'un cordon doit se faire sur le SEGMENT, pas sur sa droite.

    Sans cela, un clic loin au-delà d'une extrémité sélectionnerait quand même le
    cordon, ce qui rendrait la sélection imprévisible.
    """
    a, b = (0.0, 0.0), (10.0, 0.0)

    # Au milieu, à 3 de distance perpendiculaire
    assert _distance_point_segment((5.0, 3.0), a, b) == pytest.approx(3.0)
    # Bien au-delà de l'extrémité : la distance est celle au point b, pas 0
    assert _distance_point_segment((50.0, 0.0), a, b) == pytest.approx(40.0)


# ------------------------------------------------------------------ tracé

def test_un_clic_demarre_un_trace(editeur, qtbot) -> None:
    """Le premier appui pose un point et ouvre un tracé — mais aucun cordon n'existe
    encore : un point isolé n'a rien à déposer."""
    _clic(qtbot, editeur, 10.0, 10.0)

    assert editeur.a_un_trace_en_cours
    assert editeur.cordons == [], "un tracé en cours n'est pas encore un cordon"


def test_double_clic_termine_le_cordon(editeur, qtbot) -> None:
    """Le double-appui clôt le tracé. Le point du premier appui du double n'est PAS
    dupliqué : Qt remplace le second press par l'événement de double-clic."""
    _clic(qtbot, editeur, 10.0, 10.0)
    _clic(qtbot, editeur, 30.0, 10.0)
    _double_clic(qtbot, editeur, 50.0, 20.0)

    assert not editeur.a_un_trace_en_cours
    assert len(editeur.cordons) == 1
    assert len(editeur.cordons[0]) == 3, f"obtenu {editeur.cordons[0]}"


def test_points_convertis_en_millimetres_de_zone(editeur, qtbot) -> None:
    """Un appui doit être mémorisé en mm relatifs à la zone, pas en pixels : c'est ce
    format qui permettra de reporter le cordon sur les autres zones."""
    _clic(qtbot, editeur, 15.0, 25.0)
    _double_clic(qtbot, editeur, 45.0, 30.0)

    premier = editeur.cordons[0][0]
    assert premier == pytest.approx((15.0, 25.0), abs=0.3)


def test_trace_de_moins_de_deux_points_abandonne(editeur, qtbot) -> None:
    """Un cordon d'un seul point n'a aucun segment : le clore ne doit rien créer."""
    _double_clic(qtbot, editeur, 10.0, 10.0)

    assert editeur.cordons == []
    assert not editeur.a_un_trace_en_cours


def test_plusieurs_cordons_sur_une_zone(editeur, qtbot) -> None:
    """Une zone accueille plusieurs cordons — c'est le besoin de départ."""
    _clic(qtbot, editeur, 5.0, 5.0)
    _double_clic(qtbot, editeur, 55.0, 5.0)
    _clic(qtbot, editeur, 5.0, 35.0)
    _double_clic(qtbot, editeur, 55.0, 35.0)

    assert len(editeur.cordons) == 2


def test_appui_en_haut_de_l_ecran_donne_un_grand_y(editeur, qtbot) -> None:
    """Un appui en HAUT du widget doit produire un grand y en mm, pas un petit.

    C'est le trajet complet « ce que voit l'opérateur → ce que mémorise le logiciel »,
    et le seul endroit où le retournement de Y du lot C2bis se vérifie côté IHM.
    L'origine du repère de la zone est son coin bas-gauche, alors que la ligne 0 de
    l'image en est le haut : sans retournement dans _position_mm(), un cordon tracé
    en haut de la pièce serait mémorisé en bas — et déposé au mauvais endroit.

    Volontairement écrit en PIXELS et non via le helper _clic() : ce dernier applique
    déjà le retournement, il ne pourrait donc pas détecter son absence dans le code.
    """
    hauteur_px = int(ZONE_H * ZOOM_PX_PER_MM)

    qtbot.mouseClick(editeur, Qt.LeftButton, pos=QPoint(100, 4))          # tout en haut
    qtbot.mouseDClick(editeur, Qt.LeftButton, pos=QPoint(100, hauteur_px - 4))  # tout en bas

    haut, bas = editeur.cordons[0]
    assert haut[1] > bas[1], (
        f"le point cliqué en haut de l'écran ({haut[1]:.1f} mm) doit avoir un y PLUS "
        f"GRAND que celui cliqué en bas ({bas[1]:.1f} mm)"
    )
    assert haut[1] == pytest.approx(ZONE_H, abs=1.0), "le haut du widget = hauteur de la zone"
    assert bas[1] == pytest.approx(0.0, abs=1.0), "le bas du widget = origine de la zone"


def test_un_cordon_trace_en_haut_de_la_zone_est_en_haut_du_plateau(editeur, qtbot) -> None:
    """Le report d'un cordon vers le repère du plateau doit conserver le haut en haut.

    Le test précédent s'arrête au repère de la ZONE ; celui-ci franchit la frontière
    vers le repère du PLATEAU, où l'origine de la zone a aussi changé de coin
    (`origin_mm` = coin bas-gauche). Une erreur là ne se verrait pas en restant dans
    le repère de la zone : le cordon serait cohérent avec lui-même et posé du mauvais
    côté de la pièce.

    (Le troisième endroit où le Y est retourné, `warp_zone()`, est couvert côté vision
    par `test_warp_zone_origine_du_repere_au_coin_bas_gauche`.)
    """
    _clic(qtbot, editeur, 10.0, ZONE_H - 5.0)     # près du bord haut de la zone
    _double_clic(qtbot, editeur, 50.0, 5.0)       # près du bord bas

    zone = _zone(4, 40.0, 60.0)
    haut_plateau = zone.to_plateau_mm(editeur.cordons[0][0])
    bas_plateau = zone.to_plateau_mm(editeur.cordons[0][1])

    assert haut_plateau[1] > bas_plateau[1], (
        "le point tracé en haut de la zone doit ressortir plus haut sur le plateau"
    )
    # La zone occupe 60 → 100 mm en Y sur le plateau : les deux points doivent y tomber
    assert 60.0 <= bas_plateau[1] <= 100.0 and 60.0 <= haut_plateau[1] <= 100.0


# ------------------------------------------------------------------ undo / redo

def test_annuler_retire_le_dernier_point(editeur, qtbot) -> None:
    """Annuler après un appui corrige un clic imprécis sans tout reprendre."""
    _clic(qtbot, editeur, 10.0, 10.0)
    _clic(qtbot, editeur, 30.0, 10.0)

    editeur.annuler()

    assert editeur.a_un_trace_en_cours, "le tracé ne doit pas être perdu"
    _double_clic(qtbot, editeur, 50.0, 10.0)
    assert len(editeur.cordons[0]) == 2, "le point annulé ne doit pas réapparaître"


def test_annuler_une_cloture_rouvre_le_trace(editeur, qtbot) -> None:
    """Annuler juste après avoir terminé un cordon doit le rouvrir, pas le détruire."""
    _clic(qtbot, editeur, 10.0, 10.0)
    _double_clic(qtbot, editeur, 40.0, 10.0)
    assert len(editeur.cordons) == 1

    editeur.annuler()

    assert editeur.cordons == []
    assert editeur.a_un_trace_en_cours, "le cordon doit redevenir le tracé en cours"


def test_refaire_rejoue_l_action_annulee(editeur, qtbot) -> None:
    """Refaire doit rétablir exactement ce qu'annuler venait de défaire."""
    _clic(qtbot, editeur, 10.0, 10.0)
    _double_clic(qtbot, editeur, 40.0, 10.0)
    editeur.annuler()

    editeur.refaire()

    assert len(editeur.cordons) == 1
    assert not editeur.a_un_trace_en_cours


def test_profondeur_un_seul_niveau(editeur, qtbot) -> None:
    """Undo est de profondeur 1 : après une annulation, il n'y a plus rien à annuler."""
    _clic(qtbot, editeur, 10.0, 10.0)
    _clic(qtbot, editeur, 30.0, 10.0)

    editeur.annuler()

    assert not editeur.peut_annuler(), "une seule action est mémorisée"
    assert editeur.peut_refaire()


def test_nouvelle_action_invalide_le_refaire(editeur, qtbot) -> None:
    """Une action nouvelle rend caduque la branche qu'on aurait pu refaire."""
    _clic(qtbot, editeur, 10.0, 10.0)
    editeur.annuler()
    assert editeur.peut_refaire()

    _clic(qtbot, editeur, 20.0, 20.0)

    assert not editeur.peut_refaire()


# ------------------------------------------------------------------ sélection

def test_clic_sur_un_cordon_le_selectionne(editeur, qtbot) -> None:
    """Hors tracé, un appui sur un cordon existant le sélectionne au lieu d'en démarrer
    un nouveau."""
    _clic(qtbot, editeur, 10.0, 20.0)
    _double_clic(qtbot, editeur, 50.0, 20.0)

    # Appui sur le milieu du cordon
    _clic(qtbot, editeur, 30.0, 20.0)

    assert editeur.selection == 0
    assert not editeur.a_un_trace_en_cours, "aucun nouveau tracé ne doit démarrer"


def test_clic_loin_des_cordons_demarre_un_trace(editeur, qtbot) -> None:
    """Un appui à l'écart d'un cordon existant démarre bien un nouveau tracé."""
    _clic(qtbot, editeur, 10.0, 5.0)
    _double_clic(qtbot, editeur, 50.0, 5.0)

    _clic(qtbot, editeur, 30.0, 35.0)

    assert editeur.selection is None
    assert editeur.a_un_trace_en_cours


def test_supprimer_le_cordon_selectionne(editeur, qtbot) -> None:
    """Un cordon sélectionné doit pouvoir être supprimé entièrement."""
    _clic(qtbot, editeur, 10.0, 20.0)
    _double_clic(qtbot, editeur, 50.0, 20.0)
    _clic(qtbot, editeur, 30.0, 20.0)

    editeur.supprimer_selection()

    assert editeur.cordons == []
    assert editeur.selection is None


def test_annuler_une_suppression_restaure_le_cordon(editeur, qtbot) -> None:
    """La suppression étant destructrice, elle doit être annulable — et le cordon doit
    revenir à sa place, pas à la fin de la liste."""
    _clic(qtbot, editeur, 10.0, 10.0)
    _double_clic(qtbot, editeur, 50.0, 10.0)
    _clic(qtbot, editeur, 10.0, 30.0)
    _double_clic(qtbot, editeur, 50.0, 30.0)

    _clic(qtbot, editeur, 30.0, 10.0)     # sélectionne le PREMIER cordon
    assert editeur.selection == 0
    editeur.supprimer_selection()
    assert len(editeur.cordons) == 1

    editeur.annuler()

    assert len(editeur.cordons) == 2
    assert editeur.cordons[0][0] == pytest.approx((10.0, 10.0), abs=0.3), \
        "le cordon restauré doit retrouver sa position dans la liste"


# ------------------------------------------------------------------ écran complet

@pytest.fixture
def ecran(qtbot) -> ScreenCordons:
    widget = ScreenCordons()
    qtbot.addWidget(widget)
    widget.resize(800, 480)
    return widget


def test_ouverture_affiche_la_vue_plateau(ecran, qtbot) -> None:
    """À l'arrivée, l'opérateur voit son plateau et doit choisir une zone."""
    ecran.set_plateau(_donnees_plateau())

    assert ecran._vues.currentIndex() == 0
    assert "appuyer sur une zone" in ecran._status.text()
    assert not ecran._btn_editer.isEnabled(), "aucune zone de référence encore choisie"


def test_choisir_une_zone_ouvre_le_zoom(ecran, qtbot) -> None:
    """Choisir une zone bascule en mode tracé et fixe la zone de référence."""
    zone = _zone()
    ecran.set_plateau(_donnees_plateau([zone]))

    ecran._ouvrir_zone(zone)

    assert ecran._vues.currentIndex() == 1
    assert ecran.zone_reference is zone
    assert "double-appui pour terminer" in ecran._status.text()


def test_la_zone_de_reference_ne_change_pas(ecran, qtbot) -> None:
    """Ouvrir une autre zone ne doit PAS changer le repère de référence : les cordons
    déjà tracés y sont exprimés, changer de repère les déplacerait."""
    premiere, seconde = _zone(4, 40.0, 40.0), _zone(6, 120.0, 40.0)
    ecran.set_plateau(_donnees_plateau([premiere, seconde]))

    ecran._ouvrir_zone(premiere)
    ecran._ouvrir_zone(seconde)

    assert ecran.zone_reference is premiere


def test_valider_revient_au_plateau_avec_les_cordons(ecran, qtbot) -> None:
    """Valider ramène à la vue d'ensemble, où les cordons sont annoncés comme appliqués
    à toutes les zones."""
    zones = [_zone(4, 40.0, 40.0), _zone(6, 120.0, 40.0)]
    ecran.set_plateau(_donnees_plateau(zones))
    ecran._ouvrir_zone(zones[0])

    _clic(qtbot, ecran._editeur, 10.0, 10.0)
    _double_clic(qtbot, ecran._editeur, 40.0, 10.0)
    ecran._valider_trace()

    assert ecran._vues.currentIndex() == 0
    assert len(ecran.cordons) == 1
    assert "1 cordon(s) appliqué(s) aux 2 zone(s)" in ecran._status.text()
    assert ecran._btn_editer.isEnabled(), "on doit pouvoir revenir modifier le tracé"


def test_valider_impossible_avec_un_trace_en_cours(ecran, qtbot) -> None:
    """Valider alors qu'un tracé est ouvert le perdrait en silence : le bouton doit
    rester inactif tant que le cordon n'est pas terminé."""
    zone = _zone()
    ecran.set_plateau(_donnees_plateau([zone]))
    ecran._ouvrir_zone(zone)

    _clic(qtbot, ecran._editeur, 10.0, 10.0)

    assert not ecran._btn_valider.isEnabled()


def test_signal_emis_a_chaque_modification(ecran, qtbot) -> None:
    """L'écran signale toute modification des cordons — c'est ce à quoi le lot C3
    branchera la sauvegarde automatique."""
    zone = _zone()
    ecran.set_plateau(_donnees_plateau([zone]))
    ecran._ouvrir_zone(zone)

    with qtbot.waitSignal(ecran.cordons_modified, timeout=1000):
        _clic(qtbot, ecran._editeur, 10.0, 10.0)


def test_clic_sur_une_zone_du_plateau_l_ouvre(ecran, qtbot) -> None:
    """Le clic sur la vue d'ensemble doit retrouver la zone visée, y compris quand elle
    est inclinée — le test de présence se fait dans le repère de la zone.

    L'écran est réellement affiché : sans cela, Qt ne calcule pas la géométrie des
    widgets, et la conversion coordonnées d'affichage → pixels d'image s'appuierait sur
    une taille factice. Le test passait alors ou non selon ce qui l'avait précédé.
    """
    zone = _zone(4, 40.0, 40.0, rotation_deg=8.0)
    donnees = _donnees_plateau([zone])
    ecran.set_plateau(donnees)

    ecran.show()
    qtbot.waitExposed(ecran)

    vue = ecran._vue_plateau
    recu = []
    vue.zone_clicked.connect(recu.append)

    # Viser le centre de la zone : mm → pixels de l'image → coordonnées du widget
    centre_px = ecran._vision.mm_to_pixels([zone.center_mm], donnees["homography"])[0]
    x, y = _image_vers_label(vue, vue._image, centre_px[0], centre_px[1])

    assert 0 <= x <= vue.width() and 0 <= y <= vue.height(), (
        f"prérequis : le point visé ({x:.0f}, {y:.0f}) doit tomber dans le widget "
        f"({vue.width()}×{vue.height()})"
    )
    qtbot.mouseClick(vue, Qt.LeftButton, pos=QPoint(int(x), int(y)))

    assert recu and recu[0] is zone
