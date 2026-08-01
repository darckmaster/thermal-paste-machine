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
    preparation_path,
    save_autosave,
    save_preparation,
)
from modules.vision import DepositZone


# ------------------------------------------------------------------ utilitaires

def _zone(id_tl: int = 4, x: float = 10.0, y: float = 20.0,
          w: float = 60.0, h: float = 40.0, rotation_deg: float = 0.0) -> DepositZone:
    """Fabrique une zone dont le coin haut-gauche est en (x, y).

    Les 4 coins sont calculés comme le fait _rectangle_from_diagonal : rotation
    appliquée aux deux vecteurs de côté depuis le coin haut-gauche.
    """
    theta = math.radians(rotation_deg)
    u = (math.cos(theta), math.sin(theta))       # direction de la largeur
    v = (-math.sin(theta), math.cos(theta))      # direction de la hauteur

    haut_gauche = (x, y)
    haut_droit = (x + w * u[0], y + w * u[1])
    bas_droit = (haut_droit[0] + h * v[0], haut_droit[1] + h * v[1])
    bas_gauche = (x + h * v[0], y + h * v[1])

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
    vers le coin haut-gauche de la zone."""
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

    # Une rotation de 90° dans un repère dont le Y descend amène l'axe X sur l'axe Y
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
        # Le premier point doit tomber à +5/+5 du coin haut-gauche de CHAQUE zone
        coin = zone.corners_mm[0]
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
    assert reconstruit.zones[0].corners_mm[0] == pytest.approx((10.0, 20.0), abs=0.01)
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
