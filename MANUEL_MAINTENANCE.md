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

### Repère géométrique du plateau (⚠ mis à jour le 2026-08-02, lot C2bis)

Disposition physique des marqueurs de coin, **telle qu'elle apparaît à l'écran** :

```
3 ─────── 0        origine mm = marqueur 2 (bas-gauche)        Y
│         │        X+ vers la droite, vers le tag 1            ↑
│         │        Y+ vers le HAUT, vers le tag 3              └──→ X
2 ─────── 1        tag 0 = redondant → contrôle de cohérence
```

Les axes X et Y du repère mm vont désormais dans le **même sens** que les axes machine.
La conversion, dans `gui/screen_run.py`, est donc devenue deux additions :
`machine_x = x_mm + MACHINE_ORIGIN_X`, `machine_y = y_mm + MACHINE_ORIGIN_Y`.
⚠️ Le sens réel des axes machine n'est **pas encore validé** (action `M4`) : ces deux
additions sont cohérentes avec la convention, rien de plus. À trancher au lot D, en
interactif, machine sous tension.

`MACHINE_ORIGIN_X/Y` (`modules/config.py`) est la position machine du **marqueur 2** :
c'est au-dessus de lui, et pas d'un autre, qu'il faut faire le `M114` de mesure.

#### Mesure de l'origine machine — procédure et relevé du 2026-08-02

```gcode
G28                  ; obligatoire : Marlin démarre à 0 où que soit le chariot
G1 Z10 F300          ; lever Z avant de balader le chariot
G91                  ; déplacements RELATIFS pour approcher
G1 X10 F3000         ; ... répéter jusqu'à viser le centre du marqueur 2
G90                  ; RETOUR EN ABSOLU — l'oublier fausse toute la suite
G1 Z1 F100           ; descendre près du plateau : de haut, la parallaxe fausse le visé
M114                 ; X et Y = MACHINE_ORIGIN_X / MACHINE_ORIGIN_Y
```

**Relevé du 2026-08-02** (buse, sans dispositif de seringue) :
`X:5.00 Y:0.00 Z:0.00 · Count X:394 Y:0 Z:0` → `MACHINE_ORIGIN` = `5.0 / 0.0`.
⚠️ **Valeurs périmées**, conservées pour la démarche — voir le relevé du 2026-08-03.

**Vérifier aussi le repère de home**, une fois, et le noter : `G28` suivi d'un `M114`
immédiat doit rendre `X:0.00 Y:0.00 Count 0/0`. C'est ce qui prouve qu'il n'y a ni
`X_MIN_POS` non nul ni décalage `M206` en EEPROM. Ça compte : un `M206` effacé un jour par
un reset EEPROM décalerait toute la dépose **sans rien signaler**. Vérifié conforme le
2026-08-02.

#### ✅ Relevé du 2026-08-03 — valeurs en vigueur (action `M2 bis`)

Le relevé a été repris **dispositif de seringue monté**, et **dans l'autre sens** : au lieu
d'amener la buse sur le marqueur puis de lire `M114`, on laisse la machine au homing et on
regarde **où tombe la pointe** dans le repère plateau. C'est plus commode, et ça vise
directement la pointe qui dépose plutôt que la buse.

**Relevé** : au homing, la pointe de seringue est au point **`(-6.0, +2.0)`** du repère
plateau.

La conversion `plateau = machine - ORIGIN`, appliquée au homing où `machine = (0, 0)`,
donne par simple inversion :

```
-6 = 0 - MACHINE_ORIGIN_X   →   MACHINE_ORIGIN_X = +6.0
+2 = 0 - MACHINE_ORIGIN_Y   →   MACHINE_ORIGIN_Y = -2.0
```

Ce relevé **absorbe l'action `M2 ter`** (mesure du décalage buse ↔ pointe), qui n'a plus
lieu d'être puisqu'on vise la pointe. Recoupement avec la mesure de la veille, prise sur la
buse : l'écart buse↔pointe ressort à `(-1, +2)` mm, crédible pour un support de seringue.
Les deux mesures se confirment mutuellement.

