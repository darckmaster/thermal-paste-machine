# Point d'entrée principal de l'application
# Lancer avec : python3 main.py

import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from gui.app import MainApp


def main() -> None:
    """Créer l'application Qt et afficher la fenêtre principale."""
    # QApplication doit être créé avant tout widget Qt
    app = QApplication(sys.argv)

    # Désactiver le scaling automatique Qt sur les écrans haute densité
    # (l'écran tactile 7" du RPi est en 800×480 natif — pas de DPI scaling nécessaire)
    app.setAttribute(Qt.AA_DisableHighDpiScaling, True)

    window = MainApp()

    # Démarrer en fenêtre maximisée — la barre des tâches reste accessible
    # Sur le RPi avec l'écran tactile, remplacer par window.showFullScreen()
    window.showMaximized()

    # Proposer de reprendre un travail interrompu, s'il en existe un. APRÈS le show() :
    # une boîte de dialogue modale avant l'affichage laisserait l'opérateur devant un
    # dialogue flottant, sans la fenêtre qui lui donne son contexte.
    window.propose_resume()

    # Démarrer la boucle d'événements Qt — bloque jusqu'à fermeture de la fenêtre
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
