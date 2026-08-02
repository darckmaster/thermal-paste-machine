# Tests unitaires pour modules/preparation.py
# Aucun matériel requis : le modèle et sa persistance sont du calcul et du fichier.
# Les tests qui écrivent sur disque utilisent la fixture pytest tmp_path, qui fournit un
# dossier temporaire propre par test — jamais le vrai dossier preparations/ du projet.

import json
import math
import os

import pytest

from modules.preparation import (
    AUTOSAVE_SUFFIX,
    FORMAT_VERSION,
    Cordon,
    Preparation,
    Settings,
    _safe_filename,
    autosave_path,
    discard_autosave,
    has_autosave,
    list_autosaves,
    list_preparations,
    load_preparation,
    next_default_product_name,
    preparation_path,
    product_name_from_path,
    save_autosave,
    save_preparation,
)
from modules.vision import DepositZone
from modules.config import WORK_AREA_HEIGHT_MM


# ------------------------------------------------------------------ utilitaires

def _zone(id_tl: int = 4, x: float = 10.0, y: float = 20.0,
          w: float = 60.0, h: float = 40.0, rotation_deg: float = 0.0) -> DepositZone:
    """Fabrique une zone dont le coin BAS-GAUCHE — son origine — est en (x, y).

    L'ancrage a suivi le lot C2bis : c'était le coin haut-gauche avant, c'est
    désormais l'origine du repère de la zone (DepositZone.origin_mm), donc le point
    auquel se rapportent tous les cordons. Ancrer les données de test sur autre chose
    que l'origine obligerait chaque test à faire mentalement la translation.

    Les 4 coins sont donnés dans l'ordre VU à l'écran (haut-gauche, haut-droit,
    bas-droit, bas-gauche), comme le fait _rectangle_from_diagonal.
    """
    theta = math.radians(rotation_deg)
    u = (math.cos(theta), math.sin(theta))       # direction de la largeur
    n = (-math.sin(theta), math.cos(theta))      # direction de la hauteur, vers le HAUT

    bas_gauche = (x, y)
    bas_droit = (x + w * u[0], y + w * u[1])
    haut_gauche = (x + h * n[0], y + h * n[1])
    haut_droit = (haut_gauche[0] + w * u[0], haut_gauche[1] + w * u[1])

    return DepositZone(
        id_top_left=id_tl,
        id_bottom_right=id_tl + 1,
        corners_mm=(haut_gauche, haut_droit, bas_droit, bas_gauche),
        rotation_deg=rotation_deg,
        diagonal_mm=math.hypot(w, h),
        size_mm=(w, h),
        anomalies=[],
    )


def _preparation_exemple() -> Preparation:
    """Une préparation complète : 2 zones et 2 cordons."""
    return Preparation(
        product_name="Calculateur ABC",
        zones=[_zone(4, 10.0, 20.0), _zone(6, 110.0, 20.0)],
        cordons=[
            Cordon([(5.0, 5.0), (55.0, 5.0)]),
            Cordon([(5.0, 35.0), (30.0, 20.0), (55.0, 35.0)]),
        ],
        reference_zone_id=4,
    )


# ------------------------------------------------------------------ Cordon

def test_cordon_longueur_somme_des_segments() -> None:
    """La longueur d'un cordon est la somme de ses segments, pas la distance
    bout à bout — un cordon en zigzag est plus long qu'il n'en a l'air."""
    cordon = Cordon([(0.0, 0.0), (30.0, 40.0), (60.0, 0.0)])

    # Deux segments de 50 mm chacun (triangle 30-40-50)
    assert cordon.length_mm == pytest.approx(100.0, abs=0.01)


def test_cordon_un_seul_point_est_invalide() -> None:
    """Un cordon d'un seul point n'a aucun segment : rien à déposer."""
    cordon = Cordon([(10.0, 10.0)])

    assert not cordon.is_valid
    assert cordon.length_mm == 0.0


