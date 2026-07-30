import sys
import cv2
import numpy as np
from typing import Optional

from modules.config import CAMERA_WIDTH, CAMERA_HEIGHT


class Camera:
    """Gestion du flux vidéo depuis la webcam USB."""

    @staticmethod
    def _open_cap(device_index: int) -> cv2.VideoCapture:
        """Ouvrir une VideoCapture avec le backend le plus adapté à la plateforme.

        Sur Windows : tente d'abord CAP_DSHOW (rapide : 200 ms vs 2-3 s en auto),
        MAIS vérifie que le backend délivre effectivement des frames avant de le valider.
        Certains pilotes retournent isOpened()=True sans jamais fournir d'image → on
        détecte ce cas en tentant une vraie lecture. Si ça échoue, fallback CAP_ANY.

        Sur Linux (RPi) : CAP_ANY directement → V4L2 par défaut, déjà rapide.
        """
        if sys.platform.startswith("win"):
            cap = cv2.VideoCapture(device_index, cv2.CAP_DSHOW)
            if cap.isOpened():
                # Vérification renforcée : DSHOW peut mentir → tenter une vraie lecture
                for _ in range(5):
                    ret, _ = cap.read()
                    if ret:
                        return cap  # DSHOW fonctionne bien avec cette caméra
                # DSHOW ouvert mais ne délivre pas de frames → abandonner ce backend
                cap.release()

        # Fallback (Windows si DSHOW échoue, ou Linux directement) : backend par défaut
        return cv2.VideoCapture(device_index)

    @staticmethod
    def _find_best_index() -> int:
        """Détecte automatiquement la caméra USB à utiliser.

        Teste les indices 0 à 4 et retourne le dernier index fonctionnel.
        Logique : sur un PC avec webcam intégrée (index 0) + caméra USB (index 1),
        retourne 1. Sur un RPi avec une seule caméra USB, retourne 0.
        """
        dernier_trouve = -1
        for i in range(5):
            cap = Camera._open_cap(i)
            if cap.isOpened():
                dernier_trouve = i
                cap.release()  # Libérer immédiatement — on voulait juste tester la présence

        if dernier_trouve == -1:
            raise RuntimeError("Aucune caméra détectée sur ce système")

        return dernier_trouve

    def __init__(self, device_index: Optional[int] = None) -> None:
        # Si aucun index fourni (None), détecter automatiquement la meilleure caméra
        if device_index is None:
            device_index = Camera._find_best_index()

        self._cap = Camera._open_cap(device_index)

        # Vérifier que l'ouverture a réussi — la caméra peut être occupée par un autre processus
        if not self._cap.isOpened():
            raise RuntimeError(f"Impossible d'ouvrir la caméra à l'index {device_index}")

        # Résolution native (avant toute demande de changement) — sert de repli si la
        # résolution demandée ci-dessous s'avère non utilisable (voir vérification plus bas)
        native_width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        native_height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Demander la résolution souhaitée à la caméra (OpenCV tente de l'appliquer, sans garantie)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)

        # Lire la résolution réellement appliquée — peut différer si la caméra ne supporte pas
        # exactement CAMERA_WIDTH × CAMERA_HEIGHT (ex: 1280×960 non supporté → retombe sur 640×480)
        self.width: int = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height: int = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Warmup : jeter les 10 premières images pour laisser le capteur/l'auto-exposition
        # se stabiliser. Ret=False à ce stade est normal — on ignore et on continue.
        for _ in range(10):
            self._cap.read()

        # Piège observé sur Windows/DSHOW : cap.get() peut confirmer la résolution demandée
        # (ex. 1280x960) alors que le pilote ne délivre en réalité que des frames noires
        # (mean ET std ~ 0 — pas juste une scène sombre, un vrai buffer vide) à cette résolution.
        # Si c'est le cas, revenir à la résolution native où la caméra fonctionne vraiment.
        ret, frame = self._cap.read()
        if ret and frame.mean() < 1.0 and frame.std() < 1.0:
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, native_width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, native_height)
            self.width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            for _ in range(10):
                self._cap.read()

    def capture(self) -> np.ndarray:
        """Capture une image et la retourne sous forme de tableau numpy BGR.

        Réessaye jusqu'à 3 fois avant d'échouer, pour absorber les ret=False transitoires
        (fréquents avec DSHOW sur Windows en cas de charge CPU ou de perte de frame).
        """
        for _ in range(3):
            ret, frame = self._cap.read()
            if ret:
                return frame
        # 3 échecs d'affilée = la caméra est probablement débranchée / défaillante
        raise RuntimeError("Échec de la lecture de l'image depuis la caméra")

    def release(self) -> None:
        """Ferme le flux vidéo et libère la ressource caméra."""
        # Libérer explicitement la caméra — sans cela, le flux reste ouvert même après la fin du programme
        if self._cap.isOpened():
            self._cap.release()
