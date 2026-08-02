import math          # Trigonométrie pour les rotations de zone (atan2, cos, sin)
import statistics    # median() — plus robuste que la moyenne face à une zone mal montée

import cv2
import numpy as np

from modules.config import (
    ARUCO_DICT_ID,
    ARUCO_MARKER_SIZE_MM,
    WORK_AREA_WIDTH_MM,
    WORK_AREA_HEIGHT_MM,
)


# Correspondance entre le nom de dictionnaire (string de config.py) et la constante interne OpenCV
_ARUCO_DICTS = {
    "DICT_4X4_50": cv2.aruco.DICT_4X4_50,
    "DICT_4X4_100": cv2.aruco.DICT_4X4_100,
    "DICT_5X5_50": cv2.aruco.DICT_5X5_50,
}


def _plateau_corner_positions_mm() -> dict:
    """Positions mm connues des 4 marqueurs de coin du plateau, dans son propre repère.

    Disposition physique constatée le 2026-08-01 :

        3 ─────── 0            Y
        │         │            ↑
        2 ─────── 1            └──→ X   (origine sur le tag 2)

    Repère ORTHONORMÉ du plateau, arrêté au lot C2bis (2026-08-01 au soir) :
      - origine       = centre du marqueur **2** (BAS-GAUCHE)
      - axe X (abscisses) = vers le centre du marqueur 1 (bas-droit)
      - axe Y (ordonnées) = vers le centre du marqueur 3 (haut-gauche),
        donc **Y vers le HAUT**
      - le marqueur 0 (haut-droit) devient redondant : il sert de **contrôle de
        cohérence** (voir VisionProcessor.compute_plateau_reference)

    Pourquoi ce sens, alors que la v0.1.1 avait choisi l'inverse le matin même
    ---------------------------------------------------------------------------
    Pour aligner le repère logiciel sur le repère physique dans lequel on
    raisonne devant la machine, avant d'écrire la construction des commandes
    machine (lot D). L'axe Y machine monte vers le fond : le repère plateau monte
    désormais lui aussi, ce qui supprime l'inversion de signe qui se cachait dans
    gui/screen_run.py.

    ⚠️ Ce que ce choix N'AUTORISE PAS à oublier — le miroir vertical
    ---------------------------------------------------------------------------
    Une image a son origine en haut à gauche et son Y qui **descend** (ligne 0 =
    ligne du haut) ; aucune convention de notre côté ne change ça. Avec Y montant,
    `y = 0 mm` est le BAS du plateau : sans précaution, ce bas atterrirait sur la
    ligne 0, donc en HAUT de l'écran, et l'opérateur verrait le plateau à
    l'envers. Les trois méthodes warp_* retournent donc Y explicitement :

        y_pixel = (hauteur_mm − y_mm) × échelle

    Règle posée par l'étudiant : la convention sert à faciliter les calculs, elle
    ne doit RIEN changer pour l'opérateur — ce qu'il voit à l'écran est ce qui se
    passe sur le plateau. Ce miroir a déjà existé dans le projet de la Phase 2 au
    2026-08-01 sans que personne ne le voie à l'œil (un plateau à peu près
    symétrique ne trahit pas son propre retournement) : il a été démasqué par le
    calcul. D'où test_warp_image_orientation_non_miroir, à ne pas affaiblir.

    L'argument « toutes les coordonnées du plateau restent positives », qui avait
    motivé le Y descendant, est préservé : l'origine reste sur un COIN.

    Table partagée par compute_homography() (4 marqueurs, précis) et
    compute_homography_approx() (2-3 marqueurs, dégradé — repli caméra Geeetech,
    voir son docstring).
    """
    return {
        2: (0.0,                  0.0),                  # bas-gauche = origine
        1: (WORK_AREA_WIDTH_MM,   0.0),                  # bas-droit
        0: (WORK_AREA_WIDTH_MM,   WORK_AREA_HEIGHT_MM),  # haut-droit
        3: (0.0,                  WORK_AREA_HEIGHT_MM),  # haut-gauche
    }


# Marqueur qui porte l'origine du repère plateau. Nommé plutôt qu'écrit « 2 » un peu
# partout : c'est LA valeur qui a changé au lot C2bis, et une constante rend visible
# chaque endroit qui en dépend.
PLATEAU_ORIGIN_MARKER_ID = 2

# Marqueur redondant, utilisé comme contrôle de cohérence du montage optique.
PLATEAU_CHECK_MARKER_ID = 0

# Au-delà de cet écart (en mm) entre la position VUE du marqueur de contrôle et sa
# position ATTENDUE, on prévient l'opérateur. Le seuil est volontairement large : cet
# écart mêle l'inclinaison de la caméra, la distorsion de l'objectif (~10 % non encore
# corrigés, action M5), une déformation du plateau et un tag mal collé. Il sert à
# repérer une dérive franche, pas à mesurer une précision.
PLATEAU_CHECK_TOLERANCE_MM = 5.0


# ===========================================================================
# Zones de dépose — géométrie
# ===========================================================================
#
# Une zone de dépose est l'emplacement d'un produit sur le plateau. Elle est
# matérialisée par DEUX marqueurs ArUco, dont les centres sont posés aux deux
# extrémités de la diagonale haut-gauche → bas-droit du rectangle.
#
# Convention d'appariement : l'ID du marqueur bas-droit vaut celui du marqueur
# haut-gauche PLUS UN. Cette règle donne une orientation à la zone : si le
# marqueur n se retrouve en bas à droite du n+1, la zone a été montée à
# l'envers — c'est détectable (voir ANOMALIE_INVERSEE).
#
# ⚠️ « haut-gauche » et « bas-droit » décrivent CE QUE VOIT L'OPÉRATEUR à l'écran,
# pas le signe des coordonnées. Depuis le lot C2bis l'axe Y du plateau monte : le
# vecteur diagonale d'une zone bien montée va donc vers la droite et vers le BAS de
# l'écran, soit dx > 0 et **dy < 0**. Vocabulaire conservé volontairement (décidé le
# 2026-08-02) : l'image affichée restant à l'endroit, ces noms continuent de désigner
# exactement ce que l'opérateur a sous les yeux.
#
# Les zones sont vissées à demeure et accueillent toutes le MÊME produit :
# leurs diagonales ont donc la même longueur, à l'erreur de montage près.
# C'est cette invariante qui lève l'ambiguïté d'appariement — sans elle, le
# tag 5 pourrait aussi bien clore la paire (4,5) qu'ouvrir la paire (5,6).

# Premier ID utilisable pour une zone. Les IDs 0 à 3 sont réservés aux coins du
# plateau (voir _plateau_corner_positions_mm) : sans cette borne, la paire (2,3)
# formée par deux coins du plateau serait prise pour une zone de dépose.
FIRST_ZONE_MARKER_ID = 4

# Tolérance sur la longueur de diagonale, en mm. Deux zones dont les diagonales
# diffèrent de moins que ça sont considérées comme portant le même produit.
# Doit rester supérieure à l'imprécision de mesure (homographie approchée du
# repli 2 marqueurs comprise) mais très inférieure à l'écart qui séparerait une
# vraie diagonale d'un appariement fantaisiste.
ZONE_DIAGONAL_TOLERANCE_MM = 5.0

# Au-delà de cet angle (en degrés) par rapport au repère du plateau, une zone est
# signalée comme mal montée. Le technicien qui visse les zones a pour consigne de
# les poser toutes droites et orientées pareil : un écart important trahit une
# erreur de montage, pas une variation normale.
ZONE_MAX_ROTATION_DEG = 10.0