> 🔎 **Ce que ce relevé a tranché.** La veille, `Y` valait `0.00` avec un compteur de pas à
> **0 exact** — l'axe n'avait pas bougé d'un pas depuis le homing. Deux lectures étaient
> possibles : soit le marqueur 2 tombait déjà sous la buse, soit le plateau **butait sur la
> fin de course** et `0` était une limite, pas une mesure. La nouvelle valeur, **négative**,
> tranche pour la butée.
>
> **Règle de diagnostic à retenir** : une grandeur relevée à `0` exact, sur un axe dont le
> compteur de pas est lui aussi à `0` exact, est presque toujours une **butée** et non une
> mesure.

> ⚠️ **CONSÉQUENCE PHYSIQUE — une bande de 2 mm en bas du plateau est HORS COURSE.**
> Atteindre `plateau_y = 0` demanderait `machine_y = -2`, en deçà de la fin de course : seul
> `plateau_y >= 2` est réellement atteignable.
>
> **Le piège** : Marlin ne refuse pas une coordonnée hors course, il la **rogne en
> silence**. Une dépose déformée passerait donc pour une erreur de vision ou de calibration.
> C'est pourquoi le lot D1 ajoute un **contrôle de course avant le premier mouvement**, qui
> fait échouer le lancement en nommant la zone fautive.
>
> **En dépannage** : si une dépose ressort tassée vers le bas du plateau, vérifier d'abord
> que les cordons ne descendent pas sous `plateau_y = 2`. Le remède durable est mécanique —
> rapprocher le plateau du fond — et non logiciel.

**Pas/mm** : le rapport `Count / position` donne les pas/mm de l'axe — ici 394 pas pour
5,00 mm, soit ≈ 78,74 pas/mm (courroie MXL, valeur Geeetech classique). Utile comme
recoupement rapide ; la valeur officielle se lit avec `M503` ou `M92`.

#### ⚠️ Si vous touchez au sens de Y — la règle à ne pas casser

Une image a son origine en haut à gauche et son Y qui **descend**. Le repère mm, lui,
monte. Les trois méthodes `warp_*` compensent cet écart par une ligne explicite :

```
y_pixel = (hauteur_mm − y_mm) × échelle
```

C'est elle qui garantit que **ce que l'opérateur voit à l'écran est ce qui se passe sur
le plateau**. Sans elle, le plateau s'affiche à l'envers — et un plateau à peu près
symétrique ne trahit pas son propre retournement : le projet a vécu avec ce miroir de la
Phase 2 au 2026-08-01 sans que personne ne le voie. Il a été démasqué par le calcul.

