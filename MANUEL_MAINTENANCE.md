# Manuel de maintenance — Machine de Dépose de Pâte Thermique

> Guide technique : installation, configuration machine par machine, dépannage.
> Pour le guide d'utilisation quotidienne, voir `MANUEL_UTILISATEUR.md`.
> Pour l'architecture détaillée et l'historique des décisions techniques,
> voir `CONCEPTION.md` et `CLAUDE.md`.

---

## 1. Architecture rapide

```
modules/    logique métier (caméra, vision ArUco/ChArUco, machine G-code, calibration,
            planification de trajectoire, rapport PDF) — indépendante de l'interface
gui/        écrans PyQt5 (5 écrans, voir MANUEL_UTILISATEUR.md) — orchestrés par gui/app.py
tests/      tests unitaires (tests/test_*.py, pytest) et démos manuelles (tests/demo_*.py)
assets/     ressources générées ou statiques (mires, calibration, synoptiques)
```

`gui/app.py::MainApp` possède **une seule instance `Camera`**, partagée entre l'écran
de capture et l'écran de calibration (évite un release/reopen coûteux à chaque
changement d'écran). Il possède aussi l'unique instance `Machine`.

**Conséquence pour tout ajout de fonctionnalité** : un écran ne remplace jamais la
caméra ni la machine lui-même. Les listes déroulantes de l'écran 1 émettent les signaux
`camera_selected(int)` / `machine_port_selected(str)`, et c'est `MainApp` qui applique le
changement puis redistribue la nouvelle référence aux écrans. Sans cette règle, deux
endroits différents ouvriraient la caméra et l'un des deux handles finirait non libéré.

### Repère géométrique du plateau (⚠ mis à jour le 2026-08-01)

Disposition physique des marqueurs de coin, **telle qu'elle apparaît à l'écran** :

```
3 ─────── 0        origine mm = marqueur 3 (haut-gauche)
│         │        X+ vers la droite
│         │        Y+ vers le BAS (comme les lignes d'une image)
2 ─────── 1
```

L'axe Y du repère mm est donc **opposé** à l'axe Y machine (qui croît vers le fond).
L'inversion se fait à **un seul endroit** du code, `gui/screen_run.py` :
`machine_y = MACHINE_ORIGIN_Y - y_mm`. Ne pas la dupliquer ailleurs.

`MACHINE_ORIGIN_X/Y` (`modules/config.py`) est la position machine du **marqueur 3** :
c'est au-dessus de lui, et pas d'un autre, qu'il faut faire le `M114` de mesure.

### Zones de dépose — règles de reconstruction

Une **zone de dépose** est l'emplacement d'un produit, vissé à demeure sur le plateau.
Elle est repérée par **deux marqueurs ArUco** dont les centres sont posés aux extrémités
de la diagonale haut-gauche → bas-droit, avec la convention
`id(bas-droit) = id(haut-gauche) + 1`. Les IDs des zones commencent à **4** (0 à 3 étant
les coins du plateau). Toutes les zones portent le **même produit**, donc la même
diagonale : c'est cette invariante qui fait tout fonctionner.

`modules/vision.py::detect_deposit_zones_mm()` enchaîne six étapes :

| # | Étape | Rôle |
|---|---|---|
| 1 | Paires candidates `(n, n+1)` | Un tag peut apparaître dans deux paires — l'ambiguïté est levée plus loin |
| 2 | Tri par signe des composantes | `(+,+)` = zone plausible · `(−,−)` = zone inversée · **signes mixtes = paire fantôme, écartée** |
| 3 | Longueur de diagonale de référence | Groupe majoritaire à ± tolérance, puis médiane du groupe |
| 4 | Conflits | Un tag revendiqué par deux paires invalide les deux |
| 5 | Format `(w, h)` du produit | Médiane des composantes de diagonale des zones saines |
| 6 | Rectangle et rotation | `θ = angle(diagonale) − angle(w, h)` |

**Deux pièges déjà rencontrés, à ne pas réintroduire :**

