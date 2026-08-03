# Génération du rapport PDF de fin de cycle de dépose
# Utilise fpdf2 (LGPL) — open source, pas de licence tierce payante.
#
# Contenu du rapport (version simple Phase 7) :
#   - Titre et date/heure de la dépose
#   - Photo de la pièce capturée
#   - Résumé : statut, quantité, nombre de points, longueur du tracé

import os
import math
import tempfile
from datetime import datetime

import cv2
import numpy as np
from fpdf import FPDF

from modules.config import REPORTS_DIR


def _ecrire_image_temporaire(image: np.ndarray) -> str:
    """Écrit une image OpenCV dans un JPEG temporaire et rend son chemin.

    fpdf2 attend un chemin de fichier, pas un tableau numpy.

    ⚠️ **On n'appelle PAS `cvtColor(BGR2RGB)` avant d'écrire.** `cv2.imwrite` suppose déjà
    que le tableau qu'on lui donne est en BGR et se charge lui-même de la conversion :
    convertir avant revient à la faire deux fois, ce qui **échange le rouge et le bleu**
    dans le fichier enregistré.

    Le défaut existait depuis la Phase 7 (2026-07-01) et a été trouvé en écrivant le
    sous-lot D3. Il ne saute pas aux yeux sur un plateau plutôt gris, mais il rendait
    faux tous les rapports PDF produits jusqu'ici.
    """
    fd, chemin = tempfile.mkstemp(suffix='.jpg')
    os.close(fd)   # fermer le descripteur — on écrit via OpenCV, pas via fd
    cv2.imwrite(chemin, image)
    return chemin


def plateau_report_lines(
    product_name: str,
    zones_faites: list,
    zones_prevues: list,
    seconds: int,
    interrupted: bool,
    dry_run: bool,
    length_mm: float = 0.0,
    amount_mm: float = 0.0,
    cadrage_incertain: bool = False,
) -> list:
    """Le CONTENU textuel du rapport de plateau, ligne par ligne.

    Séparé du rendu PDF pour une raison précise : la règle qui gouverne ce rapport —
    détail par zone **uniquement** en cas d'interruption (décision D9) — est une règle de
    contenu. La vérifier à travers un PDF compressé serait pénible et fragile ; ici elle
    se lit et se teste directement.

    Le rendu, lui, ne fait qu'habiller ces lignes.
    """
    lignes = []

    lignes.append(
        "DEPOSE INTERROMPUE" if interrupted else "Depose terminee"
    )

    # Les avertissements viennent AVANT le résumé : ils conditionnent la confiance qu'on
    # peut accorder à tout ce qui suit.
    if dry_run:
        lignes.append(
            "DEPOSE A BLANC : aucune pate n'a ete extrudee et la machine n'a pas "
            "quitte la hauteur du homing. Ce rapport atteste d'un parcours, pas "
            "d'une depose."
        )
    if cadrage_incertain:
        lignes.append(
            "La vue n'a PAS ete prise depuis la position de prise de vue de "
            "reference : la machine a ete arretee et ne pouvait plus etre deplacee. "
            "Le cadrage differe des autres rapports."
        )

    lignes.append(f"Zones deposees  : {len(zones_faites)} / {len(zones_prevues)}")
    lignes.append(f"Temps total     : {seconds // 60} min {seconds % 60:02d} s")
    lignes.append(f"Longueur tracee : {length_mm:.1f} mm")
    if not dry_run:
        lignes.append(f"Pate extrudee   : {amount_mm:.2f} mm d'axe E")

    # Détail par zone : SEULEMENT s'il porte une information (décision D9)
    if interrupted:
        faites = set(zones_faites)
        for zone_id in zones_prevues:
            etat = "deposee" if zone_id in faites else "NON deposee"
            lignes.append(f"Zone {zone_id} : {etat}")
        lignes.append(
            "Une zone interrompue en cours de cordon a recu une dose partielle : "
            "la verifier avant de relancer."
        )

    return lignes


