# Modèle de données d'une préparation de plateau, et sa persistance en JSON.
#
# Vocabulaire du projet :
#   - PLATEAU      : le support de la machine, repéré par 4 marqueurs ArUco (IDs 0-3)
#   - ZONE         : l'emplacement d'un produit sur le plateau, vissé à demeure et
#                    repéré par 2 marqueurs (voir modules/vision.py)
#   - CORDON       : une polyline le long de laquelle on dépose la pâte thermique
#   - PRÉPARATION  : l'ensemble « produit + zones + cordons + paramètres », c'est
#                    exactement ce qu'on enregistre dans un fichier JSON
#
# Choix structurant : les cordons appartiennent à la PRÉPARATION, pas à une zone.
# Toutes les zones accueillant le même produit, les cordons sont tracés une seule fois
# et rejoués dans le repère de chaque zone. Les dupliquer par zone créerait autant de
# copies à maintenir cohérentes, pour aucune information supplémentaire.

import json
import math
import os
import re
import tempfile
from datetime import datetime

from modules.config import (
    PREPARATIONS_DIR,
    DEFAULT_TRAVEL_SPEED_MM_MIN,
    DEFAULT_EXTRUSION_SPEED_MM_MIN,
    WORK_AREA_HEIGHT_MM,
)
from modules.vision import (
    DepositZone,
    ZONE_DIAGONAL_TOLERANCE_MM,
    ZONE_MAX_ROTATION_DEG,
)


# Version du format de fichier. À incrémenter dès qu'un changement rend les anciens
# fichiers illisibles — sans ce numéro, un fichier écrit par une version antérieure du
# logiciel serait relu de travers, en silence, avec des cordons faux à la clé.
#
# Historique :
#   1 → format initial (lot B, v0.3.0). Repère plateau ET repère de zone à Y DESCENDANT,
#       origine du plateau au marqueur 3 (haut-gauche), origine de zone au coin
#       haut-gauche.
#   2 → lot C2bis. Les deux repères passent à Y MONTANT : origine du plateau au
#       marqueur 2 (bas-gauche), origine de zone au coin bas-gauche. Toutes les
#       ordonnées enregistrées changent donc de sens.
FORMAT_VERSION = 2

# Dernière version dont ce logiciel sait convertir les fichiers au chargement.
# Sans conversion, un fichier v1 serait relu SILENCIEUSEMENT à l'envers : le contrôle
# de version n'interdisait que les fichiers plus RÉCENTS que le logiciel, jamais les
# plus anciens. Sur des coordonnées de dépose, c'est la buse qui part au mauvais endroit.
OLDEST_CONVERTIBLE_VERSION = 1

# Suffixe des fichiers de sauvegarde automatique. Un fichier portant ce suffixe signale
# un travail interrompu (plantage, coupure) : l'application propose de le reprendre.
AUTOSAVE_SUFFIX = ".autosave.json"

# Caractères interdits dans un nom de fichier sous Windows comme sous Linux. Le nom du
# produit est saisi librement par l'opérateur et sert de nom de fichier : sans ce
# filtrage, une référence du type "REF 12/34" créerait un sous-dossier fantôme, ou
# ferait échouer l'enregistrement.
_CARACTERES_INTERDITS = '<>:"/\\|?*'


def _safe_filename(nom: str) -> str:
    """Transforme un nom de produit saisi par l'opérateur en nom de fichier valide.

    Les caractères interdits sont remplacés par un tiret bas, et les espaces de début
    et de fin supprimés. Le nom d'origine reste conservé tel quel DANS le fichier
    (champ product_name) : seul le nom du fichier est assaini, pour que l'affichage à
    l'écran garde la référence exacte du produit.
    """
    nettoye = "".join("_" if c in _CARACTERES_INTERDITS else c for c in nom).strip()

    # Un nom vide donnerait un fichier caché ou un chemin invalide selon le système
    return nettoye or "sans_nom"


