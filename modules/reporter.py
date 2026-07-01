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


class Reporter:
    """Génère un rapport PDF à la fin de chaque cycle de dépose.

    Utilisation :
        reporter = Reporter()
        chemin = reporter.generate(image, points_mm, quantity, status)
        print(f"PDF sauvegardé : {chemin}")
    """

    def __init__(self, output_dir: str = "reports") -> None:
        # Créer le dossier de sortie s'il n'existe pas encore
        # os.makedirs avec exist_ok=True ne lève pas d'erreur si le dossier existe déjà
        self._output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

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

        # Sauvegarder l'image dans un fichier temporaire car fpdf2 attend un chemin
        # tempfile.mkstemp crée un fichier vide et retourne (descripteur, chemin)
        fd, img_path = tempfile.mkstemp(suffix='.jpg')
        os.close(fd)  # Fermer le descripteur — on écrit via OpenCV, pas via fd

        # Convertir BGR (convention OpenCV) en RGB (convention standard) avant JPEG
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        cv2.imwrite(img_path, image_rgb)

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
