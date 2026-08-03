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
    QCheckBox, QProgressBar, QMessageBox,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap

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

        # Les paramètres que ce dialogue n'édite PAS sont conservés tels quels et
        # recopiés dans l'objet rendu (voir `values()`). Sans cela, ouvrir puis valider
        # cette fenêtre les remettrait à leur valeur par défaut **sans rien signaler** —
        # une perte de réglage d'autant plus traîtresse qu'elle survient au moment où
        # l'opérateur croit justement régler la machine. C'est aujourd'hui sans effet
        # (les tempos valent tous 0), mais ce ne le sera plus dès le sous-lot D4.
        self._settings_recus = settings

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
            # Report des paramètres non édités ici — voir le commentaire du constructeur.
            # Les tempos d'extrusion se règlent au sous-lot D4, avec la pâte sous les
            # yeux ; les leur faire perdre au passage par cette fenêtre annulerait
            # précisément le travail de mise au point qu'elle est censée servir.
            priming_seconds=self._settings_recus.priming_seconds,
            end_anticipation_mm=self._settings_recus.end_anticipation_mm,
            retract_mm=self._settings_recus.retract_mm,
            row_tolerance_mm=self._settings_recus.row_tolerance_mm,
        )


# ===========================================================================
# Lot D2 — les trois modales du cycle de dépose
# ===========================================================================

def _pixmap_depuis_image(image, largeur_max: int) -> QPixmap:
    """Convertit une image OpenCV (BGR) en QPixmap mis à l'échelle.

    Les imports d'OpenCV et de Qt sont faits ici plutôt qu'en tête de module : ce fichier
    ne sert qu'à des boîtes de dialogue, et seule celle-ci a besoin d'afficher une image.
    """
    import cv2
    from PyQt5.QtGui import QImage

    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    hauteur, largeur, canaux = rgb.shape
    qimage = QImage(rgb.data, largeur, hauteur, canaux * largeur, QImage.Format_RGB888)
    return QPixmap.fromImage(qimage).scaledToWidth(
        largeur_max, Qt.SmoothTransformation
    )

class ConfirmDepositDialog(QDialog):
    """Dernier point d'arrêt avant que la machine ne bouge.

    Rappelle ce qui va se passer — combien de zones, quel produit — et laisse revenir en
    arrière. « Annuler » ramène à la sélection des zones et **pas** à l'écran d'accueil :
    se tromper d'une zone est l'erreur la plus probable à cet instant, et refaire tout le
    cycle pour un clic de trop serait décourageant.

    La case « dépose à blanc » est ici plutôt que dans les paramètres parce que c'est une
    décision qui se prend **pour cette exécution-là**, en regardant le plateau : y a-t-il
    de la pâte dans la seringue, est-ce un essai ou une pièce à livrer.
    """

    def __init__(self, product_name: str, zone_count: int,
                 dry_run_default: bool = True, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Confirmer la depose")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        resume = QLabel(
            f"Produit : <b>{product_name}</b><br>"
            f"Zones a deposer : <b>{zone_count}</b>"
        )
        resume.setTextFormat(Qt.RichText)
        resume.setWordWrap(True)
        layout.addWidget(resume)

        self._case_a_blanc = QCheckBox("Depose a blanc (aucune extrusion)")
        self._case_a_blanc.setChecked(dry_run_default)
        self._case_a_blanc.setMinimumHeight(_HAUTEUR_CHAMP_PX)
        layout.addWidget(self._case_a_blanc)

        explication = QLabel(
            "En depose a blanc, la machine parcourt exactement le meme chemin mais "
            "n'extrude rien et ne descend pas : elle reste a la hauteur du homing. "
            "C'est le mode pour verifier un plateau neuf, ou montrer le cycle sans "
            "gacher de pate."
        )
        explication.setProperty("role", "status")
        explication.setWordWrap(True)
        layout.addWidget(explication)

        avertissement = QLabel(
            "/!\\ La machine va faire un homing puis se deplacer. Degager la zone de "
            "travail avant de confirmer."
        )
        avertissement.setWordWrap(True)
        layout.addWidget(avertissement)

        boutons = QDialogButtonBox()
        # Libellés explicites plutôt que « OK / Annuler » : à cet instant, l'opérateur
        # doit pouvoir lire ce que fait le bouton sans relire toute la fenêtre.
        self._btn_lancer = boutons.addButton("Lancer la depose",
                                             QDialogButtonBox.AcceptRole)
        self._btn_lancer.setProperty("role", "success")
        boutons.addButton("Revenir a la selection", QDialogButtonBox.RejectRole)
        boutons.accepted.connect(self.accept)
        boutons.rejected.connect(self.reject)
        layout.addWidget(boutons)

    @property
    def dry_run(self) -> bool:
        """Vrai si l'opérateur a laissé la dépose à blanc active."""
        return self._case_a_blanc.isChecked()


