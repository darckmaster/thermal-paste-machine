# Tests du parcours multi-zones (lot D1) — modules/path_planner.py
# Pas de matériel requis : logique pure, aucune caméra, aucune machine, aucune IHM.
#
# Ces tests portent sur des INVARIANTS, c'est-à-dire des propriétés du résultat, et non
# sur la façon dont il est calculé. C'est voulu : la dépose est la fonction critique de la
# machine, et le lot D sera livré en cinq fois. Un test qui décrit le résultat survit à une
# réécriture interne ; un test qui décrit l'implémentation casse à chaque session et finit
# par être affaibli pour qu'il passe — ce qui est pire que pas de test du tout.

import math

import pytest

from modules.path_planner import (
    PathPlanner,
    sort_zones_for_deposit,
    split_polyline_at,
    plateau_to_machine_mm,
    check_machine_limits,
    format_limit_violations,
)
from modules.preparation import Cordon, Settings
from modules.vision import DepositZone


# ------------------------------------------------------------------ utilitaires

def _zone(id_tl: int = 4, x: float = 10.0, y: float = 20.0,
          w: float = 60.0, h: float = 40.0, rotation_deg: float = 0.0) -> DepositZone:
    """Fabrique une zone dont le coin BAS-GAUCHE — son origine — est en (x, y).

    Même fabrique que dans test_preparation.py. Ancrer sur l'origine et non sur un autre
    coin évite à chaque test de refaire mentalement la translation.
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


# Origine machine FIXE pour les tests, volontairement différente de la vraie.
# Les valeurs réelles sont une mesure physique qui a déjà changé trois fois : y adosser
# les tests les ferait tomber à la prochaine mesure, sans qu'aucun défaut n'existe.
ORIGINE_X = 100.0
ORIGINE_Y = 50.0

Z_DEPOSE = 1.0
Z_TRANSIT = 5.0


def _planner(settings: Settings = None, dry_run: bool = False) -> PathPlanner:
    return PathPlanner.from_settings(
        settings or Settings(travel_speed_mm_min=1000.0, extrusion_speed_mm_min=100.0),
        z_dispense_mm=Z_DEPOSE,
        z_travel_mm=Z_TRANSIT,
        dry_run=dry_run,
        machine_origin_x=ORIGINE_X,
        machine_origin_y=ORIGINE_Y,
    )


def _cordon_en_L() -> Cordon:
    """Un cordon volontairement ASYMÉTRIQUE, en L.

    Un tracé symétrique ne trahit pas son propre retournement : c'est exactement ainsi
    qu'un miroir vertical a survécu de la Phase 2 au 2026-08-01 sans que personne ne le
    voie. Toute donnée de test géométrique de ce fichier est donc dissymétrique.
    """
    return Cordon([(5.0, 5.0), (25.0, 5.0), (25.0, 15.0)])


# ================================================================ I4 — ordre de parcours

def test_ordre_par_rangees_du_bas_vers_le_haut_et_de_gauche_a_droite():
    """La rangée du bas d'abord, de gauche à droite, puis celle du dessus."""
    bas_gauche = _zone(id_tl=4, x=10.0, y=10.0)
    bas_droite = _zone(id_tl=6, x=100.0, y=10.0)
    haut_gauche = _zone(id_tl=8, x=10.0, y=100.0)
    haut_droite = _zone(id_tl=10, x=100.0, y=100.0)

    ordre = sort_zones_for_deposit([haut_droite, bas_droite, haut_gauche, bas_gauche])

    assert [z.id_top_left for z in ordre] == [4, 6, 8, 10]


def test_ordre_insensible_a_l_ordre_dans_lequel_les_zones_arrivent():
    """INVARIANT I4 — le tri ne doit rien devoir à l'ordre de détection.

    La vision ne rend pas les zones dans un ordre stable : il dépend de l'image. Si le
    parcours en héritait, un même plateau serait déposé dans un ordre différent d'une
    photo à l'autre, et la reprise après un arrêt deviendrait illisible.
    """
    zones = [
        _zone(id_tl=4, x=10.0, y=10.0),
        _zone(id_tl=6, x=100.0, y=10.0),
        _zone(id_tl=8, x=10.0, y=100.0),
    ]
    attendu = [z.id_top_left for z in sort_zones_for_deposit(zones)]

    # Toutes les permutations de la liste d'entrée doivent donner le même ordre
    import itertools
    for permutation in itertools.permutations(zones):
        obtenu = [z.id_top_left for z in sort_zones_for_deposit(list(permutation))]
        assert obtenu == attendu


