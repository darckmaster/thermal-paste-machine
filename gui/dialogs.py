# Boîtes de dialogue partagées — lot C3
#
# Deux dialogues qui ne sont pas des écrans de la pile de navigation : ils s'ouvrent
# par-dessus l'écran courant, rendent une réponse, et disparaissent. Les regrouper ici
# évite de gonfler les fichiers d'écran avec de la construction d'interface qui ne les
# concerne qu'au moment de l'appel.
#
# Contrainte commune, et elle est structurante : **il n'y a pas de clavier physique sur
# le Raspberry Pi**. Tout ce qui se saisit au texte doit avoir une alternative au doigt,
# et toutes les cibles tactiles doivent rester atteignables sur un écran de 7 pouces.

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QPushButton, QDoubleSpinBox, QFormLayout, QDialogButtonBox,
)
from PyQt5.QtCore import Qt

from modules.preparation import (
    Settings,
    list_preparations,
    load_preparation,
    next_default_product_name,
    product_name_from_path,
)


# Hauteur minimale des champs de saisie, en pixels. Les boutons héritent déjà d'un
# minimum via la feuille de style globale (app.py), mais pas les champs de texte ni les
# compteurs : sans ce réglage ils sortent à ~25 px, soit bien en deçà des 44 px que
# demande une cible tactile utilisable au doigt.
_HAUTEUR_CHAMP_PX = 48


class ProductNameDialog(QDialog):
    """Saisie de la référence du produit — trois voies dans le même dialogue.

    Décidé le 2026-08-01. Le clavier physique n'existant pas sur le RPi, une simple
    boîte de saisie texte rendrait l'écran inutilisable au doigt. L'opérateur a donc
    trois façons d'arriver au même résultat, sans avoir à choisir un mode :

      1. **saisie libre** dans le champ (clavier virtuel du système, ou clavier BT) ;
      2. **choix dans la liste** des produits déjà enregistrés — ce qui évite aussi les
         fautes de frappe sur une référence, une zone où elles coûtent cher ;
      3. **valider en laissant le champ vide** → repli automatique sur le premier
         `BOITIER_X` libre (voir preparation.next_default_product_name).

    La troisième voie est celle du geste minimal : ouvrir, valider, travailler. C'est
    elle qui rend l'écran utilisable quand on a les mains prises.
    """

    def __init__(self, nom_initial: str = "", directory: str = None, parent=None) -> None:
        super().__init__(parent)
        # Dossier des préparations — paramétrable pour que les tests écrivent dans un
        # dossier temporaire plutôt que dans celui du projet
        self._directory = directory

        self.setWindowTitle("Nouveau plateau")
        # Un dialogue dimensionné sur son contenu sort minuscule et au titre tronqué :
        # acceptable à la souris, inutilisable au doigt sur l'écran 7 pouces
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Référence du produit :"))

        self._champ = QLineEdit(nom_initial)
        self._champ.setMinimumHeight(_HAUTEUR_CHAMP_PX)
        self._champ.setPlaceholderText(
            "laisser vide pour un nom automatique"
        )
        layout.addWidget(self._champ)

        # Liste des produits déjà enregistrés. Masquée s'il n'y en a aucun : un cadre
        # vide occuperait une place précieuse sur 480 px de haut sans rien apprendre.
        self._noms_existants = self._lire_produits_existants()
        if self._noms_existants:
            layout.addWidget(QLabel("…ou reprendre une référence existante :"))
            self._liste = QListWidget()
            self._liste.addItems(self._noms_existants)
            self._liste.setMinimumHeight(140)
            # Un appui remplit le champ plutôt que de valider directement : l'opérateur
            # voit ce qu'il a choisi avant de confirmer, et peut encore le corriger
            self._liste.itemClicked.connect(
                lambda item: self._champ.setText(item.text())
            )
            layout.addWidget(self._liste)
        else:
            self._liste = None

        # Boutons standard. QDialogButtonBox gère seul l'ordre attendu par le système
        # et le raccordement des touches Entrée / Échap.
        boutons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self
        )
        boutons.button(QDialogButtonBox.Ok).setText("Valider")
        boutons.button(QDialogButtonBox.Cancel).setText("Annuler")
        boutons.button(QDialogButtonBox.Cancel).setProperty("role", "secondary")
        boutons.accepted.connect(self.accept)
        boutons.rejected.connect(self.reject)
        layout.addWidget(boutons)

    def _lire_produits_existants(self) -> list:
        """Noms des préparations déjà enregistrées, sans doublon et triés."""
        chemins = list_preparations(self._directory)
        return sorted({product_name_from_path(c) for c in chemins})

    @property
    def product_name(self) -> str:
        """Référence retenue — jamais vide.

        C'est ici, et pas à la construction, que le repli `BOITIER_X` est calculé :
        le dossier des préparations a pu changer pendant que le dialogue était ouvert,
        et surtout le numéro ne doit être consommé que si l'opérateur valide réellement
        à vide. Le calculer d'avance réserverait un numéro pour rien à chaque ouverture.
        """
        saisi = self._champ.text().strip()
        if saisi:
            return saisi
        return next_default_product_name(self._directory)