# Anomalies détectables sur une zone. Des chaînes plutôt qu'une énumération :
# elles seront affichées telles quelles à l'opérateur et sérialisées en JSON.
ANOMALIE_INVERSEE = "zone_inversee"
ANOMALIE_DIAGONALE = "diagonale_hors_norme"
ANOMALIE_CONFLIT = "paire_en_conflit"
ANOMALIE_ANGLE = "angle_excessif"
# Aucun format de produit n'a pu être déduit, donc aucun rectangle reconstruit. Arrive
# quand plus aucune zone n'est à la fois saine et à l'endroit — typiquement un plateau
# intégralement monté à l'envers.
ANOMALIE_FORMAT_INCONNU = "format_indeterminable"


class DepositZone:
    """Une zone de dépose reconstruite : son rectangle, son orientation, son état.

    Toutes les coordonnées sont en mm dans le repère du plateau (origine au
    marqueur 2, X vers la droite, **Y vers le haut** — voir
    _plateau_corner_positions_mm).
    """

    def __init__(
        self,
        id_top_left: int,
        id_bottom_right: int,
        corners_mm: tuple,
        rotation_deg: float,
        diagonal_mm: float,
        size_mm: tuple,
        anomalies: list,
    ) -> None:
        # IDs des deux marqueurs qui définissent la zone (id_bottom_right = id_top_left + 1)
        self.id_top_left = id_top_left
        self.id_bottom_right = id_bottom_right
        # Les 4 coins du rectangle reconstruit, dans l'ordre haut-gauche, haut-droit,
        # bas-droit, bas-gauche — l'ordre TEL QU'ON LE VOIT À L'ÉCRAN, et l'ordre
        # attendu par cv2.polylines pour tracer le contour sans croisement.
        # L'origine du repère de la zone est le coin BAS-GAUCHE, donc corners_mm[3].
        self.corners_mm = corners_mm
        # Rotation de la zone par rapport au repère du plateau, en degrés.
        # Positive = sens TRIGONOMÉTRIQUE, c'est-à-dire antihoraire à l'écran, depuis
        # que l'axe Y du repère plateau monte (lot C2bis). C'était l'inverse avant.
        self.rotation_deg = rotation_deg
        # Longueur mesurée de la diagonale entre les deux centres de marqueurs
        self.diagonal_mm = diagonal_mm
        # (largeur, hauteur) retenues pour cette zone, issues du format de référence
        self.size_mm = size_mm
        # Liste des anomalies (constantes ANOMALIE_*) — vide si la zone est saine
        self.anomalies = anomalies

    @property
    def is_valid(self) -> bool:
        """Une zone est exploitable si aucune anomalie n'a été relevée."""
        return not self.anomalies

    @property
    def center_mm(self) -> tuple:
        """Centre géométrique du rectangle — sert à placer une étiquette à l'écran."""
        xs = [c[0] for c in self.corners_mm]
        ys = [c[1] for c in self.corners_mm]
        return (sum(xs) / 4.0, sum(ys) / 4.0)

    # ------------------------------------------------------------------ repères
    #
    # Les cordons sont mémorisés en mm RELATIFS à la zone : origine au coin
    # BAS-GAUCHE, X le long de la largeur, **Y le long de la hauteur vers le haut**.
    # C'est ce qui permet de tracer un cordon une seule fois et de l'appliquer à
    # toutes les autres zones du plateau, qui accueillent le même produit — il
    # suffit de rejouer les mêmes coordonnées dans le repère de chaque zone.
    #
    # Le repère de la zone a basculé en Y montant au lot C2bis, en même temps que
    # celui du plateau. Garder deux conventions opposées aurait réintroduit
    # exactement la confusion que ce lot supprime — et les coordonnées de la zone
    # restent positives, l'origine étant sur un coin, comme pour le plateau.
    #
    # Les deux méthodes ci-dessous sont exactement inverses l'une de l'autre. Leurs
    # FORMULES n'ont pas changé au lot C2bis (une rotation directe s'écrit pareil
    # dans les deux repères) : seule l'origine a changé de coin.

    @property
    def origin_mm(self) -> tuple:
        """Origine du repère de la zone : son coin BAS-GAUCHE, en mm plateau.

        Nommée plutôt qu'écrite `corners_mm[3]` aux trois endroits qui en dépendent :
        c'est l'index qui a changé au lot C2bis (c'était `[0]`, le coin haut-gauche),
        et le nommer rend le point de bascule visible d'un coup d'œil.
        """
        return self.corners_mm[3]

    def to_plateau_mm(self, point_zone_mm: tuple) -> tuple:
        """Convertit un point exprimé dans le repère de la zone → repère du plateau.

        Applique la rotation de la zone puis la translation vers son coin bas-gauche.
        """
        x, y = point_zone_mm
        theta = math.radians(self.rotation_deg)
        cos_t, sin_t = math.cos(theta), math.sin(theta)

        origine = self.origin_mm
        return (
            origine[0] + x * cos_t - y * sin_t,
            origine[1] + x * sin_t + y * cos_t,
        )

    def to_zone_mm(self, point_plateau_mm: tuple) -> tuple:
        """Convertit un point du repère du plateau → repère de la zone.

        Opération inverse de to_plateau_mm : on translate d'abord vers l'origine de
        la zone, puis on applique la rotation opposée (-θ).
        """
        origine = self.origin_mm
        dx = point_plateau_mm[0] - origine[0]
        dy = point_plateau_mm[1] - origine[1]

        theta = math.radians(-self.rotation_deg)
        cos_t, sin_t = math.cos(theta), math.sin(theta)

        return (dx * cos_t - dy * sin_t, dx * sin_t + dy * cos_t)

    def __repr__(self) -> str:
        etat = "OK" if self.is_valid else ",".join(self.anomalies)
        return (
            f"DepositZone({self.id_top_left}/{self.id_bottom_right}, "
            f"rot={self.rotation_deg:.1f}°, diag={self.diagonal_mm:.1f}mm, {etat})"
        )


class PlateauLayout:
    """Résultat complet de l'analyse d'un plateau : les zones trouvées et le contexte."""

    def __init__(
        self,
        zones: list,
        unpaired_ids: list,
        reference_diagonal_mm,
        product_size_mm,
    ) -> None:
        # Toutes les zones reconstruites, valides ou non — l'IHM a besoin des
        # invalides pour les signaler visuellement à l'opérateur
        self.zones = zones
        # Marqueurs de la plage "zone" (ID >= FIRST_ZONE_MARKER_ID) qui n'ont abouti
        # à aucune paire retenue : soit leur voisin n'est pas détecté, soit la paire
        # qu'ils formaient avait une diagonale hors norme
        self.unpaired_ids = unpaired_ids
        # Longueur de diagonale de référence (médiane du groupe majoritaire), ou None
        self.reference_diagonal_mm = reference_diagonal_mm
        # Format (largeur, hauteur) déduit du produit, ou None si indéterminable
        self.product_size_mm = product_size_mm

    @property
    def valid_zones(self) -> list:
        """Les seules zones sur lesquelles on peut travailler sans risque."""
        return [z for z in self.zones if z.is_valid]

    @property
    def has_anomalies(self) -> bool:
        """True si l'opérateur doit être averti avant de continuer."""
        return bool(self.unpaired_ids) or any(not z.is_valid for z in self.zones)


def _candidate_pairs(marker_ids, first_zone_marker_id: int) -> list:
    """Liste les paires (n, n+1) possibles parmi les marqueurs détectés.

    Une même étiquette peut apparaître dans DEUX paires candidates : le tag 5
    ouvre la paire (5,6) et clôt la paire (4,5). C'est volontaire — on énumère
    tout, le tri se fait ensuite sur la longueur de diagonale.
    """
    ids = sorted(i for i in marker_ids if i >= first_zone_marker_id)
    presents = set(ids)
    return [(i, i + 1) for i in ids if (i + 1) in presents]


