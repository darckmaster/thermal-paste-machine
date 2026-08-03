# Threads machine partagés entre plusieurs écrans — lot D2
#
# Pourquoi un fichier à part : trois écrans photographient le plateau (accueil, création
# de plateau, cycle de dépose) et doivent tous le faire depuis la MÊME position machine.
# Dupliquer la mise en position dans chacun garantirait qu'elles divergent — c'est déjà
# arrivé sur ce projet avec le choix d'homographie, dupliqué entre deux écrans jusqu'à ce
# que le lot C2bis le regroupe.
#
# Pourquoi un thread : une commande G-code bloque jusqu'au « ok » de Marlin, et un homing
# prend de 30 à 60 secondes. Dans le thread Qt, l'interface gèlerait entièrement.

from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot


class PhotoPositionWorker(QObject):
    """Connexion, homing, dégagement en Z, puis mise en position de prise de vue.

    C'est la séquence qui doit précéder TOUTE photo du plateau. Sans elle, la photo est
    prise là où la machine se trouvait — et sur le PoC, où le plateau est solidaire du
    lit qui bouge en Y, cela veut dire un cadrage différent à chaque fois.
    """

    progress = pyqtSignal(str)
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, machine, position: tuple) -> None:
        super().__init__()
        self._machine = machine
        self._position = position

    @pyqtSlot()
    def run(self) -> None:
        try:
            self.progress.emit("Connexion a la machine...")
            self._machine.connect()

            self.progress.emit("Homing en cours (30-60 s)...")
            self._machine.home()

            self.progress.emit("Mise en position de prise de vue...")
            x, y, z = self._position
            # ⚠️ Monter d'abord, se déplacer ensuite. `move_to()` envoie `G1 X Y` PUIS
            # `G1 Z` : juste après un homing, il balaierait le plateau à la hauteur du
            # homing avant de monter. Constaté sur la machine le 2026-08-04.
            self._machine.move_z(z)
            self._machine.move_to(x, y, z)
        except Exception as e:
            self.error_occurred.emit(str(e))
            return
        finally:
            # Libérer le port : la suite peut durer (l'opérateur regarde, choisit,
            # sélectionne) et rien ne justifie de garder la machine réservée pendant ce
            # temps. La connexion sera rouverte au moment de déposer.
            try:
                self._machine.disconnect()
            except Exception:
                pass

        self.finished.emit()


class PhotoPositionRunner(QObject):
    """Enveloppe le worker ci-dessus avec son thread, pour les écrans qui l'utilisent.

    Les écrans n'ont ainsi qu'à écouter deux signaux au lieu de recréer à chaque fois le
    câblage QThread — qui est exactement le genre de code qu'on recopie mal.

    Le thread et le worker sont conservés en attributs pendant toute leur vie : sans
    cela, le ramasse-miettes de Python détruirait les objets pendant que le thread
    système tourne encore. Ce projet a déjà connu ce défaut le 2026-07-01.
    """

    progress = pyqtSignal(str)
    done = pyqtSignal(bool)    # True = position atteinte, False = échec

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: PhotoPositionWorker | None = None
        self._reussi = False
        self.last_error = ""

    @property
    def busy(self) -> bool:
        """Vrai tant qu'une mise en position est en cours.

        Sert aux écrans à ne pas en lancer deux à la fois — un double appui sur
        « Capturer » enverrait sinon deux séquences concurrentes sur le même port série.
        """
        return self._thread is not None and self._thread.isRunning()

    def start(self, machine, position: tuple) -> None:
        if self.busy:
            return

        self._reussi = False
        self.last_error = ""

        self._thread = QThread()
        self._worker = PhotoPositionWorker(machine, position)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.progress)
        self._worker.finished.connect(self._on_ok)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error_occurred.connect(self._thread.quit)
        # Prévenir l'écran sur la fin du THREAD et non sur celle du worker : le slot
        # appelé ouvre souvent une fenêtre modale, donc une boucle d'évènements
        # imbriquée. Sur le signal du worker, le `quit()` du thread attendrait derrière.
        self._thread.finished.connect(self._on_thread_finished)

        self._thread.start()

    @pyqtSlot()
    def _on_ok(self) -> None:
        self._reussi = True

    @pyqtSlot(str)
    def _on_error(self, message: str) -> None:
        self.last_error = message

    @pyqtSlot()
    def _on_thread_finished(self) -> None:
        self.done.emit(self._reussi)