def test_zones_legerement_desalignees_restent_sur_la_meme_rangee():
    """La vision ne rend jamais deux ordonnées exactement égales.

    Deux zones physiquement alignées, mesurées à 1,5 mm près, doivent rester sur la même
    rangée — sinon celle de droite passerait devant celle de gauche par le seul effet du
    bruit de mesure.
    """
    gauche = _zone(id_tl=4, x=10.0, y=10.0, h=40.0)
    droite = _zone(id_tl=6, x=100.0, y=11.5, h=40.0)   # 1,5 mm plus haut, même rangée

    ordre = sort_zones_for_deposit([droite, gauche])

    assert [z.id_top_left for z in ordre] == [4, 6]


def test_deux_rangees_franchement_distinctes_ne_fusionnent_pas():
    """La tolérance ne doit pas non plus tout confondre : 90 mm, c'est deux rangées."""
    bas = _zone(id_tl=4, x=100.0, y=10.0, h=40.0)      # à DROITE, mais en bas
    haut = _zone(id_tl=6, x=10.0, y=100.0, h=40.0)     # à gauche, mais en haut

    ordre = sort_zones_for_deposit([haut, bas])

    # La zone du bas passe en premier même si elle est plus à droite
    assert [z.id_top_left for z in ordre] == [4, 6]


def test_zones_regulierement_espacees_ne_se_rattachent_pas_de_proche_en_proche():
    """Chaque zone est comparée à la PREMIÈRE de sa rangée, pas à la précédente.

    Sans cela, des zones espacées d'un peu moins que la tolérance se rattacheraient de
    proche en proche et finiraient toutes dans une seule « rangée », aussi éloignées
    soient-elles l'une de l'autre.
    """
    # Tolérance automatique = 40 / 2 = 20 mm. Trois zones espacées de 15 mm en Y :
    # chacune est à moins de 20 mm de la précédente, mais la troisième est à 30 mm de la
    # première — elle doit donc ouvrir une nouvelle rangée.
    z1 = _zone(id_tl=4, x=50.0, y=0.0, h=40.0)
    z2 = _zone(id_tl=6, x=40.0, y=15.0, h=40.0)
    z3 = _zone(id_tl=8, x=30.0, y=30.0, h=40.0)

    ordre = sort_zones_for_deposit([z1, z2, z3])

    # Rangée 1 = {z1, z2} triées par x → 6 puis 4 ; rangée 2 = {z3}
    assert [z.id_top_left for z in ordre] == [6, 4, 8]


def test_liste_de_zones_vide():
    """Aucune zone sélectionnée : pas d'erreur, une liste vide."""
    assert sort_zones_for_deposit([]) == []


# ================================================================ I8 / I9 — chaîne de repères

def test_conversion_verifiee_sur_un_point_interieur_du_cordon():
    """INVARIANT I8 — vérifier sur un point qui n'a PAS servi à poser le repère.

    ⚠️ Règle de méthode acquise le 2026-08-02 : un ajustement retombe toujours juste sur
    ses propres points d'appui, c'est sa définition et non une preuve. Un test sur les
    coins de la zone ne prouverait donc rien du tout — c'est exactement ainsi qu'un
    défaut de repère avait échappé à 193 tests verts.

    On prend ici un point INTÉRIEUR, sur une zone TOURNÉE, et on refait le calcul à la
    main par un autre chemin que celui du code.
    """
    zone = _zone(id_tl=4, x=10.0, y=20.0, w=60.0, h=40.0, rotation_deg=30.0)
    planner = _planner()

    point_zone = (17.0, 11.0)            # ni un coin, ni un milieu, ni sur un axe
    obtenu = planner.zone_point_to_machine_mm(zone, point_zone)

    # Calcul indépendant : rotation de 30°, translation vers l'origine de la zone,
    # puis addition de l'origine machine.
    theta = math.radians(30.0)
    x_att = 10.0 + 17.0 * math.cos(theta) - 11.0 * math.sin(theta) + ORIGINE_X
    y_att = 20.0 + 17.0 * math.sin(theta) + 11.0 * math.cos(theta) + ORIGINE_Y

    assert obtenu[0] == pytest.approx(x_att)
    assert obtenu[1] == pytest.approx(y_att)


