# Tests unitaires pour modules/machine.py
# Le port série est simulé (mocké) — pas besoin de la Geeetech pour lancer ces tests.

import pytest
from unittest.mock import MagicMock, patch, call
from modules.machine import Machine
from modules.config import (
    SERIAL_PORT, SERIAL_BAUDRATE,
    MACHINE_FEEDRATE_XY, MACHINE_FEEDRATE_Z, MACHINE_FEEDRATE_DISPENSE,
)


# ------------------------------------------------------------------ utilitaires

def creer_machine() -> Machine:
    """Crée une instance Machine avec les paramètres de config."""
    return Machine(
        port=SERIAL_PORT,
        baudrate=SERIAL_BAUDRATE,
        feedrate_xy=MACHINE_FEEDRATE_XY,
        feedrate_z=MACHINE_FEEDRATE_Z,
        feedrate_dispense=MACHINE_FEEDRATE_DISPENSE,
    )


def creer_port_serie_mock(reponses: list) -> MagicMock:
    """Crée un faux port série qui retourne les lignes données dans l'ordre.

    Chaque élément de `reponses` est une chaîne qui sera retournée par readline().
    """
    mock = MagicMock()
    mock.is_open = True
    # side_effect = liste de valeurs retournées tour à tour par readline()
    mock.readline.side_effect = [r.encode('utf-8') for r in reponses]
    return mock


# ------------------------------------------------------------------ tests connexion

@patch('modules.machine.time.sleep')           # on neutralise l'attente de 2 s
@patch('modules.machine.serial.Serial')        # on remplace le vrai port série
def test_connect_ouvre_port_et_vide_buffer(mock_serial_class, mock_sleep):
    """connect() doit ouvrir le port avec les bons paramètres et vider le buffer."""
    # connect() envoie 2 commandes : G90 puis M302 S0 → 2 réponses 'ok' attendues
    mock_port = creer_port_serie_mock(['ok\n', 'ok\n'])
    mock_serial_class.return_value = mock_port

    machine = creer_machine()
    machine.connect()

    # Vérifier l'ouverture avec les bons paramètres (timeout=30 pour G28 lent)
    mock_serial_class.assert_called_once_with(SERIAL_PORT, SERIAL_BAUDRATE, timeout=30)
    # Vérifier la pause de 2 secondes pour laisser Marlin booter
    mock_sleep.assert_called_once_with(2)
    # Vérifier que les messages de démarrage ont été vidés
    mock_port.flushInput.assert_called_once()
    # La machine doit se déclarer connectée
    assert machine.is_connected()


@patch('modules.machine.time.sleep')
@patch('modules.machine.serial.Serial')
def test_disconnect_ferme_port(mock_serial_class, mock_sleep):
    """disconnect() doit fermer le port et passer is_connected() à False."""
    # connect() envoie G90 + M302 S0 → 2 réponses 'ok' attendues
    mock_port = creer_port_serie_mock(['ok\n', 'ok\n'])
    mock_serial_class.return_value = mock_port

    machine = creer_machine()
    machine.connect()
    machine.disconnect()

    mock_port.close.assert_called_once()
    assert not machine.is_connected()


def test_is_connected_false_sans_connect():
    """is_connected() retourne False si connect() n'a pas été appelé."""
    machine = creer_machine()
    assert not machine.is_connected()


# ------------------------------------------------------------------ tests send_command

@patch('modules.machine.time.sleep')
@patch('modules.machine.serial.Serial')
def test_send_command_attend_ok(mock_serial_class, mock_sleep):
    """send_command() doit lire les lignes jusqu'à trouver 'ok'."""
    # Simuler une réponse multi-ligne (comme Marlin peut en envoyer)
    mock_port = creer_port_serie_mock([
        'ok\n',             # réponse au G90 dans connect()
        'ok\n',             # réponse au M302 S0 dans connect()
        'echo:busy\n',      # Marlin peut envoyer des lignes avant 'ok'
        'ok\n',             # confirmation finale de la commande G28
    ])
    mock_serial_class.return_value = mock_port

    machine = creer_machine()
    machine.connect()
    lignes = machine.send_command('G28')

    # On doit récupérer toutes les lignes jusqu'au 'ok'
    assert 'echo:busy' in lignes
    assert 'ok' in lignes


@patch('modules.machine.time.sleep')
@patch('modules.machine.serial.Serial')
def test_send_command_timeout_leve_exception(mock_serial_class, mock_sleep):
    """send_command() doit lever TimeoutError si readline() retourne vide (timeout série)."""
    mock_port = creer_port_serie_mock([
        'ok\n',   # réponse au G90 dans connect()
        'ok\n',   # réponse au M302 S0 dans connect()
        '',       # ligne vide = timeout série simulé
    ])
    mock_serial_class.return_value = mock_port

    machine = creer_machine()
    machine.connect()

    with pytest.raises(TimeoutError):
        machine.send_command('G1 X50 Y50 F3000')