def _reference_diagonal_mm(longueurs: list, tolerance_mm: float):
    """Détermine la longueur de diagonale de référence du plateau.

    Principe : toutes les zones portant le même produit, la « bonne » longueur est
    celle qui revient le plus souvent. On regroupe donc les longueurs par proximité
    (± tolerance_mm), on retient le groupe le plus peuplé, et on renvoie sa MÉDIANE
    plutôt que le représentant qui a servi à le former — la médiane moyenne les
    petites erreurs de mesure sur toutes les zones du groupe.

    En cas d'égalité de taille entre deux groupes, le premier rencontré l'emporte
    (ordre croissant des IDs) : c'est arbitraire mais déterministe, donc reproductible.

    Retourne None si la liste est vide.
    """
    if not longueurs:
        return None

    meilleur_groupe: list = []
    for candidate in longueurs:
        # Toutes les longueurs qui « ressemblent » à ce candidat
        groupe = [L for L in longueurs if abs(L - candidate) <= tolerance_mm]
        if len(groupe) > len(meilleur_groupe):
            meilleur_groupe = groupe

    return statistics.median(meilleur_groupe)


def _rectangle_from_diagonal(p_tl: tuple, p_br: tuple, w_mm: float, h_mm: float) -> tuple:
    """Reconstruit un rectangle de format (w_mm, h_mm) à partir de sa diagonale.

    Les deux extrémités de la diagonale ne suffisent PAS à définir un rectangle : il
    en existe une infinité, un par angle. Connaître le format du produit lève cette
    indétermination, et le calcul devient direct : faire tourner un rectangle de θ
    fait tourner sa diagonale de θ aussi. L'angle de la diagonale mesurée vaut donc
    θ + angle(w, −h), d'où **θ = angle(diagonale) − angle(w, −h)**.

    ⚠️ Le signe MOINS sur la hauteur est un point de bascule du lot C2bis : l'axe Y
    du plateau monte désormais, donc la diagonale d'une zone bien montée descend à
    l'écran et vaut (largeur, −hauteur), pas (largeur, +hauteur). Les paramètres
    w_mm et h_mm, eux, restent des LONGUEURS, donc positifs.

    Pourquoi une SEULE solution, et pas les deux solutions symétriques
    ------------------------------------------------------------------
    Il subsiste une ambiguïté classique quand on ignore lequel des deux côtés est la
    largeur : le rectangle (h, w) posé droit a la même direction de diagonale que le
    rectangle (w, h) tourné. On aurait alors deux solutions, et il faudrait départager
    en gardant la plus faible rotation.

    Cette ambiguïté n'existe pas ici, parce que le format est déduit de la MÉDIANE des
    composantes de diagonale sur toutes les zones du plateau (voir
    detect_deposit_zones_mm, étape 5) : c'est donc un format ORIENTÉ, la majorité des
    zones ayant déjà tranché quel côté est la largeur. Envisager l'échange (h, w)
    serait même nuisible : une zone vissée à 25° verrait sa diagonale réinterprétée
    comme celle d'une zone 40×60 posée à 2°, et l'anomalie de montage passerait
    inaperçue. C'est précisément ce qu'a montré test_zone_trop_inclinee_signalee.

    Une zone réellement montée à 90° du format de référence n'est pas perdue pour
    autant : sa diagonale pointe alors vers la gauche, ce qui la fait détecter comme
    zone inversée (ANOMALIE_INVERSEE).

    Retourne (coins, rotation_deg, (largeur, hauteur)) où coins est le tuple
    (haut-gauche, haut-droit, bas-droit, bas-gauche) en mm — l'ordre tel qu'on le
    VOIT à l'écran. rotation_deg est positif dans le sens trigonométrique.

    ⚠️ Le coin bas-droit reconstruit peut différer de quelques dixièmes de p_br : le
    rectangle est bâti sur le format de RÉFÉRENCE du produit, pas sur la longueur
    mesurée de cette diagonale-ci, qui porte le bruit de détection.
    """
    angle_diagonale = math.atan2(p_br[1] - p_tl[1], p_br[0] - p_tl[0])
    largeur, hauteur = w_mm, h_mm

    theta = angle_diagonale - math.atan2(-hauteur, largeur)
    # Ramener dans [-pi, pi] — sans ça un angle de -179° passerait pour « plus grand »
    # que +181°, alors que c'est le même écart au repère du plateau
    theta = math.atan2(math.sin(theta), math.cos(theta))

    # Vecteurs unitaires des deux côtés du rectangle, tournés de theta.
    # u longe la largeur (vers la droite de l'écran), v longe la hauteur ; v est u
    # tourné d'un quart de tour DANS LE SENS HORAIRE, car « descendre le long de la
    # hauteur » à l'écran, c'est faire décroître y depuis que l'axe Y monte.
    u = (math.cos(theta), math.sin(theta))
    v = (math.sin(theta), -math.cos(theta))

    haut_gauche = p_tl
    haut_droit = (p_tl[0] + largeur * u[0], p_tl[1] + largeur * u[1])
    bas_droit = (haut_droit[0] + hauteur * v[0], haut_droit[1] + hauteur * v[1])
    bas_gauche = (p_tl[0] + hauteur * v[0], p_tl[1] + hauteur * v[1])

    coins = (haut_gauche, haut_droit, bas_droit, bas_gauche)
    return coins, math.degrees(theta), (largeur, hauteur)


