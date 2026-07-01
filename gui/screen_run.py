# Écran 3 — Exécution de la dépose
# Lance la trajectoire G-code dans un thread séparé pour ne pas bloquer l'interface.
# L'utilisateur voit la progression en temps réel et peut déclencher l'arrêt d'urgence.

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar
)
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QThread, QObject

from modules.machine import Machine
from modules.path_planner import PathPlanner
from modules.config import DISPENSE_Z_HEIGHT_MM, MACHINE_Z_TRAVEL_MM


# ================================================================ worker thread

class RunWorker(QObject):
    """Exécute la trajectoire G-code dans un thread séparé (QThread).

    Pourquoi un thread séparé ?
    Les commandes G-code bloquent jusqu'à recevoir 'ok' de Marlin (jusqu'à 30 s pour G28).
    Si on les exécutait dans le thread Qt principal, l'interface serait complètement gelée
    pendant toute la dépose — le bouton d'arrêt d'urgence ne répondrait plus.

    Le worker s'exécute dans le thread, émet des signaux Qt pour communiquer avec
    l'interface — les signaux traversent la frontière inter-thread de façon sécurisée.
    """

    # Signaux émis depuis le thread vers l'interface Qt
    progress_updated = pyqtSignal(int, int, str)  # (étape courante, total, description)
    finished = pyqtSignal()                        # Dépose terminée normalement
    error_occurred = pyqtSignal(str)               # Erreur machine (timeout, déconnexion...)

    def __init__(self, machine: Machine, steps: list) -> None:
        super().__init__()
        self._machine = machine
        self._steps = steps
        # Flag d'arrêt — mis à True par stop() depuis le thread principal
        # volatile implicite car Python GIL garantit la visibilité inter-threads
        self._should_stop = False

    @pyqtSlot()
    def run(self) -> None:
        """Point d'entrée du thread — connexion + exécution des steps + déconnexion."""
        total = len(self._steps)

        # --- Connexion à la machine ---
        # Cette opération prend ~2 s (reset Arduino + boot Marlin) mais elle est
        # dans le thread → l'interface reste réactive pendant ce temps
        try:
            self.progress_updated.emit(0, total, "Connexion a la machine...")
            self._machine.connect()
        except Exception as e:
            self.error_occurred.emit(f"Connexion impossible : {e}")
            return

        # --- Exécution des steps ---
        try:
            for i, step in enumerate(self._steps):
                # Vérifier si l'utilisateur a demandé l'arrêt
                if self._should_stop:
                    break

                description = self._describe_step(step, i, total)
                self.progress_updated.emit(i, total, description)

                self._execute_step(step)

                self.progress_updated.emit(i + 1, total, description)

        except Exception as e:
            self.error_occurred.emit(f"Erreur pendant la depose : {e}")
        finally:
            # Toujours déconnecter proprement, même en cas d'erreur
            try:
                self._machine.disconnect()
            except Exception:
                pass  # On ignore les erreurs de déconnexion

        if not self._should_stop:
            self.finished.emit()

    def _execute_step(self, step: dict) -> None:
        """Exécuter un step selon son type (travel ou dispense)."""
        if step["type"] == "travel":
            # Déplacement rapide sans dépôt de pâte
            self._machine.move_to(step["x"], step["y"], step["z"])

        elif step["type"] == "dispense":
            # Déplacement lent avec extrusion simultanée
            # Z est déjà à la bonne hauteur (step travel précédent) — on ne bouge que XY+E
            self._machine.move_and_dispense(step["x"], step["y"], step["amount"])

    def _describe_step(self, step: dict, i: int, total: int) -> str:
        """Générer un message lisible décrivant le step en cours."""
        if step["type"] == "travel":
            return f"Etape {i+1}/{total} — deplacement vers ({step['x']:.1f}, {step['y']:.1f}) mm"
        else:
            return (
                f"Etape {i+1}/{total} — depose "
                f"vers ({step['x']:.1f}, {step['y']:.1f}) mm "
                f"({step['amount']:.3f} mm E)"
            )

    def stop(self) -> None:
        """Demander l'arrêt après le step courant (appelé depuis le thread principal)."""
        self._should_stop = True


# ================================================================ écran Qt

