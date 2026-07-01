# Tests unitaires pour modules/path_planner.py
# Pas de matériel requis — logique pure.

import pytest
from modules.path_planner import PathPlanner


def creer_planner() -> PathPlanner:
    """Créer un PathPlanner avec des paramètres typiques pour les tests."""
    return PathPlanner(
        line_spacing_mm=5.0,
        z_dispense_mm=1.0,
        z_travel_mm=5.0,
        amount_per_mm=0.05,
    )


# ------------------------------------------------------------------ structure générale

def test_generate_path_retourne_une_liste():
    """generate_path() doit retourner une liste non vide."""
    planner = creer_planner()
    steps = planner.generate_path(zone_mm=(0.0, 0.0, 50.0, 20.0))
    assert isinstance(steps, list)
    assert len(steps) > 0


def test_chaque_step_a_les_bons_champs():
    """Chaque step doit avoir les champs type, x, y, z, amount."""
    planner = creer_planner()
    steps = planner.generate_path(zone_mm=(0.0, 0.0, 50.0, 20.0))
    for step in steps:
        assert "type" in step
        assert "x" in step
        assert "y" in step
        assert "z" in step
        assert "amount" in step
        assert step["type"] in ("travel", "dispense")


def test_premier_step_est_un_travel_a_z_transit():
    """Le premier step doit aller au-dessus de la zone (z_travel) sans déposer."""
    planner = creer_planner()
    steps = planner.generate_path(zone_mm=(10.0, 20.0, 50.0, 30.0))
    assert steps[0]["type"] == "travel"
    assert steps[0]["z"] == 5.0    # z_travel
    assert steps[0]["amount"] == 0.0


def test_dernier_step_est_un_travel_a_z_transit():
    """Le dernier step doit remonter à z_travel (fin de trajectoire)."""
    planner = creer_planner()
    steps = planner.generate_path(zone_mm=(0.0, 0.0, 50.0, 20.0))
    assert steps[-1]["type"] == "travel"
    assert steps[-1]["z"] == 5.0    # z_travel


def test_steps_dispense_ont_z_depose():
    """Tous les steps de type 'dispense' doivent être à z_dispense."""
    planner = creer_planner()
    steps = planner.generate_path(zone_mm=(0.0, 0.0, 50.0, 20.0))
    for step in steps:
        if step["type"] == "dispense":
            assert step["z"] == 1.0    # z_dispense


# ------------------------------------------------------------------ nombre de lignes

def test_nombre_de_lignes_correct():
    """Le nombre de steps 'dispense' doit correspondre au nombre de rangées."""
    planner = PathPlanner(line_spacing_mm=5.0, z_dispense_mm=1.0,
                          z_travel_mm=5.0, amount_per_mm=0.05)
    steps = planner.generate_path(zone_mm=(0.0, 0.0, 50.0, 20.0))
    # Hauteur 20 mm / espacement 5 mm = 4 intervalles → 5 lignes (0, 5, 10, 15, 20)
    n_dispense = sum(1 for s in steps if s["type"] == "dispense")
    assert n_dispense == 5


def test_zone_petite_donne_au_moins_une_ligne():
    """Une zone plus petite que l'espacement doit quand même donner 1 ligne de dépose."""
    planner = PathPlanner(line_spacing_mm=10.0, z_dispense_mm=1.0,
                          z_travel_mm=5.0, amount_per_mm=0.05)
    steps = planner.generate_path(zone_mm=(0.0, 0.0, 30.0, 3.0))
    n_dispense = sum(1 for s in steps if s["type"] == "dispense")
    assert n_dispense >= 1


# ------------------------------------------------------------------ pattern boustrophedon

def test_lignes_alternent_direction():
    """Les lignes paires vont gauche→droite, impaires droite→gauche."""
    planner = PathPlanner(line_spacing_mm=5.0, z_dispense_mm=1.0,
                          z_travel_mm=5.0, amount_per_mm=0.05)
    zone = (10.0, 10.0, 40.0, 15.0)  # x=10, y=10, w=40, h=15
    steps = planner.generate_path(zone_mm=zone)

    dispense_steps = [s for s in steps if s["type"] == "dispense"]

    # Ligne 0 (paire) : doit finir à x_max = 10 + 40 = 50
    assert dispense_steps[0]["x"] == pytest.approx(50.0)

    # Ligne 1 (impaire) : doit finir à x_min = 10
    assert dispense_steps[1]["x"] == pytest.approx(10.0)

    # Ligne 2 (paire) : doit finir à x_max = 50
    assert dispense_steps[2]["x"] == pytest.approx(50.0)


# ------------------------------------------------------------------ calcul de quantité

def test_amount_proportionnel_a_la_largeur():
    """La quantité E sur chaque ligne doit être proportionnelle à la largeur."""
    planner = PathPlanner(line_spacing_mm=5.0, z_dispense_mm=1.0,
                          z_travel_mm=5.0, amount_per_mm=0.1)
    steps = planner.generate_path(zone_mm=(0.0, 0.0, 30.0, 10.0))
    for step in steps:
        if step["type"] == "dispense":
            # 30 mm de largeur × 0.1 mm/mm = 3.0 mm d'axe E
            assert step["amount"] == pytest.approx(3.0, rel=1e-3)