`test_warp_image_orientation_non_miroir` et `test_boussole_de_la_convention_du_repere`
sont les garde-fous. **Ne pas les affaiblir.** Le second est fait pour échouer en premier
si la convention rebouge : il épingle en un seul endroit les quatre faits qui la
définissent (tag 2 à l'origine, Y montant, image non miroir, diagonale de zone à `dy < 0`).

#### Choix de l'homographie et qualité du repère

`VisionProcessor.compute_plateau_reference()` est le **seul** endroit qui décide entre
homographie exacte (4 tags, perspective) et approchée (2-3 tags, similitude). La règle
était dupliquée dans `screen_plateau.py` et `screen_zone.py` avant le lot C2bis — ne pas
la réintroduire ailleurs. La méthode retourne un `PlateauReference` qui porte, en plus de
la matrice :

- `exact` — mode précis ou dégradé ;
- `origin_extrapolated` — vrai quand le tag 2 (l'origine) n'est pas dans le champ. C'est
  le cas **nominal** sur la Geeetech : l'origine est alors déduite de `plateau_size_mm`,
  et toute erreur sur ce paramètre décale toute la dépose (action `M1`) ;
- `check_error_mm` — écart entre la position vue du tag 0 et sa position attendue,
  mesuré contre une similitude ajustée sur les tags 2/1/3. Indicateur de qualité du
  montage optique : il agrège inclinaison de caméra, distorsion d'objectif, plateau
  déformé et tag mal collé, sans savoir les distinguer. Au-delà de
  `PLATEAU_CHECK_TOLERANCE_MM` (5 mm), l'IHM le signale.

> Cet écart ne peut pas se lire sur la matrice de `compute_homography()` : avec exactement
> 4 points, `getPerspectiveTransform` ajuste sans résidu et le donnerait nul quelle que
> soit la réalité du plateau. D'où la similitude sur 3 tags.

#### ⚠️ Le repli 2-3 marqueurs doit retourner Y explicitement

**Défaut constaté sur la machine le 2026-08-02** : plus aucune zone de dépose n'était
détectée, les quatre marqueurs de zone ressortant tous « orphelins ».

`cv2.estimateAffinePartial2D` ajuste une **similitude** — rotation, échelle uniforme,
translation — dont le déterminant est toujours **positif**. Elle ne sait donc pas produire
de miroir. Or passer du repère image (Y vers le bas) au repère plateau (Y vers le haut
depuis le lot C2bis) **est** un retournement. Appelée directement sur les positions mm,
elle rendait une matrice où `y_mm` croît vers le bas : l'ancienne convention. Toute la
logique de signe des zones s'en trouvait inversée, et le filtre des paires plausibles
écartait les vraies zones comme fantômes.

La parade, dans `compute_homography_approx()` : ajuster la similitude vers un repère
intermédiaire **retourné en Y** — de même « main » que l'image, le seul qu'elle sache
atteindre — puis composer avec une matrice de retournement (déterminant −1) pour revenir
au repère du plateau. La partie rotation + échelle reste ajustée exactement comme avant.

> **Pourquoi les tests ne l'avaient pas vu**, et quoi en retenir : les deux tests
> existants du repli ne vérifiaient que les points **ajustés**, qui retombent juste quelle
> que soit l'orientation, et le test « boussole » travaille avec 4 marqueurs — donc
> `compute_homography`, une vraie homographie, qui sait mirroiter. Personne ne convertissait
> un **troisième** point pour regarder dans quel sens il partait. Le repli 2 marqueurs
> étant le mode **nominal** sur la Geeetech, le trou portait sur le chemin le plus
> emprunté du logiciel.
>
> Deux tests le gardent désormais : `test_compute_homography_approx_conserve_le_sens_de_y`
> (la cause) et `test_zones_detectees_avec_deux_marqueurs_de_plateau` (l'effet visible par
> l'opérateur). **Règle générale à retenir : vérifier une transformation sur un point qui
> n'a pas servi à l'ajuster.**

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
| 2 | Tri par signe des composantes | `(+,−)` = zone plausible · `(−,+)` = zone inversée · **signes identiques = paire fantôme, écartée** |
| 3 | Longueur de diagonale de référence | Groupe majoritaire à ± tolérance, puis médiane. Vote sur les paires plausibles **ET** inversées |
| 4 | Conflits | Un tag revendiqué par deux paires invalide les deux |
| 5 | Format `(w, h)` du produit | Médiane des composantes de diagonale des zones saines, **hauteur ramenée en positif** |
| 6 | Rectangle et rotation | `θ = angle(diagonale) − angle(w, −h)`, positif dans le sens trigonométrique |

> ⚠️ **Les signes de l'étape 2 ont été inversés au lot C2bis** (ils étaient `(+,+)` pour une
> zone plausible). Le repère du plateau ayant son Y montant, une zone bien montée avance en
> X et **redescend** en Y. C'est le premier filtre à basculer quand l'axe Y change de sens,
> et `ANOMALIE_INVERSEE` repose entièrement dessus : le vérifier avant tout le reste.
>
> **Convention de signe de `product_size_mm`** : deux **longueurs**, donc toujours positives.
> La médiane des `dy` étant négative, la conversion se fait à l'étape 5 et nulle part
> ailleurs — le reste du fichier peut supposer partout `largeur > 0` et `hauteur > 0`.

**Deux pièges déjà rencontrés, à ne pas réintroduire :**

**a) Le filtrage par longueur ne suffit pas sur un plateau en grille.** Deux zones
voisines sur une même ligne engendrent une paire fantôme (coin bas-droit de l'une, coin
haut-gauche de l'autre) dont le vecteur est le symétrique du vrai : `(60, +40)` contre
`(60, −40)`, donc **exactement la même longueur**. Elle empruntant leurs tags aux deux
zones réelles, elle les invalidait par conflit et rendait un plateau parfaitement monté
inexploitable. C'est le tri par signe de l'étape 2 qui l'élimine.

**b) Ne pas chercher « la plus petite rotation » parmi les solutions symétriques.** Un
rectangle 60×40 tourné de 25,8° a une diagonale orientée comme un 40×60 posé droit :
retenir la plus petite rotation ferait ressortir toute zone très inclinée à ~2°, et
l'anomalie de montage passerait inaperçue. L'ambiguïté n'existe pas ici parce que le
format déduit à l'étape 5 est **orienté** — la majorité des zones a déjà tranché quel
côté est la largeur. Une zone réellement montée à 90° sort en zone inversée.

**c) Le vote sur la longueur doit inclure les zones inversées.** Une zone montée à
l'envers reste une zone, et sa diagonale a bien la longueur du produit. Si le vote ne
portait que sur les paires d'orientation plausible, un plateau dont **toutes** les zones
sont inversées les exclurait toutes du scrutin : les rares paires fantômes d'orientation
plausible fixeraient alors seules la référence, les vraies zones seraient rejetées comme
orphelines, et des fantômes seraient présentés comme des zones **valides**. Faux et
silencieux (constaté en écrivant les tests du lot C1, corrigé en v0.4.0). Seules les
paires à signes mixtes restent hors du vote.