**a) Le filtrage par longueur ne suffit pas sur un plateau en grille.** Deux zones
voisines sur une même ligne engendrent une paire fantôme (coin bas-droit de l'une, coin
haut-gauche de l'autre) dont le vecteur est le symétrique du vrai : `(60, −40)` contre
`(60, +40)`, donc **exactement la même longueur**. Elle empruntant leurs tags aux deux
zones réelles, elle les invalidait par conflit et rendait un plateau parfaitement monté
inexploitable. C'est le tri par signe de l'étape 2 qui l'élimine.

**b) Ne pas chercher « la plus petite rotation » parmi les solutions symétriques.** Un
rectangle 60×40 tourné de 25,8° a une diagonale orientée comme un 40×60 posé droit :
retenir la plus petite rotation ferait ressortir toute zone très inclinée à ~2°, et
l'anomalie de montage passerait inaperçue. L'ambiguïté n'existe pas ici parce que le
format déduit à l'étape 5 est **orienté** — la majorité des zones a déjà tranché quel
côté est la largeur. Une zone réellement montée à 90° sort en zone inversée.

**Limite du dispositif** : avec une **seule** zone détectée, elle définit à elle seule la
référence de format ; sa rotation ressort donc nulle même si elle est physiquement de
travers. Ce n'est pas un bug (test `test_zone_unique_ne_permet_pas_de_detecter_un_mauvais_montage`).

Deux seuils de réglage, dans `modules/vision.py` : `ZONE_DIAGONAL_TOLERANCE_MM` (5 mm)
et `ZONE_MAX_ROTATION_DEG` (10°).

## 2. Configuration par machine

Chaque machine (PC de dev, RPi Geeetech, futur RPi CNC) a son propre
**`local_config.json`** à la racine du projet — **gitignoré**, jamais commité, car les
paramètres diffèrent par machine (index caméra, port série...). Modèle à copier :
`local_config.json.example`.

Paramètres surchargeables (voir `modules/config.py` pour les valeurs par défaut) :

| Clé | Rôle |
|---|---|
| `camera_index` | Index OpenCV de la caméra USB. **Voir section 4 — ne jamais supposer un index sans vérifier.** |
| `serial_port` | Port de la carte Marlin. Défaut `/dev/ttyUSB0` (RPi) ; sous Windows, mettre `COM3` ou équivalent |
| `serial_baudrate` | Vitesse série, doit correspondre au firmware. Défaut 250000 (Geeetech) ; souvent 115200 ailleurs |
| `calibration_min_images` | Nombre minimum de poses ChArUco avant de pouvoir calibrer (défaut 15) |
| `charuco_cols` / `charuco_rows` | Dimensions de la mire en cases (défaut 4×4) |
| `charuco_square_mm` / `charuco_marker_mm` | Taille physique case/marqueur de la mire imprimée |
| `charuco_dict` | Dictionnaire ArUco de la mire (défaut `DICT_4X4_50`, **même dictionnaire que les marqueurs du plateau** — voir section 5, problème connu) |
| `charuco_legacy_pattern` | Voir section 4.2 — **doit être `false`** pour une mire générée par ce projet |

`assets/camera_calibration.npz` (coefficients de distorsion objectif) est **gitignoré**
lui aussi depuis la session v0.1 : il dépend du capteur/objectif physique exact de
chaque machine, comme `local_config.json`. Chaque machine doit refaire sa propre
calibration (écran "Calibration caméra", voir `MANUEL_UTILISATEUR.md` section 6).

## 3. Prérequis logiciels

Voir `CLAUDE.md` section 12 pour la liste complète des dépendances et leur licence.
Résumé rapide :

```bash
pip install opencv-contrib-python pyserial fpdf2 numpy pytest PyQt5
```

Sur Raspberry Pi, `python3-pyqt5` s'installe via `apt` plutôt que `pip` (voir
`CLAUDE.md` section 12 pour la commande complète).

**OpenCV ≥ 5.0** : certaines fonctions ChArUco "legacy" ont été supprimées entre
OpenCV 4.x et 5.0 (voir section 4.3 ci-dessous). Si le projet est un jour installé
avec une version antérieure d'OpenCV, vérifier que `modules/calibration.py` reste
compatible (`board.matchImagePoints()` existe depuis OpenCV 4.7+).