def test_boussole_une_zone_plus_a_droite_donne_un_x_machine_plus_grand():
    """INVARIANT I9 — assertif sur le SENS, pas sur une valeur.

    Un test sur des valeurs numériques change de valeurs attendues à chaque remesure de
    l'origine. Un test sur le sens épingle la CONVENTION, qui elle ne doit pas bouger.
    """
    gauche = _zone(id_tl=4, x=10.0, y=20.0)
    droite = _zone(id_tl=6, x=90.0, y=20.0)
    planner = _planner()

    x_gauche = planner.zone_point_to_machine_mm(gauche, (0.0, 0.0))[0]
    x_droite = planner.zone_point_to_machine_mm(droite, (0.0, 0.0))[0]

    assert x_droite > x_gauche


def test_boussole_une_zone_plus_haute_donne_un_y_machine_plus_grand():
    """INVARIANT I9 — le pendant vertical, celui qui attrape un miroir.

    C'est ici que se verrait un retour à l'ancienne convention (Y descendant) : une zone
    plus haute sur le plateau rendrait alors un Y machine plus PETIT.
    """
    bas = _zone(id_tl=4, x=10.0, y=20.0)
    haut = _zone(id_tl=6, x=10.0, y=120.0)
    planner = _planner()

    y_bas = planner.zone_point_to_machine_mm(bas, (0.0, 0.0))[1]
    y_haut = planner.zone_point_to_machine_mm(haut, (0.0, 0.0))[1]

    assert y_haut > y_bas


def test_plateau_vers_machine_est_une_double_addition():
    """La conversion plateau → machine ne doit rester que deux additions.

    Une soustraction qui réapparaîtrait ici signalerait un retour de l'inversion isolée
    que le lot C2bis a supprimée.
    """
    assert plateau_to_machine_mm((10.0, 20.0), 6.0, -2.0) == (16.0, 18.0)


# ================================================================ I1 / I2 / I3 — structure

def test_chaque_zone_selectionnee_apparait_exactement_une_fois():
    """INVARIANT I3 — ni zone oubliée, ni zone déposée deux fois."""
    zones = [
        _zone(id_tl=4, x=10.0, y=10.0),
        _zone(id_tl=6, x=100.0, y=10.0),
        _zone(id_tl=8, x=10.0, y=100.0),
    ]
    steps = _planner().generate_plateau_path(zones, [_cordon_en_L()])

    vues = [s["zone"] for s in steps]
    for zone in zones:
        assert vues.count(zone.id_top_left) >= 1
    # Chaque zone forme un bloc contigu : les zones ne s'entrelacent pas
    assert sorted(set(vues)) == [4, 6, 8]
    blocs = [cle for cle, _ in _groupes_consecutifs(vues)]
    assert blocs == [4, 6, 8]


def _groupes_consecutifs(valeurs: list) -> list:
    """Regroupe les valeurs consécutives identiques : [4,4,6,6,4] → [(4,2),(6,2),(4,1)]."""
    groupes = []
    for valeur in valeurs:
        if groupes and groupes[-1][0] == valeur:
            groupes[-1][1] += 1
        else:
            groupes.append([valeur, 1])
    return [(cle, n) for cle, n in groupes]