**Limite du dispositif** : avec une **seule** zone détectée, elle définit à elle seule la
référence de format ; sa rotation ressort donc nulle même si elle est physiquement de
travers. Ce n'est pas un bug (test `test_zone_unique_ne_permet_pas_de_detecter_un_mauvais_montage`).

**Les cinq anomalies** (`modules/vision.py`) : `zone_inversee`, `diagonale_hors_norme`,
`paire_en_conflit`, `angle_excessif`, et `format_indeterminable` — cette dernière quand
plus aucune zone n'est saine et à l'endroit, donc qu'aucun format ne peut être déduit et
qu'aucun rectangle ne peut être reconstruit. Elle est distincte de `diagonale_hors_norme`,
qui signalerait à tort un problème de diagonale alors que celle-ci est correcte.

Deux seuils de réglage, dans `modules/vision.py` : `ZONE_DIAGONAL_TOLERANCE_MM` (5 mm)
et `ZONE_MAX_ROTATION_DEG` (10°).

### Redressement d'une zone pour le tracé

`VisionProcessor.warp_zone()` produit l'image d'une zone vue **droite**, même si elle est
vissée de travers. À ne pas confondre avec `warp_region()`, qui ne sait extraire qu'un
rectangle aligné sur les axes du plateau.

Le transport compose trois matrices, appliquées de droite à gauche :

```
pixel source → mm plateau       : l'homographie
mm plateau   → mm zone          : translation vers le coin, puis rotation -θ
mm zone      → pixel de sortie  : mise à l'échelle px_per_mm
```

Conséquence pratique dont dépend tout l'éditeur de cordons : l'image obtenue a son coin
`(0, 0)` sur le coin haut-gauche de la zone et une échelle constante. **Un clic à
`(px, py)` vaut donc `(px / px_per_mm, py / px_per_mm)` en mm relatifs à la zone** — une
simple division, sans repasser par l'homographie point par point.

### Report des cordons et précision

Les cordons sont mémorisés en mm relatifs à la **zone de référence**, celle que
l'opérateur a ouverte en premier. Les afficher sur une autre zone consiste à appliquer
`DepositZone.to_plateau_mm()` de la zone visée, puis à reprojeter en pixels avec
`mm_to_pixels()`.