class Cordon:
    """Une polyline de dépose, en mm RELATIFS à la zone.

    Coordonnées relatives et pas absolues : c'est ce qui permet d'appliquer le même
    cordon à toutes les zones du plateau (voir DepositZone.to_plateau_mm).
    """

    def __init__(self, points_mm: list) -> None:
        # Liste de (x_mm, y_mm) dans le repère de la zone — origine au coin BAS-gauche,
        # Y vers le haut depuis le lot C2bis (format de fichier version 2)
        self.points_mm = [tuple(p) for p in points_mm]

    @property
    def length_mm(self) -> float:
        """Longueur totale du cordon, somme des longueurs de ses segments.

        Sert au rapport PDF (longueur déposée) et à l'estimation du temps de dépose.
        Un cordon de moins de 2 points a une longueur nulle : il n'a aucun segment.
        """
        return sum(
            math.dist(self.points_mm[i - 1], self.points_mm[i])
            for i in range(1, len(self.points_mm))
        )

    @property
    def is_valid(self) -> bool:
        """Un cordon exploitable a au moins 2 points, donc au moins un segment."""
        return len(self.points_mm) >= 2

    def to_dict(self) -> dict:
        """Représentation sérialisable en JSON.

        Les points sont arrondis au centième de mm : c'est très en deçà de la précision
        réelle de la vision (de l'ordre du mm), et ça évite des fichiers illisibles
        remplis de décimales flottantes sans signification.
        """
        return {
            "points_mm": [[round(x, 2), round(y, 2)] for x, y in self.points_mm]
        }

    @staticmethod
    def from_dict(data: dict) -> "Cordon":
        return Cordon([tuple(p) for p in data["points_mm"]])

    def __repr__(self) -> str:
        return f"Cordon({len(self.points_mm)} points, {self.length_mm:.1f} mm)"


class Settings:
    """Paramètres globaux d'une préparation, modifiables dans la fenêtre de paramètres.

    La quantité de pâte déposée n'est pas réglée directement : elle résulte du RAPPORT
    entre la vitesse d'extrusion et la vitesse de déplacement. À vitesse d'extrusion
    constante, ralentir la buse épaissit le cordon.
    """

    def __init__(
        self,
        travel_speed_mm_min: float = DEFAULT_TRAVEL_SPEED_MM_MIN,
        extrusion_speed_mm_min: float = DEFAULT_EXTRUSION_SPEED_MM_MIN,
        zone_diagonal_tolerance_mm: float = ZONE_DIAGONAL_TOLERANCE_MM,
        zone_max_rotation_deg: float = ZONE_MAX_ROTATION_DEG,
    ) -> None:
        # Vitesse de déplacement de la buse pendant la dépose (mm/min)
        self.travel_speed_mm_min = float(travel_speed_mm_min)
        # Vitesse d'avance du piston de la seringue (mm/min sur l'axe E)
        self.extrusion_speed_mm_min = float(extrusion_speed_mm_min)
        # Seuils de contrôle du montage du plateau. Enregistrés avec la préparation
        # plutôt que figés dans le code : ils qualifient la qualité de montage de CE
        # plateau-ci, qui peut différer d'une machine à l'autre.
        self.zone_diagonal_tolerance_mm = float(zone_diagonal_tolerance_mm)
        self.zone_max_rotation_deg = float(zone_max_rotation_deg)

    def to_dict(self) -> dict:
        return {
            "travel_speed_mm_min": self.travel_speed_mm_min,
            "extrusion_speed_mm_min": self.extrusion_speed_mm_min,
            "zone_diagonal_tolerance_mm": self.zone_diagonal_tolerance_mm,
            "zone_max_rotation_deg": self.zone_max_rotation_deg,
        }

    @staticmethod
    def from_dict(data: dict) -> "Settings":
        """Reconstruit les paramètres, en tolérant les clés absentes.

        Une clé manquante reprend sa valeur par défaut : un fichier enregistré par une
        version antérieure du logiciel, avant l'ajout d'un paramètre, reste lisible.
        """
        defauts = Settings()
        return Settings(
            travel_speed_mm_min=data.get(
                "travel_speed_mm_min", defauts.travel_speed_mm_min),
            extrusion_speed_mm_min=data.get(
                "extrusion_speed_mm_min", defauts.extrusion_speed_mm_min),
            zone_diagonal_tolerance_mm=data.get(
                "zone_diagonal_tolerance_mm", defauts.zone_diagonal_tolerance_mm),
            zone_max_rotation_deg=data.get(
                "zone_max_rotation_deg", defauts.zone_max_rotation_deg),
        )