def detect_deposit_zones_mm(
    centers_mm: dict,
    first_zone_marker_id: int = FIRST_ZONE_MARKER_ID,
    diagonal_tolerance_mm: float = ZONE_DIAGONAL_TOLERANCE_MM,
    max_rotation_deg: float = ZONE_MAX_ROTATION_DEG,
) -> PlateauLayout:
    """Reconstruit les zones de dépose à partir des centres de marqueurs en mm.

    Fonction PURE : elle ne touche ni à la caméra ni à OpenCV, elle ne manipule que
    des coordonnées en mm. C'est ce qui la rend entièrement testable sans matériel —
    la conversion pixels → mm est faite en amont par VisionProcessor.

    Paramètre :
        centers_mm : {id_marqueur: (x_mm, y_mm)} — centres des marqueurs détectés,
                     déjà convertis dans le repère du plateau

    Déroulé (chaque étape dépend de la précédente) :
        1. énumérer les paires candidates (n, n+1)
        2. en déduire la longueur de diagonale de référence (groupe majoritaire)
        3. écarter les paires dont la diagonale s'en écarte
        4. invalider les paires qui se disputent un même marqueur
        5. déduire le format (w, h) du produit des zones saines et à l'endroit
        6. reconstruire chaque rectangle et mesurer sa rotation

    ⚠️ Limite connue : avec une SEULE zone détectée, celle-ci définit à elle seule la
    référence. Sa rotation ressort donc nulle par construction et aucune erreur de
    montage n'est décelable. Ce n'est pas un défaut d'implémentation mais une limite
    du dispositif : il faut au moins deux zones pour que la comparaison ait un sens.
    """
    # --- Étape 1 : paires candidates ---------------------------------------
    paires = _candidate_pairs(centers_mm.keys(), first_zone_marker_id)

    # Vecteur diagonale de chaque paire, du marqueur haut-gauche vers le bas-droit
    diagonales = {}
    for id_tl, id_br in paires:
        p_tl = centers_mm[id_tl]
        p_br = centers_mm[id_br]
        diagonales[(id_tl, id_br)] = (p_br[0] - p_tl[0], p_br[1] - p_tl[1])

    longueurs = {
        paire: math.hypot(d[0], d[1]) for paire, d in diagonales.items()
    }

    # --- Étape 2 : trier les paires par plausibilité d'orientation ----------
    # Le repère du plateau ayant son Y dirigé vers le HAUT (lot C2bis), une zone
    # correctement montée va du haut-gauche vers le bas-droit de l'ÉCRAN : elle avance
    # en X et redescend en Y, donc **dx > 0 et dy < 0**. Trois cas se présentent :
    #   - (+, −) → zone plausible
    #   - (−, +) → zone montée à l'envers, à signaler
    #   - signes identiques (+,+) ou (−,−) → paire FANTÔME, à écarter sans bruit
    #
    # ⚠️ C'est l'exact opposé du test d'avant le lot C2bis (`d[0] > 0 and d[1] > 0`) :
    # retourner l'axe Y retourne aussi ce filtre, et ANOMALIE_INVERSEE repose
    # entièrement dessus.
    #
    # Ce tri n'est pas un raffinement : sur un plateau en grille régulière, la paire
    # fantôme formée du coin bas-droit d'une zone et du coin haut-gauche de sa voisine
    # de droite a exactement la MÊME longueur de diagonale que les vraies zones, par
    # symétrie. Sans ce tri elle passerait le filtre de longueur, puis invaliderait par
    # conflit les deux zones réelles avec lesquelles elle partage ses tags — un plateau
    # parfaitement monté deviendrait inexploitable.
    plausibles = {p: d for p, d in diagonales.items() if d[0] > 0 and d[1] < 0}
    inversees = {p: d for p, d in diagonales.items() if d[0] < 0 and d[1] > 0}

    # --- Étape 3 : longueur de référence et filtrage ------------------------
    # La référence se calcule sur TOUTES les paires d'orientation cohérente, inversées
    # comprises : une zone montée à l'envers reste une zone, et sa diagonale a bien la
    # longueur du produit. Seules les paires à signes mixtes — les fantômes — sont
    # exclues du vote.
    #
    # Ne voter que sur les paires plausibles serait un piège : si TOUTES les zones d'un
    # plateau sont montées à l'envers, elles disparaissent du vote et les rares fantômes
    # d'orientation plausible fixent seuls la référence. Les vraies zones sont alors
    # rejetées comme orphelines pendant que des fantômes sont présentés comme des zones
    # valides — un résultat faux et silencieux, constaté en écrivant les tests du lot C1.
    pool_reference = list(plausibles) + list(inversees)
    reference = _reference_diagonal_mm(
        [longueurs[p] for p in pool_reference], diagonal_tolerance_mm
    )

    def _a_la_bonne_longueur(paire) -> bool:
        """Une paire est retenue si sa diagonale correspond au format du plateau."""
        return (
            reference is not None
            and abs(longueurs[paire] - reference) <= diagonal_tolerance_mm
        )

    retenues = [p for p in plausibles if _a_la_bonne_longueur(p)]
    retenues_inversees = [p for p in inversees if _a_la_bonne_longueur(p)]

    # --- Étape 4 : conflits -------------------------------------------------
    # Un marqueur ne peut appartenir qu'à une seule zone physique. S'il subsiste dans
    # deux paires retenues, on ne peut pas trancher automatiquement : les DEUX sont
    # marquées en conflit et l'opérateur devra rectifier le plateau.
    # Les zones inversées participent à l'analyse : si l'une d'elles se dispute un tag
    # avec une zone saine, l'opérateur doit le savoir. Les fantômes, eux, ont déjà été
    # écartés à l'étape 2 et ne peuvent donc plus invalider personne.
    usages: dict = {}
    for paire in retenues + retenues_inversees:
        for marker_id in paire:
            usages.setdefault(marker_id, []).append(paire)
    paires_en_conflit = {
        paire for paires_du_tag in usages.values() if len(paires_du_tag) > 1
        for paire in paires_du_tag
    }

    # --- Étape 5 : format du produit ---------------------------------------
    # Une zone bien montée est quasiment droite : son vecteur diagonale vaut donc
    # directement (largeur, −hauteur). En prenant la médiane sur toutes les zones
    # saines, on obtient le format du produit sans rien demander à l'opérateur, et
    # une zone isolée montée de travers ne fausse pas le résultat.
    # Seules les paires « retenues » entrent ici : les inversées sont exclues, leur
    # diagonale pointant à l'opposé tirerait la médiane vers des valeurs aberrantes.
    #
    # CONVENTION DE SIGNE, à tenir dans tout le projet (lot C2bis) : product_size_mm
    # est un couple de LONGUEURS, donc les deux composantes sont POSITIVES. Le repère
    # plateau ayant son Y montant, la médiane des dy est négative — d'où le signe moins
    # ci-dessous, seul endroit du code où la conversion « composante → longueur » se
    # fait. Le reste du fichier (size_mm, _rectangle_from_diagonal, warp_zone) peut
    # donc supposer partout largeur > 0 et hauteur > 0.
    diagonales_saines = [
        diagonales[paire] for paire in retenues
        if paire not in paires_en_conflit
    ]
    if diagonales_saines:
        product_size_mm = (
            statistics.median(d[0] for d in diagonales_saines),
            -statistics.median(d[1] for d in diagonales_saines),
        )
    else:
        product_size_mm = None

    # --- Étape 6 : reconstruction de chaque zone ---------------------------
    zones = []
    for paire in sorted(retenues + retenues_inversees):
        id_tl, id_br = paire
        anomalies = []
        est_inversee = paire in retenues_inversees

        if paire in paires_en_conflit:
            anomalies.append(ANOMALIE_CONFLIT)

        if est_inversee:
            anomalies.append(ANOMALIE_INVERSEE)

        # Pour une zone inversée, le marqueur porteur du plus petit ID se trouve
        # physiquement en bas à droite : on inverse les deux points d'appui pour que
        # le rectangle reconstruit recouvre quand même la zone réelle. L'opérateur
        # verra ainsi le défaut signalé AU BON ENDROIT sur l'image.
        point_haut_gauche = centers_mm[id_br] if est_inversee else centers_mm[id_tl]
        point_bas_droit = centers_mm[id_tl] if est_inversee else centers_mm[id_br]

        if product_size_mm is None:
            # Aucune référence de format : impossible de reconstruire un rectangle.
            # On dégrade proprement plutôt que de lever une exception — la zone reste
            # listée, avec ses deux marqueurs comme unique géométrie, pour que l'IHM
            # puisse quand même la signaler à l'opérateur au bon endroit.
            # Les 4 « coins » se réduisent aux 2 marqueurs, répétés pour garder un
            # tuple de longueur 4 : l'IHM lit corners_mm[0] pour poser son étiquette
            # et trace le contour tel quel. Le repère de zone (origin_mm =
            # corners_mm[3]) n'a lui aucun sens ici — sans format connu il n'y a pas
            # de rectangle, donc pas de repère : la zone est de toute façon marquée
            # ANOMALIE_FORMAT_INCONNU, donc jamais exploitée pour un tracé.
            zones.append(DepositZone(
                id_tl, id_br,
                corners_mm=(point_haut_gauche, point_bas_droit,
                            point_bas_droit, point_haut_gauche),
                rotation_deg=0.0,
                diagonal_mm=longueurs[paire],
                size_mm=(0.0, 0.0),
                anomalies=anomalies + [ANOMALIE_FORMAT_INCONNU],
            ))
            continue

        coins, rotation_deg, taille = _rectangle_from_diagonal(
            point_haut_gauche, point_bas_droit, product_size_mm[0], product_size_mm[1]
        )

        if abs(rotation_deg) > max_rotation_deg:
            anomalies.append(ANOMALIE_ANGLE)

        zones.append(DepositZone(
            id_tl, id_br, coins, rotation_deg, longueurs[paire], taille, anomalies
        ))

    # Marqueurs de la plage "zone" restés sur le carreau : soit leur voisin manque à
    # l'appel, soit la paire qu'ils formaient a été écartée à l'étape 3
    ids_utilises = {i for paire in retenues + retenues_inversees for i in paire}
    unpaired_ids = sorted(
        i for i in centers_mm
        if i >= first_zone_marker_id and i not in ids_utilises
    )

    return PlateauLayout(zones, unpaired_ids, reference, product_size_mm)


