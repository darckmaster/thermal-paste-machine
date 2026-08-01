import pytest
import numpy as np

from modules.camera import Camera


@pytest.fixture
def camera():
    """Fixture pytest : ouvre la caméra avant le test, la ferme après dans tous les cas."""
    # Tenter d'ouvrir la caméra — si elle n'est pas branchée, on saute le test plutôt que de le faire échouer
    try:
        cam = Camera(device_index=0)
    except RuntimeError:
        pytest.skip("Caméra non disponible sur cette machine — test ignoré")

    # 'yield' passe l'objet cam au test ; tout ce qui est après s'exécute en nettoyage (teardown)
    yield cam

    # Libérer la caméra après le test, même si le test a échoué ou levé une exception
    cam.release()


def test_capture_retourne_un_tableau_numpy(camera: Camera) -> None:
    """capture() doit retourner un objet numpy ndarray."""
    image = camera.capture()

    # np.ndarray est le type qu'OpenCV utilise pour représenter les images en mémoire
    assert isinstance(image, np.ndarray), "capture() doit retourner un np.ndarray"


def test_capture_image_trois_dimensions(camera: Camera) -> None:
    """L'image capturée doit avoir 3 dimensions : (hauteur, largeur, canaux)."""
    image = camera.capture()

    # Une image couleur BGR a toujours la forme (h, w, 3) — vérifier le nombre de dimensions
    assert image.ndim == 3, f"L'image doit avoir 3 dimensions, obtenu : {image.ndim}"

    # La dernière dimension doit valoir 3 (canaux Blue, Green, Red)
    assert image.shape[2] == 3, f"L'image doit avoir 3 canaux BGR, obtenu : {image.shape[2]}"


def test_capture_dimensions_correspondent_a_la_resolution_reelle(camera: Camera) -> None:
    """Les dimensions de l'image doivent correspondre à la résolution réellement appliquée."""
    image = camera.capture()
    hauteur, largeur, _ = image.shape

    # camera.width et camera.height reflètent la résolution réellement négociée avec la caméra
    # (peut différer de CAMERA_WIDTH / CAMERA_HEIGHT si la caméra ne supporte pas cette résolution)
    assert largeur == camera.width, (
        f"Largeur image ({largeur}) ≠ résolution caméra ({camera.width})"
    )
    assert hauteur == camera.height, (
        f"Hauteur image ({hauteur}) ≠ résolution caméra ({camera.height})"
    )


def test_list_devices_retourne_des_index_ouvrables() -> None:
    """list_devices() doit retourner une liste d'index croissants, tous réellement
    ouvrables — c'est ce qui alimente la liste déroulante de choix de caméra (écran 1).

    Ce test tourne même sans caméra branchée : dans ce cas la liste est simplement vide,
    ce qui est le comportement attendu (l'interface affiche "Aucune camera detectee").
    """
    indices = Camera.list_devices()

    assert isinstance(indices, list)
    assert all(isinstance(i, int) for i in indices), "les index doivent être des entiers"
    assert indices == sorted(indices), "les index doivent être triés (ordre d'affichage stable)"
    assert len(indices) == len(set(indices)), "aucun index ne doit apparaître deux fois"

    # Chaque index annoncé doit vraiment donner une caméra utilisable — c'est toute la
    # raison d'être du test de lecture ajouté dans list_devices (isOpened() ment sur
    # Windows, voir son docstring)
    for i in indices:
        cam = Camera(device_index=i)
        try:
            image = cam.capture()
            assert image.ndim == 3, f"l'index {i} est listé mais ne délivre pas d'image BGR"
        finally:
            cam.release()


def test_list_devices_exclude_preserve_la_camera_en_service(camera: Camera) -> None:
    """Régression du bug du 2026-08-01 : l'aperçu affichait "Camera deconnectee" dès que
    la liste des caméras était rafraîchie (au démarrage et après chaque bascule).

    Cause : le scan ouvrait AUSSI l'index déjà utilisé par l'application, créant un second
    handle sur le même périphérique. Sous DirectShow, le release() de ce second handle
    coupe le flux du premier — la caméra en service devenait muette sans jamais avoir été
    débranchée.

    Le paramètre `exclude` évite de sonder l'index en service. Ce test vérifie les deux
    garanties : l'index exclu n'est pas dans le résultat, et la caméra ouverte capture
    toujours après le scan.
    """
    # La fixture ouvre l'index 0 — c'est donc lui qui est "en service" ici
    assert camera.capture().ndim == 3, "prérequis : la caméra doit capturer avant le scan"

    indices = Camera.list_devices(exclude={camera.index})

    assert camera.index not in indices, \
        f"l'index en service ({camera.index}) ne doit pas figurer dans un scan qui l'exclut"

    # Le point crucial : la caméra doit avoir survécu au scan des autres index
    image = camera.capture()
    assert image.ndim == 3, "la caméra en service a été cassée par le scan des autres index"


def test_release_ferme_le_flux(camera: Camera) -> None:
    """Après release(), toute tentative de capture doit lever une RuntimeError."""
    # Fermer le flux manuellement dans le test
    camera.release()

    # La fixture appellera aussi release() en nettoyage — c'est sans danger car
    # notre implémentation vérifie isOpened() avant de libérer
    with pytest.raises(RuntimeError):
        camera.capture()
