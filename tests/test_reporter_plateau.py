# Tests du rapport de fin de cycle multi-zones (lot D3) — modules/reporter.py
#
# Le CONTENU du rapport est testé sur `plateau_report_lines()`, qui rend les lignes une
# par une. C'est la raison d'être de cette séparation : la règle qui gouverne ce rapport —
# détail par zone uniquement en cas d'interruption (décision D9) — est une règle de
# contenu, et la vérifier à travers un PDF compressé serait pénible et fragile.
#
# Le RENDU est testé à part, et plus grossièrement : qu'un fichier sorte, qu'il ne soit
# pas vide, qu'il n'en écrase aucun autre.

import os

import cv2
import numpy as np
import pytest

from modules.reporter import (
    Reporter, plateau_report_lines, _ecrire_image_temporaire,
)


def _lignes(**kwargs) -> list:
    """Lignes du rapport, avec des valeurs par défaut plausibles."""
    defauts = dict(
        product_name="Calculateur ABC",
        zones_faites=[4, 6],
        zones_prevues=[4, 6],
        seconds=95,
        interrupted=False,
        dry_run=False,
        length_mm=250.0,
        amount_mm=25.0,
    )
    defauts.update(kwargs)
    return plateau_report_lines(**defauts)


def _texte(**kwargs) -> str:
    return "\n".join(_lignes(**kwargs))


# ================================================================ décision D9

def test_le_rapport_nominal_ne_detaille_pas_les_zones():
    """DÉCISION D9 — un tableau dont toutes les lignes disent « fait » noie l'information.

    En marche nominale, le nombre de zones suffit. Le détail par zone n'apporte rien et
    repousse plus bas ce qu'on cherche vraiment.
    """
    texte = _texte(interrupted=False)

    assert "Zones deposees  : 2 / 2" in texte
    assert "Zone 4 :" not in texte
    assert "Zone 6 :" not in texte


def test_le_rapport_interrompu_dit_quelles_zones_n_ont_pas_ete_faites():
    """Après un arrêt, c'est le seul renseignement qui compte pour la traçabilité.

    Savoir quelles pièces ont reçu de la pâte détermine ce qu'on fait du plateau : ce
    qu'on garde, ce qu'on nettoie, ce qu'on refait.
    """
    texte = _texte(interrupted=True, zones_faites=[4], zones_prevues=[4, 6, 8])

    assert "DEPOSE INTERROMPUE" in texte
    assert "Zone 4 : deposee" in texte
    assert "Zone 6 : NON deposee" in texte
    assert "Zone 8 : NON deposee" in texte
    # ... et ce qu'il faut en faire
    assert "dose partielle" in texte


def test_le_statut_est_la_premiere_ligne():
    """C'est la première chose qu'on lit sur un rapport : elle ne doit pas être enfouie."""
    assert _lignes(interrupted=False)[0] == "Depose terminee"
    assert _lignes(interrupted=True)[0] == "DEPOSE INTERROMPUE"


# ================================================================ avertissements

def test_la_depose_a_blanc_est_annoncee_avant_le_resume():
    """Un rapport de dépose à blanc n'atteste pas d'une dépose : il faut le lire d'abord.

    Placé après le résumé, l'avertissement serait lu une fois les chiffres déjà pris pour
    argent comptant.
    """
    lignes = _lignes(dry_run=True)

    index_avertissement = next(
        i for i, l in enumerate(lignes) if "DEPOSE A BLANC" in l
    )
    index_resume = next(
        i for i, l in enumerate(lignes) if l.startswith("Zones deposees")
    )
    assert index_avertissement < index_resume


def test_la_depose_a_blanc_n_annonce_aucune_quantite_de_pate():
    """Afficher « 0,00 mm d'axe E » laisserait croire à une dépose qui a mal extrudé.

    Il vaut mieux ne rien dire que d'annoncer un zéro qui ressemble à une panne.
    """
    assert "axe E" not in _texte(dry_run=True)
    assert "axe E" in _texte(dry_run=False)


def test_un_cadrage_non_reference_est_signale():
    """Après un arrêt, la machine ne peut plus bouger : la vue n'a pas le cadrage habituel.

    Sans ce mot, on comparerait deux rapports en croyant comparer deux plateaux.
    """
    assert "cadrage" in _texte(cadrage_incertain=True).lower()
    assert "cadrage" not in _texte(cadrage_incertain=False).lower()


def test_le_temps_est_lisible_en_minutes_et_secondes():
    assert "1 min 35 s" in _texte(seconds=95)
    assert "0 min 07 s" in _texte(seconds=7)


# ================================================================ rendu PDF

def test_le_pdf_est_produit_et_non_vide(tmp_path):
    reporter = Reporter(output_dir=str(tmp_path))
    image = np.full((80, 120, 3), 200, dtype=np.uint8)

    chemin = reporter.generate_plateau_report(
        image=image, product_name="PROD", zones_faites=[4], zones_prevues=[4],
        seconds=30, interrupted=False, dry_run=True,
    )

    assert os.path.exists(chemin)
    assert os.path.getsize(chemin) > 500


