# Tests des boîtes de dialogue partagées (lot C3).
#
# Elles ne sont pas ouvertes en modal ici : `exec_()` bloquerait la suite du test en
# attendant un clic. On construit le dialogue, on manipule ses champs comme le ferait
# l'opérateur, et on lit le résultat — ce qui exerce exactement la logique testable,
# sans la boucle d'événements modale.

import pytest

from gui.dialogs import PreparationPickerDialog, ProductNameDialog, SettingsDialog
from modules.preparation import (
    AUTOSAVE_SUFFIX,
    Cordon,
    Preparation,
    Settings,
    save_autosave,
    save_preparation,
)


# ------------------------------------------------------------------ nom de produit

def _poser_preparation(tmp_path, nom_fichier: str) -> None:
    """Crée un fichier de préparation, pour peupler la liste des produits existants."""
    (tmp_path / nom_fichier).write_text("{}", encoding="utf-8")


def test_saisie_libre_retournee_telle_quelle(qtbot, tmp_path) -> None:
    """Une référence saisie au clavier doit ressortir intacte."""
    dialogue = ProductNameDialog(directory=str(tmp_path))
    qtbot.addWidget(dialogue)

    dialogue._champ.setText("Calculateur ABC")

    assert dialogue.product_name == "Calculateur ABC"


def test_espaces_de_bord_retires(qtbot, tmp_path) -> None:
    """Un appui maladroit sur la barre d'espace ne doit pas créer une seconde référence.

    Sans ce nettoyage, « REF12 » et « REF12 » donneraient deux plateaux distincts, et
    l'opérateur ne verrait aucune différence entre les deux dans la liste.
    """
    dialogue = ProductNameDialog(directory=str(tmp_path))
    qtbot.addWidget(dialogue)

    dialogue._champ.setText("  REF12  ")

    assert dialogue.product_name == "REF12"


def test_champ_vide_donne_le_nom_automatique(qtbot, tmp_path) -> None:
    """Valider sans rien saisir est la voie du geste minimal — ouvrir, valider, travailler.

    C'est ce qui rend l'écran utilisable au doigt : sur le RPi, il n'y a pas de clavier
    physique, et saisir du texte coûte cher.
    """
    dialogue = ProductNameDialog(directory=str(tmp_path))
    qtbot.addWidget(dialogue)

    assert dialogue.product_name == "BOITIER_1"


def test_nom_automatique_tient_compte_des_existants(qtbot, tmp_path) -> None:
    """Le repli ne doit jamais réutiliser un numéro déjà pris."""
    _poser_preparation(tmp_path, "BOITIER_1.json")
    dialogue = ProductNameDialog(directory=str(tmp_path))
    qtbot.addWidget(dialogue)

    assert dialogue.product_name == "BOITIER_2"


def test_numero_non_consomme_si_l_operateur_saisit(qtbot, tmp_path) -> None:
    """Ouvrir le dialogue ne doit réserver aucun numéro.

    Le repli est calculé à la lecture de `product_name`, pas à la construction : sinon
    chaque ouverture de dialogue, même annulée, ferait avancer la numérotation.
    """
    dialogue = ProductNameDialog(directory=str(tmp_path))
    qtbot.addWidget(dialogue)
    dialogue._champ.setText("Calculateur ABC")

    assert dialogue.product_name == "Calculateur ABC"
    # Un second dialogue doit toujours proposer BOITIER_1 : rien n'a été consommé
    autre = ProductNameDialog(directory=str(tmp_path))
    qtbot.addWidget(autre)
    assert autre.product_name == "BOITIER_1"


def test_liste_propose_les_produits_enregistres(qtbot, tmp_path) -> None:
    """Choisir dans la liste évite les fautes de frappe sur une référence."""
    _poser_preparation(tmp_path, "Calculateur ABC.json")
    _poser_preparation(tmp_path, "Calculateur XYZ.json")

    dialogue = ProductNameDialog(directory=str(tmp_path))
    qtbot.addWidget(dialogue)

    assert dialogue._liste is not None
    proposes = [dialogue._liste.item(i).text() for i in range(dialogue._liste.count())]
    assert proposes == ["Calculateur ABC", "Calculateur XYZ"]


def test_liste_ignore_les_travaux_interrompus(qtbot, tmp_path) -> None:
    """Un autosave est un travail en cours, pas une référence validée : il n'a rien à
    faire dans la liste des produits proposés."""
    _poser_preparation(tmp_path, "Calculateur ABC.json")
    _poser_preparation(tmp_path, "Brouillon" + AUTOSAVE_SUFFIX)

    dialogue = ProductNameDialog(directory=str(tmp_path))
    qtbot.addWidget(dialogue)

    proposes = [dialogue._liste.item(i).text() for i in range(dialogue._liste.count())]
    assert proposes == ["Calculateur ABC"]


