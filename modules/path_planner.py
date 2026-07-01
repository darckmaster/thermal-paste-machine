# Calcul des trajectoires de dépose de pâte thermique
# Transforme une zone rectangulaire (en mm) en liste de waypoints G-code

import math


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

        # --- Étape 3 : suivre le tracé point par point en déposant de la pâte
        for i in range(1, len(points_mm)):
            x_prec, y_prec = points_mm[i - 1]
            x_curr, y_curr = points_mm[i]

            # Calculer la longueur réelle du segment (théorème de Pythagore)
            longueur = math.sqrt((x_curr - x_prec) ** 2 + (y_curr - y_prec) ** 2)

            # Quantité d'axe E proportionnelle à la longueur du segment
            steps.append(_dispense(x_curr, y_curr, self._z_dispense, longueur, self._amount_per_mm))

        # --- Étape 4 : remonter à la hauteur de transit en fin de tracé
        x_fin, y_fin = points_mm[-1]
        steps.append(_travel(x_fin, y_fin, self._z_travel))

        return steps

    def total_line_length_mm(self, points_mm: list) -> float:
        """Calculer la longueur totale d'un tracé libre (en mm)."""
        total = 0.0
        for i in range(1, len(points_mm)):
            x1, y1 = points_mm[i - 1]
            x2, y2 = points_mm[i]
            total += math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        return total


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
