# Fixtures partagées par les tests qui ont besoin d'une caméra réelle.
#
# Problème résolu ici : sur un PC de développement, plusieurs caméras répondent — la
# webcam intégrée et la caméra USB du projet. Se fier à un index configuré ne prouve
# rien : si cet index est faux, les tests passent en validant le MAUVAIS matériel, sans
# que rien ne le signale. Le projet s'est fait piéger deux fois par ce mécanisme (le
# blocage ChArUco du 2026-07-29, et la fixture codée en dur corrigée le 2026-08-01).
#
# Critère retenu : la bonne caméra est celle qui **voit le plateau**, donc celle où l'on
# détecte au moins un marqueur ArUco. C'est un critère objectif, vérifiable à l'exécution
# et indépendant de toute configuration. La webcam intégrée, qui filme la pièce ou
# l'opérateur, n'y répond jamais.
#
# La caméra n'est sollicitée qu'UNE FOIS pour toute la session de test (scope="session")
# et l'image capturée est ensuite réutilisée par tous les tests qui n'ont besoin que de
# pixels — ce qui les rend à la fois plus rapides et déterministes.

import pytest

from modules.camera import Camera
from modules.config import ARUCO_DICT_ID, ARUCO_MARKER_SIZE_MM, CAMERA_INDEX
from modules.vision import VisionProcessor


# Nombre de captures tentées sur une caméra avant de conclure qu'elle ne voit pas le
# plateau. Une seule ne suffit pas : les premières images d'une webcam sont souvent
# sombres ou floues (auto-exposition, autofocus), et un marqueur peut n'apparaître
# net qu'au bout de quelques trames.
_ESSAIS_PAR_CAMERA = 5


class PlateauCapture:
    """Résultat de la sélection : la caméra retenue et l'image qu'elle a fournie."""

    def __init__(self, index, image, width, height, marker_ids) -> None:
        # Index OpenCV de la caméra qui a réellement vu le plateau
        self.index = index
        # Image BGR capturée, réutilisée par tous les tests de la session
        self.image = image
        # Résolution réellement négociée avec cette caméra
        self.width = width
        self.height = height
        # IDs des marqueurs ArUco trouvés — utile pour comprendre un échec de test
        self.marker_ids = marker_ids

    def __repr__(self) -> str:
        return (
            f"PlateauCapture(camera {self.index}, {self.width}x{self.height}, "
            f"marqueurs {self.marker_ids})"
        )


def _essayer_camera(index: int, vision: VisionProcessor):
    """Ouvre une caméra et cherche des marqueurs ArUco dans son flux.

    Retourne un PlateauCapture si au moins un marqueur est trouvé, None sinon.
    La caméra est refermée dans tous les cas, y compris en cas d'échec : laisser un
    flux ouvert empêcherait les tests suivants d'y accéder.
    """
    try:
        cam = Camera(index)
    except RuntimeError:
        # Caméra absente, occupée par un autre logiciel, ou index fantôme
        return None

    try:
        for _ in range(_ESSAIS_PAR_CAMERA):
            try:
                frame = cam.capture()
            except RuntimeError:
                return None

            marqueurs = vision.detect_markers(frame)
            if marqueurs:
                # copy() : l'image doit survivre au release() de la caméra, or OpenCV
                # peut réutiliser le tampon de la dernière trame
                return PlateauCapture(
                    index, frame.copy(), cam.width, cam.height, sorted(marqueurs)
                )
        return None
    finally:
        cam.release()


@pytest.fixture(scope="session")
def plateau_capture() -> PlateauCapture:
    """Sélectionne la caméra qui voit le plateau et capture une image, une seule fois.

    Ordre d'essai :
      1. la caméra configurée (CAMERA_INDEX) — dans le cas nominal on s'arrête là, et
         aucune autre caméra de la machine n'est sollicitée ;
      2. les autres caméras détectées, si la configurée ne voit aucun marqueur.

    Cet ordre est important : il évite d'allumer inutilement la webcam intégrée du PC
    quand la configuration est correcte, tout en rattrapant le cas où elle ne l'est pas.

    Les tests qui en dépendent sont ignorés (`skip`) si aucune caméra ne voit de
    marqueur — par exemple sur une machine sans caméra, ou quand le plateau n'est pas
    devant l'objectif. Un échec serait trompeur : ce n'est pas le code qui est en cause.
    """
    vision = VisionProcessor(ARUCO_DICT_ID, ARUCO_MARKER_SIZE_MM)

    # 1) La caméra configurée d'abord
    if CAMERA_INDEX is not None:
        capture = _essayer_camera(CAMERA_INDEX, vision)
        if capture is not None:
            return capture

    # 2) Repli : balayer les autres caméras présentes
    for index in Camera.list_devices():
        if index == CAMERA_INDEX:
            continue  # déjà essayée ci-dessus
        capture = _essayer_camera(index, vision)
        if capture is not None:
            return capture

    pytest.skip(
        "Aucune caméra ne voit de marqueur ArUco — brancher la caméra du projet et "
        "placer le plateau dans son champ pour exécuter les tests caméra"
    )


@pytest.fixture
def camera(plateau_capture: PlateauCapture) -> Camera:
    """Une caméra ouverte sur l'index VALIDÉ, pour les tests qui ont besoin d'un flux.

    La plupart des tests n'en ont pas besoin et se contentent de `plateau_capture.image` :
    n'utiliser cette fixture que pour vérifier un comportement de l'objet Camera
    lui-même (ouverture, libération, lecture répétée).
    """
    cam = Camera(plateau_capture.index)
    yield cam
    # Libérer même si le test a échoué ; release() est sans danger s'il a déjà été appelé
    cam.release()