def test_la_buse_passe_par_le_zero_de_chaque_zone():
    """DÉCISION D8 — le passage au zéro de zone est un vrai mouvement, pas un calcul.

    Il ne dépose rien et n'est pas nécessaire au tracé : il est là pour être VU. C'est le
    seul contrôle à l'œil de la chaîne de repères tant que la dépose se fait sans pâte,
    le sens réel des axes machine (action M4) n'étant pas validé.
    """
    zone = _zone(id_tl=4, x=10.0, y=20.0)
    steps = _planner().generate_plateau_path([zone], [_cordon_en_L()])

    origine_attendue = plateau_to_machine_mm((10.0, 20.0), ORIGINE_X, ORIGINE_Y)
    premier = steps[0]

    assert premier["type"] == "travel"
    assert premier["z"] == Z_TRANSIT
    assert premier["x"] == pytest.approx(origine_attendue[0])
    assert premier["y"] == pytest.approx(origine_attendue[1])


def test_aucune_depose_ailleurs_qu_a_la_hauteur_de_depose():
    """INVARIANT I1 — une dépose en l'air, ou dans la pièce, serait invisible aux tests."""
    zones = [_zone(id_tl=4, x=10.0, y=10.0), _zone(id_tl=6, x=100.0, y=10.0)]
    steps = _planner().generate_plateau_path(zones, [_cordon_en_L()])

    for step in steps:
        if step["type"] == "dispense":
            assert step["z"] == Z_DEPOSE


def test_aucun_deplacement_xy_ne_part_de_la_hauteur_de_depose_pour_changer_de_cordon():
    """INVARIANT I2 — le défaut le plus coûteux visuellement : la buse qui traîne.

    ⚠️ **Le point subtil, et la raison d'être exacte de ce test.** Un step porte x, y ET
    z, mais la machine ne les exécute pas ensemble : `Machine.move_to()` envoie d'abord
    `G1 X Y`, puis `G1 Z` (voir modules/machine.py). Le déplacement XY a donc lieu à la
    hauteur du step **PRÉCÉDENT**, pas à la sienne.

    Conséquence : regarder le `z` du step qui bouge ne prouve rien. Un step « remonter à
    5 mm en allant en (30, 40) » descend en réalité la buse à travers toute la pâte déjà
    posée avant de remonter. La première version de ce test faisait exactement cette
    erreur et laissait passer la suppression de la remontée de fin de cordon — seul le
    test doré l'avait vue. C'est la hauteur de DÉPART qu'il faut regarder.

    La règle testée : tout déplacement XY qui part de la hauteur de dépose doit y rester
    — c'est alors qu'on est en train de tracer. Changer de cordon impose donc d'être
    remonté d'abord.
    """
    zones = [_zone(id_tl=4, x=10.0, y=10.0), _zone(id_tl=6, x=100.0, y=10.0)]
    cordons = [_cordon_en_L(), Cordon([(40.0, 30.0), (50.0, 35.0)])]
    steps = _planner().generate_plateau_path(zones, cordons)

    precedent = None
    for step in steps:
        if precedent is not None:
            bouge_en_xy = (step["x"], step["y"]) != (precedent["x"], precedent["y"])
            if bouge_en_xy and precedent["z"] == Z_DEPOSE:
                assert step["z"] == Z_DEPOSE, (
                    f"La buse quitte un cordon en se deplacant en XY avant d'etre "
                    f"remontee : {precedent} -> {step}"
                )
        precedent = step


def test_chaque_cordon_se_termine_par_une_remontee_en_hauteur_de_transit():
    """Le pendant direct du test ci-dessus, énoncé sur la cause plutôt que sur l'effet.

    Doubler l'invariant d'un test de sa cause est délibéré : celui du dessus décrit ce
    que l'opérateur constaterait (une traînée de pâte), celui-ci décrit la ligne de code
    qui l'évite. Les deux ensemble disent où chercher quand ça casse.
    """
    zone = _zone(id_tl=4, x=10.0, y=10.0)
    cordons = [_cordon_en_L(), Cordon([(40.0, 30.0), (50.0, 35.0)])]
    steps = _planner().generate_plateau_path([zone], cordons)

    # Le dernier step de chaque cordon est une remontée sans déplacement XY
    remontees = [
        i for i, s in enumerate(steps)
        if s["type"] == "travel" and s["z"] == Z_TRANSIT and i > 0
        and (s["x"], s["y"]) == (steps[i - 1]["x"], steps[i - 1]["y"])
    ]
    assert len(remontees) == len(cordons), (
        f"attendu une remontee par cordon, trouve {len(remontees)}"
    )