def test_cordon_serialisation_aller_retour() -> None:
    """Un cordon doit survivre à un aller-retour dict → cordon sans perte utile."""
    original = Cordon([(1.234, 5.678), (10.0, 20.0)])

    reconstruit = Cordon.from_dict(original.to_dict())

    # Arrondi au centième assumé : très en deçà de la précision de la vision
    assert reconstruit.points_mm[0] == pytest.approx((1.23, 5.68), abs=0.001)
    assert reconstruit.points_mm[1] == pytest.approx((10.0, 20.0), abs=0.001)


# ------------------------------------------------------------------ repères de zone

def test_cordon_applique_a_une_zone_non_tournee() -> None:
    """Sur une zone droite, appliquer un cordon revient à une simple translation
    vers le coin BAS-gauche de la zone, qui en est l'origine."""
    zone = _zone(4, 100.0, 50.0)
    prep = Preparation("P", zones=[zone], cordons=[Cordon([(5.0, 5.0), (15.0, 5.0)])])

    polylines = prep.cordons_for_zone(zone)

    assert polylines[0][0] == pytest.approx((105.0, 55.0), abs=0.01)
    assert polylines[0][1] == pytest.approx((115.0, 55.0), abs=0.01)


def test_cordon_applique_a_une_zone_tournee() -> None:
    """Sur une zone inclinée, le cordon doit être tourné du même angle : c'est ce qui
    fait qu'un cordon tracé sur une zone reste correctement placé sur une autre, même
    si le montage n'est pas rigoureusement identique."""
    zone = _zone(4, 0.0, 0.0, rotation_deg=90.0)
    prep = Preparation("P", zones=[zone], cordons=[Cordon([(10.0, 0.0)])])

    point = prep.cordons_for_zone(zone)[0][0]

    # Une rotation de 90° dans le sens trigonométrique (positif depuis le lot C2bis)
    # amène l'axe X de la zone sur l'axe Y du plateau
    assert point == pytest.approx((0.0, 10.0), abs=0.01)


def test_conversion_zone_plateau_est_reversible() -> None:
    """to_plateau_mm et to_zone_mm doivent être exactement inverses l'une de l'autre,
    y compris sur une zone inclinée — sinon un aller-retour d'affichage déplacerait
    lentement les cordons."""
    zone = _zone(4, 37.0, 91.0, rotation_deg=7.5)
    point_origine = (12.3, 27.8)

    aller = zone.to_plateau_mm(point_origine)
    retour = zone.to_zone_mm(aller)

    assert retour == pytest.approx(point_origine, abs=1e-9)


def test_meme_cordon_applique_a_toutes_les_zones() -> None:
    """Le cœur du besoin : un cordon tracé une fois doit se retrouver au même endroit
    RELATIF dans chacune des zones du plateau."""
    zones = [_zone(4, 10.0, 20.0), _zone(6, 110.0, 20.0), _zone(8, 10.0, 90.0)]
    prep = Preparation("P", zones=zones, cordons=[Cordon([(5.0, 5.0), (55.0, 35.0)])])

    for zone in zones:
        polyline = prep.cordons_for_zone(zone)[0]
        # Le premier point doit tomber à +5/+5 de l'ORIGINE (coin bas-gauche) de
        # CHAQUE zone — c'est le point auquel se rapportent les coordonnées relatives
        coin = zone.origin_mm
        assert polyline[0] == pytest.approx((coin[0] + 5.0, coin[1] + 5.0), abs=0.01)


def test_longueur_totale_multipliee_par_le_nombre_de_zones() -> None:
    """La longueur totale à déposer couvre tout le plateau, pas une seule zone."""
    prep = Preparation(
        "P",
        zones=[_zone(4), _zone(6, 110.0)],
        cordons=[Cordon([(0.0, 0.0), (10.0, 0.0)])],
    )

    # 10 mm par zone × 2 zones
    assert prep.total_length_mm == pytest.approx(20.0, abs=0.01)


