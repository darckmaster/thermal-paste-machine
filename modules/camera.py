import sys
import cv2
import numpy as np
from typing import Optional

from modules.config import CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_FLUSH_FRAMES


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
    def list_devices(max_index: int = 5, exclude: Optional[set] = None) -> list:
        """Liste les index de caméra qui répondent sur ce système.

        Teste les index 0 à max_index-1 en ouvrant puis refermant chacun, et retourne
        les index qui se sont ouverts (ordre croissant). Sert à remplir la liste
        déroulante de choix de caméra sur l'écran 1.

        ⚠️ `exclude` n'est PAS une commodité, c'est une protection. Sonder un index déjà
        ouvert par l'application ouvre un SECOND handle sur le même périphérique ; sous
        DirectShow (Windows) le release() de ce second handle coupe le flux du premier,
        et la caméra en service se met à échouer à chaque lecture (symptôme observé le
        2026-08-01 : l'aperçu affichait "Camera deconnectee" juste après le scan).
        L'appelant doit donc y passer l'index en cours d'utilisation, puis le réintégrer
        lui-même dans la liste affichée — voir gui/screen_capture.py::_refresh_camera_list().

        Méthode statique : on doit pouvoir lister les caméras avant d'en avoir ouvert une.
        """
        exclus = exclude or set()
        disponibles = []
        for i in range(max_index):
            # Ne jamais toucher un index déjà en service (voir l'avertissement ci-dessus)
            if i in exclus:
                continue
            cap = Camera._open_cap(i)
            if cap.isOpened():
                # isOpened() ne suffit PAS : sur Windows, des index fantômes s'ouvrent
                # sans jamais délivrer la moindre image (même piège que dans _open_cap).
                # Proposer une telle caméra dans la liste ferait choisir à l'opérateur un
                # périphérique inutilisable → on exige une lecture réellement réussie.
                for _ in range(3):
                    ret, _frame = cap.read()
                    if ret:
                        disponibles.append(i)
                        break
            # Libérer dans tous les cas — on voulait juste tester la présence, et un cap
            # non ouvert doit quand même être relâché pour ne pas fuir de descripteur
            cap.release()
        return disponibles

    @staticmethod
    def _find_best_index() -> int:
        """Détecte automatiquement la caméra USB à utiliser.

        Retourne le DERNIER index fonctionnel trouvé par list_devices().
        Logique : sur un PC avec webcam intégrée (index 0) + caméra USB (index 1),
        retourne 1. Sur un RPi avec une seule caméra USB, retourne 0.
        """
        disponibles = Camera.list_devices()

        if not disponibles:
            raise RuntimeError("Aucune caméra détectée sur ce système")

        return disponibles[-1]

    def __init__(self, device_index: Optional[int] = None) -> None:
        # Si aucun index fourni (None), détecter automatiquement la meilleure caméra
        if device_index is None:
            device_index = Camera._find_best_index()

        # Mémoriser l'index réellement utilisé — permet à l'interface de présélectionner
        # la bonne entrée dans la liste déroulante de choix de caméra (écran 1), y compris
        # quand l'index a été déterminé automatiquement juste au-dessus
        self.index: int = device_index

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

    def capture(self, flush_frames: int = None) -> np.ndarray:
        """Capture une image FRAÎCHE et la retourne sous forme de tableau numpy BGR.

        Réessaye jusqu'à 3 fois avant d'échouer, pour absorber les ret=False transitoires
        (fréquents avec DSHOW sur Windows en cas de charge CPU ou de perte de frame).

        ⚠️ **Pourquoi on jette des images avant de lire la bonne.** Le pilote garde
        quelques images d'avance dans un tampon. `read()` rend la plus ancienne, pas la
        plus récente : si personne n'a lu la caméra depuis un moment, on récupère une
        image périmée — vieille de tout l'intervalle, pas de quelques millisecondes.

        Le défaut s'est manifesté le 2026-08-04 sur un second cycle de dépose : la photo
        analysée était celle de la FIN du cycle précédent. L'enchaînement est traître —
        l'écran d'accueil lit la caméra en continu, l'arrêter fige le tampon, puis le
        homing et la mise en position durent de 30 à 60 secondes pendant lesquelles plus
        personne ne lit. L'image rendue datait donc d'avant le déplacement de la machine,
        et montrait le plateau à sa position précédente.

        Conséquence si on n'y prend pas garde : les zones sont détectées au mauvais
        endroit, et **rien ne le signale** — la photo est nette, les marqueurs sont
        dedans, le diagnostic est vert. C'est exactement la famille de défaut silencieux
        que ce projet traque depuis le lot C2bis.
        """
        if flush_frames is None:
            flush_frames = CAMERA_FLUSH_FRAMES

        # Vider le tampon : ces images sont lues puis jetées sans être décodées plus loin
        for _ in range(max(0, flush_frames)):
            self._cap.read()

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