# ================================================================ I5 — dépose à blanc

def test_depose_a_blanc_n_extrude_jamais():
    """INVARIANT I5 — aucune goutte de pâte pendant la démonstration."""
    zones = [_zone(id_tl=4, x=10.0, y=10.0), _zone(id_tl=6, x=100.0, y=10.0)]
    settings = Settings(travel_speed_mm_min=1000.0, extrusion_speed_mm_min=100.0,
                        priming_seconds=2.0, end_anticipation_mm=3.0)
    steps = _planner(settings, dry_run=True).generate_plateau_path(zones, [_cordon_en_L()])

    assert steps, "la depose a blanc doit tout de meme produire une trajectoire"
    for step in steps:
        assert step["amount"] == 0.0
        assert step["type"] != "prime"


def test_depose_a_blanc_ne_bouge_jamais_en_z():
    """INVARIANT I5 — la sécurité de la démonstration repose là-dessus.

    Les deux hauteurs sont ramenées à une seule et même valeur. Aucun step ne peut donc
    faire descendre la buse, quelle que soit la suite du calcul — et l'action M3 (hauteur
    Z de la pointe) n'est pas nécessaire avant le sous-lot D4.

    C'est l'UNICITÉ de la hauteur qui fait la sûreté, pas sa valeur : le test ne fixe
    donc pas la valeur, qui a déjà bougé une fois (marge ajoutée le 2026-08-04).
    """
    zones = [_zone(id_tl=4, x=10.0, y=10.0)]
    steps = _planner(dry_run=True).generate_plateau_path(zones, [_cordon_en_L()])

    hauteurs = {step["z"] for step in steps}
    assert len(hauteurs) == 1, f"la depose a blanc a bouge en Z : {hauteurs}"


def test_depose_a_blanc_travaille_au_dessus_de_la_hauteur_du_homing():
    """Constaté sur la machine le 2026-08-04 : la hauteur du homing passe trop près.

    Sans extrusion la pointe ne touche pas, mais la marge est trop faible pour être
    rassurante — un plateau posé un peu haut, une pièce plus épaisse que prévu, et elle
    accroche. La dépose à blanc doit donc travailler STRICTEMENT au-dessus du homing.
    """
    from modules.config import MACHINE_Z_HOME_MM

    zones = [_zone(id_tl=4, x=10.0, y=10.0)]
    steps = _planner(dry_run=True).generate_plateau_path(zones, [_cordon_en_L()])

    hauteur = steps[0]["z"]
    assert hauteur > MACHINE_Z_HOME_MM, (
        f"la depose a blanc travaille a {hauteur} mm, soit la hauteur du homing"
    )


def test_depose_a_blanc_suit_exactement_le_meme_chemin_xy_que_la_depose_reelle():
    """La dépose à blanc est une RÉPÉTITION, pas une trajectoire approchée.

    Si le chemin différait, valider le parcours à blanc ne dirait rien du parcours réel —
    et tout l'intérêt du mode disparaîtrait.
    """
    zones = [_zone(id_tl=4, x=10.0, y=10.0), _zone(id_tl=6, x=100.0, y=10.0)]
    cordon = [_cordon_en_L()]

    reels = _planner().generate_plateau_path(zones, cordon)
    blancs = _planner(dry_run=True).generate_plateau_path(zones, cordon)

    xy_reels = [(s["x"], s["y"]) for s in reels]
    xy_blancs = [(s["x"], s["y"]) for s in blancs]
    assert xy_blancs == xy_reels


# ================================================================ I6 — quantité déposée

def test_la_quantite_deposee_est_proportionnelle_au_nombre_de_zones():
    """INVARIANT I6 — attrape un facteur faux ou un cordon compté deux fois."""
    cordons = [_cordon_en_L()]
    planner = _planner()

    une = planner.generate_plateau_path([_zone(id_tl=4, x=10.0, y=10.0)], cordons)
    trois = planner.generate_plateau_path([
        _zone(id_tl=4, x=10.0, y=10.0),
        _zone(id_tl=6, x=100.0, y=10.0),
        _zone(id_tl=8, x=10.0, y=100.0),
    ], cordons)

    total_une = sum(s["amount"] for s in une)
    total_trois = sum(s["amount"] for s in trois)

    assert total_une > 0
    assert total_trois == pytest.approx(3 * total_une)