⚠️ **La précision du report dépend de la qualité de l'homographie.** Avec le repli à 2
marqueurs — le mode nominal sur la Geeetech — il n'y a pas de correction de perspective :
plus une zone est éloignée des marqueurs servant de référence, plus sa position accumule
d'erreur. Imperceptible à l'écran, cela se traduira par quelques millimètres de décalage à
la dépose réelle. Les deux parades sont la calibration ChArUco (corrige la distorsion
d'objectif, première source d'erreur) et, sur la CNC, un recul de caméra permettant de
voir les quatre coins du plateau.

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
| `work_area_width_mm` / `work_area_height_mm` | **Distance CENTRE À CENTRE des marqueurs de coin.** La grandeur réellement utilisée par l'homographie. ✅ Mesurée sur le PoC le 2026-08-04 : **205,5 mm**. À privilégier — c'est ce qu'on mesure naturellement au mètre |
| `plateau_size_mm` (+ `_width_` / `_height_`) | Voie indirecte : mesure bord **EXTÉRIEUR** à bord extérieur, dont une largeur de marqueur est retranchée automatiquement. ⚠️ **Ne JAMAIS y saisir une mesure centre-à-centre** : elle retrancherait une seconde fois les 28 mm du marqueur, soit une erreur silencieuse de 28 mm |
| `photo_position_x` / `_y` / `_z` | Position où la machine se place avant **toute** acquisition. Défaut `(0,0,0)` = le homing, ce qui convient au PoC (caméra fixe sur le bâti). La CNC aura une vraie position, sa caméra étant solidaire de la seringue — action `M10` |
| `machine_travel_x_max_mm` / `_y_` / `_z_` | Bornes du domaine atteignable, pour le contrôle de course fait avant chaque dépose. ⚠️ Valeurs actuelles = dimensions **catalogue** d'une Geeetech I3, **jamais relevées** (action `M11`). Une valeur trop **grande** laisse passer un dépassement réel : c'est le sens dangereux |
| `dry_run_z_clearance_mm` | Marge ajoutée à la hauteur du homing pour la **dépose à blanc** (défaut 2,0). Constatée nécessaire le 2026-08-04 : à la hauteur du homing seule, la pointe passe trop près du dessus des zones |
| `camera_flush_frames` | Nombre d'images jetées avant celle qu'on garde, à chaque capture (défaut 5). Voir section 4.7 |

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

### 4.7 La photo analysée est celle du cycle PRÉCÉDENT

**Symptôme** (constaté le 2026-08-04) : au second cycle de dépose, l'image analysée
montre le plateau tel qu'il était à la **fin du cycle précédent**. Les zones sont donc
détectées au mauvais endroit — et **rien ne le signale** : la photo est nette, les
marqueurs sont dedans, le diagnostic ressort vert.

**Cause** : le pilote garde quelques images d'avance dans un tampon, et `read()` rend la
**plus ancienne**, pas la plus récente. L'enchaînement est traître :

1. l'écran d'accueil lit la caméra en continu → tampon frais ;
2. l'appui sur « Lancer une dépose » **arrête** cette lecture → tampon figé à cet instant ;
3. le homing et la mise en position durent 30 à 60 s, pendant lesquelles **plus personne
   ne lit** ;
4. `capture()` lit une image → celle figée à l'étape 2, donc **d'avant le déplacement**.

**Protection en place** : `Camera.capture()` lit et jette `CAMERA_FLUSH_FRAMES` images
(défaut 5) avant de garder la suivante. Réglable par `camera_flush_frames`. Verrouillé
par trois tests dans `test_camera.py`, qui n'ont besoin d'aucun matériel : ils remplacent
le flux par un faux qui rend des images numérotées.

⚠️ **Symptôme voisin à ne pas confondre** : si l'image est bonne mais que la MACHINE
semble mal placée, c'est la mise en position qu'il faut regarder (`PhotoPositionWorker`
dans `gui/workers.py`), pas le tampon.

**Règle générale** : après toute période sans lecture, la première image d'une caméra est
suspecte. Ne jamais la traiter comme fraîche.

### 4.8 La buse traverse le plateau à la hauteur du homing

**Symptôme** (constaté le 2026-08-04) : au tout début d'un parcours, la buse se déplace
horizontalement en rasant les pièces avant de monter.

**Cause** : `Machine.move_to()` envoie `G1 X Y` **puis** `G1 Z` — le déplacement XY a donc
toujours lieu à la hauteur où la buse se trouvait **avant**. Juste après un homing, cette
hauteur est celle du homing.

**Protection en place** : `Machine.move_z()` déplace **uniquement** l'axe Z, et les deux
workers de `gui/workers.py` et `gui/screen_execution.py` s'en servent pour se dégager
avant tout déplacement horizontal. Verrouillé par
`test_le_worker_se_degage_en_z_avant_tout_deplacement_horizontal`.