def test_zone_de_reference_retrouvee_par_son_id() -> None:
    """L'IHM doit pouvoir revenir à la zone sur laquelle les cordons ont été tracés."""
    prep = _preparation_exemple()

    assert prep.reference_zone is not None
    assert prep.reference_zone.id_top_left == 4


def test_zone_de_reference_absente_retourne_none() -> None:
    """Si la zone de référence n'est plus détectée, on ne doit pas planter."""
    prep = Preparation("P", zones=[_zone(6, 110.0)], reference_zone_id=4)

    assert prep.reference_zone is None


# ------------------------------------------------------------------ sérialisation

def test_preparation_aller_retour_complet() -> None:
    """Tout le contenu utile doit survivre à une sérialisation complète."""
    original = _preparation_exemple()

    reconstruit = Preparation.from_dict(original.to_dict())

    assert reconstruit.product_name == "Calculateur ABC"
    assert len(reconstruit.zones) == 2
    assert len(reconstruit.cordons) == 2
    assert reconstruit.reference_zone_id == 4
    assert reconstruit.zones[0].origin_mm == pytest.approx((10.0, 20.0), abs=0.01)
    # Un aller-retour ne doit PAS déclencher de conversion : le format écrit est le
    # format courant
    assert reconstruit.converted_from_version is None
    assert reconstruit.cordons[1].length_mm == pytest.approx(
        original.cordons[1].length_mm, abs=0.01
    )


def test_settings_tolere_les_cles_absentes() -> None:
    """Un fichier écrit avant l'ajout d'un paramètre doit rester lisible : les clés
    manquantes reprennent leur valeur par défaut."""
    settings = Settings.from_dict({"travel_speed_mm_min": 1234.0})

    assert settings.travel_speed_mm_min == 1234.0
    # Non fourni → valeur par défaut, pas une erreur
    assert settings.extrusion_speed_mm_min == Settings().extrusion_speed_mm_min


def test_format_version_future_refusee() -> None:
    """Un fichier écrit par une version PLUS RÉCENTE du logiciel doit être refusé
    franchement : mieux vaut une erreur claire que des coordonnées de dépose
    interprétées de travers."""
    data = _preparation_exemple().to_dict()
    data["format_version"] = FORMAT_VERSION + 1

    with pytest.raises(ValueError):
        Preparation.from_dict(data)


# ------------------------------------------------------ conversion des fichiers v1

def _fichier_v1() -> dict:
    """Un fichier tel que l'écrivait le logiciel AVANT le lot C2bis.

    Repères à Y descendant des deux côtés : le coin haut-gauche de la zone est son
    origine et porte le plus petit y, et les cordons sont mesurés depuis lui vers le
    bas. Fabriqué à la main plutôt qu'en rejouant l'ancien code : c'est le FICHIER
    qu'on doit savoir relire, pas une version passée du logiciel.
    """
    return {
        "format_version": 1,
        "product_name": "Ancien plateau",
        "reference_zone_id": 4,
        "settings": {},
        "zones": [{
            "id_top_left": 4,
            "id_bottom_right": 5,
            # Ordre vu à l'écran : haut-gauche, haut-droit, bas-droit, bas-gauche.
            # En v1 le haut portait les PETITS y.
            "corners_mm": [[10.0, 20.0], [70.0, 20.0], [70.0, 60.0], [10.0, 60.0]],
            "rotation_deg": 0.0,
            "diagonal_mm": 72.11,
            "size_mm": [60.0, 40.0],
            "anomalies": [],
        }],
        # Un cordon à 5 mm sous le bord HAUT de la zone, dans l'ancien repère
        "cordons": [{"points_mm": [[5.0, 5.0], [55.0, 5.0]]}],
    }