def _zone_to_dict(zone: DepositZone) -> dict:
    """Sérialise une zone détectée.

    On enregistre la géométrie reconstruite (coins, rotation, format) et pas seulement
    les IDs des marqueurs : cela permet de rouvrir un fichier et d'afficher le plateau
    sans reprendre de photo.

    ⚠️ Les positions sont en mm ABSOLUS dans le repère du plateau (origine au marqueur
    2, Y montant), donc dépendantes de la position de la caméra au moment de la
    détection. Si la caméra a bougé depuis, ces coordonnées ne correspondent plus
    exactement — d'où l'intérêt d'avoir gardé les cordons en coordonnées RELATIVES,
    qui, elles, restent valides.
    """
    return {
        "id_top_left": zone.id_top_left,
        "id_bottom_right": zone.id_bottom_right,
        "corners_mm": [[round(x, 2), round(y, 2)] for x, y in zone.corners_mm],
        "rotation_deg": round(zone.rotation_deg, 3),
        "diagonal_mm": round(zone.diagonal_mm, 2),
        "size_mm": [round(zone.size_mm[0], 2), round(zone.size_mm[1], 2)],
        "anomalies": list(zone.anomalies),
    }


def _zone_from_dict(data: dict) -> DepositZone:
    """Reconstruit une zone à partir de sa forme sérialisée."""
    return DepositZone(
        id_top_left=data["id_top_left"],
        id_bottom_right=data["id_bottom_right"],
        corners_mm=tuple(tuple(c) for c in data["corners_mm"]),
        rotation_deg=data["rotation_deg"],
        diagonal_mm=data["diagonal_mm"],
        size_mm=tuple(data["size_mm"]),
        anomalies=list(data.get("anomalies", [])),
    )


def _hauteur_zone_de_reference(preparation) -> float:
    """Hauteur en mm de la zone dans le repère de laquelle les cordons sont exprimés.

    La zone de référence d'abord, puisque c'est elle qui définit le repère des
    cordons ; à défaut la première zone du fichier, toutes les zones portant le même
    produit et ayant donc la même hauteur. Retourne None si aucune zone n'a de
    hauteur exploitable.
    """
    candidates = []
    if preparation.reference_zone is not None:
        candidates.append(preparation.reference_zone)
    candidates.extend(preparation.zones)

    for zone in candidates:
        if zone.size_mm and zone.size_mm[1] > 0:
            return float(zone.size_mm[1])
    return None