⚠️ **Conséquence à garder en tête pour toute évolution** : dans une liste de steps, la
hauteur à laquelle un déplacement XY a réellement lieu est celle du step **précédent**,
pas celle du step courant. Un test qui vérifierait le `z` du step qui bouge ne prouverait
rien — l'erreur a été commise puis corrigée en écrivant l'invariant I2 du lot D1.

### 4.9 Les couleurs des rapports PDF sont fausses (rouge et bleu échangés)

**Symptôme** : sur un rapport PDF, la photo a des teintes anormales — le rouge apparaît
bleu et inversement. Peu visible sur un plateau grisâtre, flagrant dès qu'une pièce
colorée est dans le champ.

**Cause** (défaut présent de la Phase 7 au 2026-08-04) : `reporter.py` appelait
`cv2.cvtColor(image, COLOR_BGR2RGB)` **avant** `cv2.imwrite`. Or `imwrite` suppose déjà
que le tableau reçu est en BGR et fait la conversion lui-même : convertir en amont
revenait à la faire **deux fois**.

**Protection en place** : l'écriture passe par `reporter._ecrire_image_temporaire()`, qui
donne le tableau BGR tel quel à `imwrite`. Verrouillé par
`test_l_image_du_rapport_n_a_pas_le_rouge_et_le_bleu_inverses`, qui écrit un bleu franc et
vérifie qu'il ressort bleu.

⚠️ **Règle à retenir** : `cv2.imwrite` attend du **BGR**, `QImage.Format_RGB888` attend du
**RGB**. Le premier ne demande aucune conversion, le second en demande une. Les confondre
ne provoque jamais d'erreur — seulement une image fausse.

### 4.10 Les rapports PDF n'apparaissent pas dans `reports/`

**Deux causes possibles, distinctes.**

**(a) Ils ont été écrits ailleurs** (corrigé le 2026-08-04). Le dossier de sortie était le
chemin **relatif** `"reports"`, qui suit le répertoire courant : lancer l'application
autrement qu'en se plaçant d'abord à la racine — raccourci, service au démarrage du RPi,
double-clic — dispersait les rapports. `modules/config.py::REPORTS_DIR` est désormais un
chemin absolu calculé depuis l'emplacement du code, comme `PREPARATIONS_DIR`.

**(b) Un rapport en a écrasé un autre** (corrigé le 2026-08-04). Le nom de fichier n'a
qu'un horodatage **à la seconde** : deux rapports produits dans la même seconde portaient
le même nom. `Reporter._chemin_libre()` suffixe désormais plutôt que d'écraser.

⚠️ **Règle générale** : tout chemin de sortie du projet doit être calculé depuis
`os.path.dirname(__file__)`, jamais relatif au répertoire courant. Un fichier écrit au
mauvais endroit ne provoque aucune erreur — il disparaît simplement de la vue.

## 5. Lancer les tests

```bash
pytest                          # suite complète — doit passer avant tout commit/push
pytest -m "not toutes_cameras"  # sans le seul test qui ouvre toutes les caméras
pytest tests/test_vision.py     # un module en particulier
python tests/demo_camera.py     # démo manuelle (hors pytest)
```

### 5.1 Comment les tests choisissent leur caméra

**La caméra n'est pas choisie par configuration, mais par vérification** : la fixture
`plateau_capture` (`tests/conftest.py`) retient celle où des **marqueurs ArUco sont
réellement détectés**, c'est-à-dire celle qui voit le plateau. La webcam intégrée d'un PC,
qui filme la pièce ou l'opérateur, n'y répond jamais.

Ce critère remplace la confiance faite à `CAMERA_INDEX`, qui ne prouvait rien : si cet
index est faux, les tests passent en validant le **mauvais matériel** sans que rien ne le
signale. Le projet s'est fait piéger deux fois par ce mécanisme — le blocage ChArUco du
2026-07-29, puis une fixture codée en dur sur l'index 0 découverte le 2026-08-01.

L'ordre d'essai est important :

1. **la caméra configurée d'abord** — dans le cas nominal on s'arrête là, et aucune autre
   caméra de la machine n'est ouverte (la webcam intégrée ne s'allume donc pas) ;
2. les autres caméras détectées, **uniquement** si la configurée ne voit aucun marqueur.

Cinq captures sont tentées par caméra avant de conclure : les premières trames d'une
webcam sont souvent sombres ou floues (auto-exposition, autofocus).