class ScreenRun(QWidget):
    """Écran 3 : suivi en temps réel de la dépose.

    Crée un QThread + RunWorker pour exécuter la trajectoire G-code sans bloquer l'UI.
    Le bouton d'arrêt d'urgence appelle machine.emergency_stop() immédiatement (hors thread).
    """

    run_finished = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._machine: Machine | None = None
        self._thread: QThread | None = None
        self._worker: RunWorker | None = None
        self._setup_ui()

    def start_run(self, machine: Machine, points_mm: list, quantity: float) -> None:
        """Démarrer l'exécution : générer la trajectoire et lancer le thread."""
        self._machine = machine

        # Générer la trajectoire à partir des points tracés par l'utilisateur
        planner = PathPlanner(
            line_spacing_mm=3.0,         # Non utilisé pour generate_path_from_line
            z_dispense_mm=DISPENSE_Z_HEIGHT_MM,
            z_travel_mm=MACHINE_Z_TRAVEL_MM,
            amount_per_mm=quantity,       # Quantité pâte réglée par le slider
        )
        steps = planner.generate_path_from_line(points_mm)

        # Réinitialiser l'affichage
        self._progress_bar.setValue(0)
        self._progress_bar.setMaximum(len(steps))
        self._status_label.setText("Connexion a la machine en cours...")
        self._btn_stop.setEnabled(True)
        self._btn_done.setEnabled(False)

        # Créer le thread et le worker
        # QThread gère le cycle de vie du thread OS
        self._thread = QThread()
        self._worker = RunWorker(machine, steps)

        # Déplacer le worker dans le thread — ses méthodes s'exécuteront dans ce thread
        self._worker.moveToThread(self._thread)

        # Connecter les signaux du worker à l'interface (traversée inter-thread sécurisée)
        self._thread.started.connect(self._worker.run)
        self._worker.progress_updated.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error_occurred.connect(self._on_error)

        # Nettoyer le thread quand le worker a terminé
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        # Démarrer le thread → déclenche self._worker.run() via le signal started
        self._thread.start()

    # ------------------------------------------------------------------ interface

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(10)

        title = QLabel("Depose en cours")
        title.setProperty("role", "title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        layout.addStretch(1)

        # Message d'état mis à jour par le worker
        self._status_label = QLabel("En attente de lancement...")
        self._status_label.setAlignment(Qt.AlignCenter)
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        # Barre de progression (nombre de steps)
        self._progress_bar = QProgressBar()
        self._progress_bar.setMinimum(0)
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

        layout.addStretch(1)

        # Boutons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self._btn_stop = QPushButton("ARRET D'URGENCE")
        self._btn_stop.setProperty("role", "danger")
        self._btn_stop.clicked.connect(self._on_emergency_stop)

        self._btn_done = QPushButton("Voir le rapport")
        self._btn_done.setProperty("role", "success")
        self._btn_done.setEnabled(False)
        self._btn_done.clicked.connect(self._on_done)

        btn_layout.addWidget(self._btn_stop)
        btn_layout.addWidget(self._btn_done)
        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------ slots (signaux reçus du worker)

    @pyqtSlot(int, int, str)
    def _on_progress(self, current: int, total: int, description: str) -> None:
        """Mettre à jour la barre de progression et le message d'état."""
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(current)
        self._status_label.setText(description)

    @pyqtSlot()
    def _on_finished(self) -> None:
        """La dépose s'est terminée normalement."""
        self._status_label.setText("Depose terminee avec succes !")
        self._btn_stop.setEnabled(False)
        self._btn_done.setEnabled(True)

    @pyqtSlot(str)
    def _on_error(self, message: str) -> None:
        """Une erreur s'est produite pendant l'exécution."""
        self._status_label.setText(f"Erreur : {message}")
        self._btn_stop.setEnabled(False)
        self._btn_done.setEnabled(True)

    # ------------------------------------------------------------------ actions boutons

    def _on_emergency_stop(self) -> None:
        """Arrêt d'urgence : M112 immédiat + arrêt du worker."""
        # 1. Envoyer M112 directement sur le port série (hors thread, immédiat)
        #    emergency_stop() écrit directement sur le port sans attendre 'ok'
        if self._machine and self._machine.is_connected():
            self._machine.emergency_stop()

        # 2. Demander au worker de ne plus exécuter de steps supplémentaires
        if self._worker:
            self._worker.stop()

        self._status_label.setText(
            "ARRET D'URGENCE declenche !\n"
            "Redemarrer la machine avant le prochain cycle."
        )
        self._btn_stop.setEnabled(False)
        self._btn_done.setEnabled(True)

    def _on_done(self) -> None:
        """Naviguer vers l'écran de rapport."""
        self.run_finished.emit()