def test_un_rapport_reste_produisible_sans_vue(tmp_path):
    """Une photo ratée ne doit pas priver l'opérateur de son rapport.

    Le cycle a eu lieu : il doit pouvoir en rendre compte, avec ou sans image.
    """
    reporter = Reporter(output_dir=str(tmp_path))

    chemin = reporter.generate_plateau_report(
        image=None, product_name="PROD", zones_faites=[4], zones_prevues=[4],
        seconds=30, interrupted=False, dry_run=False,
    )

    assert os.path.exists(chemin)


def test_deux_rapports_de_la_meme_seconde_ne_s_ecrasent_pas(tmp_path):
    """⚠️ L'horodatage à la seconde ne suffit pas comme nom de fichier.

    Réimprimer un rapport aussitôt après le premier est un geste normal — et rien ne
    l'empêche. Sur un document de traçabilité, perdre un rapport sans le dire est
    exactement ce qu'on ne peut pas se permettre.
    """
    reporter = Reporter(output_dir=str(tmp_path))
    parametres = dict(
        image=None, product_name="PROD", zones_faites=[4], zones_prevues=[4],
        seconds=30, interrupted=False, dry_run=False,
    )

    chemins = [reporter.generate_plateau_report(**parametres) for _ in range(3)]

    assert len(set(chemins)) == 3, "les trois rapports doivent etre des fichiers distincts"
    assert all(os.path.exists(c) for c in chemins)


def test_la_vue_alourdit_le_pdf(tmp_path):
    """Contrôle que l'image est réellement intégrée, et pas seulement acceptée."""
    reporter = Reporter(output_dir=str(tmp_path))
    parametres = dict(
        product_name="PROD", zones_faites=[4], zones_prevues=[4],
        seconds=30, interrupted=False, dry_run=True,
    )

    sans = reporter.generate_plateau_report(image=None, **parametres)
    avec = reporter.generate_plateau_report(
        image=np.full((200, 300, 3), 128, dtype=np.uint8), **parametres
    )

    assert os.path.getsize(avec) > os.path.getsize(sans)


# ================================================================ emplacement des rapports

def test_le_dossier_par_defaut_est_absolu_et_a_la_racine_du_projet():
    """Les rapports doivent atterrir à la racine du projet, jamais dans le dossier courant.

    Un chemin relatif suivrait le répertoire depuis lequel l'application a été lancée :
    raccourci du bureau, service au démarrage du RPi, double-clic. Les rapports se
    disperseraient à des endroits qu'on ne penserait pas à aller regarder, et **rien ne
    le signalerait** — on croirait simplement qu'ils n'ont pas été produits.
    """
    from modules.config import REPORTS_DIR

    reporter = Reporter()

    assert os.path.isabs(reporter._output_dir)
    assert reporter._output_dir == REPORTS_DIR
    # ... et c'est bien un frère de modules/, donc la racine du projet
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assert os.path.dirname(REPORTS_DIR) == racine


def test_le_dossier_par_defaut_ne_depend_pas_du_repertoire_courant(tmp_path, monkeypatch):
    """Le test qui prouve vraiment la propriété : on change de répertoire courant.

    Vérifier que le chemin est absolu ne suffit pas — il pourrait être rendu absolu à
    partir du dossier courant, ce qui reproduirait exactement le défaut.
    """
    from modules.config import REPORTS_DIR

    monkeypatch.chdir(tmp_path)

    assert Reporter()._output_dir == REPORTS_DIR


# ================================================================ couleurs de la vue

def test_l_image_du_rapport_n_a_pas_le_rouge_et_le_bleu_inverses(tmp_path):
    """⚠️ Défaut présent depuis la Phase 7, trouvé en écrivant D3.

    `cv2.imwrite` suppose déjà que le tableau qu'on lui donne est en BGR : appeler
    `cvtColor(BGR2RGB)` avant revenait à convertir deux fois, donc à **échanger le rouge
    et le bleu** dans le fichier enregistré. Tous les rapports produits jusqu'ici avaient
    des couleurs fausses.

    Le test écrit un bleu franc et vérifie qu'il ressort bleu.
    """
    # BGR pur bleu : (255, 0, 0) dans la convention OpenCV
    image = np.zeros((60, 60, 3), dtype=np.uint8)
    image[:, :, 0] = 255

    chemin = _ecrire_image_temporaire(image)
    try:
        relue = cv2.imread(chemin)   # imread rend du BGR
        bleu, vert, rouge = relue[30, 30]
    finally:
        os.remove(chemin)

    # JPEG est destructif : on raisonne en dominante, pas en valeur exacte
    assert bleu > 200, f"le bleu devait rester bleu, canal B = {bleu}"
    assert rouge < 60, f"le rouge devait rester nul, canal R = {rouge}"