class PlateauReference:
    """Le repère du plateau tel qu'il a pu être établi sur une photo — et sa qualité.

    Transporte la matrice d'homographie ET de quoi renseigner la barre de statut.
    Les deux voyagent ensemble volontairement : l'opérateur doit pouvoir savoir, en
    regardant l'écran, si le logiciel travaille en mode précis ou dégradé. Une
    matrice seule ne le dit pas, et c'est exactement l'information qui manquait
    avant le lot C2bis.
    """

    def __init__(
        self,
        homography: np.ndarray,
        marker_ids: list,
        exact: bool,
        check_error_mm=None,
    ) -> None:
        # Matrice 3×3 pixel → mm, utilisable telle quelle par pixel_to_mm/warp_*
        self.homography = homography
        # IDs des marqueurs de plateau (0-3) réellement vus et utilisés
        self.marker_ids = list(marker_ids)
        # True = 4 marqueurs, vraie correction de perspective (compute_homography).
        # False = 2 ou 3 marqueurs, similitude approchée (compute_homography_approx).
        self.exact = exact
        # Écart du marqueur de contrôle, en mm, ou None s'il n'était pas visible
        self.check_error_mm = check_error_mm

    @property
    def origin_extrapolated(self) -> bool:
        """L'origine du repère est-elle DÉDUITE plutôt que vue ?

        L'origine est le centre du marqueur 2. S'il n'est pas dans le champ, sa
        position est extrapolée à partir des marqueurs vus et de la taille du plateau
        (WORK_AREA_*, issue de PLATEAU_SIZE_MM). C'est le mode NOMINAL sur la
        Geeetech, dont la caméra ne cadre que les deux tags du haut : toute erreur sur
        la taille du plateau décale alors la totalité de la dépose. D'où l'action M1
        (mesurer le plateau au mètre) — tant qu'elle n'est pas faite, ce mode repose
        sur une valeur supposée.
        """
        return PLATEAU_ORIGIN_MARKER_ID not in self.marker_ids

    @property
    def check_error_excessive(self) -> bool:
        """Le marqueur de contrôle est-il trop loin de sa position attendue ?"""
        return (
            self.check_error_mm is not None
            and self.check_error_mm > PLATEAU_CHECK_TOLERANCE_MM
        )

    @property
    def status_text(self) -> str:
        """Résumé destiné à la barre de statut de l'IHM, en une ligne.

        Volontairement TERSE. Sur l'écran tactile 800×480, la barre de statut
        partage sa place avec l'image du plateau : chaque caractère de trop est pris
        sur ce que l'opérateur peut voir. Le détail vit dans les manuels, pas ici.
        """
        parties = []

        if self.exact:
            parties.append(f"Repère exact ({len(self.marker_ids)} marqueurs)")
        else:
            parties.append(
                f"⚠ Précision réduite ({len(self.marker_ids)} marqueurs "
                f"{self.marker_ids}, pas de correction de perspective)"
            )

        if self.origin_extrapolated:
            parties.append(
                f"origine extrapolée (marqueur {PLATEAU_ORIGIN_MARKER_ID} hors champ)"
            )

        if self.check_error_mm is not None:
            marque = " ⚠" if self.check_error_excessive else ""
            parties.append(
                f"tag {PLATEAU_CHECK_MARKER_ID} : "
                f"{self.check_error_mm:.1f} mm d'écart{marque}"
            )

        return " · ".join(parties)

    def __repr__(self) -> str:
        mode = "exact" if self.exact else "approché"
        return f"PlateauReference({mode}, marqueurs={self.marker_ids})"


