# Écran 4 — Rapport de dépose
# Affiche un résumé de l'opération et permet de démarrer une nouvelle pièce
# Phase 4 : placeholder — la génération PDF sera implémentée en Phase 7

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
)
from PyQt5.QtCore import Qt, pyqtSignal


class ScreenReport(QWidget):
    """Écran 4 : résumé de la dépose terminée + bouton pour recommencer.

    Phase 4 (actuel) : placeholder avec données fictives.
    Phase 7 : intégration réelle avec Reporter (génération PDF, photos avant/après).
    """

    # Signal émis quand l'utilisateur veut traiter une nouvelle pièce
    new_piece_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._setup_ui()

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

        # Icône de succès
        icon = QLabel("OK")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("font-size: 48px; color: #4caf50; font-weight: bold;")
        layout.addWidget(icon)

        # Résumé fictif (Phase 4) — sera rempli dynamiquement en Phase 7
        self._summary_label = QLabel(
            "Depose terminee avec succes\n\n"
            "Zone traitee : zone complete (placeholder)\n"
            "Quantite deposee : 3 mm axe E (placeholder)\n"
            "Duree : --:-- (placeholder)\n\n"
            "Phase 7 : génération PDF a implémenter"
        )
        self._summary_label.setAlignment(Qt.AlignCenter)
        self._summary_label.setStyleSheet("line-height: 1.8;")
        layout.addWidget(self._summary_label)

        layout.addStretch(1)

        # Boutons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        btn_pdf = QPushButton("Exporter PDF")
        btn_pdf.setProperty("role", "secondary")
        btn_pdf.setEnabled(False)   # Activé en Phase 7
        btn_pdf.setToolTip("Disponible en Phase 7")

        btn_new = QPushButton("Nouvelle piece")
        btn_new.setProperty("role", "success")
        btn_new.clicked.connect(self._on_new_piece)

        btn_layout.addWidget(btn_pdf)
        btn_layout.addWidget(btn_new, stretch=2)
        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------ actions

    def _on_new_piece(self) -> None:
        """Retourner à l'écran de capture pour traiter une nouvelle pièce."""
        self.new_piece_requested.emit()
