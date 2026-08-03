# Tests de modules/camera.py.
#
# La caméra utilisée n'est PAS choisie par configuration mais par vérification : la
# fixture `plateau_capture` (voir tests/conftest.py) retient celle où des marqueurs
# ArUco sont réellement détectés, c'est-à-dire celle qui voit le plateau. Une image
# est capturée une seule fois pour toute la session, et la plupart des tests
# travaillent sur cette image plutôt que de rouvrir la caméra.

import numpy as np
import pytest

from modules.camera import Camera


# ------------------------------------------------------------------ sélection

def test_camera_retenue_voit_bien_le_plateau(plateau_capture) -> None:
    """Contrat de la fixture : la caméra sélectionnée voit au moins un marqueur ArUco.

    Ce test paraît tautologique — la sélection impose déjà ce critère — mais il rend le
    contrat explicite et fait apparaître QUELLE caméra a été retenue et quels marqueurs
    elle voit, ce qui est la première information utile quand un test caméra échoue.
    """
    assert plateau_capture.marker_ids, "la caméra retenue doit voir des marqueurs"
    assert plateau_capture.index >= 0


# ------------------------------------------------------------------ image capturée

def test_capture_retourne_un_tableau_numpy(plateau_capture) -> None:
    """capture() doit retourner un objet numpy ndarray."""
    # np.ndarray est le type qu'OpenCV utilise pour représenter les images en mémoire
    assert isinstance(plateau_capture.image, np.ndarray)


def test_capture_image_trois_dimensions(plateau_capture) -> None:
    """L'image capturée doit avoir 3 dimensions : (hauteur, largeur, canaux)."""
    image = plateau_capture.image

    # Une image couleur BGR a toujours la forme (h, w, 3)
    assert image.ndim == 3, f"L'image doit avoir 3 dimensions, obtenu : {image.ndim}"
    assert image.shape[2] == 3, f"3 canaux BGR attendus, obtenu : {image.shape[2]}"


def test_capture_dimensions_correspondent_a_la_resolution_reelle(plateau_capture) -> None:
    """Les dimensions de l'image doivent correspondre à la résolution réellement
    appliquée, qui peut différer de celle demandée dans config.py si la caméra ne la
    supporte pas."""
    hauteur, largeur, _ = plateau_capture.image.shape

    assert largeur == plateau_capture.width, (
        f"Largeur image ({largeur}) ≠ résolution caméra ({plateau_capture.width})"
    )
    assert hauteur == plateau_capture.height, (
        f"Hauteur image ({hauteur}) ≠ résolution caméra ({plateau_capture.height})"
    )


def test_image_capturee_n_est_pas_noire(plateau_capture) -> None:
    """Régression du piège DirectShow : une caméra peut annoncer une résolution qu'elle
    ne délivre pas, et ne renvoyer que des trames vides.

    Une image vraiment vide a une moyenne ET un écart-type quasi nuls — une scène
    sombre, elle, garde du contraste. C'est ce couple qui distingue les deux cas.
    """
    image = plateau_capture.image

    assert not (image.mean() < 1.0 and image.std() < 1.0), (
        f"image vide (moyenne {image.mean():.2f}, écart-type {image.std():.2f}) — "
        f"la caméra {plateau_capture.index} annonce une résolution qu'elle ne délivre pas"
    )


# ------------------------------------------------------------------ objet Camera

def test_capture_repetee_reste_stable(camera: Camera) -> None:
    """Plusieurs captures successives doivent toutes réussir et garder la même forme.

    Ouvre réellement la caméra : c'est le comportement de l'objet Camera qui est vérifié
    ici, pas le contenu de l'image.
    """
    formes = {camera.capture().shape for _ in range(3)}

    assert len(formes) == 1, f"la forme des images varie d'une capture à l'autre : {formes}"


def test_release_ferme_le_flux(camera: Camera) -> None:
    """Après release(), toute tentative de capture doit lever une RuntimeError."""
    camera.release()

    # La fixture appellera aussi release() en nettoyage — sans danger, notre
    # implémentation vérifie isOpened() avant de libérer
    with pytest.raises(RuntimeError):
        camera.capture()


def test_list_devices_exclude_preserve_la_camera_en_service(camera: Camera) -> None:
    """Régression du bug du 2026-08-01 : l'aperçu affichait « Camera deconnectee » dès
    que la liste des caméras était rafraîchie.

    Cause : le scan ouvrait AUSSI l'index déjà utilisé par l'application, créant un
    second handle sur le même périphérique. Sous DirectShow, le release() de ce second
    handle coupe le flux du premier — la caméra en service devenait muette sans avoir
    jamais été débranchée.
    """
    assert camera.capture().ndim == 3, "prérequis : la caméra capture avant le scan"

    indices = Camera.list_devices(exclude={camera.index})

    assert camera.index not in indices, (
        f"l'index en service ({camera.index}) ne doit pas figurer dans un scan qui l'exclut"
    )

    # Le point crucial : la caméra doit avoir survécu au scan des autres index
    assert camera.capture().ndim == 3, (
        "la caméra en service a été cassée par le scan des autres index"
    )