class VisionProcessor:
    """Détection de marqueurs ArUco et calibrage géométrique (Phase 2)."""

    def __init__(
        self,
        aruco_dict_id: str = ARUCO_DICT_ID,
        marker_real_size_mm: float = ARUCO_MARKER_SIZE_MM,
    ) -> None:
        # Vérifier que le nom de dictionnaire passé en config est bien supporté
        if aruco_dict_id not in _ARUCO_DICTS:
            raise ValueError(
                f"Dictionnaire ArUco inconnu : '{aruco_dict_id}'. "
                f"Valeurs acceptées : {list(_ARUCO_DICTS)}"
            )

        # Charger le dictionnaire ArUco — ensemble de motifs binaires que le détecteur reconnaît
        aruco_dict = cv2.aruco.getPredefinedDictionary(_ARUCO_DICTS[aruco_dict_id])

        # Paramètres de détection par défaut — fonctionnent bien pour une webcam USB standard
        aruco_params = cv2.aruco.DetectorParameters()

        # Créer le détecteur ArUco (API OpenCV >= 4.7 — remplace l'ancienne fonction cv2.aruco.detectMarkers)
        self._detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)

        # Taille physique d'un côté du marqueur en mm
        self.marker_real_size_mm: float = marker_real_size_mm

    def detect_markers(self, image: np.ndarray) -> dict:
        """Détecte les marqueurs ArUco dans l'image.

        Retourne un dict {id: corners} où :
        - id    : entier (ex. 0, 1, 2, 3)
        - corners : tableau numpy (4, 2) des coins du marqueur en pixels (x, y)

        Retourne un dict vide si aucun marqueur n'est trouvé.
        """
        # Lancer la détection — OpenCV retourne :
        #   corners : liste de tableaux de forme (1, 4, 2)
        #   ids     : tableau de forme (N, 1), ou None si rien n'est détecté
        corners, ids, _ = self._detector.detectMarkers(image)

        result = {}

        # ids vaut None quand aucun marqueur n'est visible dans l'image
        if ids is not None:
            for i, marker_id in enumerate(ids.flatten()):
                # corners[i] a la forme (1, 4, 2) — on retire la première dimension avec [0]
                # pour obtenir (4, 2) : les 4 coins dans l'ordre haut-gauche, haut-droit,
                # bas-droit, bas-gauche (sens horaire, convention OpenCV)
                result[int(marker_id)] = corners[i][0]

        return result

    def compute_homography(self, detected_markers: dict) -> np.ndarray:
        """Calcule la matrice d'homographie H (3×3) à partir des 4 marqueurs détectés.

        H mappe les coordonnées pixel de l'image source vers les coordonnées réelles en mm.
        Les 4 marqueurs IDs 0, 1, 2, 3 doivent être présents.

        Convention de placement des marqueurs dans la zone de travail
        (lot C2bis — voir _plateau_corner_positions_mm, qui est la seule table) :
            ID 2 → coin bas-gauche   (  0 mm,            0 mm              )  ← origine
            ID 1 → coin bas-droit    (  WORK_AREA_WIDTH, 0 mm              )
            ID 0 → coin haut-droit   (  WORK_AREA_WIDTH, WORK_AREA_HEIGHT  )
            ID 3 → coin haut-gauche  (  0 mm,            WORK_AREA_HEIGHT  )

        Cette méthode lit la table et ne l'interprète pas : c'est pour cela que le
        changement de repère du lot C2bis ne l'a pas modifiée, seulement son docstring.
        """
        ids_requis = {0, 1, 2, 3}
        ids_manquants = ids_requis - set(detected_markers.keys())
        if ids_manquants:
            raise ValueError(
                f"Impossible de calculer l'homographie — marqueurs manquants : {ids_manquants}"
            )

        # Centres des 4 marqueurs dans l'image (moyenne des 4 coins de chaque marqueur)
        # mean(axis=0) sur un tableau (4, 2) retourne le point central (x_moy, y_moy)
        src_pts = np.array([
            detected_markers[0].mean(axis=0),  # centre du marqueur 0 en pixels
            detected_markers[1].mean(axis=0),  # centre du marqueur 1 en pixels
            detected_markers[2].mean(axis=0),  # centre du marqueur 2 en pixels
            detected_markers[3].mean(axis=0),  # centre du marqueur 3 en pixels
        ], dtype=np.float32)

        # Positions réelles des 4 marqueurs dans la zone de travail (en mm)
        # Repère plateau : origine (0,0) au marqueur 2 (bas-gauche de l'image)
        #   X croît vers la droite (vers ID 1, bas-droit)
        #   Y croît vers le HAUT  (vers ID 3, haut-gauche) — à l'inverse des lignes
        #   d'une image, d'où le retournement explicite dans les trois warp_*
        # X et Y vont désormais tous deux dans le même sens que les axes machine, ce
        # qui supprime l'inversion de signe qui vivait dans gui/screen_run.py.
        corners = _plateau_corner_positions_mm()
        dst_pts = np.array([corners[0], corners[1], corners[2], corners[3]], dtype=np.float32)

        # getPerspectiveTransform calcule H exactement à partir de 4 paires de points
        # (contrairement à findHomography qui utilise RANSAC pour plus de robustesse,
        # mais ici 4 points bien définis suffisent)
        return cv2.getPerspectiveTransform(src_pts, dst_pts)

    def compute_homography_approx(self, detected_markers: dict) -> np.ndarray:
        """Calcule une homographie APPROXIMATIVE à partir de 2 ou 3 marqueurs du
        plateau seulement (parmi les IDs 0-3), au lieu des 4 exigés par
        compute_homography().

        Pourquoi cette méthode existe :
          Sur la Geeetech (PoC), la caméra est trop proche et trop peu mobile pour
          voir les 4 coins du plateau en même temps dès que celui-ci fait toute la
          taille du bâti (contrainte matérielle constatée le 2026-07-30, pas un bug
          logiciel). Seuls 2 marqueurs adjacents (ex. les 2 du haut) restent visibles.

        Différence avec compute_homography() — à bien comprendre avant d'utiliser
        cette méthode :
          compute_homography() calcule une vraie transformation PERSPECTIVE (4 points,
          8 degrés de liberté) : elle corrige le fait que la caméra n'est jamais
          parfaitement à la verticale (effet "trapèze"). Avec seulement 2 points, cette
          correction est impossible à déterminer — cette méthode calcule à la place une
          similitude (rotation + échelle uniforme + translation, 4 degrés de liberté,
          cv2.estimateAffinePartial2D) qui suppose une caméra quasi verticale. Résultat :
          moins précis que compute_homography(), avec une erreur qui grandit avec
          l'inclinaison réelle de la caméra. À réserver au PoC Geeetech ; la CNC cible,
          qui a la place pour reculer la caméra, doit utiliser compute_homography().

        Paramètres :
            detected_markers : dict {id: corners} — seuls les IDs 0-3 présents comptent,
                                les autres (ex. marqueurs de zone 4/5) sont ignorés.

        Retourne une matrice 3×3 (compatible pixel_to_mm/warp_image comme
        compute_homography(), mais sans terme de perspective).

        Lève ValueError si moins de 2 marqueurs parmi 0-3 sont présents.
        """
        corners = _plateau_corner_positions_mm()
        ids_disponibles = sorted(set(detected_markers.keys()) & corners.keys())

        if len(ids_disponibles) < 2:
            raise ValueError(
                f"Impossible d'approximer l'homographie — au moins 2 marqueurs du "
                f"plateau (IDs {sorted(corners.keys())}) sont nécessaires, "
                f"{len(ids_disponibles)} trouvé(s)"
            )

        src_pts = np.array(
            [detected_markers[i].mean(axis=0) for i in ids_disponibles], dtype=np.float32
        )
        dst_pts = np.array([corners[i] for i in ids_disponibles], dtype=np.float32)

        # estimateAffinePartial2D résout exactement avec 2 points (4 inconnues : rotation,
        # échelle, tx, ty ↔ 4 équations) ; avec 3 points, ajuste au mieux (moindres carrés)
        matrix_2x3, _inliers = cv2.estimateAffinePartial2D(src_pts, dst_pts)
        if matrix_2x3 is None:
            raise ValueError(
                "estimateAffinePartial2D n'a pas pu résoudre de transformation — "
                "vérifier que les marqueurs détectés ne sont pas confondus/alignés"
            )

        # Compléter en 3×3 (ligne [0, 0, 1]) pour rester compatible avec
        # cv2.perspectiveTransform (pixel_to_mm) et cv2.warpPerspective (warp_image),
        # qui acceptent une matrice purement affine sans terme de perspective
        return np.vstack([matrix_2x3, [0.0, 0.0, 1.0]])

    def compute_plateau_reference(self, detected_markers: dict) -> "PlateauReference":
        """Établit le repère du plateau à partir des marqueurs vus, et dit COMMENT.

        Pourquoi cette méthode existe (lot C2bis)
        ------------------------------------------
        Le choix « 4 tags → compute_homography, 2 ou 3 tags → compute_homography_approx »
        était écrit DEUX fois, dans screen_plateau.py et screen_zone.py. Deux copies
        d'une même règle finissent toujours par diverger, et c'est celle qu'on ne
        relit pas qui reste juste. Elle est donc regroupée ici — et comme l'appelant a
        besoin de savoir dans quel mode il travaille pour en informer l'opérateur, la
        méthode ne retourne pas qu'une matrice mais un PlateauReference complet.

        Lève ValueError si moins de 2 marqueurs de plateau sont visibles : sans deux
        points, aucune conversion pixels → mm n'est possible.
        """
        positions = _plateau_corner_positions_mm()
        ids_vus = sorted(set(detected_markers) & positions.keys())

        if len(ids_vus) >= 4:
            homography = self.compute_homography(detected_markers)
            exact = True
        else:
            # Lève elle-même si moins de 2 marqueurs — message déjà explicite
            homography = self.compute_homography_approx(detected_markers)
            exact = False

        return PlateauReference(
            homography=homography,
            marker_ids=ids_vus,
            exact=exact,
            check_error_mm=self._ecart_marqueur_de_controle(detected_markers),
        )

    @staticmethod
    def _ecart_marqueur_de_controle(detected_markers: dict):
        """Écart, en mm, entre la position VUE du marqueur 0 et sa position ATTENDUE.

        Le repère est défini par trois marqueurs — 2 (origine), 1 (axe X) et 3
        (axe Y). Le quatrième, le 0, est donc redondant : c'est ce qui permet de s'en
        servir comme témoin. On ajuste une SIMILITUDE (rotation + échelle + translation)
        sur les trois marqueurs qui définissent le repère, on y projette le centre vu
        du marqueur 0, et on le compare au coin (largeur, hauteur) où il devrait tomber.

        Ce que l'écart mesure, et ce qu'il ne mesure pas
        ------------------------------------------------
        Sur un plateau plan photographié par une caméra parfaitement perpendiculaire
        avec un objectif sans distorsion, l'écart serait nul. Il agrège donc, sans
        savoir les distinguer : l'inclinaison de la caméra, la distorsion de
        l'objectif (~10 % encore non corrigés — action M5), une déformation du
        plateau, et un tag décollé ou mal collé. C'est un **indicateur de qualité du
        montage optique**, à remonter à l'opérateur, pas une mesure d'incertitude.

        On ne peut PAS obtenir cet écart à partir de la matrice de compute_homography() :
        avec exactement 4 points, getPerspectiveTransform ajuste sans résidu, et l'écart
        y serait nul par construction quelle que soit la réalité du plateau.

        Retourne None si les 4 marqueurs ne sont pas tous visibles — c'est le cas
        nominal sur la Geeetech, où seuls 2 tags sont cadrés.
        """
        positions = _plateau_corner_positions_mm()
        ids_reference = [2, 1, 3]   # origine, axe X, axe Y

        requis = set(ids_reference) | {PLATEAU_CHECK_MARKER_ID}
        if not requis.issubset(detected_markers.keys()):
            return None

        src = np.array(
            [detected_markers[i].mean(axis=0) for i in ids_reference], dtype=np.float32
        )
        dst = np.array([positions[i] for i in ids_reference], dtype=np.float32)

        similitude, _inliers = cv2.estimateAffinePartial2D(src, dst)
        if similitude is None:
            return None

        # Projeter le centre vu du marqueur de contrôle dans ce repère nominal
        centre_px = detected_markers[PLATEAU_CHECK_MARKER_ID].mean(axis=0)
        point = np.array([[centre_px]], dtype=np.float32)
        vu_x, vu_y = cv2.transform(point, similitude)[0][0]

        attendu_x, attendu_y = positions[PLATEAU_CHECK_MARKER_ID]
        return float(math.hypot(vu_x - attendu_x, vu_y - attendu_y))

    def warp_image(
        self, image: np.ndarray, homography: np.ndarray, output_size: tuple
    ) -> np.ndarray:
        """Redresse l'image en vue du dessus, à l'échelle de la zone de travail.

        homography  : matrice H pixel→mm issue de compute_homography()
        output_size : (largeur_px, hauteur_px) de l'image de sortie
                      ex. (300, 200) pour 2 px/mm sur une zone 150×100 mm

        L'image retournée représente la zone de travail vue du dessus,
        où chaque pixel correspond à output_size / WORK_AREA mm.

        ⚠️ L'axe Y est RETOURNÉ ici (lot C2bis) : voir le bloc « miroir vertical »
        du docstring de _plateau_corner_positions_mm(). Le repère plateau monte, les
        lignes d'une image descendent — sans ce retournement l'opérateur verrait le
        plateau à l'envers. test_warp_image_orientation_non_miroir le garde.
        """
        output_width, output_height = output_size

        # Facteurs d'échelle : convertissent mm → pixels de l'image de sortie
        scale_x = output_width  / WORK_AREA_WIDTH_MM
        scale_y = output_height / WORK_AREA_HEIGHT_MM

        # Matrice d'échelle 3×3 pour passer de l'espace mm vers les pixels de sortie.
        # La 2e ligne se lit : y_pixel = (WORK_AREA_HEIGHT_MM − y_mm) × scale_y.
        # Le terme constant vaut exactement output_height — c'est-à-dire que
        # y_mm = 0 (le BAS du plateau) tombe sur la dernière ligne de l'image.
        scale_matrix = np.array([
            [scale_x,  0,        0],
            [0,       -scale_y,  scale_y * WORK_AREA_HEIGHT_MM],
            [0,        0,        1],
        ], dtype=np.float64)

        # H_warp = scale_matrix @ H mappe pixels source → pixels de sortie
        # warpPerspective utilise H_warp^{-1} pour retrouver, pour chaque pixel
        # de sortie, le pixel correspondant dans l'image source
        H_warp = scale_matrix @ homography

        return cv2.warpPerspective(image, H_warp, output_size)

    def warp_region(
        self,
        image: np.ndarray,
        homography: np.ndarray,
        origin_mm: tuple,
        px_per_mm: float,
        output_size: tuple,
    ) -> np.ndarray:
        """Redresse UNIQUEMENT une sous-région de l'image (ex. la zone de dépose),
        au lieu de tout le plateau (WORK_AREA) comme warp_image().

        Pourquoi cette méthode existe (et pas juste warp_image() + découpage) :
          warp_image() dimensionne toujours son image de sortie sur tout le
          WORK_AREA connu. Si la caméra n'a photographié qu'une partie du
          plateau (cas du repli 2-3 marqueurs, voir compute_homography_approx),
          les zones du canevas de sortie qui ne correspondent à aucun pixel de
          la photo source sont remplies en NOIR par warpPerspective. Si la
          sous-région qu'on veut afficher (la zone de dépose) tombe dans cette
          zone jamais photographiée, découper après-coup donne une image
          entièrement noire (bug constaté le 2026-07-30 avec le repli
          Geeetech). warp_region() redresse directement la sous-région voulue
          — il ne demande donc que des pixels réellement présents dans la
          photo, tant que la zone elle-même y est visible.

        Paramètres :
            origin_mm  : (x_min, y_min) du coin de la sous-région, dans le
                         repère du plateau (ex. le retour de deposit_zone_bounds_mm).
                         Depuis le lot C2bis, l'axe Y montant fait de ce coin le
                         BAS-GAUCHE de la sous-région, plus son haut-gauche.
            px_per_mm  : échelle de sortie, identique en X et en Y
            output_size: (largeur_px, hauteur_px) de l'image de sortie

        ⚠️ L'axe Y est RETOURNÉ ici, comme dans warp_image() et warp_zone() — même
        raison, voir _plateau_corner_positions_mm().
        """
        x0_mm, y0_mm = origin_mm
        # La hauteur de sortie sert au retournement : elle dit où retombe le bas de
        # la sous-région. C'est elle, et pas WORK_AREA, qui borne l'image ici.
        hauteur_px = output_size[1]

        # mm(plateau) → pixel(sous-région) : translater à l'origine de la zone
        # puis mettre à l'échelle — pas besoin de connaître WORK_AREA ici.
        # La 2e ligne se lit : y_pixel = hauteur_px − (y_mm − y0_mm) × px_per_mm,
        # donc y_mm = y0_mm (le bas de la sous-région) tombe sur la dernière ligne.
        zone_matrix = np.array([
            [px_per_mm,  0,          -x0_mm * px_per_mm            ],
            [0,         -px_per_mm,   y0_mm * px_per_mm + hauteur_px],
            [0,          0,           1                            ],
        ], dtype=np.float64)

        # H_zone = zone_matrix @ homography mappe pixels source → pixels de la sous-région
        H_zone = zone_matrix @ homography

        return cv2.warpPerspective(image, H_zone, output_size)

    def warp_zone(
        self,
        image: np.ndarray,
        zone: "DepositZone",
        homography: np.ndarray,
        px_per_mm: float,
    ) -> np.ndarray:
        """Redresse une zone de dépose, y compris si elle est vissée de travers.

        Différence avec warp_region() : celle-ci ne sait extraire qu'un rectangle ALIGNÉ
        sur les axes du plateau. Or une zone peut être montée avec quelques degrés
        d'écart — c'est tout l'objet du calcul de rotation. Sans redressement, l'opérateur
        tracerait ses cordons sur une image penchée, et le repère relatif de la zone ne
        correspondrait pas à ce qu'il voit.

        L'image retournée montre la zone bien droite, à l'échelle px_per_mm. Son
        pixel (0, 0) — coin haut-gauche de l'IMAGE — correspond au coin haut-gauche
        de la zone tel que l'opérateur le voit, c'est-à-dire au point (0, hauteur) du
        repère de la zone, dont l'origine est le coin BAS-gauche depuis le lot C2bis.
        Un clic à (px, py) vaut donc :

            x_mm = px / px_per_mm
            y_mm = (hauteur_px − py) / px_per_mm

        soit toujours une simple division, sans repasser par l'homographie — c'est
        cette conversion qu'applique gui/screen_cordons.py::_position_mm.

        Le transport se compose de trois étapes, appliquées de droite à gauche :
            pixel source → mm plateau      : l'homographie
            mm plateau   → mm zone         : translation vers le coin, puis rotation -θ
            mm zone      → pixel de sortie : mise à l'échelle px_per_mm ET retournement
                                             de Y (3e warp_* concerné, même raison)
        """
        theta = math.radians(zone.rotation_deg)
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        origine_x, origine_y = zone.origin_mm

        # mm plateau → mm zone. C'est la forme matricielle de DepositZone.to_zone_mm() :
        # translation de -origine, puis rotation de -θ. Les deux sont fusionnées ici en
        # une seule matrice, la translation étant déjà multipliée par la rotation.
        vers_zone = np.array([
            [cos_t,  sin_t, -cos_t * origine_x - sin_t * origine_y],
            [-sin_t, cos_t,  sin_t * origine_x - cos_t * origine_y],
            [0.0,    0.0,    1.0],
        ], dtype=np.float64)

        largeur_mm, hauteur_mm = zone.size_mm

        # mm zone → pixel de sortie. La 2e ligne se lit :
        # y_pixel = (hauteur_mm − y_mm) × px_per_mm — le retournement de Y du lot
        # C2bis, ici avec la hauteur de la ZONE et non celle du plateau.
        echelle = np.array([
            [px_per_mm, 0.0,        0.0],
            [0.0,      -px_per_mm,  hauteur_mm * px_per_mm],
            [0.0,       0.0,        1.0],
        ], dtype=np.float64)

        taille = (max(1, int(round(largeur_mm * px_per_mm))),
                  max(1, int(round(hauteur_mm * px_per_mm))))

        return cv2.warpPerspective(image, echelle @ vers_zone @ homography, taille)

    def deposit_zone_bounds_mm(
        self,
        detected_markers: dict,
        homography: np.ndarray,
        id_a: int = 4,
        id_b: int = 5,
    ) -> tuple[float, float, float, float]:
        """Calcule les bornes en mm de la zone de dépose, délimitée par deux
        marqueurs ArUco placés à ses coins opposés (en diagonale).

        La zone est supposée alignée avec les axes du plateau (pas de rotation) :
        les deux marqueurs suffisent donc à définir un rectangle simple, sans
        recalculer une seconde homographie dédiée à la zone.

        Retourne (x_min, y_min, x_max, y_max) en mm, dans le repère du plateau
        (celui de compute_homography — origine au marqueur 2, Y montant). Avec l'axe
        Y montant, (x_min, y_min) est le coin BAS-gauche de la zone : c'est bien ce
        qu'attend warp_region() comme origin_mm.

        Lève ValueError si l'un des deux marqueurs est absent.
        """
        ids_requis = {id_a, id_b}
        ids_manquants = ids_requis - set(detected_markers.keys())
        if ids_manquants:
            raise ValueError(
                f"Impossible de délimiter la zone de dépose — marqueurs manquants : {ids_manquants}"
            )

        # Centre de chaque marqueur en pixels, converti en mm via l'homographie du plateau
        cx_a, cy_a = detected_markers[id_a].mean(axis=0)
        x_a, y_a = self.pixel_to_mm(cx_a, cy_a, homography)

        cx_b, cy_b = detected_markers[id_b].mean(axis=0)
        x_b, y_b = self.pixel_to_mm(cx_b, cy_b, homography)

        # min/max plutôt que "a puis b" : peu importe lequel des deux marqueurs
        # est physiquement en haut-gauche ou bas-droit de la zone
        return (min(x_a, x_b), min(y_a, y_b), max(x_a, x_b), max(y_a, y_b))

    def mm_to_pixels(self, points_mm: list, homography: np.ndarray) -> list:
        """Conversion INVERSE de pixel_to_mm : millimètres → pixels de l'image source.

        Sert à dessiner sur la photo des éléments dont on ne connaît que la position en
        millimètres — le contour d'une zone de dépose, un cordon reprojeté, une étiquette.

        Prend une LISTE de points plutôt qu'un point isolé, car l'inversion de la matrice
        d'homographie est le calcul coûteux : la faire une fois pour les 4 coins d'une
        zone, plutôt que 4 fois de suite, évite un gaspillage inutile à chaque rafraîchissement.
        """
        # np.linalg.inv lève LinAlgError sur une matrice singulière — ce qui n'arrive pas
        # avec une homographie valide, mais laissons l'erreur remonter plutôt que de la
        # masquer : une homographie dégénérée est un problème à corriger, pas à ignorer
        inverse = np.linalg.inv(homography)

        # perspectiveTransform attend un tableau de forme (1, N, 2)
        pts = np.array([points_mm], dtype=np.float32)
        pts_px = cv2.perspectiveTransform(pts, inverse)

        return [(float(x), float(y)) for x, y in pts_px[0]]

    def mm_to_pixel(
        self, x_mm: float, y_mm: float, homography: np.ndarray
    ) -> tuple[float, float]:
        """Version point unique de mm_to_pixels — pratique quand il n'y en a qu'un."""
        return self.mm_to_pixels([(x_mm, y_mm)], homography)[0]

    def detect_deposit_zones(
        self,
        detected_markers: dict,
        homography: np.ndarray,
        first_zone_marker_id: int = FIRST_ZONE_MARKER_ID,
        diagonal_tolerance_mm: float = ZONE_DIAGONAL_TOLERANCE_MM,
        max_rotation_deg: float = ZONE_MAX_ROTATION_DEG,
    ) -> PlateauLayout:
        """Reconstruit toutes les zones de dépose visibles sur le plateau.

        Cette méthode ne fait que le passage pixels → mm ; toute la géométrie est
        dans detect_deposit_zones_mm(), volontairement laissée en fonction pure pour
        rester testable sans caméra ni homographie (voir son docstring pour le
        détail de l'algorithme et ses limites).
        """
        # Centre de chaque marqueur détecté, converti dans le repère mm du plateau
        centers_mm = {}
        for marker_id, corners in detected_markers.items():
            cx, cy = corners.mean(axis=0)
            centers_mm[marker_id] = self.pixel_to_mm(cx, cy, homography)

        return detect_deposit_zones_mm(
            centers_mm,
            first_zone_marker_id=first_zone_marker_id,
            diagonal_tolerance_mm=diagonal_tolerance_mm,
            max_rotation_deg=max_rotation_deg,
        )

    def pixel_to_mm(
        self, px: float, py: float, homography: np.ndarray
    ) -> tuple[float, float]:
        """Convertit des coordonnées pixel (image source) en coordonnées réelles (mm).

        Utilise la matrice H issue de compute_homography() qui mappe pixel→mm.
        Retourne (x_mm, y_mm) dans le repère du plateau — origine au marqueur 2
        (bas-gauche), X vers la droite, Y vers le haut.
        """
        # perspectiveTransform attend un tableau de forme (1, N, 2)
        # on enveloppe le point unique dans les deux niveaux de tableau requis
        pt = np.array([[[px, py]]], dtype=np.float32)
        pt_mm = cv2.perspectiveTransform(pt, homography)

        # pt_mm a la forme (1, 1, 2) — on extrait les deux coordonnées
        return float(pt_mm[0][0][0]), float(pt_mm[0][0][1])
