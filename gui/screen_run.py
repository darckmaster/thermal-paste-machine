# Écran 3 — Exécution de la dépose
# Affiche la progression et permet l'arrêt d'urgence
# Phase 4 : placeholder — la communication machine sera intégrée en Phase 6

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer


class ScreenRun(QWidget):
    """Écran 3 : suivi en temps réel de la dépose en cours.

    Phase 4 (actuel) : placeholder — simule une progression avec un timer.
    Phase 6 : intégration réelle avec Machine et PathPlanner.
    """

    # Signal émis quand la dépose est terminée (ou annulée)
    run_finished = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        # Timer pour simuler une progression en Phase 4
        self._sim_timer = QTimer()
        self._sim_timer.timeout.connect(self._simulate_progress)
        self._sim_progress = 0
        self._setup_ui()

    def start_run(self, zone: object, quantity: float) -> None:
        """Démarrer l'exécution avec la zone et la quantité configurées."""
        self._zone = zone
        self._quantity = quantity
        self._sim_progress = 0
        self._progress_bar.setValue(0)
        self._status_label.setText("Dépose en cours...")
        self._btn_stop.setEnabled(True)
        self._btn_done.setEnabled(False)

        # En Phase 4 : simulation d'une progression sur 3 secondes
        # En Phase 6 : remplacer par les appels réels à Machine + PathPlanner
        self._sim_timer.start(150)  # avancer de 5% toutes les 150 ms ≈ 3 s au total

    # ------------------------------------------------------------------ interface

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(10)

        # Titre
        title = QLabel("Depose en cours")
        title.setProperty("role", "title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Espace visuel
        layout.addStretch(1)

        # Message d'état (mis à jour pendant l'exécution)
        self._status_label = QLabel("En attente de lancement...")
        self._status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._status_label)

        # Barre de progression
        self._progress_bar = QProgressBar()
        self._progress_bar.setMinimum(0)
        self._progress_bar.setMaximum(100)
        self._progress_bar.setValue(0)
        self._progress_bar.setMinimumHeight(40)
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #444;
                border-radius: 4px;
                text-align: center;
                font-size: 14px;
            }
            QProgressBar::chunk {
                background-color: #2d5f8a;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self._progress_bar)

        # Note placeholder
        note = QLabel(
            "Phase 6 : integration machine a implémenter\n"
            "Pour l'instant : simulation de la progression"
        )
        note.setProperty("role", "status")
        note.setAlignment(Qt.AlignCenter)
        layout.addWidget(note)

        layout.addStretch(1)

        # Boutons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self._btn_stop = QPushButton("Arret d'urgence")
        self._btn_stop.setProperty("role", "danger")
        self._btn_stop.clicked.connect(self._on_emergency_stop)

        self._btn_done = QPushButton("Voir le rapport")
        self._btn_done.setProperty("role", "success")
        self._btn_done.setEnabled(False)  # Activé quand la dépose est terminée
        self._btn_done.clicked.connect(self._on_done)

        btn_layout.addWidget(self._btn_stop)
        btn_layout.addWidget(self._btn_done)
        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------ actions

    def _simulate_progress(self) -> None:
        """Avancer la barre de progression (simulation Phase 4)."""
        self._sim_progress += 5
        self._progress_bar.setValue(self._sim_progress)
        self._status_label.setText(f"Depose en cours... {self._sim_progress}%")

        if self._sim_progress >= 100:
            self._sim_timer.stop()
            self._status_label.setText("Depose terminee !")
            self._btn_stop.setEnabled(False)
            self._btn_done.setEnabled(True)

    def _on_emergency_stop(self) -> None:
        """Arrêt d'urgence — stopper la simulation et signaler la fin."""
        self._sim_timer.stop()
        # En Phase 6 : appeler machine.emergency_stop() ici
        self._status_label.setText("Arret d'urgence declenche !")
        self._btn_stop.setEnabled(False)
        self._btn_done.setEnabled(True)

    def _on_done(self) -> None:
        """Navigation vers l'écran de rapport."""
        self.run_finished.emit()
