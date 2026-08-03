# Calcul des trajectoires de dépose de pâte thermique
# Transforme des cordons (en mm) en liste de waypoints G-code
#
# Ce module ne parle à personne : ni caméra, ni machine, ni interface. Il prend de la
# géométrie et rend une liste de steps. C'est délibéré — la dépose est la fonction
# critique de la machine, on veut pouvoir la vérifier au `pytest` sans allumer quoi que
# ce soit, et surtout sans passer par une IHM.
#
# Trois repères se rejoignent ici, toujours dans le même ordre :
#     repère de zone  →  repère plateau  →  repère machine
# Les deux premières conversions sont dans `vision.py` (`DepositZone.to_plateau_mm`), la
# troisième est l'addition de `MACHINE_ORIGIN` (voir `plateau_to_machine_mm` plus bas).

import math

from modules.config import (
    MACHINE_ORIGIN_X, MACHINE_ORIGIN_Y,
    MACHINE_Z_HOME_MM, DRY_RUN_Z_CLEARANCE_MM,
    MACHINE_TRAVEL_X_MAX_MM, MACHINE_TRAVEL_Y_MAX_MM, MACHINE_TRAVEL_Z_MAX_MM,
)


class PathPlanner:
    """Génère la trajectoire de dépose pour une zone rectangulaire.

    Le pattern utilisé est le boustrophedon (zigzag rangée par rangée) :
    ligne 1 gauche→droite, ligne 2 droite→gauche, etc.
    C'est le pattern le plus simple et le plus efficace pour couvrir une surface.

    Utilisation typique :
        planner = PathPlanner(line_spacing_mm=3.0, z_dispense_mm=1.0,
                              z_travel_mm=5.0, amount_per_mm=0.05)
        steps = planner.generate_path(zone_mm=(10.0, 20.0, 50.0, 30.0))
        # → liste de steps à exécuter avec machine.py
    """

    def __init__(
        self,
        line_spacing_mm: float,
        z_dispense_mm: float,
        z_travel_mm: float,
        amount_per_mm: float,
        priming_amount: float = 0.0,
        end_anticipation_mm: float = 0.0,
        machine_origin_x: float = MACHINE_ORIGIN_X,
        machine_origin_y: float = MACHINE_ORIGIN_Y,
    ) -> None:
        # Espacement entre deux lignes parallèles de dépose (en mm)
        self._line_spacing = line_spacing_mm

        # Hauteur de la buse pendant la dépose — juste au-dessus de la pièce
        self._z_dispense = z_dispense_mm

        # Hauteur de déplacement rapide — suffisamment haut pour ne rien toucher
        self._z_travel = z_travel_mm

        # Quantité de pâte extrudée par mm de déplacement (mm d'axe E par mm de chemin)
        # À calibrer expérimentalement selon la viscosité de la pâte et la seringue
        self._amount_per_mm = amount_per_mm

        # Quantité d'axe E poussée À L'ARRÊT au début de chaque cordon, le temps que la
        # pâte arrive au bout de l'aiguille. Exprimée ici en mm d'axe E et non en
        # secondes : la conversion se fait dans `from_settings()`, qui connaît la vitesse
        # d'extrusion. Ce module reste ainsi purement géométrique.
        self._priming_amount = priming_amount

        # Distance avant la fin du cordon où l'extrusion s'arrête. La buse continue de
        # suivre le tracé, mais sans pousser : c'est la pâte encore sous pression dans la
        # seringue qui finit le cordon.
        self._end_anticipation = end_anticipation_mm

        # Position machine du point (0, 0) du plateau — voir `plateau_to_machine_mm`.
        # Injectables plutôt que lus dans `config` au moment de s'en servir : les tests
        # peuvent ainsi fixer une origine connue au lieu de dépendre d'une mesure
        # physique qui changera encore.
        self._machine_origin_x = machine_origin_x
        self._machine_origin_y = machine_origin_y

    # ------------------------------------------------------------------ construction

    @classmethod
    def from_settings(
        cls,
        settings,
        z_dispense_mm: float,
        z_travel_mm: float,
        dry_run: bool = False,
        machine_origin_x: float = MACHINE_ORIGIN_X,
        machine_origin_y: float = MACHINE_ORIGIN_Y,
    ) -> "PathPlanner":
        """Construire un planner à partir des paramètres d'une préparation.

        C'est le point d'entrée normal pour une dépose de plateau. Il traduit les
        réglages tels que l'opérateur les voit (deux vitesses, deux tempos) en
        grandeurs géométriques dont le planner a besoin.

        **La quantité de pâte ne se règle pas directement** : elle résulte du RAPPORT
        entre la vitesse d'extrusion et la vitesse de déplacement. À vitesse d'extrusion
        constante, ralentir la buse épaissit le cordon. C'est pourquoi il y a deux
        vitesses dans `Settings` et non un curseur « quantité », qui masquerait ce lien.

        `dry_run=True` donne la **dépose à blanc** : la machine parcourt exactement le
        même chemin, mais sans extruder et **sans jamais bouger en Z** — les deux
        hauteurs sont ramenées à celle du homing, augmentée d'une marge de sécurité.
        C'est ce qui permet de valider tout le parcours (vision, sélection, repères,
        ordre des zones, mouvement) avant d'avoir réglé quoi que ce soit de la pâte, et
        d'essayer un plateau neuf sans risque ni gâchis.

        ⚠️ La marge n'est pas décorative : constatée nécessaire sur la machine le
        2026-08-04, la hauteur du homing seule passant trop près du dessus des zones.
        """
        if dry_run:
            # Une seule et même hauteur partout : aucun step ne peut alors faire
            # descendre la buse, quelle que soit la suite du calcul. C'est cette unicité
            # qui fait la sûreté du mode — pas la valeur elle-même.
            hauteur_sure = MACHINE_Z_HOME_MM + DRY_RUN_Z_CLEARANCE_MM
            z_dispense_mm = hauteur_sure
            z_travel_mm = hauteur_sure

        # mm d'axe E par mm de trajet = (mm E/min) ÷ (mm trajet/min). Une vitesse de
        # déplacement nulle n'a pas de sens physique et ferait une division par zéro.
        if settings.travel_speed_mm_min <= 0:
            raise ValueError(
                f"Vitesse de deplacement invalide : "
                f"{settings.travel_speed_mm_min} mm/min (doit etre > 0)"
            )
        amount_per_mm = (
            0.0 if dry_run
            else settings.extrusion_speed_mm_min / settings.travel_speed_mm_min
        )

        # Amorçage : une durée en secondes devient une quantité d'axe E via la vitesse
        # d'extrusion (mm/min ÷ 60 = mm/s). En dépose à blanc il n'y a rien à amorcer.
        priming_amount = (
            0.0 if dry_run
            else settings.extrusion_speed_mm_min * settings.priming_seconds / 60.0
        )

        return cls(
            line_spacing_mm=0.0,   # inutilisé pour un cordon : ne sert qu'au remplissage
            z_dispense_mm=z_dispense_mm,
            z_travel_mm=z_travel_mm,
            amount_per_mm=amount_per_mm,
            priming_amount=priming_amount,
            end_anticipation_mm=settings.end_anticipation_mm,
            machine_origin_x=machine_origin_x,
            machine_origin_y=machine_origin_y,
        )

    def generate_path(self, zone_mm: tuple) -> list:
        """Générer la trajectoire de dépose pour une zone rectangulaire.

        Paramètre :
            zone_mm : (x, y, largeur, hauteur) en mm dans le repère machine
                      x, y = coin supérieur gauche de la zone

        Retourne une liste de steps, chaque step étant un dict :
            {"type": "travel",   "x": float, "y": float, "z": float, "amount": 0.0}
            {"type": "dispense", "x": float, "y": float, "z": float, "amount": float}

        Pour "travel"   : déplacement rapide sans dépose (G0 ou G1 rapide)
        Pour "dispense" : déplacement lent avec extrusion simultanée
        L'amount (dispense) est la quantité d'axe E à pousser sur ce segment.
        """
        x0, y0, width, height = zone_mm

        # Vérifier que la zone est valide (dimensions positives)
        if width <= 0 or height <= 0:
            raise ValueError(
                f"Zone invalide : largeur={width} mm, hauteur={height} mm "
                f"(les deux doivent être > 0)"
            )

        steps = []

        # --- Étape 1 : aller au-dessus du coin de départ (hauteur de transit)
        # On se positionne en hauteur de sécurité pour éviter de rayer la pièce
        steps.append(_travel(x0, y0, self._z_travel))

        # --- Étape 2 : descendre à la hauteur de dépose
        steps.append(_travel(x0, y0, self._z_dispense))

        # --- Étape 3 : parcourir toutes les rangées (boustrophedon)
        # On calcule le nombre de lignes nécessaires pour couvrir la hauteur
        n_lignes = math.ceil(height / self._line_spacing) + 1

        for i in range(n_lignes):
            y = y0 + i * self._line_spacing

            # Ne pas dépasser le bord inférieur de la zone
            y = min(y, y0 + height)

            if i % 2 == 0:
                # Ligne paire : gauche → droite
                x_debut, x_fin = x0, x0 + width
            else:
                # Ligne impaire : droite → gauche (boustrophedon = pas de retour à vide)
                x_debut, x_fin = x0 + width, x0

            # Aller au début de la ligne (déplacement rapide, pas de dépose)
            # Sauf pour la toute première ligne où on est déjà en position
            if i > 0:
                steps.append(_travel(x_debut, y, self._z_dispense))

            # Déposer sur toute la longueur de la ligne
            # La quantité E est proportionnelle à la longueur du segment
            steps.append(_dispense(x_fin, y, self._z_dispense, width, self._amount_per_mm))

        # --- Étape 4 : remonter à la hauteur de transit en fin de trajectoire
        # x_fin = position en x de la dernière ligne (dépend de la parité)
        last_x = x0 if (n_lignes - 1) % 2 == 0 else x0 + width
        last_y = min(y0 + (n_lignes - 1) * self._line_spacing, y0 + height)
        steps.append(_travel(last_x, last_y, self._z_travel))

        return steps

    def total_dispense_length_mm(self, zone_mm: tuple) -> float:
        """Calculer la longueur totale des segments de dépose (en mm).

        Utile pour estimer la quantité de pâte consommée avant d'exécuter.
        """
        x0, y0, width, height = zone_mm
        n_lignes = math.ceil(height / self._line_spacing) + 1
        return n_lignes * width

    def generate_path_from_line(self, points_mm: list) -> list:
        """Générer la trajectoire de dépose en suivant un tracé libre (polyline).

        L'utilisateur dessine une série de points sur l'image — la machine suit
        exactement ce tracé en déposant de la pâte en continu.

        Paramètre :
            points_mm : liste de tuples (x_mm, y_mm) définissant le tracé
                        Au moins 2 points sont requis.

        Retourne la même structure que generate_path() :
            liste de {"type": "travel"|"dispense", "x", "y", "z", "amount"}
        """
        if len(points_mm) < 2:
            raise ValueError(
                f"Au moins 2 points sont requis pour un tracé "
                f"(reçu : {len(points_mm)} point(s))"
            )

        steps = []

        # --- Étape 1 : aller au-dessus du premier point (hauteur de transit)
        x0, y0 = points_mm[0]
        steps.append(_travel(x0, y0, self._z_travel))

        # --- Étape 2 : descendre à la hauteur de dépose
        steps.append(_travel(x0, y0, self._z_dispense))

        # --- Étape 3 : amorcer, si un temps d'amorçage est réglé
        # On pousse de la pâte SANS bouger, le temps qu'elle arrive au bout de
        # l'aiguille. Sans cela, le début du cordon serait vide : la pâte thermique est
        # trop visqueuse pour sortir dès que le piston avance.
        # Aucun step n'est produit si l'amorçage vaut 0 — c'est ce qui garantit que le
        # cycle historique (screen_zone), qui construit un planner sans amorçage, obtient
        # exactement la même trajectoire qu'avant.
        if self._priming_amount > 0:
            steps.append(_prime(x0, y0, self._z_dispense, self._priming_amount))

        # --- Étape 4 : couper le tracé là où l'extrusion doit s'arrêter
        # La pâte encore sous pression continue de sortir après l'arrêt du piston. On
        # cesse donc d'extruder un peu avant la fin, et la buse finit le tracé à vide :
        # c'est cette pâte résiduelle qui termine le cordon.
        longueur_totale = self.total_line_length_mm(points_mm)
        points_extrusion, points_a_vide = split_polyline_at(
            points_mm, longueur_totale - self._end_anticipation
        )

        # --- Étape 5 : suivre le tracé point par point en déposant de la pâte
        for i in range(1, len(points_extrusion)):
            x_prec, y_prec = points_extrusion[i - 1]
            x_curr, y_curr = points_extrusion[i]

            # Calculer la longueur réelle du segment (théorème de Pythagore)
            longueur = math.sqrt((x_curr - x_prec) ** 2 + (y_curr - y_prec) ** 2)

            # Quantité d'axe E proportionnelle à la longueur du segment
            steps.append(_dispense(x_curr, y_curr, self._z_dispense, longueur, self._amount_per_mm))

        # --- Étape 6 : finir le tracé sans extruder
        # Ces déplacements restent à la HAUTEUR DE DÉPOSE : la buse suit toujours le
        # cordon, elle ne pousse simplement plus. La remonter ici couperait le cordon net.
        for i in range(1, len(points_a_vide)):
            x_curr, y_curr = points_a_vide[i]
            steps.append(_travel(x_curr, y_curr, self._z_dispense))

        # --- Étape 7 : remonter à la hauteur de transit en fin de tracé
        #
        # ⚠️ Ce step ne bouge qu'en Z, et c'est ESSENTIEL — pas une précaution de style.
        # `Machine.move_to()` envoie `G1 X Y` PUIS `G1 Z` : un déplacement XY a donc
        # toujours lieu à la hauteur où la buse se trouvait AVANT. Sans cette remontée
        # ici, le premier step du cordon suivant traînerait la buse à hauteur de dépose
        # à travers toute la pâte déjà posée, avant de remonter une fois arrivé.
        x_fin, y_fin = points_mm[-1]
        steps.append(_travel(x_fin, y_fin, self._z_travel))

        return steps

    # ------------------------------------------------------------------ plateau entier

    def generate_plateau_path(self, zones: list, cordons: list,
                              row_tolerance_mm: float = None) -> list:
        """Générer la trajectoire de dépose de TOUT un plateau, zones × cordons.

        Paramètres :
            zones   : les `DepositZone` retenues par l'opérateur (celles où il y a un
                      produit). L'ordre dans lequel elles arrivent n'a aucune importance :
                      il est recalculé ici.
            cordons : les `Cordon` de la préparation, en mm RELATIFS à la zone. Ils sont
                      tracés une seule fois et rejoués dans le repère de chaque zone —
                      c'est tout l'intérêt de les avoir mémorisés en relatif (lot B).
            row_tolerance_mm : écart en Y sous lequel deux zones sont sur la même rangée.
                      `None` = calcul automatique.

        Retourne la liste de steps de tout le plateau, **en coordonnées machine**, prête
        à être exécutée. Chaque step porte en plus une clé `"zone"` : l'ID du marqueur
        haut-gauche de la zone à laquelle il appartient. C'est ce qui permet au contrôle
        de course de nommer la zone fautive, et au suivi d'exécution d'annoncer les zones
        faites au fur et à mesure.
        """
        steps = []

        # Les cordons d'un seul point ne tracent rien : les écarter ici évite d'avoir à
        # s'en méfier plus bas, et évite surtout un cordon « fantôme » qui ferait
        # descendre puis remonter la buse pour rien.
        cordons_traçables = [c for c in cordons if c.is_valid]

        for zone in sort_zones_for_deposit(zones, row_tolerance_mm):
            steps_zone = []

            # --- Passage au zéro du repère de la zone, à hauteur de transit.
            # Ce déplacement ne dépose rien et n'est pas nécessaire au tracé : il est là
            # pour être VU. Il rend visible à l'œil la justesse de la chaîne de repères
            # zone → plateau → machine, qui n'a jamais été validée sur la machine (le
            # sens réel des axes est l'action M4). Tant que la dépose se fait sans pâte,
            # c'est le seul contrôle dont on dispose.
            origine_machine = self.zone_point_to_machine_mm(zone, (0.0, 0.0))
            steps_zone.append(
                _travel(origine_machine[0], origine_machine[1], self._z_travel)
            )

            # --- Puis les cordons, dans l'ordre où l'opérateur les a tracés.
            for cordon in cordons_traçables:
                points_machine = [
                    self.zone_point_to_machine_mm(zone, point)
                    for point in cordon.points_mm
                ]
                steps_zone.extend(self.generate_path_from_line(points_machine))

            # Étiqueter d'un coup tous les steps de cette zone, plutôt qu'à chaque
            # création : un seul endroit à corriger si l'étiquette doit changer.
            for step in steps_zone:
                step["zone"] = zone.id_top_left

            steps.extend(steps_zone)

        return steps

    def zone_point_to_machine_mm(self, zone, point_zone_mm: tuple) -> tuple:
        """Convertir un point du repère d'une zone → repère machine, en une fois.

        Enchaîne les deux conversions : la zone sait se placer sur le plateau
        (`to_plateau_mm`, qui applique sa rotation et sa translation), et le plateau se
        place dans la machine par une simple addition d'origine.
        """
        point_plateau = zone.to_plateau_mm(point_zone_mm)
        return plateau_to_machine_mm(
            point_plateau, self._machine_origin_x, self._machine_origin_y
        )

    def total_line_length_mm(self, points_mm: list) -> float:
        """Calculer la longueur totale d'un tracé libre (en mm)."""
        total = 0.0
        for i in range(1, len(points_mm)):
            x1, y1 = points_mm[i - 1]
            x2, y2 = points_mm[i]
            total += math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        return total