def test_fichier_v1_converti_et_signale() -> None:
    """Un fichier v1 doit être relu, converti, et la conversion doit être SIGNALÉE.

    Sans conversion, il serait relu silencieusement à l'envers : le contrôle de
    version ne refusait que les fichiers plus récents que le logiciel. Et sans
    signalement, l'opérateur verrait ses cordons se déplacer tout seuls — plus
    inquiétant qu'un message.
    """
    prep = Preparation.from_dict(_fichier_v1())

    assert prep.converted_from_version == 1
    assert "converti" in prep.conversion_message.lower()


def test_fichier_v1_cordons_retournes_dans_le_repere_de_la_zone() -> None:
    """Le cordon doit garder sa position PHYSIQUE sur la pièce, pas ses coordonnées.

    Il était à 5 mm du bord haut d'une zone de 40 mm de haut. Dans le repère v2, dont
    l'origine est le coin bas-gauche, ce même bord haut est à y = 40 : le cordon doit
    donc ressortir à y = 35. Un cordon laissé à y = 5 se retrouverait à l'autre bout
    de la pièce, et la buse déposerait au mauvais endroit.
    """
    prep = Preparation.from_dict(_fichier_v1())

    points = prep.cordons[0].points_mm
    assert points[0] == pytest.approx((5.0, 35.0), abs=0.01)
    assert points[1] == pytest.approx((55.0, 35.0), abs=0.01)


def test_fichier_v1_zone_retournee_dans_le_repere_du_plateau() -> None:
    """Les coins de la zone basculent eux aussi, avec la hauteur du PLATEAU.

    Deux repères sont retournés par le lot C2bis, et le fichier en contient les deux :
    n'en convertir qu'un rendrait le fichier incohérent avec lui-même — pire que de
    ne rien convertir. L'ordre des coins, lui, ne change pas : ce sont des positions
    VUES par l'opérateur, et retourner une convention ne déplace rien physiquement.
    """
    prep = Preparation.from_dict(_fichier_v1())
    zone = prep.zones[0]

    haut_gauche, _, _, bas_gauche = zone.corners_mm
    assert haut_gauche == pytest.approx((10.0, WORK_AREA_HEIGHT_MM - 20.0), abs=0.01)
    assert bas_gauche == pytest.approx((10.0, WORK_AREA_HEIGHT_MM - 60.0), abs=0.01)
    # Le haut de la zone a désormais le PLUS GRAND y — c'est tout le changement
    assert haut_gauche[1] > bas_gauche[1]
    # L'origine du repère de zone suit : c'est le coin bas-gauche
    assert zone.origin_mm == pytest.approx(bas_gauche, abs=0.01)


def test_fichier_v1_rotation_change_de_signe() -> None:
    """Un angle mesuré dans un repère retourné change de sens.

    En v1, une rotation positive était horaire à l'écran ; en v2 elle est
    trigonométrique. La zone n'a pas bougé sur le plateau : c'est son NOMBRE qui doit
    changer de signe pour continuer à la décrire.
    """
    data = _fichier_v1()
    data["zones"][0]["rotation_deg"] = 7.5

    prep = Preparation.from_dict(data)

    assert prep.zones[0].rotation_deg == pytest.approx(-7.5, abs=0.001)


def test_fichier_v1_sans_zone_mais_avec_cordons_refuse() -> None:
    """Sans zone, la hauteur nécessaire à la conversion est introuvable : il faut
    refuser franchement plutôt que de laisser passer des cordons à l'envers."""
    data = _fichier_v1()
    data["zones"] = []

    with pytest.raises(ValueError):
        Preparation.from_dict(data)


def test_fichier_v1_reecrit_en_v2_au_chargement(tmp_path) -> None:
    """load_preparation() réécrit le fichier converti : la migration n'a lieu qu'une
    fois, et le fichier sur disque cesse d'être un piège pour la lecture suivante."""
    chemin = os.path.join(str(tmp_path), "ancien.json")
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(_fichier_v1(), f)

    prep = load_preparation(chemin)
    assert prep.converted_from_version == 1

    # Le fichier sur disque porte maintenant le format courant...
    with open(chemin, encoding="utf-8") as f:
        data = json.load(f)
    assert data["format_version"] == FORMAT_VERSION

    # ...et une seconde lecture ne convertit plus rien, sans déplacer les cordons
    relu = load_preparation(chemin)
    assert relu.converted_from_version is None
    assert relu.cordons[0].points_mm[0] == pytest.approx((5.0, 35.0), abs=0.01)