class PreparationPickerDialog(QDialog):
    """Choix d'un plateau **déjà enregistré**, pour le rejouer sans rien retracer.

    Répond au point 7 du processus cible (`CLAUDE.md` section 1) : les zones étant
    vissées à demeure, un plateau enregistré doit pouvoir être rechargé et rejoué
    autant de fois que nécessaire.

    À ne pas confondre avec la reprise proposée au démarrage, qui porte sur les
    fichiers `*.autosave.json` — des travaux **interrompus**. Ici il s'agit de
    préparations **validées** par l'opérateur, que l'enregistrement définitif a
    justement séparées des autosaves.

    Chaque entrée affiche le nombre de cordons et la date : c'est ce qui permet de
    répondre à « est-ce bien celui que j'ai tracé hier ? » sans ouvrir le fichier.
    """

    def __init__(self, directory: str = None, parent=None) -> None:
        super().__init__(parent)
        self._directory = directory
        self._chemins: list = []

        self.setWindowTitle("Charger un plateau")
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self._chemins = list_preparations(self._directory)

        if self._chemins:
            layout.addWidget(QLabel("Plateau à recharger :"))
            self._liste = QListWidget()
            self._liste.setMinimumHeight(200)
            for chemin in self._chemins:
                self._liste.addItem(self._decrire(chemin))
            # Présélectionner la première entrée : sans ça, « Charger » resterait
            # inactif alors qu'un seul appui suffirait
            self._liste.setCurrentRow(0)
            layout.addWidget(self._liste)

            rappel = QLabel(
                "Le chargement restaure les cordons et les paramètres. Il faudra "
                "reprendre une photo du plateau — cela ne fait perdre aucun tracé."
            )
            rappel.setProperty("role", "status")
            rappel.setWordWrap(True)
            layout.addWidget(rappel)
        else:
            self._liste = None
            layout.addWidget(QLabel(
                "Aucun plateau enregistré.\n\n"
                "Créer un plateau, tracer les cordons, puis appuyer sur "
                "« Enregistrer » : il apparaîtra ici."
            ))

        boutons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self
        )
        boutons.button(QDialogButtonBox.Ok).setText("Charger")
        boutons.button(QDialogButtonBox.Ok).setEnabled(bool(self._chemins))
        boutons.button(QDialogButtonBox.Cancel).setText("Annuler")
        boutons.button(QDialogButtonBox.Cancel).setProperty("role", "secondary")
        boutons.accepted.connect(self.accept)
        boutons.rejected.connect(self.reject)
        layout.addWidget(boutons)

    @staticmethod
    def _decrire(chemin: str) -> str:
        """Une ligne de liste : nom du produit, nombre de cordons, date.

        La lecture du fichier est protégée : un JSON tronqué ou d'un format inconnu ne
        doit pas empêcher d'afficher les AUTRES plateaux. Il reste listé, avec ses
        informations remplacées par « illisible » — le masquer laisserait l'opérateur
        croire que son travail a disparu.
        """
        nom = product_name_from_path(chemin)
        try:
            preparation = load_preparation(chemin)
        except (OSError, ValueError, KeyError):
            return f"{nom}  —  ⚠ fichier illisible"

        date = preparation.updated_at.replace("T", " ")
        return f"{nom}  —  {len(preparation.cordons)} cordon(s)  —  {date}"

    @property
    def selected_path(self):
        """Chemin du plateau choisi, ou None si la liste est vide."""
        if self._liste is None or self._liste.currentRow() < 0:
            return None
        return self._chemins[self._liste.currentRow()]


