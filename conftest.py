import sys
import os

# Ajouter le répertoire racine au chemin Python pour que les imports "modules.xxx" fonctionnent
# quand pytest est lancé depuis n'importe quel sous-dossier du projet
sys.path.insert(0, os.path.dirname(__file__))