def test_la_quantite_par_mm_est_le_rapport_des_deux_vitesses():
    """L'épaisseur du cordon vient du RAPPORT des vitesses, pas d'un réglage direct.

    C'est le point que la fenêtre de paramètres rappelle à l'opérateur, et la raison pour
    laquelle il y a deux vitesses plutôt qu'un curseur « quantité ».
    """
    cordon = Cordon([(0.0, 0.0), (10.0, 0.0)])      # 10 mm exactement
    settings = Settings(travel_speed_mm_min=600.0, extrusion_speed_mm_min=60.0)
    steps = _planner(settings).generate_plateau_path(
        [_zone(id_tl=4, x=0.0, y=0.0)], [cordon]
    )

    # 60 / 600 = 0,1 mm d'axe E par mm de trajet, sur 10 mm → 1,0
    assert sum(s["amount"] for s in steps) == pytest.approx(1.0)


def test_une_vitesse_de_deplacement_nulle_est_refusee():
    """Une division par zéro doit sortir en message clair, pas en ZeroDivisionError."""
    with pytest.raises(ValueError, match="Vitesse de deplacement"):
        PathPlanner.from_settings(
            Settings(travel_speed_mm_min=0.0),
            z_dispense_mm=Z_DEPOSE, z_travel_mm=Z_TRANSIT,
        )


# ================================================================ tempos d'extrusion

def test_l_amorcage_extrude_sans_bouger():
    """L'amorçage laisse le temps à la pâte d'arriver au bout de l'aiguille."""
    settings = Settings(travel_speed_mm_min=600.0, extrusion_speed_mm_min=60.0,
                        priming_seconds=2.0)
    steps = _planner(settings).generate_plateau_path(
        [_zone(id_tl=4, x=0.0, y=0.0)], [_cordon_en_L()]
    )

    primes = [s for s in steps if s["type"] == "prime"]
    assert len(primes) == 1, "un amorcage par cordon"
    # 60 mm/min pendant 2 s = 60/60 × 2 = 2,0 mm d'axe E
    assert primes[0]["amount"] == pytest.approx(2.0)

    # L'amorçage a lieu à la position du premier point du cordon, sans déplacement
    index = steps.index(primes[0])
    assert (steps[index]["x"], steps[index]["y"]) == \
           (steps[index - 1]["x"], steps[index - 1]["y"])


def test_aucun_amorcage_quand_le_parametre_est_nul():
    """NON-RÉGRESSION du cycle historique : sans réglage, la trajectoire est inchangée.

    `screen_zone.py` construit son planner sans amorçage. Tant qu'il reste le seul chemin
    validé jusqu'à la dépose réelle (son retrait est le sous-lot D5), il ne doit pas voir
    la moindre différence.
    """
    steps = _planner().generate_plateau_path(
        [_zone(id_tl=4, x=0.0, y=0.0)], [_cordon_en_L()]
    )
    assert not [s for s in steps if s["type"] == "prime"]


def test_l_anticipation_coupe_l_extrusion_avant_la_fin_du_cordon():
    """La pâte sous pression finit le cordon toute seule : on cesse de pousser avant."""
    cordon = Cordon([(0.0, 0.0), (30.0, 0.0)])      # 30 mm en ligne droite
    settings = Settings(travel_speed_mm_min=600.0, extrusion_speed_mm_min=60.0,
                        end_anticipation_mm=10.0)
    steps = _planner(settings).generate_plateau_path(
        [_zone(id_tl=4, x=0.0, y=0.0)], [cordon]
    )

    # On extrude sur 20 mm et non 30 → 0,1 × 20 = 2,0 mm d'axe E
    assert sum(s["amount"] for s in steps) == pytest.approx(2.0)

    # ... mais la buse va bien jusqu'au bout du tracé, à hauteur de dépose
    fin = plateau_to_machine_mm((30.0, 0.0), ORIGINE_X, ORIGINE_Y)
    atteints = [(s["x"], s["y"]) for s in steps if s["z"] == Z_DEPOSE]
    assert (pytest.approx(fin[0]), pytest.approx(fin[1])) in \
           [(pytest.approx(x), pytest.approx(y)) for x, y in atteints]


