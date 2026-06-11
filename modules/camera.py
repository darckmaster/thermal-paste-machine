import cv2
import numpy as np

from modules.config import CAMERA_WIDTH, CAMERA_HEIGHT


class Camera:
    """Gestion du flux vidéo depuis la webcam USB."""

    def __init__(self, device_index: int = 0) -> None:
        # Ouvrir le flux vidéo à l'index donné (0 = première caméra détectée par le système)
        self._cap = cv2.VideoCapture(device_index)

        # Vérifier que l'ouverture a réussi — la caméra peut être occupée par un autre processus
        if not self._cap.isOpened():
            raise RuntimeError(f"Impossible d'ouvrir la caméra à l'index {device_index}")

        # Demander la résolution souhaitée à la caméra (OpenCV tente de l'appliquer, sans garantie)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)

        # Lire la résolution réellement appliquée — peut différer si la caméra ne supporte pas
        # exactement CAMERA_WIDTH × CAMERA_HEIGHT (ex: 1280×960 non supporté → retombe sur 640×480)
        self.width: int = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height: int = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def capture(self) -> np.ndarray:
        """Capture une image et la retourne sous forme de tableau numpy BGR."""
        # Lire une image depuis le flux (ret = succès booléen, frame = image numpy BGR)
        ret, frame = self._cap.read()

        # Si la lecture échoue (caméra débranchée, perte de signal...), on lève une exception
        if not ret:
            raise RuntimeError("Échec de la lecture de l'image depuis la caméra")

        return frame

    def release(self) -> None:
        """Ferme le flux vidéo et libère la ressource caméra."""
        # Libérer explicitement la caméra — sans cela, le flux reste ouvert même après la fin du programme
        if self._cap.isOpened():
            self._cap.release()