**Une seule capture pour toute la session** (`scope="session"`) : l'image est ensuite
réutilisée par tous les tests qui n'ont besoin que de pixels. C'est plus rapide, et
surtout **déterministe** — deux tests portent exactement sur les mêmes pixels.

Si aucune caméra ne voit de marqueur (pas de caméra branchée, ou plateau hors champ),
les tests concernés se `skip` proprement. Un échec serait trompeur : ce n'est pas le code
qui est en cause.

### 5.2 Le test qui ouvre toutes les caméras

`test_list_devices_retourne_des_index_ouvrables` vérifie que la liste déroulante de
l'écran 1 ne propose pas de caméras fantômes : il **doit** donc toutes les ouvrir, webcam
intégrée comprise. C'est le seul du projet dans ce cas, et il porte le marqueur
`toutes_cameras` (déclaré dans `pytest.ini`) pour pouvoir être écarté :

```bash
pytest -m "not toutes_cameras"
```

Ordre de grandeur observé sur PC de développement : ~65 s avec, ~41 s sans.

## 6. Où sont stockées les données

| Donnée | Emplacement | Suivi par git ? |
|---|---|---|
| Calibration objectif | `assets/camera_calibration.npz` | Non — spécifique à chaque machine |
| Config par machine | `local_config.json` | Non |
| Préparations validées | `preparations/<produit>.json` | Non |
| Travaux interrompus (autosave) | `preparations/<produit>.autosave.json` | Non |
| Rapports PDF générés | `reports/*.pdf` | Non |
| Mire ChArUco générée | `assets/charuco_calibration.png` | À vérifier au cas par cas |

### 6.1 Fichier de préparation — format et cycle de vie

Une **préparation** rassemble tout le travail fait sur un plateau : la référence du
produit, les zones détectées, les cordons et les paramètres de dépose. Le module
responsable est `modules/preparation.py`.

**Deux fichiers, deux rôles** :

| Fichier | Écrit par | Rôle |
|---|---|---|
| `<produit>.json` | Le bouton d'enregistrement | La préparation **validée** par l'opérateur |
| `<produit>.autosave.json` | Automatiquement, toutes les 5 s | Filet **anti-plantage** |

L'autosave ne touche jamais au fichier définitif : tant que l'opérateur n'a pas validé,
son dernier enregistrement volontaire reste intact. À l'inverse, l'enregistrement
définitif **supprime** l'autosave — sans quoi l'application proposerait indéfiniment de
reprendre un travail déjà terminé. La présence d'un `.autosave.json` au démarrage
signale donc un travail interrompu, et rien d'autre.

**Écriture atomique** : les deux fichiers passent par un temporaire puis `os.replace()`.
Une coupure en pleine écriture laisserait sinon un fichier tronqué — particulièrement
absurde pour une sauvegarde dont le rôle est justement de protéger des plantages.

**Coordonnées** : les cordons sont enregistrés en **mm relatifs à la zone** — origine au
coin **bas-gauche** (`DepositZone.origin_mm`), X le long de la largeur, **Y le long de la
hauteur vers le haut** depuis le lot C2bis. C'est ce qui permet de rejouer un même cordon
dans toutes les zones, et ça les rend insensibles à un léger déplacement de la caméra.
Les positions des zones, elles, sont en mm **absolus** dans le repère du plateau : elles
ne valent donc que pour la position de caméra du jour où la photo a été prise.

**`format_version`** : un fichier écrit par une version **plus récente** du logiciel est
refusé avec un message explicite, plutôt que relu de travers — sur des coordonnées de
dépose, une lecture silencieusement fausse enverrait la buse au mauvais endroit. À
l'inverse une clé *manquante* reprend sa valeur par défaut, donc un fichier ancien reste
lisible. Incrémenter `FORMAT_VERSION` dès qu'un changement rend les anciens fichiers
inexploitables.

**Version 2 (lot C2bis) et conversion des fichiers v1.** Le changement de repère a
retourné l'axe Y du plateau **et** celui des zones : toutes les ordonnées enregistrées ont
changé de sens. Le contrôle de version ne protégeait pas de ce cas — il ne refusait que
les fichiers plus récents — donc un v1 aurait été relu silencieusement à l'envers. Les
fichiers v1 sont désormais **convertis au chargement** puis **réécrits en v2**, et la
conversion est signalée à l'opérateur (`Preparation.conversion_message`) : un cordon qui
bouge tout seul sans explication est plus inquiétant qu'un message.