# --------------------------------------------------- nom de produit par defaut (lot C3)

def _poser_fichier(tmp_path, nom_fichier: str) -> None:
    """Crée un fichier de préparation vide, juste pour occuper un nom."""
    (tmp_path / nom_fichier).write_text("{}", encoding="utf-8")


@pytest.mark.parametrize("chemin, attendu", [
    ("preparations/BOITIER_3.json", "BOITIER_3"),
    ("preparations/BOITIER_3.autosave.json", "BOITIER_3"),
    ("preparations/REF 12_34.json", "REF 12_34"),
])
def test_nom_de_produit_deduit_du_chemin(chemin: str, attendu: str) -> None:
    """Le suffixe d'autosave doit être retiré AVANT l'extension.

    Sans cette précaution, `os.path.splitext` ne retirerait que le `.json` final et
    laisserait un `.autosave` parasite dans le nom du produit — qui serait alors
    présenté tel quel à l'opérateur, et compté comme un produit distinct.
    """
    assert product_name_from_path(chemin) == attendu


def test_premier_nom_par_defaut_sur_dossier_vide(tmp_path) -> None:
    """Sur un dépôt fraîchement cloné, le premier plateau doit s'appeler BOITIER_1.

    C'est tout l'intérêt de la décision du 2026-08-01 : aucun compteur à initialiser
    nulle part, le dossier des préparations porte à lui seul l'information.
    """
    assert next_default_product_name(str(tmp_path)) == "BOITIER_1"


def test_nom_par_defaut_saute_les_numeros_pris(tmp_path) -> None:
    """Les numéros déjà utilisés ne doivent pas être réattribués."""
    _poser_fichier(tmp_path, "BOITIER_1.json")
    _poser_fichier(tmp_path, "BOITIER_2.json")

    assert next_default_product_name(str(tmp_path)) == "BOITIER_3"


def test_nom_par_defaut_remplit_le_premier_trou(tmp_path) -> None:
    """Après suppression d'un plateau, son numéro redevient libre et est réutilisé.

    Choix assumé : la numérotation sert à distinguer des plateaux de travail, pas à
    tracer un historique. Un compteur toujours croissant obligerait à conserver un état
    en dehors du dossier — exactement ce qu'on voulait éviter.
    """
    _poser_fichier(tmp_path, "BOITIER_1.json")
    _poser_fichier(tmp_path, "BOITIER_3.json")

    assert next_default_product_name(str(tmp_path)) == "BOITIER_2"


def test_nom_par_defaut_compte_les_travaux_interrompus(tmp_path) -> None:
    """Un BOITIER_1 interrompu garde son numéro : le réattribuer ferait travailler
    deux plateaux différents sous le même nom, et le second écraserait le premier."""
    _poser_fichier(tmp_path, "BOITIER_1" + AUTOSAVE_SUFFIX)

    assert next_default_product_name(str(tmp_path)) == "BOITIER_2"


def test_nom_par_defaut_ignore_les_references_libres(tmp_path) -> None:
    """Une référence saisie par l'opérateur ne consomme aucun numéro automatique."""
    _poser_fichier(tmp_path, "Calculateur ABC.json")
    _poser_fichier(tmp_path, "BOITIER_XYZ.json")   # ne finit pas par un entier

    assert next_default_product_name(str(tmp_path)) == "BOITIER_1"


# ------------------------------------------------------------------ noms de fichiers