def test_send_command_sans_connect_leve_runtime_error():
    """send_command() doit lever RuntimeError si la machine n'est pas connectée."""
    machine = creer_machine()
    with pytest.raises(RuntimeError):
        machine.send_command('G28')


# ------------------------------------------------------------------ tests mouvements

@patch('modules.machine.time.sleep')
@patch('modules.machine.serial.Serial')
def test_move_to_envoie_g1_xy_z_et_m400(mock_serial_class, mock_sleep):
    """move_to() doit envoyer G1 XY, G1 Z et M400 dans cet ordre."""
    # Préparer assez de 'ok' : 2 pour connect (G90 + M302) + 3 pour move_to (XY, Z, M400)
    mock_port = creer_port_serie_mock(['ok\n'] * 5)
    mock_serial_class.return_value = mock_port

    machine = creer_machine()
    machine.connect()
    machine.move_to(x=10.0, y=20.0, z=1.0)

    # Récupérer toutes les commandes envoyées via write()
    commandes_envoyees = [
        c.args[0].decode('utf-8').strip()
        for c in mock_port.write.call_args_list
    ]

    assert 'G90' in commandes_envoyees                          # G90 initial (connect)
    assert 'G1 X10.000 Y20.000 F3000' in commandes_envoyees    # déplacement XY
    assert f'G1 Z1.000 F{MACHINE_FEEDRATE_Z}' in commandes_envoyees  # déplacement Z lent
    assert 'M400' in commandes_envoyees                          # attente fin de mouvement


@patch('modules.machine.time.sleep')
@patch('modules.machine.serial.Serial')
def test_dispense_entoure_de_g91_g90(mock_serial_class, mock_sleep):
    """dispense() doit utiliser le mode relatif G91 et revenir en G90 après."""
    # 2 ok (connect : G90 + M302) + 4 ok (dispense : G91, G1 E, M400, G90)
    mock_port = creer_port_serie_mock(['ok\n'] * 6)
    mock_serial_class.return_value = mock_port

    machine = creer_machine()
    machine.connect()
    machine.dispense(amount_mm=2.5)

    commandes_envoyees = [
        c.args[0].decode('utf-8').strip()
        for c in mock_port.write.call_args_list
    ]

    assert 'G91' in commandes_envoyees                                      # mode relatif
    assert f'G1 E2.500 F{MACHINE_FEEDRATE_DISPENSE}' in commandes_envoyees  # extrusion
    assert 'M400' in commandes_envoyees                                      # attente
    assert commandes_envoyees[-1] == 'G90'                                   # retour absolu


# ------------------------------------------------------------------ test move_and_dispense

@patch('modules.machine.time.sleep')
@patch('modules.machine.serial.Serial')
def test_move_and_dispense_envoie_m83_g1_m400_m82(mock_serial_class, mock_sleep):
    """move_and_dispense() doit envoyer M83, G1 XYE, M400, M82 dans cet ordre."""
    # 2 ok (connect) + 4 ok (move_and_dispense : M83, G1, M400, M82)
    mock_port = creer_port_serie_mock(['ok\n'] * 6)
    mock_serial_class.return_value = mock_port

    machine = creer_machine()
    machine.connect()
    machine.move_and_dispense(x=25.0, y=10.0, amount_mm=1.5)

    commandes_envoyees = [
        c.args[0].decode('utf-8').strip()
        for c in mock_port.write.call_args_list
    ]

    assert 'M83' in commandes_envoyees                          # E relatif
    assert 'G1 X25.000 Y10.000 E1.5000 F3000' in commandes_envoyees  # move + extrusion
    assert 'M400' in commandes_envoyees                          # attente fin
    assert 'M82' in commandes_envoyees                          # retour E absolu


# ------------------------------------------------------------------ test sécurité

@patch('modules.machine.time.sleep')
@patch('modules.machine.serial.Serial')
def test_emergency_stop_ecrit_m112_directement(mock_serial_class, mock_sleep):
    """emergency_stop() doit écrire M112 directement sans attendre 'ok'."""
    mock_port = creer_port_serie_mock(['ok\n', 'ok\n'])  # G90 + M302 dans connect()
    mock_serial_class.return_value = mock_port

    machine = creer_machine()
    machine.connect()
    machine.emergency_stop()

    # M112 doit avoir été écrit directement (pas via send_command)
    commandes = [c.args[0] for c in mock_port.write.call_args_list]
    assert b'M112\n' in commandes


def test_emergency_stop_sans_connexion_ne_plante_pas():
    """emergency_stop() ne doit pas lever d'exception si non connecté."""
    machine = creer_machine()
    machine.emergency_stop()  # ne doit pas planter
