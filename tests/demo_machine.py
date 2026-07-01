# Démonstration interactive de modules/machine.py sur la vraie Geeetech.
# À lancer AU BOULOT avec la machine branchée en USB.
#
# Utilisation :
#   python3 tests/demo_machine.py

import sys
import os

# Permettre les imports depuis la racine du projet
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.machine import Machine
from modules.config import (
    SERIAL_PORT, SERIAL_BAUDRATE,
    MACHINE_FEEDRATE_XY, MACHINE_FEEDRATE_Z, MACHINE_FEEDRATE_DISPENSE,
    DISPENSE_Z_HEIGHT_MM,
)


def demander_confirmation(question: str) -> bool:
    """Pose une question oui/non à l'utilisateur et retourne True si oui."""
    reponse = input(f"\n{question} [o/N] : ").strip().lower()
    return reponse in ('o', 'oui', 'y', 'yes')


def main():
    print("=" * 60)
    print("  Démonstration machine.py — Geeetech + Marlin 1.1.8")
    print(f"  Port : {SERIAL_PORT}  |  Baudrate : {SERIAL_BAUDRATE}")
    print("=" * 60)

    # Créer l'objet Machine avec les paramètres de config
    machine = Machine(
        port=SERIAL_PORT,
        baudrate=SERIAL_BAUDRATE,
        feedrate_xy=MACHINE_FEEDRATE_XY,
        feedrate_z=MACHINE_FEEDRATE_Z,
        feedrate_dispense=MACHINE_FEEDRATE_DISPENSE,
    )

    # ------------------------------------------------------------------ connexion
    print("\n[1/5] Connexion au port série...")
    print("      (La carte va resetter automatiquement — attente 2 s)")
    try:
        machine.connect()
        print("      ✓ Connecté !")
    except Exception as e:
        print(f"      ✗ Erreur de connexion : {e}")
        print(f"      Vérifier que /dev/ttyUSB0 existe et que tu es dans le groupe dialout.")
        print(f"      Commande : sudo usermod -aG dialout $USER  (puis se reconnecter)")
        return

    # ------------------------------------------------------------------ homing
    if demander_confirmation("[2/5] Lancer le HOMING (G28) ? Les axes vont revenir à zéro."):
        print("      Homing en cours... (peut durer 30-60 secondes)")
        try:
            machine.home()
            print("      ✓ Homing terminé — position (0, 0, 0)")
        except Exception as e:
            print(f"      ✗ Erreur pendant le homing : {e}")
            machine.disconnect()
            return
    else:
        print("      Homing ignoré — ATTENTION : la position machine est inconnue.")
        print("      Les déplacements absolus risquent de sortir de la zone de travail.")

    # ------------------------------------------------------------------ déplacement test
    if demander_confirmation("[3/5] Test de déplacement vers (30, 30, 5) mm ?"):
        print("      Déplacement en cours...")
        try:
            machine.move_to(x=30.0, y=30.0, z=5.0)
            print("      ✓ Position atteinte : X=30mm Y=30mm Z=5mm")
        except Exception as e:
            print(f"      ✗ Erreur pendant le déplacement : {e}")

    # ------------------------------------------------------------------ dépose test
    if demander_confirmation(
        "[4/5] Test de dépose ? (E avance de 10 mm — SANS seringue si possible)"
    ):
        print("      Dépose en cours...")
        try:
            machine.dispense(amount_mm=10.0)
            print("      ✓ Axe E avancé de 10 mm")
            # Rétraction pour revenir à la position initiale
            if demander_confirmation("      Rétracter de 10 mm pour revenir à la position initiale ?"):
                machine.dispense(amount_mm=-10.0)
                print("      ✓ Rétraction faite")
        except Exception as e:
            print(f"      ✗ Erreur pendant la dépose : {e}")

    # ------------------------------------------------------------------ déconnexion
    print("\n[5/5] Déconnexion...")
    machine.disconnect()
    print("      ✓ Port série fermé.")
    print("\nDémonstration terminée.")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterruption clavier détectée — arrêt d'urgence !")
        # On ne peut pas appeler emergency_stop() ici car la variable machine
        # n'est pas accessible depuis ce bloc. Redémarrer la Geeetech manuellement.
        print("Redémarre la Geeetech manuellement si elle est encore en mouvement.")
        sys.exit(1)