## 4. Dépannage — problèmes déjà rencontrés

### 4.1 La caméra affichée n'est pas la bonne (webcam intégrée au lieu de l'USB)

**Symptôme** : le flux vidéo montre l'utilisateur/la pièce au lieu du plateau, ou
inversement, alors que `camera_index` semble correct.

**Cause** : sur Windows notamment, l'ordre d'énumération des caméras par DirectShow
**ne suit pas forcément la convention "0 = intégrée, 1 = USB"**. Ça dépend de l'ordre
de chargement des pilotes, pas de l'ordre de branchement physique.

**Diagnostic** : capturer une image à chaque index (0 à 4) et regarder laquelle montre
le plateau :

```python
import cv2
for i in range(5):
    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
    if cap.isOpened():
        for _ in range(15):  # warmup — les premières frames sont souvent invalides
            cap.read()
        ret, frame = cap.read()
        if ret:
            cv2.imwrite(f"cam_index_{i}.png", frame)
    cap.release()
```

Puis corriger `camera_index` dans `local_config.json` en conséquence.

### 4.2 Frames entièrement noires à une résolution donnée

**Symptôme** : `cap.get(CAP_PROP_FRAME_WIDTH)` confirme la résolution demandée (ex.
1280×960), mais les frames capturées sont uniformément noires (mean ≈ 0, std ≈ 0 —
pas juste une scène sombre, un vrai buffer vide).

**Cause connue** : certains pilotes DirectShow (Windows) mentent sur le succès du
`.set()` de résolution — ils acceptent la valeur sans pouvoir réellement la délivrer.

**Protection en place** : `modules/camera.py::Camera.__init__` détecte ce cas (frame
quasi uniformément noire après le `.set()`) et retombe automatiquement sur la
résolution native de la caméra. Si le problème persiste malgré ça, vérifier la
résolution native réellement supportée par la caméra (sans forcer de `.set()`).

### 4.3 `AttributeError: module 'cv2.aruco' has no attribute 'calibrateCameraCharuco'`

**Cause** : cette fonction "legacy" a été supprimée dans OpenCV 5.0.

**Solution appliquée** (`modules/calibration.py::calibrate_charuco`) : remplacée par
`board.matchImagePoints(corners, ids)` (convertit les coins ChArUco détectés en paires
points-objet 3D / points-image 2D) suivi de `cv2.calibrateCamera()` (la fonction
générique, déjà utilisée pour l'échiquier simple).

### 4.4 `detectMarkers` trouve les tags mais `detectBoard`/`CharucoDetector` ne
reconstruit aucun coin de mire (0 coin, malgré tags détectés)

Deux causes distinctes identifiées, à vérifier dans l'ordre :

**a) `charuco_legacy_pattern` mal réglé.** `board.generateImage()` (utilisé par le
bouton "Générer la mire") produit toujours la disposition "nouvelle" (post-OpenCV 4.6)
des marqueurs, **quel que soit** le réglage de `setLegacyPattern()`. Mais la détection
(`CharucoDetector.detectBoard()`), elle, respecte ce réglage. Résultat : avec
`charuco_legacy_pattern: true`, le code génère une mire au format nouveau puis essaie
de la détecter avec les règles de l'ancien format → échec systématique.
→ **`charuco_legacy_pattern` doit être `false`** pour toute mire générée par ce
projet. Ne mettre `true` que pour une mire **externe** (calib.io, kalibr...).

**b) Collision d'IDs entre le plateau et la mire.** Les 4 marqueurs fixes du plateau et
les marqueurs de la mire ChArUco utilisent tous les deux le dictionnaire `DICT_4X4_50`,
sans plage d'IDs dédiée. Si le plateau et la mire sont visibles simultanément dans le
même cadre (cas normal en calibration : la mire est posée sur le plateau), certains
marqueurs du plateau et de la mire partagent le même ID → le détecteur confond les deux
jeux de marqueurs, ce qui corrompt la reconstruction géométrique de la mire même quand
`detectMarkers` voit très bien les tags individuellement.
→ **Statut : non corrigé.** Contournement actuel : masquer temporairement les
marqueurs du plateau (papier blanc) pendant la calibration. Correctif propre à
prévoir : attribuer à la mire une plage d'IDs disjointe de celle du plateau (voir
`CONCEPTION.md` pour le suivi).