class DepositProgressDialog(QDialog):
    """Suivi de la dépose en cours : avancement, zones faites, temps écoulé.

    Modale et **non refermable par la croix** : tant que la machine bouge, la seule
    sortie légitime est le bouton d'arrêt. Fermer la fenêtre laisserait le thread
    d'exécution tourner en retirant à l'opérateur l'accès à l'arrêt — c'est exactement le
    trou de sécurité relevé sur `app.py::closeEvent` (dette L2), qu'on ne va pas
    reproduire ici.
    """

    pause_toggled = pyqtSignal(bool)   # True = mettre en pause, False = reprendre
    stop_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Depose en cours")
        self.setMinimumWidth(560)
        # Retirer la croix de fermeture — voir la docstring
        self.setWindowFlags(
            (self.windowFlags() | Qt.CustomizeWindowHint) & ~Qt.WindowCloseButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self._label_zones = QLabel("Preparation...")
        self._label_zones.setWordWrap(True)
        layout.addWidget(self._label_zones)

        self._barre = QProgressBar()
        self._barre.setMinimum(0)
        # En millièmes : la progression est une FRACTION de longueur, pas un compte
        self._barre.setMaximum(1000)
        self._barre.setValue(0)
        self._barre.setMinimumHeight(40)
        self._barre.setFormat("%p%")
        layout.addWidget(self._barre)

        self._label_temps = QLabel("Temps ecoule : 0:00")
        layout.addWidget(self._label_temps)

        self._label_etat = QLabel("")
        self._label_etat.setProperty("role", "status")
        self._label_etat.setWordWrap(True)
        layout.addWidget(self._label_etat)

        boutons = QHBoxLayout()
        boutons.setSpacing(8)

        self._btn_pause = QPushButton("Pause")
        self._btn_pause.setProperty("role", "secondary")
        self._btn_pause.setCheckable(True)
        self._btn_pause.clicked.connect(self._on_pause)
        boutons.addWidget(self._btn_pause)

        self._btn_stop = QPushButton("ARRET")
        self._btn_stop.setProperty("role", "danger")
        self._btn_stop.clicked.connect(self._on_stop)
        boutons.addWidget(self._btn_stop)

        layout.addLayout(boutons)

    # ------------------------------------------------------------------ mises à jour

    def set_progress(self, fraction: float, zones_faites: int, zones_total: int) -> None:
        """Avancement, exprimé en FRACTION DE LONGUEUR déposée et non en steps.

        Un step de dépose de 80 mm et un déplacement de 2 mm comptent pareil dans une
        progression en steps : la barre avancerait par à-coups et mentirait sur le temps
        restant. La longueur, elle, est à peu près proportionnelle au temps.
        """
        self._barre.setValue(int(max(0.0, min(1.0, fraction)) * 1000))
        self._label_zones.setText(
            f"Zone {min(zones_faites + 1, zones_total)} sur {zones_total} — "
            f"{zones_faites} terminee(s)"
        )

    def set_elapsed(self, secondes: int) -> None:
        self._label_temps.setText(f"Temps ecoule : {secondes // 60}:{secondes % 60:02d}")

    def set_state_text(self, texte: str) -> None:
        self._label_etat.setText(texte)

    def set_finished(self, message: str) -> None:
        """La dépose est terminée : les commandes n'ont plus lieu d'être."""
        self._btn_pause.setEnabled(False)
        self._btn_stop.setEnabled(False)
        self._label_etat.setText(message)

    # ------------------------------------------------------------------ actions

    def _on_pause(self) -> None:
        en_pause = self._btn_pause.isChecked()
        self._btn_pause.setText("Reprendre" if en_pause else "Pause")
        self.pause_toggled.emit(en_pause)

    def _on_stop(self) -> None:
        """Arrêt : demande confirmation, car il est irréversible.

        L'arrêt coupe les actionneurs et impose de redémarrer la machine — ce n'est pas
        une pause. Le bouton étant volontairement gros et rouge, à portée de doigt sur un
        tactile, la confirmation évite qu'un appui de trop ruine un plateau en cours.
        « Non » est le choix par défaut.
        """
        reponse = QMessageBox.question(
            self, "Arreter la depose ?",
            "Arreter maintenant coupe tous les actionneurs et interrompt le plateau "
            "en cours.\nLa machine devra etre redemarree avant le prochain cycle.\n\n"
            "Arreter vraiment ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reponse == QMessageBox.Yes:
            self.stop_requested.emit()

    def keyPressEvent(self, event) -> None:
        """Neutraliser Échap : il déclencherait `reject()`, donc une fermeture masquée.

        Même motif que le retrait de la croix — pendant que la machine bouge, on ne sort
        d'ici que par le bouton d'arrêt.
        """
        if event.key() == Qt.Key_Escape:
            return
        super().keyPressEvent(event)


class DepositSummaryDialog(QDialog):
    """Bilan de fin de dépose, nominal ou interrompu.

    Le détail par zone n'est affiché **qu'en cas d'interruption**. Un tableau dont toutes
    les lignes disent « fait » n'apporte rien et noie l'information ; après un arrêt,
    c'est exactement l'inverse — savoir quelles pièces ont reçu de la pâte est le seul
    renseignement qui compte.

    La **vue de fin** et le bouton d'impression sont arrivés au sous-lot D3. La vue peut
    être absente (`image=None`) : le cycle reste rapportable même si la photo a échoué, et
    un bilan sans vue vaut mieux que pas de bilan.
    """

    # L'opérateur demande l'impression du rapport. C'est l'écran qui le produit, pas ce
    # dialogue : générer un PDF n'est pas le travail d'une boîte de dialogue, et l'écran
    # seul connaît les longueurs déposées.
    report_requested = pyqtSignal()

    def __init__(self, product_name: str, zones_faites: list, zones_prevues: list,
                 secondes: int, interrompu: bool, dry_run: bool,
                 image=None, cadrage_incertain: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Depose interrompue" if interrompu else "Depose terminee")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        titre = QLabel(
            "<b>Depose INTERROMPUE</b>" if interrompu else "<b>Depose terminee</b>"
        )
        titre.setTextFormat(Qt.RichText)
        layout.addWidget(titre)

        resume = QLabel(
            f"Produit : <b>{product_name}</b><br>"
            f"Zones deposees : <b>{len(zones_faites)} / {len(zones_prevues)}</b><br>"
            f"Temps total : <b>{secondes // 60} min {secondes % 60:02d} s</b>"
        )
        resume.setTextFormat(Qt.RichText)
        resume.setWordWrap(True)
        layout.addWidget(resume)

        if dry_run:
            rappel = QLabel(
                "Depose a blanc : aucune pate n'a ete extrudee, et la machine n'a pas "
                "quitte la hauteur du homing."
            )
            rappel.setProperty("role", "status")
            rappel.setWordWrap(True)
            layout.addWidget(rappel)

        # --- Vue de fin ---
        # Affichée en petit : cette fenêtre doit tenir sur un écran de 7 pouces à côté du
        # bilan chiffré, qui est l'information principale. La vue en pleine résolution est
        # dans le PDF, là où on peut l'examiner.
        if image is not None:
            self._vue = QLabel()
            self._vue.setAlignment(Qt.AlignCenter)
            self._vue.setPixmap(_pixmap_depuis_image(image, largeur_max=460))
            layout.addWidget(self._vue)

            if cadrage_incertain:
                note = QLabel(
                    "Vue prise a la position ou la machine s'est arretee, et non depuis "
                    "la position de prise de vue habituelle : le cadrage differe."
                )
                note.setProperty("role", "status")
                note.setWordWrap(True)
                layout.addWidget(note)

        # Détail par zone : seulement quand il porte une information — voir la docstring
        if interrompu:
            faites = set(zones_faites)
            lignes = [
                f"- Zone {zone_id} : "
                f"{'deposee' if zone_id in faites else 'NON deposee'}"
                for zone_id in zones_prevues
            ]
            detail = QLabel("\n".join(lignes))
            detail.setWordWrap(True)
            layout.addWidget(detail)

            consigne = QLabel(
                "Verifier les zones non deposees avant de relancer : une zone "
                "interrompue en cours de cordon a recu une dose partielle."
            )
            consigne.setProperty("role", "status")
            consigne.setWordWrap(True)
            layout.addWidget(consigne)

        boutons = QDialogButtonBox()
        # ActionRole : ce bouton ne ferme PAS la fenêtre. Imprimer un rapport puis vouloir
        # relire le bilan est le comportement normal, et un opérateur qui doit rouvrir un
        # cycle terminé pour réimprimer ne le ferait tout simplement pas.
        self._btn_rapport = boutons.addButton(
            "Imprimer le rapport", QDialogButtonBox.ActionRole
        )
        self._btn_rapport.clicked.connect(self.report_requested)

        btn = boutons.addButton("Terminer", QDialogButtonBox.AcceptRole)
        btn.setProperty("role", "success")
        boutons.accepted.connect(self.accept)
        layout.addWidget(boutons)

        # Message de confirmation d'impression, sous les boutons — l'opérateur doit voir
        # que quelque chose s'est passé, et surtout OÙ le fichier a été écrit
        self._confirmation = QLabel("")
        self._confirmation.setProperty("role", "status")
        self._confirmation.setWordWrap(True)
        layout.addWidget(self._confirmation)

    def set_report_result(self, message: str) -> None:
        """Afficher le résultat de l'impression (chemin du PDF, ou message d'erreur)."""
        self._confirmation.setText(message)