Trois points à connaître si vous ajoutez un jour une version 3 :

- **Convertir après avoir reconstruit, pas au fil de la lecture.** Retourner un cordon
  demande la hauteur de sa zone (`size_mm`), connue seulement une fois les zones relues.
  Lire dans l'ordre du fichier reviendrait à espérer que les zones y précèdent les
  cordons — dépendance invisible et fragile.
- **Convertir tout ce qui bascule, ou rien.** Un fichier à moitié converti est incohérent
  avec lui-même, ce qui est pire que pas de conversion du tout.
- **C'est `load_preparation()` qui réécrit, pas `from_dict()`.** Cette dernière ne doit
  pas toucher au disque : elle sert aussi sur des données en mémoire, tests compris.

Un fichier v1 contenant des cordons **mais aucune zone** est refusé : la hauteur
nécessaire est introuvable, et laisser passer des cordons à l'envers enverrait la buse au
mauvais endroit.

#### Câblage dans l'IHM (lot C3) — trois pièges à ne pas réintroduire

**a) La sauvegarde automatique n'écrit que si `_modifie` est levé.** Le `QTimer` de
`ScreenCordons` bat toutes les 5 s tant que l'écran est ouvert, mais n'écrit que si le
signal `cordons_modified` a été émis depuis la dernière écriture. Retirer ce drapeau
réécrirait le fichier toutes les 5 s indéfiniment — sur la **carte SD** du Raspberry Pi,
c'est de l'usure gratuite. Le drapeau n'est abaissé qu'après une écriture **réussie** :
un échec passager ne doit pas faire perdre les modifications de la période.

**b) La zone de RÉFÉRENCE doit être restaurée avant tout affichage à la reprise.** Les
cordons sont exprimés dans son repère. Si la première zone rouverte par l'opérateur
devenait la nouvelle référence, ils seraient réinterprétés dans un repère qui n'est pas le
leur et se retrouveraient décalés, **sans que rien ne le signale**. Même famille de faute
silencieuse que le miroir vertical du lot C2bis. Verrouillé par
`test_reprise_restaure_la_zone_de_reference`.

**c) Le numéro `BOITIER_X` ne se calcule qu'à la lecture de `product_name`.** Le calculer
à la construction du dialogue ferait avancer la numérotation à chaque ouverture, même
annulée. Les autosaves comptent comme numéros occupés : sans ça, un `BOITIER_3` inachevé
verrait son numéro réattribué, et le second plateau écraserait le premier.

> **Ce qui n'est PAS enregistré : la photo du plateau.** Reprendre un travail interrompu
> restaure les cordons, les paramètres et la zone de référence, puis demande une nouvelle
> capture. C'est possible parce que les cordons sont en mm **relatifs à la zone** — voir
> plus haut. Ne pas « corriger » cela en persistant l'image : ce serait ajouter une gestion
> de fichiers annexes pour restaurer une donnée que le dispositif reconstruit en un appui.
>
> `MainApp.propose_resume()` est appelée depuis `main.py` **après** `show()`, jamais depuis
> `__init__` : une boîte modale pendant la construction s'afficherait sans la fenêtre qui
> lui donne son contexte. Répondre « Non » conserve le fichier — on ne détruit pas un
> travail sur une réponse hâtive.

**Nom de fichier** : le nom du produit est saisi librement par l'opérateur et sert de nom
de fichier. Les caractères interdits (`< > : " / \ | ? *`) sont remplacés par `_`, sinon
une référence du type `REF 12/34` créerait un sous-dossier fantôme. Le champ
`product_name` **à l'intérieur** du fichier garde la référence exacte, c'est lui qui est
affiché à l'écran.

**Lisibilité** : les paires de coordonnées sont maintenues sur une seule ligne. Sans ce
traitement, `json.dumps(indent=2)` éclaterait chaque `[x, y]` sur six lignes et un
plateau réaliste ferait plusieurs centaines de lignes de crochets quasi vides. Le
résultat reste du JSON strictement standard.