### 4.5 IDs réels des marqueurs du plateau — ✅ résolu (v0.1.1)

**Doute de la session v0.1** : un test de détection avait montré `{0, 3, 4, 5}`, laissant
craindre que les marqueurs du plateau soient `{0, 3, 4, 5}` au lieu de `{0, 1, 2, 3}`.

**Conclusion (2026-08-01, observation en direct sur le plateau réel)** : fausse piste. Le
plateau utilise bien `{0, 1, 2, 3}`. La liste `{0, 3, 4, 5}` se décompose en :

- `3` et `0` = les deux marqueurs du **haut** du plateau, seuls cadrés par la caméra fixe ;
- `4` et `5` = les deux marqueurs de la **zone de dépose**, qui ne sont pas des marqueurs
  de plateau ;
- `1` et `2` = les coins du bas, hors champ.

Aucune collision d'IDs entre plateau et zone. Autre enseignement : **le repli à 2
marqueurs est le mode nominal** sur la Geeetech, pas un cas dégradé rare — voir
`modules/vision.py::compute_homography_approx()`.

### 4.6 « Camera deconnectee — rebrancher et relancer » alors que rien n'est débranché

**Symptôme** : l'aperçu de l'écran 1 se fige sur ce message, au démarrage ou juste après
un changement de caméra, sans qu'aucun câble n'ait bougé.

**Cause** (identifiée en v0.1.1) : le scan qui remplit la liste déroulante des caméras
ouvrait **tous** les index, y compris celui déjà utilisé par l'application. Ça crée un
second handle sur le même périphérique ; sous DirectShow, le `release()` de ce second
handle **coupe le flux du premier**. La caméra devient muette, `capture()` échoue 3 fois
de suite et l'écran affiche le message de déconnexion — qui est donc trompeur.

**Protection en place** : `Camera.list_devices(exclude=...)` ne sonde jamais un index
déjà en service ; `gui/screen_capture.py::_refresh_camera_list()` y passe l'index courant
puis le réintègre à la main dans la liste affichée. Verrouillé par le test
`test_list_devices_exclude_preserve_la_camera_en_service`.

⚠️ **Règle générale à retenir** : ne jamais ouvrir une `VideoCapture` sur un index déjà
ouvert ailleurs dans le processus, même brièvement, même pour "juste tester".

## 5. Lancer les tests

```bash
pytest              # suite complète — doit toujours passer avant un commit/push
pytest tests/test_vision.py   # un module en particulier
python tests/demo_camera.py   # démo manuelle avec caméra réelle (pas dans pytest)
```

**Les tests caméra utilisent la caméra CONFIGURÉE**, c'est-à-dire `CAMERA_INDEX` issu de
`local_config.json`, et non l'index 0 en dur. Jusqu'au 2026-08-01 la fixture ouvrait
l'index 0 : sur un PC de développement elle validait donc la webcam intégrée pendant que
le projet travaillait avec la caméra USB, et un défaut propre à cette dernière serait
passé inaperçu. Conséquence pratique : la suite est plus lente (~1 min contre ~30 s), la
caméra USB étant plus longue à s'initialiser — c'est le prix de tester le bon matériel.

Si aucune caméra n'est branchée, les tests concernés se `skip` proprement, ils
n'échouent pas.

## 6. Où sont stockées les données

| Donnée | Emplacement | Suivi par git ? |
|---|---|---|
| Calibration objectif | `assets/camera_calibration.npz` | Non — spécifique à chaque machine |
| Config par machine | `local_config.json` | Non |
| Préparations (tracés sauvegardés) | `preparations/` | ⬜ Fonctionnalité pas encore implémentée |
| Rapports PDF générés | `reports/*.pdf` | Non |
| Mire ChArUco générée | `assets/charuco_calibration.png` | À vérifier au cas par cas |