def test_travel_steps_ont_amount_zero():
    """Les steps de type 'travel' ne doivent pas extruder (amount = 0)."""
    planner = creer_planner()
    steps = planner.generate_path(zone_mm=(0.0, 0.0, 50.0, 20.0))
    for step in steps:
        if step["type"] == "travel":
            assert step["amount"] == 0.0


# ------------------------------------------------------------------ coordonnées dans la zone

def test_coordonnees_restent_dans_la_zone():
    """Tous les waypoints doivent rester dans les limites x/y de la zone."""
    planner = creer_planner()
    zone = (5.0, 8.0, 60.0, 25.0)
    x0, y0, w, h = zone
    steps = planner.generate_path(zone_mm=zone)

    for step in steps:
        # Tolérance de 0.01 mm pour les arrondis
        assert step["x"] >= x0 - 0.01
        assert step["x"] <= x0 + w + 0.01
        assert step["y"] >= y0 - 0.01
        assert step["y"] <= y0 + h + 0.01


# ------------------------------------------------------------------ validation des entrées

def test_zone_invalide_leve_value_error():
    """generate_path() doit lever ValueError si la zone a des dimensions nulles ou négatives."""
    planner = creer_planner()
    with pytest.raises(ValueError):
        planner.generate_path(zone_mm=(0.0, 0.0, 0.0, 20.0))   # largeur nulle
    with pytest.raises(ValueError):
        planner.generate_path(zone_mm=(0.0, 0.0, 30.0, -5.0))  # hauteur négative


# ------------------------------------------------------------------ longueur totale (fill)

def test_total_dispense_length():
    """total_dispense_length_mm() doit retourner la somme des longueurs de dépose."""
    planner = PathPlanner(line_spacing_mm=5.0, z_dispense_mm=1.0,
                          z_travel_mm=5.0, amount_per_mm=0.05)
    zone = (0.0, 0.0, 40.0, 20.0)
    # 5 lignes × 40 mm = 200 mm
    assert planner.total_dispense_length_mm(zone) == pytest.approx(200.0)


# ------------------------------------------------------------------ tracé libre (polyline)

def test_line_path_structure():
    """generate_path_from_line() doit retourner la même structure que generate_path()."""
    planner = creer_planner()
    points = [(0.0, 0.0), (30.0, 0.0), (30.0, 20.0)]
    steps = planner.generate_path_from_line(points)
    assert isinstance(steps, list)
    assert len(steps) > 0
    for step in steps:
        assert "type" in step and "x" in step and "y" in step and "z" in step and "amount" in step


def test_line_path_premier_dernier_travel():
    """Premier et dernier step doivent être des travels à z_travel."""
    planner = creer_planner()
    points = [(5.0, 10.0), (50.0, 10.0)]
    steps = planner.generate_path_from_line(points)
    assert steps[0]["type"] == "travel" and steps[0]["z"] == 5.0
    assert steps[-1]["type"] == "travel" and steps[-1]["z"] == 5.0


def test_line_path_n_segments_dispense():
    """Nombre de steps dispense = nombre de segments = nombre de points - 1."""
    planner = creer_planner()
    points = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (20.0, 10.0)]
    steps = planner.generate_path_from_line(points)
    n_dispense = sum(1 for s in steps if s["type"] == "dispense")
    assert n_dispense == 3  # 4 points → 3 segments


def test_line_path_amount_proportionnel_longueur():
    """La quantité E doit être proportionnelle à la longueur du segment."""
    planner = PathPlanner(line_spacing_mm=5.0, z_dispense_mm=1.0,
                          z_travel_mm=5.0, amount_per_mm=0.1)
    # Segment horizontal de 40 mm → amount = 40 × 0.1 = 4.0 mm
    steps = planner.generate_path_from_line([(0.0, 0.0), (40.0, 0.0)])
    dispense_steps = [s for s in steps if s["type"] == "dispense"]
    assert dispense_steps[0]["amount"] == pytest.approx(4.0, rel=1e-3)


def test_line_path_segment_diagonal():
    """Un segment diagonal doit utiliser la distance euclidienne, pas Manhattan."""
    planner = PathPlanner(line_spacing_mm=5.0, z_dispense_mm=1.0,
                          z_travel_mm=5.0, amount_per_mm=1.0)
    # Triangle 3-4-5 : segment de (0,0) à (3,4) → longueur = 5
    steps = planner.generate_path_from_line([(0.0, 0.0), (3.0, 4.0)])
    dispense_steps = [s for s in steps if s["type"] == "dispense"]
    assert dispense_steps[0]["amount"] == pytest.approx(5.0, rel=1e-3)


def test_line_path_moins_de_2_points_leve_erreur():
    """generate_path_from_line() doit lever ValueError si moins de 2 points."""
    planner = creer_planner()
    with pytest.raises(ValueError):
        planner.generate_path_from_line([])
    with pytest.raises(ValueError):
        planner.generate_path_from_line([(10.0, 20.0)])


def test_total_line_length():
    """total_line_length_mm() doit retourner la somme des longueurs de segments."""
    planner = creer_planner()
    # Deux segments de 10 mm chacun (horizontal) → 20 mm au total
    points = [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0)]
    assert planner.total_line_length_mm(points) == pytest.approx(20.0)