def test_une_anticipation_plus_longue_que_le_cordon_ne_depose_rien():
    """Cas limite : un réglage trop généreux ne doit pas produire de quantité négative."""
    cordon = Cordon([(0.0, 0.0), (5.0, 0.0)])       # 5 mm
    settings = Settings(travel_speed_mm_min=600.0, extrusion_speed_mm_min=60.0,
                        end_anticipation_mm=20.0)   # plus long que le cordon
    steps = _planner(settings).generate_plateau_path(
        [_zone(id_tl=4, x=0.0, y=0.0)], [cordon]
    )

    assert sum(s["amount"] for s in steps) == 0.0
    assert all(s["amount"] >= 0.0 for s in steps)


# ------------------------------------------------------------------ découpe de polyline

def test_couper_une_polyline_au_milieu_d_un_segment():
    avant, apres = split_polyline_at([(0.0, 0.0), (10.0, 0.0)], 4.0)
    assert avant == [(0.0, 0.0), (4.0, 0.0)]
    assert apres == [(4.0, 0.0), (10.0, 0.0)]


def test_les_deux_morceaux_partagent_le_point_de_coupure():
    """Les enchaîner doit reparcourir le tracé d'origine, sans trou ni doublon."""
    points = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
    avant, apres = split_polyline_at(points, 15.0)
    assert avant[-1] == apres[0]

    longueur = lambda p: sum(math.dist(p[i - 1], p[i]) for i in range(1, len(p)))
    assert longueur(avant) + longueur(apres) == pytest.approx(longueur(points))


def test_couper_au_dela_de_la_fin_ne_laisse_rien_a_parcourir():
    """Cas NOMINAL (anticipation nulle) : sans ce comportement, un step en double."""
    points = [(0.0, 0.0), (10.0, 0.0)]
    avant, apres = split_polyline_at(points, 10.0)
    assert avant == points
    assert apres == [(10.0, 0.0)]


def test_couper_au_debut_met_tout_dans_la_seconde_moitie():
    points = [(0.0, 0.0), (10.0, 0.0)]
    avant, apres = split_polyline_at(points, 0.0)
    assert avant == [(0.0, 0.0)]
    assert apres == points


# ================================================================ I7 — contrôle de course

def test_un_plateau_dans_la_course_ne_produit_aucun_depassement():
    zones = [_zone(id_tl=4, x=10.0, y=10.0)]
    steps = _planner().generate_plateau_path(zones, [_cordon_en_L()])

    assert check_machine_limits(steps, x_max=200.0, y_max=200.0, z_max=180.0) == []


def test_un_cordon_hors_course_est_detecte_et_nomme_sa_zone():
    """INVARIANT I7 — Marlin rognerait en silence ; on refuse bruyamment.

    Reproduit la situation réelle du 2026-08-03 : avec `MACHINE_ORIGIN_Y = -2.0`, un
    cordon passant sous `plateau_y = 2` demande un Y machine négatif, hors course.
    """
    zone = _zone(id_tl=7, x=0.0, y=0.0)
    cordon = Cordon([(0.0, 0.5), (10.0, 0.5)])       # à 0,5 mm du bas de la zone
    planner = PathPlanner.from_settings(
        Settings(travel_speed_mm_min=600.0, extrusion_speed_mm_min=60.0),
        z_dispense_mm=Z_DEPOSE, z_travel_mm=Z_TRANSIT,
        machine_origin_x=6.0, machine_origin_y=-2.0,   # les valeurs réelles du 03/08
    )
    steps = planner.generate_plateau_path([zone], [cordon])

    violations = check_machine_limits(steps, x_max=200.0, y_max=200.0, z_max=180.0)

    assert violations, "un Y machine negatif doit etre refuse"
    assert all(v["axis"] == "Y" for v in violations)
    assert {v["zone"] for v in violations} == {7}


