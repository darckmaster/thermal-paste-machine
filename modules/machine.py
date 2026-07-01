# Communication série avec la Geeetech via le protocole G-code Marlin 1.x
# Firmware confirmé : Marlin 1.1.8 — port /dev/ttyUSB0 — 250000 baud

import serial   # Librairie pyserial pour la communication série USB
import time     # Pour la pause après l'ouverture du port (reset Arduino)
from typing import Optional


class Machine:
    """Gère la connexion et les commandes G-code vers la Geeetech (Marlin 1.1.8).

    Utilisation typique :
        machine = Machine(port='/dev/ttyUSB0', baudrate=115200, ...)
        machine.connect()
        machine.home()
        machine.move_to(x=50.0, y=30.0, z=1.0)
        machine.dispense(amount_mm=2.0)
        machine.disconnect()
    """

    def __init__(
        self,
        port: str,
        baudrate: int,
        feedrate_xy: int,
        feedrate_z: int,
        feedrate_dispense: int,
    ) -> None:
        # Paramètres de connexion série — identiques à ce que PuTTY utilisait
        self._port = port
        self._baudrate = baudrate

        # Vitesses de déplacement en mm/min (F dans le G-code)
        # XY : rapide (3000 mm/min), Z : lent (max physique 120 mm/min), E : très lent
        self._feedrate_xy = feedrate_xy
        self._feedrate_z = feedrate_z
        self._feedrate_dispense = feedrate_dispense

        # Objet port série — None tant que connect() n'a pas été appelé
        self._serial: Optional[serial.Serial] = None

    # ------------------------------------------------------------------ connexion

    def connect(self) -> None:
        """Ouvre le port série et attend la fin du boot Marlin.

        L'ouverture du port déclenche un reset automatique de la carte Arduino
        (via la ligne DTR). Marlin envoie alors ~20 lignes de config au démarrage.
        On attend 2 secondes puis on vide le buffer pour ignorer ces messages.
        """
        # Ouvrir le port avec un timeout de 30s — nécessaire pour G28 (homing lent)
        self._serial = serial.Serial(self._port, self._baudrate, timeout=30)

        # Attendre que Marlin finisse son boot (il envoie des messages pendant ~1,5 s)
        time.sleep(2)

        # Vider le buffer d'entrée — les messages de démarrage ne sont pas exploitables
        self._serial.flushInput()

        # Forcer le mode de positionnement absolu dès la connexion
        # G90 = les coordonnées envoyées sont relatives à l'origine machine (0,0,0)
        self.send_command('G90')

        # Autoriser l'extrusion à froid — Marlin bloque l'axe E par défaut si la
        # buse n'est pas chauffée (~170°C). On utilise l'axe E pour pousser une
        # seringue, pas pour fondre du plastique → on supprime cette protection.
        # M302 S0 = température minimale d'extrusion = 0°C (aucune restriction)
        self.send_command('M302 S0')

    def disconnect(self) -> None:
        """Ferme proprement le port série."""
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._serial = None

    def is_connected(self) -> bool:
        """Retourne True si le port série est ouvert et la machine joignable."""
        return self._serial is not None and self._serial.is_open

    # ------------------------------------------------------------------ protocole

    def send_command(self, cmd: str) -> list:
        """Envoie une commande G-code et attend la réponse 'ok' de Marlin.

        Marlin traite les commandes dans l'ordre et répond toujours 'ok'
        quand une commande est acceptée dans son buffer de planification.
        Pour attendre la FIN d'un mouvement, utiliser M400 après le G1.

        Retourne la liste de toutes les lignes reçues avant le 'ok'.
        Lève RuntimeError si non connecté, TimeoutError si pas de réponse en 30 s.
        """
        if not self.is_connected():
            raise RuntimeError("Machine non connectée — appeler connect() d'abord")

        # Encoder la commande en bytes et ajouter le saut de ligne (protocole Marlin)
        self._serial.write((cmd + '\n').encode('utf-8'))

        # Forcer l'envoi immédiat des octets depuis le buffer du système d'exploitation
        self._serial.flush()

        lignes_reponse = []
        while True:
            # Lire une ligne (bloque jusqu'à '\n' ou jusqu'au timeout de 30 s)
            ligne_brute = self._serial.readline()
            ligne = ligne_brute.decode('utf-8', errors='replace').strip()

            # Stocker toutes les lignes non vides (utile pour le debug)
            if ligne:
                lignes_reponse.append(ligne)

            # 'ok' = Marlin a accepté la commande, on peut envoyer la suivante
            if ligne.startswith('ok'):
                break

            # Ligne vide = readline() a expiré sans recevoir de '\n' → timeout
            if ligne == '':
                raise TimeoutError(
                    f"Pas de réponse 'ok' de Marlin pour la commande : {cmd}"
                )

        return lignes_reponse

    # ------------------------------------------------------------------ mouvements

    def home(self) -> None:
        """Ramène tous les axes à leur butée de fin de course (G28).

        Cette opération peut prendre 30 à 60 secondes — le timeout série de 30 s
        est configuré pour l'attendre. Après le homing, la position est (0, 0, 0).
        """
        # G28 sans argument = homing de tous les axes (X, Y, Z)
        self.send_command('G28')

    def move_to(self, x: float, y: float, z: float) -> None:
        """Déplace la tête vers la position absolue (x, y, z) en millimètres.

        XY et Z sont envoyés séparément car leurs vitesses max sont très différentes.
        M400 attend que TOUS les mouvements en cours soient physiquement terminés
        avant de retourner 'ok' — essentiel avant une dépose de pâte.
        """
        # Déplacement XY rapide — les deux axes se déplacent en même temps
        self.send_command(f'G1 X{x:.3f} Y{y:.3f} F{self._feedrate_xy}')

        # Déplacement Z séparé avec sa propre vitesse (max 120 mm/min sur Geeetech)
        self.send_command(f'G1 Z{z:.3f} F{self._feedrate_z}')

        # Attendre la fin physique de tous les mouvements avant de continuer
        self.send_command('M400')

    def dispense(self, amount_mm: float) -> None:
        """Pousse la seringue de amount_mm millimètres d'axe E.

        Un amount_mm positif pousse la pâte vers la pièce.
        Un amount_mm négatif aspire (rétraction — utile pour couper le filet).

        Le mode G91 (relatif) est utilisé pour que chaque appel soit indépendant :
        on indique un déplacement relatif, pas une position absolue de l'axe E.
        """
        # G91 = mode relatif : E+2.0 signifie "avancer de 2 mm" (pas "aller à E=2")
        self.send_command('G91')

        # Pousser (ou rétracter) la seringue à la vitesse de dépose configurée
        self.send_command(f'G1 E{amount_mm:.3f} F{self._feedrate_dispense}')

        # Attendre la fin physique de l'extrusion avant de bouger ailleurs
        self.send_command('M400')

        # Revenir en mode absolu pour ne pas perturber les move_to() suivants
        self.send_command('G90')

    def move_and_dispense(self, x: float, y: float, amount_mm: float) -> None:
        """Déplace la tête en XY tout en déposant de la pâte simultanément.

        Envoie un seul G1 avec X, Y et E — les trois axes bougent en même temps.
        La pâte est donc déposée de façon continue le long du segment, pas en un
        seul blob à l'arrivée. Z doit déjà être à la hauteur de dépose avant cet appel.

        M83 = mode relatif pour E uniquement : E{amount} est un incrément, pas une position.
        M82 en fin de méthode remet E en mode absolu pour cohérence avec le reste du code.
        """
        # Passer E en mode relatif (M83) tout en gardant XYZ en mode absolu (G90)
        # C'est différent de G91 qui passerait TOUS les axes en relatif
        self.send_command('M83')

        # Déplacement XY absolu + extrusion E relative dans la même commande
        # La vitesse F s'applique au déplacement XY ; E suit proportionnellement
        self.send_command(
            f'G1 X{x:.3f} Y{y:.3f} E{amount_mm:.4f} F{self._feedrate_xy}'
        )

        # Attendre la fin physique du mouvement avant de continuer
        self.send_command('M400')

        # Remettre E en mode absolu pour que dispense() continue de fonctionner normalement
        self.send_command('M82')

    # ------------------------------------------------------------------ sécurité

    def emergency_stop(self) -> None:
        """Arrêt d'urgence immédiat — coupe tous les moteurs instantanément (M112).

        M112 est traité hors-file par Marlin : il interrompt tout immédiatement.
        Il ne retourne PAS de 'ok', c'est pourquoi on écrit directement sur le port.
        Après M112, la machine doit être redémarrée physiquement (coupure/remise sous tension).
        """
        if not self.is_connected():
            return

        # Envoi direct sans passer par send_command (qui attendrait un 'ok' qui ne vient pas)
        self._serial.write(b'M112\n')
        self._serial.flush()