def test_liste_masquee_si_aucun_produit(qtbot, tmp_path) -> None:
    """Sur un dépôt neuf, pas de cadre vide : 480 px de haut, ça se ménage."""
    dialogue = ProductNameDialog(directory=str(tmp_path))
    qtbot.addWidget(dialogue)

    assert dialogue._liste is None


def test_appui_sur_la_liste_remplit_le_champ(qtbot, tmp_path) -> None:
    """Un appui remplit le champ plutôt que de valider directement : l'opérateur voit
    ce qu'il a choisi avant de confirmer, et peut encore le corriger."""
    _poser_preparation(tmp_path, "Calculateur ABC.json")
    dialogue = ProductNameDialog(directory=str(tmp_path))
    qtbot.addWidget(dialogue)

    dialogue._liste.itemClicked.emit(dialogue._liste.item(0))

    assert dialogue._champ.text() == "Calculateur ABC"
    assert dialogue.product_name == "Calculateur ABC"


# ------------------------------------------------- chargement d'un plateau enregistré

def _enregistrer_plateau(tmp_path, nom: str, nb_cordons: int = 2) -> None:
    """Écrit une vraie préparation sur disque, via la couche de persistance du projet."""
    cordons = [Cordon([(0.0, 0.0), (10.0, 0.0)]) for _ in range(nb_cordons)]
    save_preparation(Preparation(nom, cordons=cordons), directory=str(tmp_path))


def test_selecteur_liste_les_plateaux_enregistres(qtbot, tmp_path) -> None:
    """Le sélecteur doit proposer les préparations validées, avec de quoi les
    distinguer : le nombre de cordons répond à « est-ce bien celui d'hier ? »."""
    _enregistrer_plateau(tmp_path, "AIVC", nb_cordons=2)
    _enregistrer_plateau(tmp_path, "Calculateur XYZ", nb_cordons=1)

    dialogue = PreparationPickerDialog(directory=str(tmp_path))
    qtbot.addWidget(dialogue)

    lignes = [dialogue._liste.item(i).text() for i in range(dialogue._liste.count())]
    assert len(lignes) == 2
    assert any(l.startswith("AIVC") and "2 cordon(s)" in l for l in lignes), lignes
    assert any("Calculateur XYZ" in l and "1 cordon(s)" in l for l in lignes), lignes


def test_selecteur_ignore_les_travaux_interrompus(qtbot, tmp_path) -> None:
    """Un autosave relève de la reprise après plantage, pas du rechargement volontaire :
    les deux mécanismes ne doivent pas se mélanger."""
    _enregistrer_plateau(tmp_path, "AIVC")
    save_autosave(Preparation("Brouillon"), directory=str(tmp_path))

    dialogue = PreparationPickerDialog(directory=str(tmp_path))
    qtbot.addWidget(dialogue)

    lignes = [dialogue._liste.item(i).text() for i in range(dialogue._liste.count())]
    assert len(lignes) == 1 and lignes[0].startswith("AIVC")


def test_selecteur_rend_le_chemin_choisi(qtbot, tmp_path) -> None:
    """La première entrée est présélectionnée : un seul appui doit suffire à charger."""
    _enregistrer_plateau(tmp_path, "AIVC")

    dialogue = PreparationPickerDialog(directory=str(tmp_path))
    qtbot.addWidget(dialogue)

    assert dialogue.selected_path is not None
    assert dialogue.selected_path.endswith("AIVC.json")


def test_selecteur_sans_plateau_enregistre(qtbot, tmp_path) -> None:
    """Sur un dossier vide, le dialogue doit l'expliquer et ne rien rendre — plutôt que
    d'afficher une liste vide sans dire quoi faire."""
    dialogue = PreparationPickerDialog(directory=str(tmp_path))
    qtbot.addWidget(dialogue)

    assert dialogue._liste is None
    assert dialogue.selected_path is None


def test_selecteur_reste_utilisable_avec_un_fichier_illisible(qtbot, tmp_path) -> None:
    """Un fichier corrompu ne doit pas empêcher d'afficher les autres plateaux.

    Il reste listé et signalé plutôt que masqué : le faire disparaître laisserait
    l'opérateur croire que son travail s'est évaporé.
    """
    _enregistrer_plateau(tmp_path, "AIVC")
    (tmp_path / "Casse.json").write_text("{ ceci n'est pas du JSON", encoding="utf-8")

    dialogue = PreparationPickerDialog(directory=str(tmp_path))
    qtbot.addWidget(dialogue)

    lignes = [dialogue._liste.item(i).text() for i in range(dialogue._liste.count())]
    assert len(lignes) == 2, "le fichier illisible doit rester listé"
    assert any("illisible" in l for l in lignes), lignes