class SettingsDialog(QDialog):
    """Réglage des paramètres d'une préparation : 2 vitesses et 2 seuils.

    Les quatre valeurs vivent déjà dans `preparation.Settings` depuis le lot B — ce
    dialogue n'est que leur interface. Elles sont enregistrées **avec la préparation**
    et non dans la configuration globale : elles qualifient CE plateau-ci, qui peut
    différer d'une machine à l'autre.

    Sur la quantité de pâte : elle ne se règle pas directement. C'est le **rapport**
    entre la vitesse d'extrusion et la vitesse de déplacement qui fixe l'épaisseur du
    cordon — à extrusion constante, ralentir la buse épaissit le boudin. D'où deux
    vitesses plutôt qu'un curseur « quantité », qui masquerait ce lien.
    """

    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Paramètres du plateau")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        formulaire = QFormLayout()
        formulaire.setSpacing(8)

        # --- les deux vitesses, qui déterminent ensemble la quantité déposée ---
        self._vitesse_deplacement = self._compteur(
            valeur=settings.travel_speed_mm_min,
            mini=100.0, maxi=24000.0, pas=100.0, suffixe=" mm/min",
        )
        formulaire.addRow("Vitesse de déplacement :", self._vitesse_deplacement)

        self._vitesse_extrusion = self._compteur(
            valeur=settings.extrusion_speed_mm_min,
            mini=1.0, maxi=3000.0, pas=10.0, suffixe=" mm/min",
        )
        formulaire.addRow("Vitesse d'extrusion :", self._vitesse_extrusion)

        # --- les deux seuils de contrôle du montage du plateau ---
        self._tolerance_diagonale = self._compteur(
            valeur=settings.zone_diagonal_tolerance_mm,
            mini=0.5, maxi=50.0, pas=0.5, suffixe=" mm",
        )
        formulaire.addRow("Tolérance de diagonale :", self._tolerance_diagonale)

        self._rotation_max = self._compteur(
            valeur=settings.zone_max_rotation_deg,
            mini=1.0, maxi=45.0, pas=1.0, suffixe=" °",
        )
        formulaire.addRow("Inclinaison max d'une zone :", self._rotation_max)

        layout.addLayout(formulaire)

        # Rappel du sens physique des réglages : sans lui, « vitesse d'extrusion » et
        # « vitesse de déplacement » se règlent au hasard jusqu'à ce que le cordon ait
        # l'air correct — et le lien entre les deux reste invisible.
        aide = QLabel(
            "L'épaisseur du cordon dépend du RAPPORT entre les deux vitesses : "
            "à extrusion constante, ralentir le déplacement épaissit le cordon.\n"
            "Les deux seuils servent au contrôle du montage : au-delà, une zone est "
            "signalée comme mal vissée."
        )
        aide.setProperty("role", "status")
        aide.setWordWrap(True)
        layout.addWidget(aide)

        boutons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self
        )
        boutons.button(QDialogButtonBox.Ok).setText("Appliquer")
        boutons.button(QDialogButtonBox.Cancel).setText("Annuler")
        boutons.button(QDialogButtonBox.Cancel).setProperty("role", "secondary")
        boutons.accepted.connect(self.accept)
        boutons.rejected.connect(self.reject)
        layout.addWidget(boutons)

    @staticmethod
    def _compteur(valeur: float, mini: float, maxi: float,
                  pas: float, suffixe: str) -> QDoubleSpinBox:
        """Fabrique un compteur numérique utilisable au doigt.

        Les bornes ne sont pas cosmétiques : elles empêchent de saisir une vitesse
        aberrante qui partirait telle quelle en G-code. Le pas est choisi pour que les
        flèches restent utiles — monter une vitesse de 3000 à 4000 mm/min par pas de 1
        demanderait mille appuis.
        """
        compteur = QDoubleSpinBox()
        compteur.setRange(mini, maxi)
        compteur.setSingleStep(pas)
        compteur.setDecimals(1)
        compteur.setSuffix(suffixe)
        compteur.setValue(valeur)
        compteur.setMinimumHeight(_HAUTEUR_CHAMP_PX)
        return compteur

    @property
    def settings(self) -> Settings:
        """Un nouvel objet Settings portant les valeurs saisies.

        On retourne un objet neuf plutôt que de modifier celui reçu : tant que
        l'opérateur n'a pas validé, la préparation ne doit pas avoir bougé. C'est ce
        qui rend le bouton « Annuler » réellement sans effet.
        """
        return Settings(
            travel_speed_mm_min=self._vitesse_deplacement.value(),
            extrusion_speed_mm_min=self._vitesse_extrusion.value(),
            zone_diagonal_tolerance_mm=self._tolerance_diagonale.value(),
            zone_max_rotation_deg=self._rotation_max.value(),
        )