def _convertir_v1_vers_v2(preparation) -> None:
    """Retourne l'axe Y d'une préparation enregistrée avant le lot C2bis, EN PLACE.

    Le lot C2bis retourne DEUX repères d'un coup, et un fichier v1 contient des
    coordonnées dans les deux — les convertir à moitié serait pire que ne rien
    convertir, puisque le fichier deviendrait incohérent avec lui-même :

      - repère du PLATEAU (les coins des zones) : y_v2 = WORK_AREA_HEIGHT_MM − y_v1
      - repère de la ZONE (les points des cordons) : y_v2 = hauteur_zone − y_v1

    La rotation des zones change de signe par la même occasion : mesurée dans un
    repère retourné, un angle change de sens (v1 comptait positivement le sens
    horaire à l'écran, v2 compte le sens trigonométrique).

    Ce qui NE change pas : l'ordre des coins reste (haut-gauche, haut-droit,
    bas-droit, bas-gauche). Ce sont des positions VUES par l'opérateur, et retourner
    une convention de coordonnées ne déplace rien physiquement — seule leur valeur y
    change. Les longueurs (size_mm, diagonal_mm) ne changent pas non plus.

    ⚠️ Limite assumée : la hauteur du plateau utilisée est WORK_AREA_HEIGHT_MM, la
    valeur configurée AUJOURD'HUI, alors que le fichier a pu être écrit avec une autre
    (PLATEAU_SIZE_MM est devenu configurable au même lot). Un décalage constant sur
    les coins de zone en découlerait. C'est sans conséquence en pratique : ces
    coordonnées absolues dépendent déjà de la position de la caméra au moment de la
    photo, et sont redétectées à la capture suivante. Les cordons, eux, sont convertis
    avec la hauteur de LEUR zone, qui est dans le fichier — donc exactement.
    """
    for zone in preparation.zones:
        zone.corners_mm = tuple(
            (x, WORK_AREA_HEIGHT_MM - y) for x, y in zone.corners_mm
        )
        zone.rotation_deg = -zone.rotation_deg

    if not preparation.cordons:
        return

    hauteur_zone = _hauteur_zone_de_reference(preparation)
    if hauteur_zone is None:
        # Refuser franchement plutôt que de laisser des cordons à l'envers : sans la
        # hauteur de la zone, la conversion est impossible et un tracé non converti
        # enverrait la buse au mauvais endroit, en silence.
        raise ValueError(
            "Fichier de préparation en version 1 impossible à convertir : il contient "
            "des cordons mais aucune zone dont on puisse lire la hauteur. Les "
            "coordonnées des cordons y sont relatives à une zone — sans elle, leur "
            "sens ne peut pas être rétabli."
        )

    for cordon in preparation.cordons:
        cordon.points_mm = [(x, hauteur_zone - y) for x, y in cordon.points_mm]


