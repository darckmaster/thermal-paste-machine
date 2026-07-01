# Écran 4 — Rapport de dépose
# Affiche le résumé du cycle terminé et permet d'exporter un PDF ou de traiter une nouvelle pièce.

import numpy as np
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)
from PyQt5.QtCore import Qt, pyqtSignal

from modules.reporter import Reporter


class ScreenReport(QWidget):
    """Écran 4 : résumé de la dépose terminée.

    Reçoit les données du cycle via set_result() (appelé par app.py avant d'afficher cet écran).
    Permet d'exporter un rapport PDF ou de démarrer un nouveau cycle.
    """

    # Signal émis quand l'utilisateur veut traiter une nouvelle pièce
    new_piece_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        # Données du cycle courant — remplies par set_result() avant l'affichage
        self._image: np.ndarray | None = None
        self._points_mm: list = []
        self._quantity: float = 0.0
        self._status: str = ""
        self._setup_ui()

    # ------------------------------------------------------------------ mise à jour des données

    def set_result(
        self,
        image: np.ndarray | None,
        points_mm: list,
        quantity: float,
        status: str,
    ) -> None:
        """Renseigne les données du cycle et met à jour l'affichage.

        Appelé par app.py juste avant de basculer vers cet écran.
        image      : photo de la pièce (numpy BGR) ou None si non disponible
        points_mm  : tracé dessiné par l'opérateur en coordonnées ArUco (mm)
        quantity   : quantité de pâte configurée (mm axe E / mm de tracé)
        status     : "Succes", "Arret d'urgence", ou message d'erreur
        """
        self._image = image
        self._points_mm = points_mm
        self._quantity = quantity
        self._status = status

        # Mettre à jour l'icône selon le statut (vert = succès, rouge = problème)
        succes = 'urgence' not in status.lower() and 'erreur' not in status.lower()
        if succes:
            self._icon_label.setText("OK")
            self._icon_label.setStyleSheet("font-size: 48px; color: #4caf50; font-weight: bold;")
        else:
            self._icon_label.setText("!")
            self._icon_label.setStyleSheet("font-size: 48px; color: #e53935; font-weight: bold;")

        # Calculer la longueur totale du tracé pour l'afficher dans le résumé
        longueur = Reporter._longueur_totale(points_mm) if points_mm else 0.0

        self._summary_label.setText(
            f"Statut : {status}\n\n"
            f"Points traces    : {len(points_mm)}\n"
            f"Longueur du trace: {longueur:.1f} mm\n"
            f"Quantite         : {quantity:.3f} mm E / mm\n"
            f"Volume estime    : {quantity * longueur:.2f} mm E total"
        )

        # Activer le bouton PDF uniquement si on a une image valide
        self._btn_pdf.setEnabled(image is not None)
        self._pdf_status_label.setText("")

    # ------------------------------------------------------------------ interface

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(10)

        # Titre
        title = QLabel("Rapport de depose")
        title.setProperty("role", "title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        layout.addStretch(1)

        # Icône de statut — mise à jour par set_result()
        self._icon_label = QLabel("OK")
        self._icon_label.setAlignment(Qt.AlignCenter)
        self._icon_label.setStyleSheet("font-size: 48px; color: #4caf50; font-weight: bold;")
        layout.addWidget(self._icon_label)

        # Résumé du cycle — mis à jour par set_result()
        self._summary_label = QLabel("En attente des donnees...")
        self._summary_label.setAlignment(Qt.AlignCenter)
        self._summary_label.setStyleSheet("line-height: 1.8;")
        layout.addWidget(self._summary_label)

        # Label d'état du PDF (chemin ou message d'erreur) — vide par défaut
        self._pdf_status_label = QLabel("")
        self._pdf_status_label.setAlignment(Qt.AlignCenter)
        self._pdf_status_label.setProperty("role", "status")
        self._pdf_status_label.setWordWrap(True)
        layout.addWidget(self._pdf_status_label)

        layout.addStretch(1)

        # Boutons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self._btn_pdf = QPushButton("Exporter PDF")
        self._btn_pdf.setProperty("role", "secondary")
        self._btn_pdf.setEnabled(False)   # Activé par set_result() quand l'image est disponible
        self._btn_pdf.clicked.connect(self._on_generate_pdf)

        btn_new = QPushButton("Nouvelle piece")
        btn_new.setProperty("role", "success")
        btn_new.clicked.connect(self._on_new_piece)

        btn_layout.addWidget(self._btn_pdf)
        btn_layout.addWidget(btn_new, stretch=2)
        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------ actions

    def _on_generate_pdf(self) -> None:
        """Générer le rapport PDF et afficher son chemin."""
        self._btn_pdf.setEnabled(False)
        self._pdf_status_label.setText("Generation du PDF en cours...")

        try:
            # Reporter() crée le dossier reports/ si nécessaire
            reporter = Reporter()
            chemin = reporter.generate(
                self._image,
                self._points_mm,
                self._quantity,
                self._status,
            )
            # Afficher le chemin du fichier généré pour que l'opérateur puisse le retrouver
            self._pdf_status_label.setText(f"PDF sauvegarde :\n{chemin}")
        except Exception as e:
            self._pdf_status_label.setText(f"Erreur PDF : {e}")
            self._btn_pdf.setEnabled(True)

    def _on_new_piece(self) -> None:
        """Retourner à l'écran de capture pour traiter une nouvelle pièce."""
        self.new_piece_requested.emit()