# ------------------------------------------------------------------ ordre de parcours

def sort_zones_for_deposit(zones: list, row_tolerance_mm: float = None) -> list:
    """Ordonner les zones pour la dépose : par RANGÉES, de bas en haut.

    La buse fait la rangée du bas de gauche à droite, puis la rangée au-dessus, etc.
    Autrement dit : tri par `y` croissant, puis par `x` croissant à l'intérieur d'une
    rangée. La première zone déposée est donc toujours celle dont l'origine a le plus
    petit `(y, x)`.

    **Pourquoi une tolérance, et pas une égalité sur `y`.** Les positions viennent de la
    vision : deux zones physiquement alignées ne rendront jamais des ordonnées exactement
    égales. Un tri strict découperait donc chaque rangée en autant de « rangées » d'une
    seule zone, dans un ordre qui changerait d'une photo à l'autre pour un plateau
    pourtant identique. La tolérance est ce qui rend l'ordre **reproductible**.

    `row_tolerance_mm=None` la calcule : la moitié de la hauteur d'une zone. Deux zones
    séparées de moins d'une demi-hauteur ne peuvent pas être sur deux rangées distinctes,
    elles se chevaucheraient.
    """
    if not zones:
        return []

    if row_tolerance_mm is None:
        # Médiane plutôt que moyenne : une zone au format aberrant (mal détectée) ne doit
        # pas tirer la tolérance de tout le plateau avec elle.
        hauteurs = sorted(zone.size_mm[1] for zone in zones)
        row_tolerance_mm = hauteurs[len(hauteurs) // 2] / 2.0

    rangees = []
    for zone in sorted(zones, key=lambda z: z.origin_mm[1]):
        # Comparer à la PREMIÈRE zone de la rangée en cours, et non à la précédente.
        # Sinon des zones régulièrement espacées de moins d'une tolérance se
        # rattacheraient de proche en proche et finiraient toutes dans la même rangée,
        # aussi éloignées soient-elles.
        if rangees and zone.origin_mm[1] - rangees[-1][0].origin_mm[1] <= row_tolerance_mm:
            rangees[-1].append(zone)
        else:
            rangees.append([zone])

    ordonnees = []
    for rangee in rangees:
        ordonnees.extend(sorted(rangee, key=lambda z: z.origin_mm[0]))
    return ordonnees


# ------------------------------------------------------------------ géométrie des cordons

def split_polyline_at(points_mm: list, distance_mm: float) -> tuple:
    """Couper une polyline à une distance donnée depuis son début.

    Retourne `(avant, apres)`, deux polylines qui **partagent leur point de coupure** :
    `avant` s'y termine, `apres` y commence. Les enchaîner reparcourt donc exactement le
    tracé d'origine, sans trou ni doublon.

    Sert à l'anticipation de fin de cordon : on extrude sur `avant`, on finit `apres` à
    vide. Le point de coupure tombe presque toujours au milieu d'un segment, d'où
    l'interpolation.
    """
    if len(points_mm) < 2:
        return (list(points_mm), list(points_mm))

    # Couper avant le début : tout le tracé est dans `apres` (rien n'est extrudé).
    # C'est le cas d'une anticipation plus longue que le cordon lui-même.
    if distance_mm <= 0:
        return ([points_mm[0]], list(points_mm))

    # Couper au-delà de la fin, ou EXACTEMENT dessus : rien à finir à vide.
    # Ce second cas n'est pas théorique, c'est le cas NOMINAL — une anticipation nulle
    # demande de couper à la longueur totale. Sans ce garde, la boucle ci-dessous
    # trouverait la coupure sur le dernier segment et rendrait un `apres` de deux points
    # confondus, donc un déplacement supplémentaire vers un point où la buse est déjà.
    # Le cycle historique (screen_zone) n'aurait alors plus la même trajectoire qu'avant.
    longueur_totale = sum(
        math.dist(points_mm[i - 1], points_mm[i]) for i in range(1, len(points_mm))
    )
    if distance_mm >= longueur_totale:
        return (list(points_mm), [points_mm[-1]])

    parcouru = 0.0
    for i in range(1, len(points_mm)):
        x_prec, y_prec = points_mm[i - 1]
        x_curr, y_curr = points_mm[i]
        longueur = math.dist((x_prec, y_prec), (x_curr, y_curr))

        # Le point de coupure tombe-t-il sur ce segment ?
        if parcouru + longueur >= distance_mm:
            # Un segment de longueur nulle (deux points confondus) ne peut pas être
            # interpolé — on coupe alors sur son extrémité.
            if longueur == 0:
                coupure = (x_curr, y_curr)
            else:
                # Fraction du segment à parcourir pour atteindre la distance visée
                t = (distance_mm - parcouru) / longueur
                coupure = (
                    x_prec + t * (x_curr - x_prec),
                    y_prec + t * (y_curr - y_prec),
                )
            return (points_mm[:i] + [coupure], [coupure] + points_mm[i:])

        parcouru += longueur

    # Distance au-delà du tracé : rien à finir à vide.
    return (list(points_mm), [points_mm[-1]])


# ------------------------------------------------------------------ repère machine

def plateau_to_machine_mm(point_mm: tuple, origin_x: float = MACHINE_ORIGIN_X,
                          origin_y: float = MACHINE_ORIGIN_Y) -> tuple:
    """Convertir un point du repère plateau → repère machine.

    Deux additions, et c'est tout. Le repère du plateau a été refait au lot C2bis
    précisément pour en arriver là : son X va vers la droite et son **Y vers le haut**,
    comme les axes machine. L'inversion isolée qu'il fallait autrefois penser à écrire à
    cet endroit — le seul du logiciel où les deux repères se rejoignent — a disparu.

    ⚠️ Le SENS réel des axes machine reste l'action `M4` : ces deux additions sont
    cohérentes avec la convention, elles ne sont pas validées sur la machine.
    """
    return (point_mm[0] + origin_x, point_mm[1] + origin_y)


# ------------------------------------------------------------------ contrôle de course

def check_machine_limits(
    steps: list,
    x_max: float = MACHINE_TRAVEL_X_MAX_MM,
    y_max: float = MACHINE_TRAVEL_Y_MAX_MM,
    z_max: float = MACHINE_TRAVEL_Z_MAX_MM,
) -> list:
    """Vérifier que tous les steps restent dans le domaine atteignable par la machine.

    ⚠️ **Pourquoi ce contrôle existe.** Marlin ne refuse pas une coordonnée hors course :
    il la **rogne en silence**. Une dépose sortirait donc déformée, sans le moindre
    message, et on chercherait la cause du côté de la vision ou de la calibration. Ce
    contrôle transforme une erreur silencieuse en refus explicite — même famille de
    décision que le `FORMAT_VERSION` du lot C2bis.

    Le besoin est concret depuis le 2026-08-03 : `MACHINE_ORIGIN_Y = -2.0` met une bande
    de 2 mm en bas du plateau hors d'atteinte.

    Retourne la liste des dépassements (vide si tout va bien), chacun sous la forme
    `{"axis", "value", "limit", "zone", "index"}`. À appeler **avant** le premier
    mouvement, jamais pendant.
    """
    bornes = {"X": x_max, "Y": y_max, "Z": z_max}
    violations = []

    for index, step in enumerate(steps):
        for axe, cle in (("X", "x"), ("Y", "y"), ("Z", "z")):
            valeur = step[cle]
            # Le minimum est 0 sur les trois axes : c'est la position de homing, et la
            # butée physique se trouve juste derrière.
            if valeur < 0.0:
                limite = 0.0
            elif valeur > bornes[axe]:
                limite = bornes[axe]
            else:
                continue
            violations.append({
                "axis": axe,
                "value": valeur,
                "limit": limite,
                "zone": step.get("zone"),
                "index": index,
            })

    return violations


def format_limit_violations(violations: list) -> str:
    """Rédiger le message d'erreur montré à l'opérateur en cas de dépassement.

    Le message nomme les **zones** fautives et non les numéros de step : l'opérateur
    raisonne en pièces posées sur le plateau, pas en instructions G-code. Et il dit quoi
    faire — le remède est mécanique (rapprocher le plateau), pas logiciel.
    """
    if not violations:
        return ""

    # Regrouper par zone : vingt dépassements sur la même zone sont un seul problème.
    zones = sorted({v["zone"] for v in violations}, key=lambda z: (z is None, z))
    noms = ", ".join("inconnue" if z is None else f"zone {z}" for z in zones)

    pire = min(violations, key=lambda v: v["value"] - v["limit"])
    return (
        f"Depose impossible : {len(violations)} point(s) sortent de la course de la "
        f"machine ({noms}).\n"
        f"Pire ecart : axe {pire['axis']} a {pire['value']:.2f} mm, "
        f"limite {pire['limit']:.2f} mm.\n"
        f"La machine ne signalerait rien et deposerait de travers : le lancement est "
        f"annule.\n"
        f"Remede : rapprocher le plateau, ou retracer les cordons plus loin du bord."
    )


# ------------------------------------------------------------------ fonctions utilitaires

def _travel(x: float, y: float, z: float) -> dict:
    """Créer un step de déplacement rapide sans dépose."""
    return {"type": "travel", "x": round(x, 3), "y": round(y, 3),
            "z": round(z, 3), "amount": 0.0}


def _dispense(x: float, y: float, z: float, length_mm: float, amount_per_mm: float) -> dict:
    """Créer un step de dépose sur un segment de longueur donnée."""
    # La quantité d'axe E est proportionnelle à la longueur du segment
    amount = round(length_mm * amount_per_mm, 4)
    return {"type": "dispense", "x": round(x, 3), "y": round(y, 3),
            "z": round(z, 3), "amount": amount}


def _prime(x: float, y: float, z: float, amount: float) -> dict:
    """Créer un step d'amorçage : extruder SANS bouger, au début d'un cordon.

    Les coordonnées sont celles du point où la buse se trouve déjà. Elles sont répétées
    ici pour que tous les steps aient la même forme — le contrôle de course et le suivi
    d'exécution peuvent ainsi les traiter sans cas particulier.
    """
    return {"type": "prime", "x": round(x, 3), "y": round(y, 3),
            "z": round(z, 3), "amount": round(amount, 4)}