class Preparation:
    """Le travail complet sur un plateau : produit, zones, cordons et paramètres."""

    def __init__(
        self,
        product_name: str,
        zones: list = None,
        cordons: list = None,
        settings: Settings = None,
        reference_zone_id: int = None,
        created_at: str = None,
        updated_at: str = None,
        converted_from_version: int = None,
    ) -> None:
        # Référence du produit, telle que saisie par l'opérateur. Reste affichée en
        # permanence dans l'IHM pour qu'on sache toujours sur quoi on travaille.
        self.product_name = product_name
        # Zones détectées sur le plateau (objets DepositZone)
        self.zones = zones if zones is not None else []
        # Cordons tracés une fois, applicables à toutes les zones
        self.cordons = cordons if cordons is not None else []
        self.settings = settings if settings is not None else Settings()
        # ID du marqueur haut-gauche de la zone sur laquelle les cordons ont été tracés.
        # Mémorisé pour que le bouton « revenir à la zone choisie » y retourne, plutôt
        # que d'imposer à l'opérateur de la retrouver lui-même.
        self.reference_zone_id = reference_zone_id
        # Horodatages ISO 8601 à la seconde — lisibles tels quels dans le fichier
        maintenant = datetime.now().isoformat(timespec="seconds")
        self.created_at = created_at or maintenant
        self.updated_at = updated_at or maintenant
        # Version d'origine si ce fichier a été converti au chargement, sinon None.
        # Volontairement HORS to_dict() : c'est un fait sur la lecture qu'on vient de
        # faire, pas un attribut de la préparation. L'IHM s'en sert pour prévenir
        # l'opérateur — un cordon qui bouge tout seul sans explication est plus
        # inquiétant qu'un message.
        self.converted_from_version = converted_from_version

    @property
    def conversion_message(self) -> str:
        """Message à afficher si le fichier a été converti, sinon chaîne vide."""
        if self.converted_from_version is None:
            return ""
        return (
            f"Fichier converti du format v{self.converted_from_version} vers "
            f"v{FORMAT_VERSION} : la convention du repère a changé (lot C2bis), les "
            f"ordonnées des cordons et des zones ont été retournées. Vérifier le tracé "
            f"avant de lancer une dépose."
        )

    # ------------------------------------------------------------------ requêtes

    @property
    def reference_zone(self):
        """La zone sur laquelle les cordons ont été tracés, ou None si non définie."""
        for zone in self.zones:
            if zone.id_top_left == self.reference_zone_id:
                return zone
        return None

    @property
    def total_length_mm(self) -> float:
        """Longueur totale de pâte à déposer sur TOUT le plateau.

        Les cordons étant appliqués à chaque zone valide, la longueur totale est celle
        d'une zone multipliée par le nombre de zones exploitables.
        """
        longueur_une_zone = sum(c.length_mm for c in self.cordons)
        return longueur_une_zone * len(self.valid_zones)

    @property
    def valid_zones(self) -> list:
        """Les zones exploitables — les seules sur lesquelles on déposera."""
        return [z for z in self.zones if z.is_valid]

    def cordons_for_zone(self, zone: DepositZone) -> list:
        """Projette les cordons dans le repère du plateau pour une zone donnée.

        C'est l'opération qui matérialise « les cordons définis sur une zone
        s'appliquent à toutes les autres » : les mêmes coordonnées relatives, replacées
        dans le repère de chaque zone (position + rotation propres).

        Retourne une liste de polylines, chacune étant une liste de (x_mm, y_mm) en
        coordonnées plateau — directement exploitables pour l'affichage ou le G-code.
        """
        return [
            [zone.to_plateau_mm(p) for p in cordon.points_mm]
            for cordon in self.cordons
        ]

    # ------------------------------------------------------------------ sérialisation

    def to_dict(self) -> dict:
        """Représentation complète, sérialisable en JSON."""
        return {
            "format_version": FORMAT_VERSION,
            "product_name": self.product_name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "reference_zone_id": self.reference_zone_id,
            "settings": self.settings.to_dict(),
            "zones": [_zone_to_dict(z) for z in self.zones],
            "cordons": [c.to_dict() for c in self.cordons],
        }

    @staticmethod
    def from_dict(data: dict) -> "Preparation":
        """Reconstruit une préparation depuis sa forme sérialisée.

        Lève ValueError si le fichier vient d'une version de format plus récente que
        celle que ce logiciel sait lire — mieux vaut refuser franchement que
        d'interpréter de travers des coordonnées de dépose.

        Un fichier PLUS ANCIEN, lui, est converti (voir _convertir_v1_vers_v2) et non
        refusé : décidé le 2026-08-01, un opérateur ne doit pas perdre un plateau
        déjà tracé parce que la convention interne du logiciel a changé.
        """
        version = data.get("format_version", 0)
        if version > FORMAT_VERSION:
            raise ValueError(
                f"Fichier de préparation en version {version}, alors que ce logiciel "
                f"ne sait lire que jusqu'à la version {FORMAT_VERSION}. "
                f"Mettre à jour l'application."
            )
        if version < OLDEST_CONVERTIBLE_VERSION:
            raise ValueError(
                f"Fichier de préparation en version {version} — trop ancien pour être "
                f"converti (plus ancienne version convertible : "
                f"{OLDEST_CONVERTIBLE_VERSION}). Refaire le plateau."
            )

        preparation = Preparation(
            product_name=data["product_name"],
            zones=[_zone_from_dict(z) for z in data.get("zones", [])],
            cordons=[Cordon.from_dict(c) for c in data.get("cordons", [])],
            settings=Settings.from_dict(data.get("settings", {})),
            reference_zone_id=data.get("reference_zone_id"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

        # Conversion APRÈS reconstruction, et pas au fil de la lecture : retourner un
        # cordon demande la HAUTEUR de sa zone, qui n'est connue qu'une fois les zones
        # relues. Lire dans l'ordre du fichier obligerait à espérer que les zones y
        # précèdent les cordons — une dépendance invisible et fragile.
        if version < FORMAT_VERSION:
            _convertir_v1_vers_v2(preparation)
            preparation.converted_from_version = version

        return preparation

    def touch(self) -> None:
        """Met à jour l'horodatage de dernière modification."""
        self.updated_at = datetime.now().isoformat(timespec="seconds")

    def __repr__(self) -> str:
        return (
            f"Preparation('{self.product_name}', {len(self.zones)} zones, "
            f"{len(self.cordons)} cordons)"
        )


# ===========================================================================
# Persistance sur disque
# ===========================================================================

def preparation_path(product_name: str, directory: str = None) -> str:
    """Chemin du fichier DÉFINITIF d'une préparation."""
    dossier = directory if directory is not None else PREPARATIONS_DIR
    return os.path.join(dossier, f"{_safe_filename(product_name)}.json")


def autosave_path(product_name: str, directory: str = None) -> str:
    """Chemin du fichier de sauvegarde AUTOMATIQUE d'une préparation."""
    dossier = directory if directory is not None else PREPARATIONS_DIR
    return os.path.join(dossier, f"{_safe_filename(product_name)}{AUTOSAVE_SUFFIX}")


# Jeton interne servant à garder les paires de coordonnées sur une seule ligne.
# Il n'apparaît jamais dans le fichier final : il est retiré juste après le formatage.
_JETON_INLINE = "__PAIRE__"


def _marquer_paires(obj):
    """Remplace récursivement toute paire [x, y] de nombres par un jeton texte.

    Parcourt dicts et listes en profondeur. Une paire est reconnue à sa forme : liste
    de deux nombres. Les booléens sont explicitement exclus — en Python, True est un
    entier, et [True, False] deviendrait sinon une fausse coordonnée.
    """
    if isinstance(obj, list):
        est_paire = len(obj) == 2 and all(
            isinstance(v, (int, float)) and not isinstance(v, bool) for v in obj
        )
        if est_paire:
            return f"{_JETON_INLINE}[{obj[0]}, {obj[1]}]{_JETON_INLINE}"
        return [_marquer_paires(v) for v in obj]

    if isinstance(obj, dict):
        return {k: _marquer_paires(v) for k, v in obj.items()}

    return obj


def _dumps_lisible(data: dict) -> str:
    """Sérialise en JSON indenté, mais avec les coordonnées gardées sur une ligne.

    Pourquoi ce traitement : json.dumps(indent=2) éclate TOUTE liste, y compris les
    paires [x, y], sur une ligne par élément. Un fichier de plateau réaliste (6 zones,
    une dizaine de cordons) deviendrait plusieurs centaines de lignes de crochets
    quasi vides, impossible à relire ou à corriger à la main. Or ce fichier est un
    livrable qu'on doit pouvoir ouvrir dans un éditeur.

    Le procédé : chaque paire est d'abord remplacée par une CHAÎNE contenant sa forme
    finale, ce qui la rend insécable pour l'indenteur ; les guillemets qui l'entourent
    sont ensuite retirés pour retrouver une vraie liste JSON. Le résultat reste du JSON
    parfaitement standard — c'est vérifié par les tests.
    """
    texte = json.dumps(_marquer_paires(data), indent=2, ensure_ascii=False)

    # Retirer les guillemets et les jetons : "__PAIRE__[5.0, 5.0]__PAIRE__" → [5.0, 5.0]
    jeton = re.escape(_JETON_INLINE)
    return re.sub(rf'"{jeton}(.*?){jeton}"', r"\1", texte)


def _write_json_atomic(chemin: str, data: dict) -> None:
    """Écrit un JSON de façon atomique : fichier temporaire, puis remplacement.

    Pourquoi ne pas écrire directement dans le fichier final : une coupure au milieu de
    l'écriture laisserait un fichier tronqué, donc illisible. Ce serait particulièrement
    absurde pour la sauvegarde automatique, dont c'est justement le rôle de protéger
    contre les plantages. os.replace() est atomique sur Windows comme sur Linux : soit
    l'ancien fichier est intact, soit le nouveau est complet, jamais d'entre-deux.
    """
    dossier = os.path.dirname(chemin)
    os.makedirs(dossier, exist_ok=True)

    # Créer le fichier temporaire DANS le dossier de destination : os.replace() ne peut
    # pas être atomique d'un système de fichiers à l'autre
    fd, chemin_temporaire = tempfile.mkstemp(dir=dossier, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            # _dumps_lisible : indenté, accents préservés, coordonnées sur une ligne
            f.write(_dumps_lisible(data))
            # Newline final : convention des fichiers texte, évite le « \ No newline at
            # end of file » dans les diffs git si un fichier venait à être versionné
            f.write("\n")
        os.replace(chemin_temporaire, chemin)
    except BaseException:
        # Ne jamais laisser traîner un .tmp orphelin si l'écriture a échoué
        if os.path.exists(chemin_temporaire):
            os.remove(chemin_temporaire)
        raise


def save_preparation(preparation: Preparation, directory: str = None) -> str:
    """Enregistrement DÉFINITIF, déclenché par l'opérateur.

    Écrit le fichier final puis **supprime la sauvegarde automatique** : le travail
    étant validé, le filet anti-plantage n'a plus lieu d'être, et son maintien ferait
    proposer une reprise inutile au prochain démarrage.

    Retourne le chemin du fichier écrit.
    """
    preparation.touch()
    chemin = preparation_path(preparation.product_name, directory)
    _write_json_atomic(chemin, preparation.to_dict())

    discard_autosave(preparation.product_name, directory)
    return chemin


def save_autosave(preparation: Preparation, directory: str = None) -> str:
    """Sauvegarde AUTOMATIQUE (appelée toutes les 5 s par l'IHM).

    Ne touche pas au fichier définitif : tant que l'opérateur n'a pas validé, son
    dernier enregistrement volontaire reste intact.

    ⚠️ L'appelant ne doit PAS inclure la polyline en cours de tracé : un cordon
    inachevé n'a pas de sens et serait rechargé tel quel après une reprise.

    Retourne le chemin du fichier écrit.
    """
    preparation.touch()
    chemin = autosave_path(preparation.product_name, directory)
    _write_json_atomic(chemin, preparation.to_dict())
    return chemin


def load_preparation(chemin: str) -> Preparation:
    """Relit une préparation depuis un fichier JSON (définitif ou automatique).

    Si le fichier était dans un format antérieur, il est converti (voir
    Preparation.from_dict) puis **réenregistré sur place au format courant**. La
    conversion n'a ainsi lieu qu'une fois, et le fichier sur disque cesse d'être un
    piège pour la prochaine lecture.

    C'est cette fonction, et non from_dict(), qui réécrit : from_dict ne touche pas
    au disque et doit rester utilisable sur des données en mémoire (tests compris).
    """
    with open(chemin, "r", encoding="utf-8") as f:
        preparation = Preparation.from_dict(json.load(f))

    if preparation.converted_from_version is not None:
        # touch() n'est pas appelé : la préparation n'a pas été modifiée par
        # l'opérateur, seulement transcrite. Écraser updated_at ferait passer une
        # migration technique pour un travail récent.
        _write_json_atomic(chemin, preparation.to_dict())

    return preparation


def has_autosave(product_name: str, directory: str = None) -> bool:
    """Indique si un travail a été interrompu pour ce produit."""
    return os.path.exists(autosave_path(product_name, directory))


def discard_autosave(product_name: str, directory: str = None) -> None:
    """Supprime la sauvegarde automatique d'un produit, si elle existe.

    Appelé après un enregistrement définitif, ou quand l'opérateur refuse de reprendre
    un travail interrompu. Ne lève pas d'erreur si le fichier n'existe pas.
    """
    chemin = autosave_path(product_name, directory)
    if os.path.exists(chemin):
        os.remove(chemin)


def list_autosaves(directory: str = None) -> list:
    """Liste les travaux interrompus, du plus récemment modifié au plus ancien.

    Utilisé au démarrage : l'application propose à l'opérateur de reprendre. Le tri par
    date décroissante met en tête le travail le plus probable — celui qu'il faisait
    quand l'application s'est arrêtée.

    Retourne une liste de chemins de fichiers.
    """
    dossier = directory if directory is not None else PREPARATIONS_DIR
    if not os.path.isdir(dossier):
        return []

    chemins = [
        os.path.join(dossier, nom)
        for nom in os.listdir(dossier)
        if nom.endswith(AUTOSAVE_SUFFIX)
    ]
    return sorted(chemins, key=os.path.getmtime, reverse=True)


def product_name_from_path(chemin: str) -> str:
    """Retrouve le nom de produit à partir d'un chemin de fichier de préparation.

    Gère les deux formes : `<produit>.json` et `<produit>.autosave.json`. Le suffixe
    d'autosave est retiré en premier, sinon `os.path.splitext` ne retirerait que le
    `.json` final et laisserait un `.autosave` parasite dans le nom.

    ⚠️ Le nom retourné est le nom de FICHIER, donc assaini (voir _safe_filename) : il
    peut différer de la référence exacte saisie par l'opérateur, conservée dans le champ
    `product_name` à l'intérieur du fichier. Suffisant pour lister ou numéroter, pas
    pour afficher une référence exacte.
    """
    nom = os.path.basename(chemin)
    if nom.endswith(AUTOSAVE_SUFFIX):
        return nom[: -len(AUTOSAVE_SUFFIX)]
    return os.path.splitext(nom)[0]


# Préfixe du nom de repli, quand l'opérateur valide sans rien saisir.
DEFAULT_PRODUCT_PREFIX = "BOITIER_"


def next_default_product_name(directory: str = None) -> str:
    """Premier nom `BOITIER_X` libre dans le dossier des préparations.

    Sert de repli quand l'opérateur valide le champ produit sans rien saisir — cas
    courant sur l'écran tactile, où saisir du texte coûte cher.

    Pourquoi chercher le premier trou plutôt que « le plus grand + 1 » : après
    suppression de `BOITIER_2`, le numéro redevient libre et sera réutilisé. C'est
    voulu — la numérotation sert à distinguer des plateaux de travail, pas à tracer un
    historique. Un compteur toujours croissant obligerait à conserver un état quelque
    part.

    Et c'est justement le point de la décision du 2026-08-01 : **aucun état n'est
    conservé hors du dossier des préparations lui-même**. Le mécanisme fonctionne donc
    tel quel sur un dépôt fraîchement cloné, sans compteur à initialiser ni fichier de
    séquence à sauvegarder — et il survit à la copie du dossier sur une autre machine.

    Les travaux interrompus (autosaves) comptent comme occupés : un `BOITIER_3` qu'on
    n'a pas fini ne doit pas voir son numéro réattribué à un autre plateau.
    """
    dossier = directory if directory is not None else PREPARATIONS_DIR

    # Les deux familles de fichiers réunies — définitifs ET travaux interrompus
    chemins = list_preparations(dossier) + list_autosaves(dossier)

    # Numéros déjà pris, extraits des noms de la forme BOITIER_<entier>
    motif = re.compile(rf"^{re.escape(DEFAULT_PRODUCT_PREFIX)}(\d+)$")
    occupes = set()
    for chemin in chemins:
        correspondance = motif.match(product_name_from_path(chemin))
        if correspondance:
            occupes.add(int(correspondance.group(1)))

    # Premier entier positif absent de l'ensemble. La borne de la boucle est sûre :
    # avec n numéros occupés, l'un des entiers de 1 à n+1 est forcément libre.
    numero = next(n for n in range(1, len(occupes) + 2) if n not in occupes)
    return f"{DEFAULT_PRODUCT_PREFIX}{numero}"


def list_preparations(directory: str = None) -> list:
    """Liste les préparations enregistrées définitivement, par ordre alphabétique.

    Les fichiers de sauvegarde automatique en sont exclus : ce sont des travaux en
    cours, pas des préparations validées.
    """
    dossier = directory if directory is not None else PREPARATIONS_DIR
    if not os.path.isdir(dossier):
        return []

    return sorted(
        os.path.join(dossier, nom)
        for nom in os.listdir(dossier)
        if nom.endswith(".json") and not nom.endswith(AUTOSAVE_SUFFIX)
    )