class Reporter:
    """Génère un rapport PDF à la fin de chaque cycle de dépose.

    Utilisation :
        reporter = Reporter()
        chemin = reporter.generate(image, points_mm, quantity, status)
        print(f"PDF sauvegardé : {chemin}")
    """

    def __init__(self, output_dir: str = None) -> None:
        """`output_dir` vaut par défaut `reports/` **à la racine du projet**.

        Le défaut est un chemin ABSOLU calculé depuis l'emplacement du code, et non le
        `"reports"` relatif d'avant : celui-ci suivait le répertoire courant, donc les
        rapports atterrissaient ailleurs dès qu'on lançait l'application autrement qu'en
        se plaçant d'abord à la racine — raccourci du bureau, service au démarrage du
        RPi, double-clic. Ils se dispersaient sans que rien ne le signale.

        Le paramètre reste ouvert pour que les tests écrivent dans un dossier temporaire
        plutôt que d'encombrer celui du projet.
        """
        # Créer le dossier de sortie s'il n'existe pas encore
        # os.makedirs avec exist_ok=True ne lève pas d'erreur si le dossier existe déjà
        self._output_dir = REPORTS_DIR if output_dir is None else output_dir
        os.makedirs(self._output_dir, exist_ok=True)

    def generate(
        self,
        image: np.ndarray,
        points_mm: list,
        quantity: float,
        status: str,
    ) -> str:
        """Génère le PDF et retourne son chemin absolu.

        image      : photo de la pièce (tableau numpy BGR depuis OpenCV)
        points_mm  : liste de tuples (x_mm, y_mm) du tracé dessiné par l'opérateur
        quantity   : quantité de pâte configurée (mm d'axe E par mm de tracé)
        status     : "Succes", "Arret d'urgence", ou message d'erreur
        """
        # Horodatage utilisé pour le nom du fichier et l'affichage dans le PDF
        timestamp = datetime.now()

        img_path = _ecrire_image_temporaire(image)

        try:
            # Construire le PDF et l'enregistrer dans le dossier de sortie
            pdf_path = self._build_pdf(img_path, points_mm, quantity, status, timestamp)
        finally:
            # Toujours supprimer le fichier temporaire, même en cas d'erreur
            os.remove(img_path)

        return pdf_path

    # ------------------------------------------------------------------ construction PDF

    def _build_pdf(
        self,
        img_path: str,
        points_mm: list,
        quantity: float,
        status: str,
        timestamp: datetime,
    ) -> str:
        """Construit le document PDF et le sauvegarde."""
        pdf = FPDF()
        pdf.add_page()
        pdf.set_margins(left=15, top=15, right=15)
        pdf.set_auto_page_break(auto=True, margin=15)

        # --- En-tête ---
        pdf.set_font('Helvetica', 'B', 16)
        pdf.cell(
            0, 10,
            'Rapport de depose de pate thermique',
            new_x='LMARGIN', new_y='NEXT', align='C',
        )

        pdf.set_font('Helvetica', '', 11)
        pdf.cell(
            0, 8,
            f'Date : {timestamp.strftime("%d/%m/%Y  %H:%M:%S")}',
            new_x='LMARGIN', new_y='NEXT',
        )
        pdf.ln(4)

        # --- Photo de la pièce ---
        # w=180 mm → fpdf2 calcule automatiquement la hauteur pour conserver le ratio
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, 'Photo de la piece :', new_x='LMARGIN', new_y='NEXT')
        pdf.image(img_path, x=15, w=180)
        pdf.ln(6)

        # --- Résumé ---
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, 'Resume de la depose :', new_x='LMARGIN', new_y='NEXT')

        pdf.set_font('Helvetica', '', 11)

        # Statut — met en évidence un arrêt d'urgence en rouge
        if 'urgence' in status.lower() or 'erreur' in status.lower():
            pdf.set_text_color(180, 0, 0)
        else:
            pdf.set_text_color(0, 128, 0)
        pdf.cell(0, 7, f'Statut          : {status}', new_x='LMARGIN', new_y='NEXT')
        pdf.set_text_color(0, 0, 0)  # retour noir pour la suite

        longueur = self._longueur_totale(points_mm)
        pdf.cell(
            0, 7,
            f'Points du trace : {len(points_mm)}',
            new_x='LMARGIN', new_y='NEXT',
        )
        pdf.cell(
            0, 7,
            f'Longueur totale : {longueur:.1f} mm',
            new_x='LMARGIN', new_y='NEXT',
        )
        pdf.cell(
            0, 7,
            f'Quantite        : {quantity:.3f} mm axe E / mm de trace',
            new_x='LMARGIN', new_y='NEXT',
        )
        pdf.cell(
            0, 7,
            f'Volume estime   : {quantity * longueur:.2f} mm axe E total',
            new_x='LMARGIN', new_y='NEXT',
        )

        # --- Enregistrement ---
        filename = f'rapport_{timestamp.strftime("%Y%m%d_%H%M%S")}.pdf'
        filepath = os.path.join(self._output_dir, filename)
        pdf.output(filepath)

        return os.path.abspath(filepath)

    # ------------------------------------------------------------------ calculs

    @staticmethod
    def _longueur_totale(points_mm: list) -> float:
        """Calcule la longueur totale du tracé en mm (somme des longueurs de segments)."""
        total = 0.0
        for i in range(1, len(points_mm)):
            dx = points_mm[i][0] - points_mm[i - 1][0]
            dy = points_mm[i][1] - points_mm[i - 1][1]
            # Théorème de Pythagore : longueur du segment entre deux points
            total += math.sqrt(dx * dx + dy * dy)
        return total

    # ------------------------------------------------------------------ rapport multi-zones

    def generate_plateau_report(
        self,
        image,
        product_name: str,
        zones_faites: list,
        zones_prevues: list,
        seconds: int,
        interrupted: bool,
        dry_run: bool,
        length_mm: float = 0.0,
        amount_mm: float = 0.0,
        cadrage_incertain: bool = False,
    ) -> str:
        """Rapport de fin d'un cycle de depose multi-zones (lot D3).

        Le detail par zone n'apparait **qu'en cas d'interruption** (decision D9). En
        marche nominale, un tableau dont toutes les lignes disent « fait » n'apporte rien
        et noie l'information ; apres un arret, c'est exactement l'inverse — savoir
        quelles pieces ont recu de la pate est le seul renseignement qui compte.

        `image` peut etre None : le cycle reste rapportable meme si la photo de fin a
        echoue, et un rapport sans vue vaut mieux que pas de rapport du tout.
        """
        horodatage = datetime.now()

        chemin_image = _ecrire_image_temporaire(image) if image is not None else None
        try:
            chemin_pdf = self._build_plateau_pdf(
                chemin_image, product_name, zones_faites, zones_prevues,
                seconds, interrupted, dry_run, length_mm, amount_mm,
                cadrage_incertain, horodatage,
            )
        finally:
            if chemin_image is not None:
                os.remove(chemin_image)

        return chemin_pdf

    def _build_plateau_pdf(
        self, chemin_image, product_name, zones_faites, zones_prevues,
        seconds, interrupted, dry_run, length_mm, amount_mm,
        cadrage_incertain, horodatage,
    ) -> str:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_margins(left=15, top=15, right=15)
        pdf.set_auto_page_break(auto=True, margin=15)

        # --- En-tete ---
        pdf.set_font('Helvetica', 'B', 16)
        pdf.cell(0, 10, 'Rapport de depose de pate thermique',
                 new_x='LMARGIN', new_y='NEXT', align='C')

        pdf.set_font('Helvetica', '', 11)
        pdf.cell(0, 8, f'Date    : {horodatage.strftime("%d/%m/%Y  %H:%M:%S")}',
                 new_x='LMARGIN', new_y='NEXT')
        pdf.cell(0, 8, f'Produit : {product_name}',
                 new_x='LMARGIN', new_y='NEXT')
        pdf.ln(2)

        # --- Le contenu vient de plateau_report_lines : une seule source ---
        lignes = plateau_report_lines(
            product_name, zones_faites, zones_prevues, seconds, interrupted,
            dry_run, length_mm, amount_mm, cadrage_incertain,
        )

        # Statut en couleur : c'est la premiere chose qu'on lit sur un rapport
        pdf.set_font('Helvetica', 'B', 12)
        pdf.set_text_color(180, 0, 0) if interrupted else pdf.set_text_color(0, 128, 0)
        pdf.cell(0, 8, lignes[0], new_x='LMARGIN', new_y='NEXT')
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)

        # Les avertissements eventuels, avant la vue
        pdf.set_font('Helvetica', '', 10)
        index = 1
        while index < len(lignes) and lignes[index].startswith(
                ('DEPOSE A BLANC', 'La vue')):
            pdf.multi_cell(0, 6, lignes[index], new_x='LMARGIN', new_y='NEXT')
            pdf.ln(1)
            index += 1

        # --- Vue de fin ---
        if chemin_image is not None:
            pdf.set_font('Helvetica', 'B', 12)
            pdf.cell(0, 8, 'Vue du plateau en fin de cycle :',
                     new_x='LMARGIN', new_y='NEXT')
            pdf.image(chemin_image, x=15, w=180)
            pdf.ln(4)

        # --- Resume, puis detail par zone si le rapport en comporte un ---
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, 'Resume :', new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Helvetica', '', 11)
        for ligne in lignes[index:]:
            if ligne.startswith('Zone '):
                rouge = 'NON' in ligne
                pdf.set_text_color(180, 0, 0) if rouge else pdf.set_text_color(0, 128, 0)
                pdf.cell(0, 7, f'   {ligne}', new_x='LMARGIN', new_y='NEXT')
                pdf.set_text_color(0, 0, 0)
            elif len(ligne) > 70:
                pdf.set_font('Helvetica', '', 10)
                pdf.ln(2)
                pdf.multi_cell(0, 6, ligne, new_x='LMARGIN', new_y='NEXT')
                pdf.set_font('Helvetica', '', 11)
            else:
                pdf.cell(0, 7, ligne, new_x='LMARGIN', new_y='NEXT')

        chemin = self._chemin_libre(
            f'rapport_plateau_{horodatage.strftime("%Y%m%d_%H%M%S")}'
        )
        pdf.output(chemin)
        return os.path.abspath(chemin)

    def _chemin_libre(self, base: str) -> str:
        """Chemin de sortie qui n'écrase aucun fichier existant.

        ⚠️ L'horodatage à la seconde ne suffit pas : deux rapports produits dans la même
        seconde portent le même nom, et le second écrase le premier **en silence**. C'est
        loin d'être théorique — l'opérateur peut réimprimer un rapport aussitôt après le
        premier, et rien ne l'en empêche.

        Sur un document de traçabilité, perdre un rapport sans le dire est exactement ce
        qu'on ne peut pas se permettre : on suffixe plutôt que d'écraser.
        """
        chemin = os.path.join(self._output_dir, f'{base}.pdf')
        suffixe = 2
        while os.path.exists(chemin):
            chemin = os.path.join(self._output_dir, f'{base}_{suffixe}.pdf')
            suffixe += 1
        return chemin
