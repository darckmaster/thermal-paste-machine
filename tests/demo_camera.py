"""Démonstration de la Phase 1 — affiche le flux caméra en temps réel.

Utilisation : python tests/demo_camera.py
Appuyer sur 'q' pour quitter.
"""
import sys
import os

# Ajouter le répertoire racine au chemin Python pour pouvoir importer 'modules'
# Ce script est lancé depuis le dossier tests/ ou la racine du projet
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cv2

from modules.camera import Camera
from modules.config import CAMERA_WIDTH, CAMERA_HEIGHT


def main() -> None:
    print("Ouverture de la caméra...")

    # Créer l'objet Camera — lève RuntimeError si la caméra n'est pas trouvée
    try:
        cam = Camera(device_index=0)
    except RuntimeError as e:
        print(f"Erreur : {e}")
        sys.exit(1)

    # Afficher la résolution réellement appliquée (peut différer de la config si non supportée)
    print(f"Caméra ouverte — résolution réelle : {cam.width}×{cam.height}")
    if cam.width != CAMERA_WIDTH or cam.height != CAMERA_HEIGHT:
        print(
            f"  ⚠ Résolution demandée ({CAMERA_WIDTH}×{CAMERA_HEIGHT}) non supportée par cette caméra"
        )
    print("Appuyer sur 'q' pour quitter.")

    try:
        while True:
            # Capturer une image depuis le flux vidéo
            frame = cam.capture()

            # Afficher l'image dans une fenêtre OpenCV nommée "Demo Camera"
            cv2.imshow("Demo Camera — Phase 1", frame)

            # Attendre 1 ms entre chaque image et vérifier si 'q' est pressé
            # ord('q') convertit le caractère 'q' en son code ASCII (113)
            # Le masque 0xFF est nécessaire sur certains systèmes pour isoler l'octet bas
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        # Libérer la caméra et fermer toutes les fenêtres OpenCV — exécuté même en cas d'erreur
        cam.release()
        cv2.destroyAllWindows()
        print("Caméra fermée.")


if __name__ == "__main__":
    main()