# ------------------------------------------------------------------ balayage complet

@pytest.mark.toutes_cameras
def test_list_devices_retourne_des_index_ouvrables() -> None:
    """list_devices() ne doit annoncer que des index réellement utilisables — c'est ce
    qui alimente la liste déroulante de choix de caméra de l'écran 1.

    ⚠️ Ce test ouvre TOUTES les caméras de la machine, webcam intégrée comprise : c'est
    inhérent à ce qu'il vérifie. C'est le seul du projet dans ce cas, d'où le marqueur
    `toutes_cameras` qui permet de l'exclure :

        pytest -m "not toutes_cameras"

    Tous les autres tests n'utilisent que la caméra validée par détection ArUco.

    Il tourne même sans caméra branchée : la liste est alors vide, ce qui est le
    comportement attendu (l'interface affiche « Aucune camera detectee »).
    """
    indices = Camera.list_devices()

    assert isinstance(indices, list)
    assert all(isinstance(i, int) for i in indices), "les index doivent être des entiers"
    assert indices == sorted(indices), "les index doivent être triés (affichage stable)"
    assert len(indices) == len(set(indices)), "aucun index ne doit apparaître deux fois"

    # Chaque index annoncé doit vraiment donner une caméra utilisable — c'est toute la
    # raison du test de lecture fait dans list_devices (isOpened() ment sous Windows)
    for i in indices:
        cam = Camera(device_index=i)
        try:
            assert cam.capture().ndim == 3, (
                f"l'index {i} est listé mais ne délivre pas d'image BGR"
            )
        finally:
            cam.release()


# ------------------------------------------------------------------ fraîcheur de l'image
#
# Ces trois tests n'ont besoin d'aucun matériel : ils remplacent le flux vidéo par un
# faux qui rend une suite d'images distinctes. Ce qu'on vérifie n'est pas la caméra, mais
# le fait de ne PAS rendre une image périmée — un comportement de la classe, pas du
# pilote.

class _FluxSimule:
    """Faux flux vidéo qui rend des images numérotées, une par lecture.

    Reproduit le tampon du pilote : les premières lectures rendent des images anciennes,
    les suivantes des images récentes. L'image `n` correspond à la n-ième lecture.
    """

    def __init__(self, nombre: int = 20) -> None:
        self.images = [
            np.full((4, 4, 3), i, dtype=np.uint8) for i in range(nombre)
        ]
        self.lectures = 0

    def read(self):
        image = self.images[min(self.lectures, len(self.images) - 1)]
        self.lectures += 1
        return True, image


def _camera_sur_flux(flux) -> Camera:
    """Une Camera branchée sur un faux flux, sans ouvrir de matériel.

    `__new__` court-circuite `__init__`, qui sonderait les caméras réelles du système —
    c'est précisément ce qu'on veut éviter ici.
    """
    camera = Camera.__new__(Camera)
    camera._cap = flux
    return camera


def test_capture_jette_les_images_du_tampon_avant_de_lire() -> None:
    """L'image rendue doit être la FRAÎCHE, pas la première du tampon.

    Défaut réel du 2026-08-04 : sur un second cycle de dépose, la photo analysée était
    celle de la fin du cycle précédent. Entre les deux, le homing avait duré 30 à 60 s
    sans que personne ne lise la caméra — `read()` rendait donc l'image figée d'avant.

    C'est le pire genre de défaut : la photo est nette, les marqueurs sont dedans, le
    diagnostic ressort vert, et les zones sont détectées au mauvais endroit.
    """
    flux = _FluxSimule()
    camera = _camera_sur_flux(flux)

    image = camera.capture(flush_frames=4)

    # 4 images jetées puis la 5e gardée → celle d'indice 4
    assert image[0, 0, 0] == 4
    assert flux.lectures == 5


def test_capture_flush_zero_rend_la_premiere_image() -> None:
    """L'échappatoire explicite reste possible, pour un appelant qui lit déjà en continu."""
    flux = _FluxSimule()
    camera = _camera_sur_flux(flux)

    image = camera.capture(flush_frames=0)

    assert image[0, 0, 0] == 0
    assert flux.lectures == 1


def test_capture_vide_le_tampon_par_defaut() -> None:
    """Le comportement sûr doit être celui qu'on obtient sans y penser.

    Un appelant qui écrit simplement `camera.capture()` ne doit pas hériter d'une image
    périmée : c'est le défaut par défaut qui compte, pas l'option.
    """
    flux = _FluxSimule()
    camera = _camera_sur_flux(flux)

    camera.capture()

    assert flux.lectures > 1, "capture() sans argument doit vider le tampon"