@pytest.mark.parametrize("nom, attendu", [
    ("REF 12/34", "REF 12_34"),          # la barre oblique créerait un sous-dossier
    ("A:B*C?", "A_B_C_"),                # caractères interdits sous Windows
    ("  espaces  ", "espaces"),          # espaces de bord retirés
    ("", "sans_nom"),                    # un nom vide donnerait un fichier caché
])
def test_nom_de_fichier_assaini(nom: str, attendu: str) -> None:
    """Le nom du produit est saisi librement mais sert de nom de fichier : les
    caractères qui casseraient le chemin doivent être neutralisés."""
    assert _safe_filename(nom) == attendu


def test_nom_du_produit_conserve_tel_quel_dans_le_fichier(tmp_path) -> None:
    """Seul le NOM DE FICHIER est assaini : la référence exacte du produit doit
    rester intacte dans le contenu, puisqu'elle est affichée à l'opérateur."""
    prep = Preparation("REF 12/34")

    chemin = save_preparation(prep, directory=str(tmp_path))

    assert os.path.basename(chemin) == "REF 12_34.json"
    assert load_preparation(chemin).product_name == "REF 12/34"


# ------------------------------------------------------------------ persistance

def test_enregistrement_puis_relecture(tmp_path) -> None:
    """Une préparation enregistrée doit se relire à l'identique."""
    original = _preparation_exemple()

    chemin = save_preparation(original, directory=str(tmp_path))
    relu = load_preparation(chemin)

    assert relu.product_name == original.product_name
    assert len(relu.zones) == len(original.zones)
    assert relu.total_length_mm == pytest.approx(original.total_length_mm, abs=0.01)


def test_fichier_ecrit_est_un_json_lisible(tmp_path) -> None:
    """Le fichier doit rester lisible à l'œil : c'est un livrable du projet, on doit
    pouvoir l'ouvrir dans un éditeur pour comprendre ou corriger."""
    chemin = save_preparation(_preparation_exemple(), directory=str(tmp_path))

    contenu = open(chemin, encoding="utf-8").read()
    data = json.loads(contenu)

    assert data["format_version"] == FORMAT_VERSION
    assert "\n" in contenu, "le JSON doit être indenté, pas sur une seule ligne"


def test_coordonnees_gardees_sur_une_seule_ligne(tmp_path) -> None:
    """Les paires [x, y] ne doivent pas être éclatées par l'indenteur : sans ça, un
    plateau de 6 zones donnerait des centaines de lignes de crochets quasi vides.

    Le fichier doit rester du JSON parfaitement standard malgré ce formatage.
    """
    chemin = save_preparation(_preparation_exemple(), directory=str(tmp_path))
    contenu = open(chemin, encoding="utf-8").read()

    # Le fichier reste relisible par un parseur JSON standard
    data = json.loads(contenu)
    assert data["cordons"][0]["points_mm"][0] == [5.0, 5.0]

    # Et une coordonnée tient bien sur une seule ligne
    assert "[5.0, 5.0]" in contenu, (
        "les paires de coordonnées doivent rester inline\n" + contenu
    )
    # Aucun jeton interne ne doit subsister dans le livrable
    assert "__PAIRE__" not in contenu


def test_formatage_inline_ne_touche_pas_aux_listes_non_coordonnees(tmp_path) -> None:
    """Seules les paires de NOMBRES sont concernées : une liste d'anomalies (des
    chaînes) ou une liste de 4 coins ne doit pas être transformée."""
    prep = _preparation_exemple()
    prep.zones[0].anomalies = ["zone_inversee", "angle_excessif"]

    chemin = save_preparation(prep, directory=str(tmp_path))
    data = json.loads(open(chemin, encoding="utf-8").read())

    assert data["zones"][0]["anomalies"] == ["zone_inversee", "angle_excessif"]
    assert len(data["zones"][0]["corners_mm"]) == 4


def test_accents_du_nom_de_produit_preserves(tmp_path) -> None:
    """Les références produit accentuées doivent rester lisibles dans le fichier,
    pas échappées en séquences \\uXXXX."""
    save_preparation(Preparation("Boîtier Réf. Été"), directory=str(tmp_path))

    contenu = open(
        os.path.join(str(tmp_path), "Boîtier Réf. Été.json"), encoding="utf-8"
    ).read()

    assert "Boîtier Réf. Été" in contenu


