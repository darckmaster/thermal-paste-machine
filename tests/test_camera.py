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


def test_release_ferme_le_flux(camera: Camera) -> None:
    """Après release(), toute tentative de capture doit lever une RuntimeError."""
    # Fermer le flux manuellement dans le test
    camera.release()

    # La fixture appellera aussi release() en nettoyage — c'est sans danger car
    # notre implémentation vérifie isOpened() avant de libérer
    with pytest.raises(RuntimeError):
        camera.capture()