def test_le_message_de_depassement_nomme_la_zone_et_dit_quoi_faire():
    """L'opérateur raisonne en pièces sur le plateau, pas en numéros de step."""
    violations = [
        {"axis": "Y", "value": -1.5, "limit": 0.0, "zone": 7, "index": 3},
        {"axis": "Y", "value": -0.5, "limit": 0.0, "zone": 7, "index": 4},
    ]
    message = format_limit_violations(violations)

    assert "zone 7" in message
    assert "-1.50" in message          # le PIRE écart, pas le premier rencontré
    assert "annule" in message.lower()
    assert "plateau" in message.lower()  # le remède est mécanique, et il est dit


def test_aucun_depassement_donne_un_message_vide():
    assert format_limit_violations([]) == ""


# ================================================================ I10 — test doré

def test_dore_sequence_complete_d_une_zone():
    """INVARIANT I10 — la séquence exacte, figée, d'une zone à un cordon.

    C'est le filet le plus large de ce lot : il attrape toute modification non voulue de
    la structure du parcours, y compris celles auxquelles les invariants ci-dessus ne
    pensent pas. C'est lui qui protégera les sous-lots D2 à D5 des régressions sur D1.

    S'il casse, ne pas le « réparer » en recopiant la nouvelle sortie : vérifier d'abord
    que le changement est voulu, puis mettre à jour la valeur attendue en même temps que
    la raison, en commentaire.
    """
    zone = _zone(id_tl=4, x=0.0, y=0.0, w=60.0, h=40.0)
    cordon = Cordon([(10.0, 10.0), (30.0, 10.0), (30.0, 20.0)])
    settings = Settings(travel_speed_mm_min=600.0, extrusion_speed_mm_min=60.0)

    steps = _planner(settings).generate_plateau_path([zone], [cordon])
    obtenu = [(s["type"], s["x"], s["y"], s["z"], s["amount"], s["zone"]) for s in steps]

    # Origine des tests : (100, 50). La zone est en (0, 0), donc le repère de la zone se
    # confond avec le repère plateau, et l'on ne fait qu'ajouter l'origine machine.
    assert obtenu == [
        # passage au zéro de la zone, à hauteur de transit
        ("travel",   100.0,  50.0, 5.0, 0.0, 4),
        # cordon : au-dessus du premier point, puis descente
        ("travel",   110.0,  60.0, 5.0, 0.0, 4),
        ("travel",   110.0,  60.0, 1.0, 0.0, 4),
        # tracé : 20 mm puis 10 mm, à 0,1 mm d'axe E par mm
        ("dispense", 130.0,  60.0, 1.0, 2.0, 4),
        ("dispense", 130.0,  70.0, 1.0, 1.0, 4),
        # remontée en fin de cordon
        ("travel",   130.0,  70.0, 5.0, 0.0, 4),
    ]


def test_dore_le_plateau_est_la_concatenation_des_zones_dans_l_ordre():
    """Aucun step surnuméraire, aucun entrelacement entre zones.

    Complète le test doré ci-dessus : celui-ci fige la séquence D'UNE zone, celui-là
    fige la façon dont les zones s'enchaînent.
    """
    zones = [_zone(id_tl=4, x=10.0, y=10.0), _zone(id_tl=6, x=100.0, y=10.0)]
    cordons = [_cordon_en_L()]
    planner = _planner()

    plateau = planner.generate_plateau_path(zones, cordons)
    attendu = []
    for zone in sort_zones_for_deposit(zones):
        attendu.extend(planner.generate_plateau_path([zone], cordons))

    assert plateau == attendu


def test_un_cordon_d_un_seul_point_est_ignore():
    """Un cordon sans segment ne trace rien : il ne doit pas faire descendre la buse."""
    zone = _zone(id_tl=4, x=0.0, y=0.0)
    steps = _planner().generate_plateau_path([zone], [Cordon([(5.0, 5.0)])])

    # Seul subsiste le passage au zéro de la zone
    assert len(steps) == 1
    assert steps[0]["z"] == Z_TRANSIT


def test_aucune_zone_selectionnee_ne_produit_aucun_mouvement():
    assert _planner().generate_plateau_path([], [_cordon_en_L()]) == []