# ------------------------------------------------------------------ paramètres

def test_parametres_preremplis_avec_les_valeurs_courantes(qtbot) -> None:
    """Le dialogue doit s'ouvrir sur les réglages en vigueur, pas sur des valeurs neuves."""
    settings = Settings(
        travel_speed_mm_min=2500.0, extrusion_speed_mm_min=80.0,
        zone_diagonal_tolerance_mm=3.0, zone_max_rotation_deg=7.0,
    )

    dialogue = SettingsDialog(settings)
    qtbot.addWidget(dialogue)

    assert dialogue._vitesse_deplacement.value() == pytest.approx(2500.0)
    assert dialogue._vitesse_extrusion.value() == pytest.approx(80.0)
    assert dialogue._tolerance_diagonale.value() == pytest.approx(3.0)
    assert dialogue._rotation_max.value() == pytest.approx(7.0)


def test_parametres_modifies_ressortent(qtbot) -> None:
    """Les quatre valeurs saisies doivent se retrouver dans le Settings rendu."""
    dialogue = SettingsDialog(Settings())
    qtbot.addWidget(dialogue)

    dialogue._vitesse_deplacement.setValue(1500.0)
    dialogue._vitesse_extrusion.setValue(45.0)
    dialogue._tolerance_diagonale.setValue(2.5)
    dialogue._rotation_max.setValue(15.0)

    resultat = dialogue.settings
    assert resultat.travel_speed_mm_min == pytest.approx(1500.0)
    assert resultat.extrusion_speed_mm_min == pytest.approx(45.0)
    assert resultat.zone_diagonal_tolerance_mm == pytest.approx(2.5)
    assert resultat.zone_max_rotation_deg == pytest.approx(15.0)


def test_parametres_ne_modifient_pas_l_objet_recu(qtbot) -> None:
    """Tant que l'opérateur n'a pas validé, la préparation ne doit pas avoir bougé.

    C'est ce qui rend le bouton « Annuler » réellement sans effet : le dialogue rend un
    objet NEUF au lieu de modifier celui qu'on lui a confié.
    """
    original = Settings(travel_speed_mm_min=3000.0)
    dialogue = SettingsDialog(original)
    qtbot.addWidget(dialogue)

    dialogue._vitesse_deplacement.setValue(500.0)

    assert original.travel_speed_mm_min == pytest.approx(3000.0)
    assert dialogue.settings is not original


def test_parametres_non_edites_survivent_a_un_passage_par_la_fenetre(qtbot) -> None:
    """Les réglages que ce dialogue n'affiche pas ne doivent pas disparaître en silence.

    `SettingsDialog` rend un objet NEUF — c'est ce qui rend « Annuler » sans effet, et
    c'est voulu. Mais un objet neuf reconstruit à partir des seuls widgets perdrait tout
    ce qui n'a pas de widget : les tempos d'extrusion et la tolérance de rangée, ajoutés
    au lot D1.

    La perte serait d'autant plus traîtresse qu'elle surviendrait au moment où
    l'opérateur croit régler la machine — et elle annulerait précisément le travail de
    mise au point du sous-lot D4, qui règle ces tempos à l'œil, avec la pâte.
    """
    original = Settings(
        travel_speed_mm_min=3000.0,
        priming_seconds=1.5,
        end_anticipation_mm=4.0,
        retract_mm=0.8,
        row_tolerance_mm=12.0,
    )
    dialogue = SettingsDialog(original)
    qtbot.addWidget(dialogue)

    dialogue._vitesse_deplacement.setValue(1200.0)      # l'opérateur règle ce qu'il voit
    rendu = dialogue.settings

    assert rendu.travel_speed_mm_min == pytest.approx(1200.0)   # bien pris en compte
    assert rendu.priming_seconds == pytest.approx(1.5)          # ... et le reste intact
    assert rendu.end_anticipation_mm == pytest.approx(4.0)
    assert rendu.retract_mm == pytest.approx(0.8)
    assert rendu.row_tolerance_mm == pytest.approx(12.0)


def test_vitesses_bornees_contre_les_valeurs_aberrantes(qtbot) -> None:
    """Les bornes ne sont pas cosmétiques : une vitesse aberrante partirait telle quelle
    en G-code vers la machine."""
    dialogue = SettingsDialog(Settings())
    qtbot.addWidget(dialogue)

    dialogue._vitesse_deplacement.setValue(999999.0)   # au-delà du max Marlin
    dialogue._vitesse_extrusion.setValue(-50.0)        # négatif : sans objet

    assert dialogue._vitesse_deplacement.value() <= 24000.0
    assert dialogue._vitesse_extrusion.value() > 0.0