def test_autosave_n_ecrase_pas_le_fichier_definitif(tmp_path) -> None:
    """Tant que l'opérateur n'a pas validé, son dernier enregistrement volontaire doit
    rester intact — c'est toute la raison d'avoir deux fichiers."""
    dossier = str(tmp_path)
    prep = _preparation_exemple()
    save_preparation(prep, directory=dossier)

    # Le travail continue : un cordon est ajouté, seul l'autosave doit en tenir compte
    prep.cordons.append(Cordon([(0.0, 0.0), (10.0, 10.0)]))
    save_autosave(prep, directory=dossier)

    definitif = load_preparation(preparation_path(prep.product_name, dossier))
    automatique = load_preparation(autosave_path(prep.product_name, dossier))

    assert len(definitif.cordons) == 2, "le fichier définitif ne doit pas avoir bougé"
    assert len(automatique.cordons) == 3, "l'autosave doit contenir le travail en cours"


def test_enregistrement_definitif_supprime_l_autosave(tmp_path) -> None:
    """Une fois le travail validé, le filet anti-plantage n'a plus lieu d'être : le
    laisser ferait proposer une reprise inutile au prochain démarrage."""
    dossier = str(tmp_path)
    prep = _preparation_exemple()

    save_autosave(prep, directory=dossier)
    assert has_autosave(prep.product_name, dossier)

    save_preparation(prep, directory=dossier)

    assert not has_autosave(prep.product_name, dossier)


def test_discard_autosave_sans_fichier_ne_plante_pas(tmp_path) -> None:
    """Refuser de reprendre un travail qui n'existe pas ne doit pas lever d'erreur."""
    discard_autosave("produit inexistant", directory=str(tmp_path))


def test_list_autosaves_du_plus_recent_au_plus_ancien(tmp_path) -> None:
    """Au démarrage, le travail le plus probable est le dernier interrompu : il doit
    arriver en tête de liste."""
    dossier = str(tmp_path)
    save_autosave(Preparation("ancien"), directory=dossier)
    save_autosave(Preparation("recent"), directory=dossier)

    # Forcer un écart de dates : la résolution de getmtime est trop grossière pour
    # distinguer deux écritures consécutives dans le même test
    os.utime(autosave_path("ancien", dossier), (1, 1))

    chemins = list_autosaves(dossier)

    assert [os.path.basename(c) for c in chemins] == [
        f"recent{AUTOSAVE_SUFFIX}", f"ancien{AUTOSAVE_SUFFIX}"
    ]


def test_list_preparations_exclut_les_autosaves(tmp_path) -> None:
    """Un travail en cours n'est pas une préparation validée : il ne doit pas
    apparaître dans la liste des préparations enregistrées."""
    dossier = str(tmp_path)
    save_preparation(Preparation("valide"), directory=dossier)
    save_autosave(Preparation("en cours"), directory=dossier)

    noms = [os.path.basename(c) for c in list_preparations(dossier)]

    assert noms == ["valide.json"]


def test_listes_sur_dossier_inexistant(tmp_path) -> None:
    """Au tout premier démarrage, le dossier n'existe pas encore : les listes doivent
    être vides, pas lever une exception."""
    inexistant = os.path.join(str(tmp_path), "jamais_cree")

    assert list_autosaves(inexistant) == []
    assert list_preparations(inexistant) == []


def test_ecriture_ne_laisse_pas_de_fichier_temporaire(tmp_path) -> None:
    """L'écriture atomique passe par un fichier temporaire : il ne doit rien rester
    une fois l'opération terminée."""
    dossier = str(tmp_path)
    save_preparation(_preparation_exemple(), directory=dossier)

    restes = [n for n in os.listdir(dossier) if n.endswith(".tmp")]

    assert restes == [], f"fichiers temporaires oubliés : {restes}"
