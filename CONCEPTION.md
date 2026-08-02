# Document de Conception — Machine de Dépose de Pâte Thermique

**Projet** : Automatisation de la dépose de pâte thermique sur coques de calculateur automobile  
**Contexte** : Projet d'études — apprentissage progressif  
**Dernière mise à jour** : 2026-07-11  

---

## 1. Description du système physique

### 1.1 Stratégie matérielle — deux machines, un seul logiciel

Le projet utilise **deux machines successives** avec le même firmware Marlin, ce qui permet de développer et valider le logiciel sur la machine disponible immédiatement, puis de le transférer sur la machine de production sans réécriture.

| Machine | Rôle | Calendrier |
|---|---|---|
| **Geeetech I3 (imprimante modifiée)** | Proof of concept — développement et validation logicielle | Maintenant → fin juin 2026 |
| **CNC cible** (carte Marlin) | Machine de production finale | 🔄 Quasi assemblée (méca + carte + Marlin flashés, 2026-07-11) |

> **Portabilité** : les deux machines parlent le même G-code Marlin. Le passage de l'une à l'autre se limite à la mise à jour des paramètres de `config.py` (port série, dimensions de la zone de travail, limites d'axes).

---

### 1.2 Inventaire matériel — Machine PoC (Geeetech I3)

| Composant | Référence / Modèle | Rôle |
|---|---|---|
| Ordinateur de contrôle | Raspberry Pi 3B+ | Exécute le logiciel, pilote tous les périphériques |
| Caméra | **Philips SPC 1330NC** (USB, pilote UVC) | Capture l'image de la pièce avant et après dépose |
| Interface utilisateur | Écran tactile 7 pouces (800×480) | Affichage de l'IHM, saisie par le toucher |
| Base mécanique | Imprimante 3D Geeetech I3 (axes X/Y/Z) | Déplacement de la buse sur la pièce |
| Actionneur de dépose | Moteur Nema 17 sur axe E (ex-extrudeur) + vis sans fin | Pousse le piston de la seringue de pâte thermique |
| Contrôleur machine | Carte d'origine Geeetech — firmware **Marlin 1.1.8** (compilé 2022-09-25) | Interprète les commandes G-code, pilote les moteurs |
| Pièce à traiter | Coque de calculateur automobile | Support de la dépose de pâte thermique |
| Référentiel géométrique | 4 marqueurs ArUco (DICT_4X4_50, IDs 0–3) | Permettent le calibrage de perspective par vision |

> **Caméra** : Philips SPC 1330NC USB — détectée par OpenCV via `cv2.VideoCapture(0)`. Résolution max confirmée : **1280×960** (vérifié le 2026-06-11 via `camera.width`/`camera.height`). Hauteur de montage : **200 mm** au-dessus de la zone de travail (mesure du 2026-06-12).  
> **Firmware Marlin** : **Marlin 1.1.8** (compilé 2022-09-25) — confirmé le 2026-07-01 via `M115`. Port série : `/dev/ttyUSB0` (puce CH340). Baudrate : **250000** (configuré dans l'EEPROM de la Geeetech). Steps/mm : X=80.80, Y=80.80, Z=2560.00, E=102.00. Vitesse max Z : 2 mm/s = 120 mm/min.

### 1.3 Inventaire matériel — Machine cible (CNC)

| Composant | Référence / Modèle | Statut |
|---|---|---|
| Base mécanique | CNC — châssis + axes | ✅ Montée (2026-07-11) |
| Contrôleur machine | Carte CNC — firmware **Marlin dernière version** | ✅ Intégrée, câblée, sous tension, flashée (2026-07-11) |
| Câblage capteurs + moteurs | Fins de course, caméra, moteurs Nema 17 | 🔄 En cours |
| Ordinateur de contrôle | Même Raspberry Pi 3B+ | ✅ Réutilisé depuis Geeetech |
| Caméra + écran | Même Philips SPC 1330NC USB + écran 7" | ✅ Réutilisés depuis Geeetech |

> **Avancement (2026-07-11)** : mécanique montée, carte de commande intégrée et câblée, mise sous tension et **flash Marlin dernière version** effectués. Reste le câblage des capteurs (fins de course, caméra) et des moteurs. Firmware Marlin confirmé → portage transparent (même dialecte G-code que la Geeetech, seul `config.py` change).

---

### 1.4 Connexions entrées/sorties (E/S)

Ces connexions sont identiques sur les deux machines (Geeetech et CNC cible), seul le port série peut changer.

| Interface | Protocole | Connecteur | De | Vers |
|---|---|---|---|---|
| USB caméra | UVC (pilote noyau Linux) | USB Type-A | RPi 3B+ | Philips SPC 1330NC |
| USB série | UART via CH340 (ou FT232) | USB Type-A → USB Type-B | RPi 3B+ | Carte contrôleur Marlin |
| HDMI | HDMI 1.4 | HDMI standard | RPi 3B+ | Écran tactile 7" |
| USB tactile | HID USB | USB Type-A | RPi 3B+ | Contrôleur tactile de l'écran |
| Alimentation | 5 V / 2,5 A min | Micro-USB | Alimentation murale | RPi 3B+ |

> **Note caméra :** la Philips SPC 1330NC apparaît sous `/dev/video0` (pilote UVC standard). Accessible directement via `cv2.VideoCapture(0)` sans configuration supplémentaire.  
> **Note port série :** la carte contrôleur apparaît sous `/dev/ttyUSB0` (puce CH340) ou `/dev/ttyACM0` (puce ATmega USB natif). À identifier avec `ls /dev/tty*` avant et après connexion USB.

---

### 1.3 Synoptique matériel

```mermaid
graph LR
    subgraph RPi["🖥️ Raspberry Pi 3B+"]
        SOFT["Logiciel Python\ncaméra · vision · machine\npath_planner · GUI · reporter"]
    end

    CAM["📷 Philips SPC 1330NC\n(USB, pilote UVC)"]
    SCREEN["🖱️ Écran tactile 7\"\n800×480 px\n(HDMI + USB touch)"]

    subgraph MACHINE["⚙️ Geeetech I3 — Firmware Marlin"]
        CTRL["Carte contrôleur\nGeeetech"]
        AXE_XY["Axes X / Y\n(déplacement buse)"]
        AXE_Z["Axe Z\n(hauteur buse)"]
        PISTON["Axe E → Piston Nema 17\n(dépose pâte thermique)"]
        HOMING["Capteurs fin de course\n(remise à zéro)"]
        CTRL --> AXE_XY & AXE_Z & PISTON & HOMING
    end

    subgraph ZONE["🔧 Zone de travail"]
        PIECE["Coque calculateur\nautomobile"]
        ARUCO["Marqueurs ArUco ×4\n(coins — IDs 0, 1, 2, 3)"]
    end

    CAM -->|"USB — UVC"| RPi
    SCREEN -->|"HDMI + USB"| RPi
    RPi -->|"USB série\nCH340 · 250000 baud\nprotocole G-code"| MACHINE

    CAM -. "capture image\n(avant / après)" .-> ZONE
    PISTON -. "dépose pâte\nthermique" .-> PIECE
```

> **Légende :** traits pleins = liaisons physiques permanentes · traits pointillés = interactions fonctionnelles

---

### 1.4 Contraintes matérielles et choix techniques

#### Raspberry Pi 3B+ — limitations à prendre en compte

| Ressource | Valeur RPi 3B+ | Impact sur le projet |
|---|---|---|
| RAM | 1 Go | Images OpenCV limitées à 1280×960 max en mémoire simultanée |
| CPU | Cortex-A53 × 4 cœurs @ 1,4 GHz (64 bits) | Traitement ArUco en ~100–300 ms selon résolution |
| GPU | VideoCore IV | Non utilisé dans ce projet (pas de CUDA/OpenCL nécessaire) |
| USB | USB 2.0 ×4 | Débit série largement suffisant (250000 baud = ~24 Ko/s) |
| Interface caméra | USB (UVC) | Philips SPC 1330NC — `cv2.VideoCapture(0)` directement, aucun pilote supplémentaire |

**Stratégie d'optimisation adoptée :**
- Capture en haute résolution uniquement pour la photo du rapport (résolution max de la SPC 1330NC à vérifier)
- Traitement ArUco en résolution réduite (640×480) pour la rapidité
- Pas de traitement vidéo temps réel : capture déclenchée sur demande uniquement

#### Caméra USB — interface logicielle

La Philips SPC 1330NC est une webcam USB standard (pilote UVC, natif Linux). Elle est reconnue automatiquement sous `/dev/video0` et accessible via `cv2.VideoCapture(0)` sans aucune configuration.

| Paramètre | Valeur | Comment vérifier |
|---|---|---|
| Index OpenCV | `0` | Confirmé en test |
| Nœud kernel | `/dev/video0` | `ls /dev/video*` |
| Résolution max | **1280×960** ✅ | Confirmé le 2026-06-11 via `camera.width`/`camera.height` |
| Pilote | UVC (intégré au noyau) | Aucune installation nécessaire |
| Hauteur de montage | **200 mm** | Mesurée physiquement le 2026-06-12 |

#### Firmware Marlin — commandes utilisées

Les commandes G-code utilisées dans ce projet sont standard Marlin depuis la version 1.1.x. Le projet est donc compatible avec toutes les versions récentes de Marlin installées sur les cartes Geeetech.

| Commande | Disponible depuis | Description |
|---|---|---|
| `G28` | Marlin 1.0+ | Homing tous axes |
| `G1 X Y Z F` | Marlin 1.0+ | Déplacement linéaire |
| `G1 E F` | Marlin 1.0+ | Avance extrudeur (→ piston) |
| `M114` | Marlin 1.0+ | Position courante |
| `M112` | Marlin 1.0+ | Arrêt d'urgence |
| `M115` | Marlin 1.0+ | Version firmware |

---

### 1.5 Flux de travail physique

```
[Calibration ChArUco — une seule fois] ─┐
                                        ▼
[Boîtiers + 4 ArUco sur plateau] → [Photo redressée] → [Tracé de cordons + quantité par cordon]
   → [Sauvegarde préparation JSON] → [Dépose automatique] → [Rapport PDF : temps + quantité totale]

Réutilisation (plateau inchangé) : [Charger préparation JSON] → [Éditer si besoin] → [Dépose]
```

---

## 2. Architecture logicielle

### Structure des fichiers

```
thermal_paste_dispenser/
│
├── main.py                  # Point d'entrée, machine à états principale
│
├── modules/
│   ├── camera.py            # ✅ Phase 1 — capture image via USB (classe Camera)
│   ├── vision.py            # 🔄 Phase 2 — détection ArUco, homographie, pixel→mm
│   ├── calibration.py       # 🔄 Phase 2 — calibration objectif, correction distorsion
│   ├── machine.py           # 🔄 Phase 3 — communication série G-code avec Marlin (axe E à tester)
│   ├── path_planner.py      # ⬜ Phase 5 — calcul des trajectoires de dépose
│   ├── reporter.py          # ⬜ Phase 7 — génération de rapport PDF
│   └── config.py            # ✅ Paramètres globaux et constantes
│
├── gui/
│   ├── app.py               # 🔄 Phase 4 — fenêtre principale PyQt5, gestionnaire d'écrans
│   ├── screen_capture.py    # 🔄 Phase 4 — Écran 1 : flux caméra + capture + validation
│   ├── screen_zone.py       # Écran 2 : sélection zone + quantité pâte
│   ├── screen_run.py        # Écran 3 : exécution et monitoring
│   └── screen_report.py     # Écran 4 : visualisation rapport
│
├── assets/                  # Ressources statiques (icônes, polices)
├── reports/                 # Rapports PDF générés (horodatés)
└── tests/                   # Tests unitaires par module
```

### Diagramme de navigation entre écrans

```
[Écran Capture] ──(photo OK)──► [Écran Zone/Quantité]
                                        │
                                   (lancer)
                                        ▼
                              [Écran Exécution]
                                        │
                                   (terminé)
                                        ▼
                              [Écran Rapport]
                                        │
                                (nouvelle pièce)
                                        │
                                        ▼
                              [Écran Capture]
```

### Machine à états principale

```
IDLE → CAPTURE → CONFIGURE → RUNNING → DONE → IDLE
                                ↑
                           (erreur) → ERROR → IDLE
```

---

## 3. Stack technique

Toutes les librairies utilisées sont **open source** et utilisables en entreprise sans licence tierce payante.

| Besoin | Librairie | Licence | Version cible | Justification |
|---|---|---|---|---|
| Interface tactile | PyQt5 | GPL v3* | ≥ 5.15 | Mature, bien documenté, bon rendu tactile |
| Vision / ArUco | opencv-contrib-python | Apache 2.0 | ≥ 4.8 | Standard industrie, module ArUco intégré |
| Caméra USB (UVC) | opencv-contrib-python | Apache 2.0 | ≥ 4.8 | Déjà utilisé pour la vision — `cv2.VideoCapture(0)` suffit |
| Communication machine | pyserial | BSD | ≥ 3.5 | Communication USB/UART avec Marlin |
| Rapports PDF | fpdf2 | LGPL | ≥ 2.7 | Simple, pur Python, pas de dépendances lourdes |
| Calcul numérique | numpy | BSD | ≥ 1.24 | Algèbre vectorielle pour les trajectoires |
| Tests | pytest | MIT | ≥ 7.0 | Standard Python |

> *PyQt5 est sous licence GPL v3 pour sa version open source. Dans un contexte d'usage interne (logiciel non distribué à des tiers), cette licence ne pose aucune contrainte. Si le logiciel devait être distribué commercialement, il faudrait envisager PySide6 (LGPL).

### Installation (Raspberry Pi OS — Bullseye ou Bookworm)

```bash
# Dépendances système
sudo apt update && sudo apt install -y python3-pip python3-pyqt5 libatlas-base-dev

# Dépendances Python
pip3 install opencv-contrib-python pyserial fpdf2 numpy pytest
```

> La Philips SPC 1330NC est détectée automatiquement — aucune configuration système supplémentaire.

### Installation (Windows — développement sans matériel)

```bash
pip install opencv-contrib-python pyserial fpdf2 numpy pytest PyQt5
# La classe Camera peut être mockée pour les tests sans matériel
```

---

## 4. Module : Caméra & Vision (Phase 1 & 2)

### 4.1 Capture (`modules/camera.py`) ✅ Phase 1 validée

**Responsabilité** : Ouvrir le flux caméra, capturer une image sur demande.

**Interface publique :**
```python
class Camera:
    def __init__(self, device_index: int = 0)
    def capture(self) -> np.ndarray          # Retourne image BGR
    def release(self)
    # Attributs publics : self.width, self.height (résolution réelle appliquée)
```

**Résultats (2026-06-11) :** 4/4 tests pytest passés. Résolution 1280×960 confirmée sur RPi 3B+. Warm-up de 10 frames dans `__init__` pour éviter les images noires au démarrage.

### 4.2 Calibrage ArUco (`modules/vision.py`) 🔄 Phase 2 en cours

**Principe** : 4 marqueurs ArUco placés aux coins de la zone de travail permettent de calculer une homographie (transformation de perspective) qui redresse l'image et convertit les pixels en mm.

**Marqueurs du plateau** : Dictionnaire `DICT_4X4_50`, IDs 0–3, taille physique 28 mm × 28 mm. Disposition physique relevée le 2026-08-01, **telle qu'elle apparaît à l'écran** :

```
3 ─────── 0        origine du repère mm = marqueur 2 (bas-gauche)       Y
│         │        X+ vers la droite, vers le tag 1                     ↑
│         │        Y+ vers le HAUT, vers le tag 3                       └──→ X
2 ─────── 1        tag 0 = redondant → contrôle de cohérence
```

**Marqueurs de la zone de dépose** : IDs 4 et 5, posés aux deux coins opposés (en diagonale) de la zone où se trouve la pièce. Ils ne servent pas à l'homographie, seulement à délimiter la sous-région à redresser et à afficher.

#### Choix du repère — repère orthonormé à trois tags (lot C2bis, `v0.4.2`)

Le repère est **défini par trois tags** : origine au centre du tag **2** (bas-gauche), axe des ordonnées vers le tag **3**, axe des abscisses vers le tag **1**. Le tag **0** en devient redondant et sert de **contrôle de cohérence** (voir plus bas).

**Motif du choix** : aligner le repère logiciel sur le repère physique dans lequel on raisonne devant la machine, **avant** d'écrire la construction des commandes machine (lot D). L'axe Y machine croît vers le fond ; le repère plateau monte désormais lui aussi. La conversion vers le repère machine, dans `gui/screen_run.py`, devient donc deux additions — `machine_x = x_mm + MACHINE_ORIGIN_X`, `machine_y = y_mm + MACHINE_ORIGIN_Y` — au lieu d'une addition et d'une soustraction. L'alignement est porté par le repère lui-même, plus par une inversion isolée qu'il fallait penser à écrire.

**Historique — ce repère est le troisième, et le second en une journée.** Jusqu'au 2026-08-01 : origine au marqueur 0, Y vers le haut. Le matin du 2026-08-01 (`v0.1.1`) : origine au marqueur 3 (haut-gauche), Y vers le **bas**. Le soir, décision du repère actuel, livré en `v0.4.2`. Ce va-et-vient est instructif pour le rapport : le repère du matin avait été choisi pour de bonnes raisons *locales* (voir ci-dessous), et c'est en préparant le lot D — donc en regardant le problème depuis la machine et non depuis l'image — que le bon critère est apparu. Mieux valait payer le retournement à ce moment-là, sur 155 tests verts, qu'après avoir écrit le G-code par-dessus.

**Le point le plus subtil du lot — le miroir vertical.** Le repère du matin avait été motivé par deux arguments, dont il faut savoir ce que devient chacun :

1. *Toutes les coordonnées du plateau restent positives* (0 → WORK_AREA), ce qui évite les index négatifs — voir le bug d'écran noir, section 4.2 bis. Cet argument est **entièrement préservé** : l'origine reste sur un coin, simplement l'autre.
2. *L'image redressée s'affiche dans le bon sens.* Celui-ci **s'inverse**. Une image a son origine en haut à gauche et son Y qui descend (ligne 0 = ligne du haut), et aucune convention logicielle ne change ça. Avec Y montant, `y = 0 mm` est le **bas** du plateau : sans précaution, ce bas atterrirait sur la ligne 0, donc en haut de l'écran, et l'opérateur verrait le plateau à l'envers.

D'où la ligne écrite explicitement dans les **trois** méthodes `warp_*` (`warp_image`, `warp_region`, `warp_zone`) :

```
y_pixel = (hauteur_mm − y_mm) × échelle
```

Cette ligne n'est pas une entorse à la règle posée par l'étudiant — *la convention sert à faciliter les calculs, elle ne doit rien changer pour l'opérateur* — c'est **ce qui la garantit**. Le même miroir a existé dans le projet de la Phase 2 au 2026-08-01 sans que personne ne le voie à l'œil : un plateau à peu près symétrique ne trahit pas son propre retournement, et c'est le calcul qui l'a démasqué. `test_warp_image_orientation_non_miroir` en est le garde-fou.

**Contrôle de cohérence par le tag 0.** Le repère n'ayant besoin que de trois tags, le quatrième devient un témoin. On ajuste une similitude sur les tags 2, 1 et 3, on y projette le centre vu du tag 0, et on le compare au coin `(largeur, hauteur)` où il devrait tomber. Sur un plateau plan photographié par une caméra parfaitement perpendiculaire avec un objectif sans distorsion, l'écart serait nul ; il agrège en réalité l'inclinaison de la caméra, la distorsion de l'objectif (~10 % encore non corrigés), une déformation du plateau et un tag mal collé. C'est un **indicateur de qualité du montage optique** affiché à l'opérateur, pas une mesure d'incertitude. À noter : cet écart ne peut PAS se lire sur la matrice de `compute_homography()`, qui ajuste sans résidu à partir de 4 points et le donnerait nul par construction.

**Un test « boussole » épingle la convention en un seul endroit** (`test_boussole_de_la_convention_du_repere`) : tag 2 → `(0, 0)`, tag 3 → `(0, hauteur)`, image redressée non miroir, diagonale d'une zone saine à `dy < 0`. Si la convention rebouge un jour, c'est ce test qui doit échouer en premier, avant les vingt autres qui ne feraient que constater les dégâts en aval.

**Interface publique :**
```python
class PlateauReference:      # matrice + qualité du repère, pour la barre de statut
    homography: np.ndarray   # 3×3, pixel → mm
    marker_ids: list         # marqueurs de plateau réellement vus
    exact: bool              # True = 4 tags (perspective), False = 2-3 tags (similitude)
    check_error_mm           # écart du tag 0, ou None s'il n'était pas visible
    origin_extrapolated      # True si le tag 2 (origine) n'était pas dans le champ
    status_text: str         # résumé d'une ligne pour l'IHM

class VisionProcessor:
    def __init__(self, aruco_dict_id, marker_real_size_mm: float)
    def detect_markers(self, image: np.ndarray) -> dict           # {id: corners (4,2)}
    def compute_homography(self, detected_markers: dict) -> np.ndarray  # H 3×3, 4 marqueurs
    def compute_homography_approx(self, detected_markers: dict) -> np.ndarray  # 2-3 marqueurs
    def compute_plateau_reference(self, detected_markers) -> PlateauReference  # choix + qualité
    def warp_image(self, image, homography, output_size) -> np.ndarray
    def warp_region(self, image, homography, origin_mm, px_per_mm, output_size) -> np.ndarray
    def warp_zone(self, image, zone, homography, px_per_mm) -> np.ndarray
    def deposit_zone_bounds_mm(self, detected_markers, homography, id_a=4, id_b=5) -> tuple
    def pixel_to_mm(self, px, py, homography) -> tuple[float, float]
```

**Pourquoi `compute_plateau_reference()` existe** : le choix « 4 tags → homographie exacte, 2-3 tags → approchée » était écrit **deux fois**, dans `screen_plateau.py` et `screen_zone.py`. Deux copies d'une même règle finissent toujours par diverger, et c'est celle qu'on ne relit pas qui reste juste. La méthode regroupe la règle — et comme l'appelant a besoin de savoir dans quel mode il travaille pour en informer l'opérateur, elle retourne un objet portant la matrice **et** de quoi renseigner la barre de statut, pas une matrice nue.

**Taille du plateau, devenue un paramètre.** `PLATEAU_SIZE_MM` (surchargeable dans `local_config.json`, 220 mm par défaut) remplace la constante calculée en dur. Ce n'est pas un confort : cette valeur sert de **repli quand les 4 tags ne sont pas détectés**, c'est-à-dire dans le mode nominal de la Geeetech, où seuls 2 tags sont cadrés et où la position de l'origine (le tag 2) doit donc être **extrapolée**. Toute erreur dessus décale alors la totalité de la dépose, et aucun test automatique ne peut le détecter. La mesure au mètre reste à faire — action `M1` de `CLAUDE.md` section 7 bis. L'IHM affiche « origine extrapolée » dans ce mode, précisément pour que l'opérateur sache que sa précision repose sur un paramètre et non sur une mesure.

**Principe de l'homographie :**
`cv2.getPerspectiveTransform` calcule une matrice H (3×3) à partir de 4 paires de points (centres des marqueurs en pixels → positions réelles en mm). Pour tout point `p` dans l'image source, `H·p` donne ses coordonnées en mm dans le repère de la zone de travail.

#### ⚠️ Le repli 2-3 marqueurs et le miroir — défaut corrigé le 2026-08-02

Constaté **sur la machine**, après la livraison du lot C2bis : plus aucune zone de dépose n'était détectée, les quatre marqueurs de zone ressortant « orphelins ».

`cv2.estimateAffinePartial2D` ajuste une **similitude** (rotation + échelle uniforme + translation), dont le déterminant est toujours **positif** : elle ne peut pas produire de miroir. Or passer du repère image (Y vers le bas) au repère plateau (Y vers le haut) *est* un retournement. La matrice rendue faisait donc croître `y_mm` vers le bas — l'ancienne convention — pendant que tout le reste du code supposait l'inverse. Les diagonales de zone sortaient en `(+,+)` au lieu de `(+,−)`, et le filtre des paires plausibles les écartait comme fantômes.

**Correction** : ajuster la similitude vers un repère intermédiaire retourné en Y — de même « main » que l'image, le seul qu'elle sache atteindre — puis composer avec une matrice de retournement de déterminant −1. La partie rotation + échelle reste ajustée exactement comme avant.

**Ce que cet épisode enseigne, et c'est le plus utile pour le rapport** : les tests du repli existaient, mais ne vérifiaient que les points **ayant servi à l'ajustement**. Or ceux-là retombent juste quelle que soit l'orientation — c'est la définition d'un ajustement. Le test « boussole » du lot C2bis, lui, travaillait avec 4 marqueurs, donc sur une vraie homographie, qui sait mirroiter. Personne ne convertissait un **troisième** point pour regarder dans quel sens il partait. Le défaut portait ainsi sur le chemin le plus emprunté du logiciel — le repli 2 marqueurs est le mode *nominal* sur la Geeetech — tout en restant invisible à une suite de 193 tests verts.

> **Règle qui en découle : vérifier une transformation géométrique sur un point qui n'a pas servi à l'ajuster.** Un ajustement qui retombe sur ses propres points d'appui ne prouve rien.

Deux tests le gardent désormais : `test_compute_homography_approx_conserve_le_sens_de_y` (la cause, le sens de l'axe) et `test_zones_detectees_avec_deux_marqueurs_de_plateau` (l'effet, reproduisant la géométrie exacte de la capture d'écran du défaut).

**Repli à 2-3 marqueurs — mode nominal sur la Geeetech.** La caméra fixe de la Geeetech ne peut pas cadrer les 4 coins d'un plateau pleine taille : en pratique seuls les 2 marqueurs du haut (IDs 3 et 0) sont visibles, confirmé par observation directe le 2026-08-01. `compute_homography_approx()` calcule alors une **similitude** (rotation + échelle + translation, 4 degrés de liberté, `cv2.estimateAffinePartial2D`) au lieu d'une perspective complète (8 degrés de liberté). La correction de l'effet trapèze est impossible à déterminer avec 2 points, donc la précision est moindre et l'erreur croît avec l'inclinaison réelle de la caméra. L'interface affiche en permanence « ⚠ Précision réduite » dans ce mode. La CNC cible, qui a la place de reculer la caméra, devra utiliser `compute_homography()`.

**Résultats sessions 1 & 2 (2026-06-11) :** 14/14 tests passés. Détection 4 marqueurs simultanée confirmée. Image redressée validée visuellement (le miroir vertical n'a été détecté que le 2026-08-01, par le calcul et non à l'œil).

### 4.2 bis Zones de dépose — reconstruction géométrique (lot A, 2026-08-01)

**Besoin** : le plateau porte **plusieurs zones de dépose**, chacune accueillant un
exemplaire du **même produit**. Les cordons de pâte sont tracés une seule fois sur une
zone de référence, puis appliqués à toutes les autres. Les zones étant vissées à demeure,
l'ensemble est sauvegardé pour être rejoué.

**Repérage** : chaque zone est délimitée par **2 marqueurs ArUco** dont les centres sont
posés aux extrémités de la diagonale haut-gauche → bas-droit, avec la convention
`id(bas-droit) = id(haut-gauche) + 1`. Les IDs de zone commencent à 4, les IDs 0-3 étant
réservés aux coins du plateau. Cette convention d'incrément donne une **orientation** à
la zone, ce qui rend détectable un montage à l'envers.

**Problème central** : la convention `(n, n+1)` est ambiguë. Le tag 5 peut clore la paire
`(4,5)` ou ouvrir la paire `(5,6)`. Il n'existe aucun moyen local de trancher.

**Solution retenue** : exploiter l'invariante « toutes les zones portent le même produit,
donc ont la même diagonale ». On énumère toutes les paires possibles, on détermine la
longueur de diagonale **la plus représentée** sur le plateau, et on ne retient que les
paires qui la respectent. Les appariements fantaisistes ont une diagonale sans rapport et
disparaissent.

**Deux difficultés résolues en cours de développement** — utiles pour le rapport, elles
illustrent l'écart entre une règle qui paraît juste sur le papier et son comportement réel :

1. *Le filtrage par longueur ne suffit pas.* Sur un plateau en grille, deux zones voisines
   d'une même ligne engendrent une paire fantôme dont le vecteur diagonale est le
   **symétrique** du vrai — `(60, +40)` contre `(60, −40)` — donc de longueur strictement
   identique. Elle empruntant leurs tags aux deux zones réelles, elle les invalidait par
   conflit : un plateau parfaitement monté devenait inexploitable. La correction s'appuie
   sur le repère du plateau : le Y **montant** depuis le lot C2bis, une zone correctement
   montée avance en X et redescend en Y, soit `dx > 0` et `dy < 0`. Signes identiques =
   fantôme (écarté), `(−, +)` = zone inversée (signalée). ⚠️ C'est l'exact opposé du test
   d'avant `v0.4.2`, où les deux composantes d'une zone saine étaient positives : ce
   filtre est le premier à basculer quand l'axe Y change de sens, et `ANOMALIE_INVERSEE`
   repose entièrement dessus.

2. *La règle de « la plus petite rotation » se retournait contre nous.* Deux extrémités de
   diagonale ne définissent pas un rectangle ; connaître le format du produit ramène le
   nombre de solutions à deux, symétriques. Retenir la plus faible rotation semblait
   naturel — mais un rectangle 60×40 tourné de 25,8° a une diagonale orientée exactement
   comme un 40×60 posé droit, si bien que toute zone très inclinée ressortait à ~2° et que
   l'anomalie de montage devenait indétectable. L'ambiguïté n'existe en fait pas, le format
   étant déduit de la **médiane** des composantes sur toutes les zones : c'est un format
   *orienté*, la majorité ayant déjà tranché quel côté est la largeur. La rotation se
   calcule alors directement, `θ = angle(diagonale) − angle(w, −h)` — le signe moins sur
   la hauteur venant, là encore, du Y montant. `rotation_deg` est positif dans le sens
   **trigonométrique** depuis `v0.4.2` (c'était le sens horaire avant).

**Convention de signe de `product_size_mm`** (fixée au lot C2bis) : c'est un couple de
**longueurs**, donc à composantes positives. La médiane des `dy` étant négative en repère
Y montant, la conversion « composante → longueur » se fait à un seul endroit, l'étape 5 de
`detect_deposit_zones_mm()`. Tout le reste du fichier peut alors supposer partout
`largeur > 0` et `hauteur > 0`.

**Déduction du format du produit sans saisie opérateur** : les zones étant censées être
vissées à peu près droites, le vecteur diagonale d'une zone bien montée vaut directement
`(largeur, hauteur)`. La médiane sur l'ensemble des zones saines donne donc le format du
produit sans rien demander à l'opérateur, et une zone isolée de travers ne fausse pas le
résultat.

**Anomalies détectées** : zone inversée, diagonale hors norme, paire en conflit, angle
excessif. Une zone anormale n'invalide pas le plateau : elle est signalée et l'opérateur
choisit de continuer avec les seules zones saines ou de rectifier le montage.

**Limite assumée** : avec une **seule** zone détectée, celle-ci définit à elle seule la
référence de format ; sa rotation ressort donc nulle même si elle est physiquement de
travers. C'est une limite mathématique du dispositif, pas un défaut d'implémentation — il
faut au moins deux zones pour que la comparaison ait un sens.

**Interface publique** (fonction pure, testable sans caméra) :
```python
detect_deposit_zones_mm(centers_mm, ...) -> PlateauLayout
VisionProcessor.detect_deposit_zones(detected_markers, homography, ...) -> PlateauLayout
```

**Résultat** : 15 tests dédiés, 78/78 pour la suite complète.

### 4.3 Calibration objectif (`modules/calibration.py`) ✅ ChArUco implémenté — validation terrain en attente

**Problème** : Les objectifs de webcam bon marché introduisent une **barrel distortion** — les objets au centre de l'image paraissent plus grands qu'ils ne le sont. L'homographie corrige la perspective mais pas cette distorsion, ce qui cause une erreur de mesure d'environ **10 %** sur les distances intérieures à la zone de travail (mesuré le 2026-06-12 avec la Philips SPC 1330NC à 200 mm de hauteur).

**Solution** : Calibration one-shot avec une **mire ChArUco** imprimée (damier fusionné avec des marqueurs ArUco). Les coefficients de distorsion sont sauvegardés dans `assets/camera_calibration.npz` (gitignoré — spécifique à chaque caméra/objectif physique) et appliqués via `cv2.undistort` avant tout traitement.

> **Choix ChArUco (décidé 2026-07-11)** : préféré à l'échiquier classique car chaque coin est identifié individuellement par son marqueur ArUco. La calibration reste donc valide même si la mire est partiellement hors champ ou occultée — plus robuste et plus rapide à capturer. Cohérent avec le reste du projet qui utilise déjà ArUco (opencv-contrib).

**Procédure de calibration (une seule fois) :**
1. Générer et imprimer la planche ChArUco (bouton "Générer la mire" dans `gui/screen_calibration.py`, ou `generate_charuco_image`)
2. Dans l'écran de calibration, capturer 15+ vues sous différents angles — la détection en direct affiche le nombre de coins ChArUco trouvés et la distance caméra↔mire
3. Les coefficients sont calculés en arrière-plan (`QThread`) puis sauvegardés automatiquement dans `assets/camera_calibration.npz`

**Interface publique :**
```python
create_charuco_board(squares_x, squares_y, square_mm, marker_mm, dict_id, legacy_pattern)  # → cv2.aruco.CharucoBoard
generate_charuco_image(board, output_path, ...)               # génère et sauvegarde l'image de la mire
detect_charuco(image, board, detector)                        # → (corners, ids, preview, marker_count)
calibrate_charuco(all_corners, all_ids, board, image_size)     # → (camera_matrix, dist_coeffs, error)
estimate_board_pose(corners, ids, board, camera_matrix, dist_coeffs)  # → (rvec, tvec) ou (None, None)
distance_to_board_normal_mm(rvec, tvec)                        # → distance (mm) caméra↔plan de la mire
undistort(image, camera_matrix, dist_coeffs)                   # → image corrigée (mêmes dimensions)
save_calibration(path, camera_matrix, dist_coeffs)             # sauvegarde .npz
load_calibration(path)                                         # → (camera_matrix, dist_coeffs) ou (None, None)
```

> **Bug OpenCV 5.0 (corrigé 2026-07-29)** : `cv2.aruco.calibrateCameraCharuco()` a été supprimée de l'API "legacy" ChArUco dans OpenCV 5.0. Remplacée par le mécanisme générique recommandé : `board.matchImagePoints()` convertit chaque pose (coins ChArUco détectés + IDs) en paires points-objet 3D / points-image 2D à partir de la géométrie connue de la mire, puis `cv2.calibrateCamera()` (la même fonction générique que pour un échiquier classique) calcule la calibration. Détail complet en `MANUEL_MAINTENANCE.md` section 4.3.

> **Détection débloquée (2026-07-29)** : deux causes cumulées empêchaient `CharucoDetector.detectBoard()` de reconstruire la mire alors que `detectMarkers()` (ArUco brut) fonctionnait déjà : (1) `camera_index` dans `local_config.json` pointait sur la webcam intégrée du PC de dev, pas la caméra USB ; (2) `charuco_legacy_pattern: true` était incompatible avec les mires générées par l'appli — `board.generateImage()` ignore ce réglage et produit toujours le format "nouveau" (post-4.6), alors que `detectBoard()` le respecte côté détection. Réglage par défaut désormais `false`. Détail en `MANUEL_MAINTENANCE.md` section 4.2.

> **⚠️ Point ouvert — collision d'IDs ArUco** : le plateau (marqueurs de référentiel) et la mire ChArUco partagent le même dictionnaire `DICT_4X4_50` sans plage d'IDs séparée, ce qui perturbe la détection quand les deux sont visibles simultanément (cas normal pendant la calibration, où le plateau reste posé sous la mire). Contournement actuel : masquer le plateau avec du papier pendant la calibration. Voir aussi la question ouverte sur les IDs réels du plateau en section 9.

**Critère de qualité :** erreur de reprojection < 1.0 px (acceptable), < 0.5 px (excellent).

**Précision attendue après calibration :** ≤ 2 mm sur 100 mm (vs ~10 mm sans calibration). **Non encore validé en conditions réelles** — les 15 poses ont été capturées sur le PC de développement pour valider le pipeline logiciel ; à refaire sur le Raspberry Pi + Philips SPC1330NC réels.

---

## 5. Module : Communication Machine (Phase 3) ✅ Session 1 validée

### Protocole G-code (Marlin 1.1.8)

La Geeetech I3 utilise le firmware **Marlin 1.1.8** et communique via USB série à **250000 baud** (puce CH340, port `/dev/ttyUSB0`). Confirmé le 2026-07-01.

**Point clé — reset automatique à l'ouverture du port :**  
L'ouverture du port série sur une carte Arduino déclenche un reset via la ligne DTR. Marlin envoie ~20 lignes de configuration au démarrage. `connect()` attend 2 secondes puis vide le buffer avant d'envoyer la moindre commande.

**Paramètres machine confirmés (M115 + M203) :**

| Axe | Steps/mm | Vitesse max | Vitesse utilisée |
|---|---|---|---|
| X | 80.80 | 24 000 mm/min | 3 000 mm/min (`MACHINE_FEEDRATE_XY`) |
| Y | 80.80 | 24 000 mm/min | 3 000 mm/min (`MACHINE_FEEDRATE_XY`) |
| Z | 2 560.00 | **120 mm/min** | 100 mm/min (`MACHINE_FEEDRATE_Z`) |
| E (seringue) | 102.00 | 2 700 mm/min | 100 mm/min (`MACHINE_FEEDRATE_DISPENSE`) |

> L'axe Z est très lent (vis à bille haute précision). Ne jamais utiliser `MACHINE_FEEDRATE_XY` pour Z.

**Commandes G-code utilisées :**

| Commande | Description |
|---|---|
| `G28` | Homing tous axes (30–60 s) |
| `G90` | Mode absolu — position cible relative à (0,0,0) |
| `G91` | Mode relatif — déplacement relatif à la position courante |
| `G1 X Y F` | Déplacement XY linéaire |
| `G1 Z F` | Déplacement Z (vitesse réduite) |
| `G1 E F` | Avance piston seringue |
| `M400` | Attendre fin physique de tous les mouvements |
| `M112` | Arrêt d'urgence (pas de réponse `ok`) |

**Interface publique implémentée (`modules/machine.py`) :**
```python
class Machine:
    def __init__(self, port: str, baudrate: int, feedrate_xy: int,
                 feedrate_z: int, feedrate_dispense: int)
    def connect(self) -> None          # Ouvre port, attend reset, force G90
    def disconnect(self) -> None
    def is_connected(self) -> bool
    def send_command(self, cmd: str) -> list   # Envoie G-code, attend 'ok'
    def home(self) -> None             # G28
    def move_to(self, x, y, z: float) -> None  # G1 XY + G1 Z + M400
    def dispense(self, amount_mm: float) -> None  # G91 + G1 E + M400 + G90
    def emergency_stop(self) -> None   # M112 direct (pas d'attente 'ok')
```

---

## 6. Module : Planification de trajectoire (Phase 5)

### Problème à résoudre

L'utilisateur trace un ou plusieurs **cordons** (polylines) sur l'image calibrée (en pixels). Pour chaque cordon il faut :
1. Convertir les coordonnées pixel → coordonnées réelles (mm) via l'homographie
2. Générer la trajectoire du cordon (suite de segments) + la dépose de la quantité associée
3. Traduire en liste de commandes G-code

### Approche retenue (décidée 2026-07-11) : dépose en cordon

La pâte thermique est déposée en **boudin le long d'un chemin** (pas de remplissage de surface). Chaque **préparation** contient **plusieurs cordons**, chacun avec sa **quantité de pâte**. C'est plus simple et plus fiable qu'un remplissage de zone, et correspond à l'usage réel.

- `generate_path_from_line()` (déjà implémenté) génère la trajectoire d'un cordon.
- À faire : gérer **plusieurs cordons** avec une quantité par cordon (extension Phase 5).

**Interface publique :**
```python
class PathPlanner:
    def __init__(self, mm_per_pixel: float, z_height: float)
    def generate_path_from_line(self, line_px, paste_amount_mm) -> list[dict]
    # Retourne : [{"type": "move", "x": x, "y": y}, {"type": "dispense", "amount": v}, ...]
```

### Fichier de préparation (JSON) — implémenté le 2026-08-01 (lot B)

Module : `modules/preparation.py`. Une **préparation** rassemble tout le travail fait sur un plateau — produit, zones, cordons, paramètres — et se sérialise en JSON dans `preparations/`. Les zones étant vissées à demeure, une préparation validée est rejouable telle quelle, sans rien retracer.

> **Évolution par rapport à la décision du 2026-07-11.** Le format initialement esquissé stockait les cordons en **pixels** avec une quantité de pâte par cordon. Deux choses ont changé depuis le cadrage du 2026-08-01 : (1) les points sont désormais en **mm relatifs à la zone**, ce qui les rend applicables à toutes les zones du plateau et insensibles à un déplacement de la caméra ; (2) la quantité n'est plus un attribut de cordon mais résulte de **deux paramètres globaux** — vitesse de déplacement et vitesse d'extrusion — le rapport entre les deux déterminant l'épaisseur du boudin.

**Modèle de données**

```python
Cordon       points_mm (relatifs à la zone) · length_mm · is_valid
Settings     travel_speed_mm_min · extrusion_speed_mm_min
             zone_diagonal_tolerance_mm · zone_max_rotation_deg
Preparation  product_name · zones · cordons · settings · reference_zone_id
             created_at · updated_at
             → cordons_for_zone(zone) · total_length_mm · valid_zones · reference_zone
```

Les cordons appartiennent à la **préparation**, pas à une zone : toutes les zones portant le même produit, les dupliquer par zone créerait autant de copies à maintenir cohérentes pour aucune information supplémentaire. `reference_zone_id` mémorise la zone sur laquelle l'opérateur les a tracés, pour que le bouton de retour à l'édition y revienne directement.

Le passage d'un repère à l'autre est porté par la zone elle-même : `DepositZone.to_plateau_mm()` et `to_zone_mm()`, exactement inverses l'une de l'autre. C'est l'opération qui matérialise « un cordon tracé une fois s'applique partout ».

**Repère de la zone** (lot C2bis) : origine au coin **bas-gauche** (`DepositZone.origin_mm`, soit `corners_mm[3]`), X le long de la largeur, **Y le long de la hauteur vers le haut**. Il a basculé en même temps que celui du plateau : garder deux conventions opposées aurait réintroduit exactement la confusion que ce lot supprime, et les coordonnées de zone restent positives puisque l'origine est sur un coin. Les **formules** de `to_plateau_mm()` / `to_zone_mm()` n'ont pas changé pour autant — une rotation directe s'écrit pareil dans les deux repères — seule l'origine a changé de coin. C'est précisément le genre de changement qu'aucun test de réversibilité ne peut attraper : `to_plateau_mm ∘ to_zone_mm` reste l'identité quel que soit le coin choisi.

**Stratégie à deux fichiers**

| Fichier | Écrit par | Rôle |
|---|---|---|
| `<produit>.json` | Action de l'opérateur | Préparation **validée** |
| `<produit>.autosave.json` | Automatiquement, toutes les 5 s | Filet **anti-plantage** |

L'autosave ne touche jamais au fichier définitif ; l'enregistrement définitif supprime l'autosave. La présence d'un `.autosave.json` au démarrage signale donc un travail interrompu, et rien d'autre. Les deux passent par une **écriture atomique** (temporaire + `os.replace`) : une sauvegarde anti-plantage coupée en pleine écriture laisserait un fichier tronqué et ne protégerait de rien.

**Robustesse de lecture** : un `format_version` supérieur à celui du logiciel est **refusé** avec un message explicite, plutôt que relu de travers — sur des coordonnées de dépose, une lecture silencieusement fausse enverrait la buse au mauvais endroit. Une clé manquante, à l'inverse, reprend sa valeur par défaut, ce qui garde les fichiers anciens lisibles.

#### `FORMAT_VERSION` 1 → 2 et conversion des anciens fichiers (lot C2bis)

Le lot C2bis retourne l'axe Y de **deux** repères à la fois — celui du plateau et celui de la zone — et un fichier de préparation contient des coordonnées dans les deux. Toutes les ordonnées enregistrées changent donc de sens, d'où le passage à `FORMAT_VERSION = 2`.

Le contrôle de version ne suffisait pas à protéger de ce cas : il ne refusait que les fichiers **plus récents** que le logiciel. Un fichier v1 aurait été relu silencieusement à l'envers, et l'opérateur aurait vu ses cordons se déplacer sans explication — ou pire, ne l'aurait pas vu. **Décision (2026-08-01) : conversion au chargement, pas de refus sec.** Un opérateur ne doit pas perdre un plateau déjà tracé parce que la convention interne du logiciel a changé.

Trois points de mise en œuvre méritent d'être notés :

1. *La conversion vient **après** la reconstruction, pas au fil de la lecture.* Retourner un cordon demande la **hauteur de sa zone**, qui n'est connue qu'une fois les zones relues (`size_mm`). Convertir dans l'ordre du fichier obligerait à espérer que les zones y précèdent les cordons — une dépendance invisible et fragile.
2. *Les deux repères sont convertis, pas un seul.* Les coins des zones avec la hauteur du plateau (`y₂ = WORK_AREA_HEIGHT_MM − y₁`), les points des cordons avec la hauteur de leur zone (`y₂ = hauteur_zone − y₁`), et la rotation des zones change de signe. Ne convertir qu'un des deux rendrait le fichier incohérent avec lui-même — pire que de ne rien convertir. L'**ordre des coins**, lui, ne bouge pas : ce sont des positions vues par l'opérateur, et retourner une convention de coordonnées ne déplace rien physiquement.
3. *La conversion est signalée et le fichier est réécrit.* `Preparation.converted_from_version` porte l'information jusqu'à l'IHM, et `load_preparation()` réenregistre le fichier au format courant — la migration n'a lieu qu'une fois et le fichier sur disque cesse d'être un piège. C'est `load_preparation()` qui réécrit, pas `from_dict()`, qui doit rester utilisable sur des données en mémoire.

*Limite assumée* : la hauteur de plateau utilisée est celle configurée **aujourd'hui**, alors que le fichier a pu être écrit avec une autre (`PLATEAU_SIZE_MM` est devenu configurable au même lot). Sans conséquence en pratique — ces coordonnées absolues dépendent déjà de la position de la caméra au moment de la photo et sont redétectées à la capture suivante. Les cordons, eux, sont convertis avec la hauteur de **leur** zone, qui est dans le fichier, donc exactement. Un fichier v1 contenant des cordons mais aucune zone est **refusé** : la hauteur nécessaire est introuvable, et laisser passer des cordons à l'envers enverrait la buse au mauvais endroit.

**Exemple réel** (extrait, 2 zones dont une inclinée de 2,5° ; coordonnées en repère Y montant, origine de zone au coin bas-gauche) :

```json
{
  "format_version": 2,
  "product_name": "Calculateur ABC",
  "reference_zone_id": 4,
  "settings": {
    "travel_speed_mm_min": 3000.0,
    "extrusion_speed_mm_min": 100.0,
    "zone_diagonal_tolerance_mm": 5.0,
    "zone_max_rotation_deg": 10.0
  },
  "zones": [
    {
      "id_top_left": 4, "id_bottom_right": 5,
      "corners_mm": [[10.0, 20.0], [70.0, 20.0], [70.0, 60.0], [10.0, 60.0]],
      "rotation_deg": 0.0, "diagonal_mm": 72.11,
      "size_mm": [60.0, 40.0], "anomalies": []
    },
    {
      "id_top_left": 6, "id_bottom_right": 7,
      "corners_mm": [[110.0, 20.0], [169.94, 22.62], [168.2, 62.58], [108.26, 59.96]],
      "rotation_deg": 2.5, "diagonal_mm": 72.11,
      "size_mm": [60.0, 40.0], "anomalies": []
    }
  ],
  "cordons": [
    { "points_mm": [[5, 5], [55, 5]] },
    { "points_mm": [[5, 35], [30, 20], [55, 35]] }
  ]
}
```

Les paires de coordonnées sont volontairement maintenues sur une seule ligne : `json.dumps(indent=2)` les éclaterait sur six lignes chacune, et un plateau réaliste ferait plusieurs centaines de lignes de crochets quasi vides. Le fichier étant un livrable qu'on doit pouvoir ouvrir et corriger dans un éditeur, la lisibilité compte. Le résultat reste du JSON strictement standard.

**Résultat** : 30 tests dédiés, 108/108 pour la suite complète.

### 6.1 Câblage de la persistance dans l'IHM (lot C3, `v0.4.3`)

Le modèle et sa persistance étant écrits depuis le lot B, ce lot est essentiellement du **câblage** — mais quatre décisions y méritent d'être justifiées.

#### La sauvegarde automatique n'écrit que si quelque chose a changé

Un `QTimer` bat toutes les 5 s tant que l'écran de tracé est ouvert. Il ne déclenche une écriture que si un drapeau `_modifie`, levé par le signal `cordons_modified`, est actif — et ce drapeau n'est abaissé qu'**après** une écriture réussie, pour qu'un échec passager ne fasse pas perdre définitivement les modifications de la période.

Sans ce drapeau, le fichier serait réécrit toutes les 5 s indéfiniment, y compris pendant que l'opérateur réfléchit sans rien toucher. Sur le Raspberry Pi, dont le disque est une **carte SD**, c'est de l'usure gratuite sur un support qui la supporte mal. Le coût du filet anti-plantage doit rester proportionnel au risque qu'il couvre.

Le **tracé en cours est exclu** par construction : `ScreenCordons.cordons` ne retourne que les cordons terminés. Un polyline inachevé rechargé après une reprise donnerait un tracé arbitrairement coupé, que l'opérateur croirait volontaire — rien ne le distinguerait d'un cordon réellement court.

#### Reprendre un travail interrompu ne restaure pas la photo

Le fichier de préparation ne contient **pas** l'image du plateau. Reprendre consiste donc à : recharger les cordons, les paramètres et la zone de référence, puis **reprendre une photo**. Aucun tracé n'est perdu pour autant, et c'est exactement ce que rend possible la décision du lot B de mémoriser les cordons en **mm relatifs à la zone** — une photo différente, voire une caméra déplacée, ne les invalide pas. Les zones du fichier, elles, sont des positions absolues périmées dès que la caméra bouge : elles sont remplacées par celles de la nouvelle capture.

Persister l'image aurait ajouté une gestion de fichiers annexes (nommage, nettoyage, cohérence avec le JSON) pour restaurer une donnée que le dispositif sait déjà reconstruire.

> ⚠️ **Le point à ne pas rater** : la zone de **référence** doit être restaurée avant tout affichage. Les cordons sont exprimés dans son repère ; si la première zone rouverte par l'opérateur devenait la nouvelle référence, ils seraient réinterprétés dans un repère qui n'est pas le leur et se retrouveraient décalés — **sans que rien ne le signale**. C'est le même genre de faute silencieuse que le miroir vertical du lot C2bis, et elle est verrouillée par `test_reprise_restaure_la_zone_de_reference`.

La proposition de reprise est faite par `MainApp.propose_resume()`, appelée depuis `main.py` **après** `show()` : une boîte modale pendant la construction laisserait l'opérateur devant un dialogue flottant, sans la fenêtre qui lui donne son contexte. Répondre « Non » **conserve** le fichier — la question est reposée au démarrage suivant, plutôt que de détruire un travail sur une réponse hâtive.

#### La référence produit : trois voies dans le même dialogue

Il n'y a **pas de clavier physique sur le RPi**. Une simple boîte de saisie texte rendrait l'écran inutilisable au doigt. `ProductNameDialog` offre donc trois façons d'arriver au même résultat, sans mode à choisir :

| Voie | Intérêt |
|---|---|
| Saisie libre | Référence nouvelle, clavier virtuel ou BT |
| Choix dans la liste des produits enregistrés | Évite les fautes de frappe sur une référence — coûteuses ici |
| Champ vide à la validation → `BOITIER_X` | Le geste minimal : ouvrir, valider, travailler |

`next_default_product_name()` retourne le **premier numéro libre**, pas « le plus grand + 1 ». Après suppression de `BOITIER_2`, le numéro est réutilisé : la numérotation sert à distinguer des plateaux de travail, pas à tracer un historique. Les travaux interrompus comptent comme occupés, sinon un `BOITIER_3` inachevé verrait son numéro réattribué et le second plateau écraserait le premier.

L'intérêt de fond de ce choix, décidé le 2026-08-01 : **aucun état n'est conservé hors du dossier des préparations lui-même**. Le mécanisme fonctionne tel quel sur un dépôt fraîchement cloné, sans compteur à initialiser, et survit à la copie du dossier sur une autre machine. Le numéro n'est calculé qu'à la lecture de `product_name`, jamais à l'ouverture du dialogue : une ouverture annulée ne doit consommer aucun numéro.

#### Recharger un plateau enregistré — ajouté le 2026-08-02, après usage réel

Le lot C3 tel que spécifié ne couvrait que la **récupération après plantage** (`list_autosaves()`). Il manquait la **réutilisation** — point 7 du processus cible en section 1 : *« un fichier de plateau existant peut être rechargé et rejoué autant de fois que nécessaire, sans rien retracer »*. Elle n'avait été affectée à aucun lot, et le manque n'est apparu qu'en essayant le logiciel : après un enregistrement définitif, l'autosave est supprimé — à raison — et plus rien dans l'interface ne menait au fichier validé.

Ajout d'un bouton **« Charger un plateau »** sur l'écran d'accueil, distinct de « Créer un plateau » : créer et recharger sont deux intentions différentes, et les confondre ferait risquer d'écraser un plateau en croyant en ouvrir un nouveau. Le sélecteur (`PreparationPickerDialog`) affiche nom, nombre de cordons et date — de quoi identifier un plateau sans ouvrir le fichier. Un fichier illisible reste **listé et signalé** plutôt que masqué : le faire disparaître laisserait croire que le travail s'est évaporé.

Le chargement et la reprise après plantage partagent le même tronc (`MainApp._charger_preparation`) : ils ne diffèrent que par la façon dont le fichier est choisi, et factoriser évite que le pré-remplissage du nom, la navigation ou la gestion d'erreur divergent entre les deux chemins.

**Capture automatique au rechargement.** La caméra est fixe sur le bâti et les zones sont vissées à demeure : le cadrage est toujours le même, donc demander un appui sur « Capturer » ne fait prendre aucune décision à l'opérateur — c'est un geste de plus sur un écran tactile, et rien d'autre. La photo se déclenche donc seule.

Le déclenchement attend que **les marqueurs du plateau soient effectivement vus** (≥ 2 des 4 coins, le minimum de `compute_plateau_reference`), et non l'écoulement d'un délai : une temporisation aveugle déclencherait sur la première image venue — main encore dans le champ, exposition pas stabilisée — et produirait un diagnostic raté qu'il faudrait de toute façon reprendre. Un garde-temps de 5 s rend la main avec un message explicite, plutôt que de laisser un écran qui attend sans fin.

L'automatisme est délibérément **limité au rechargement**. À la création d'un plateau, l'opérateur est en train d'y poser les boîtiers ; après un « Reprendre », il vient de constater un défaut de montage et s'apprête à le rectifier. Dans les deux cas, lui seul sait quand la scène est prête — automatiser reviendrait à décider à sa place.

**Garde-fou associé** : le nom du produit servant de nom de fichier, réutiliser le nom d'un plateau existant pour un autre travail l'écraserait en silence — d'autant que le dialogue de création propose justement la liste des produits enregistrés. L'enregistrement demande donc confirmation, avec **« Non » par défaut**. Il ne demande **rien** quand il s'agit du même travail, reconnu à sa date de création : une question posée à chaque enregistrement deviendrait un réflexe qu'on valide sans lire, donc une protection qui ne protège plus.

#### Les paramètres : un objet neuf, pas une modification en place

`SettingsDialog` rend un **nouveau** `Settings` au lieu de modifier celui qu'on lui confie. C'est ce qui rend le bouton « Annuler » réellement sans effet — tant que l'opérateur n'a pas validé, la préparation n'a pas bougé. Les bornes des quatre compteurs ne sont pas cosmétiques : une vitesse aberrante partirait telle quelle en G-code vers la machine.

Rappel affiché dans le dialogue, parce qu'il n'est pas devinable : l'épaisseur du cordon dépend du **rapport** entre les deux vitesses, pas de l'une d'elles. C'est aussi pourquoi il y a deux vitesses plutôt qu'un curseur « quantité », qui masquerait ce lien.

**Résultat** : 32 tests dédiés (`test_dialogs.py` créé, `test_screen_cordons.py` et `test_preparation.py` enrichis), 193/193 pour la suite complète.

---

## 7. Module : Rapport (Phase 7)

### Contenu du rapport PDF

1. **En-tête** : date, heure, numéro de session
2. **Photo** : image calibrée avec les cordons tracés annotés
3. **Détail par cordon** : longueur, quantité de pâte associée
4. **Résumé** : statut, **temps de dépose**, **quantité totale déposée**

> Décidé 2026-07-11 : le rapport inclut le **temps de dépose** (mesuré début/fin dans `RunWorker`) et la **quantité totale** (somme des quantités par cordon).

---

## 8. Plan de développement

### Vue d'ensemble — trois parties

| Partie | Objectif | Deadline | Jalon |
|---|---|---|---|
| **A — Logiciel sur Geeetech** | Développer et valider tout le logiciel sur le PoC | 17 juillet 2026 | Logiciel fonctionnel sur Geeetech |
| **B — Intégration CNC** | Assembler la CNC cible et porter le logiciel | 07/08 (avant 3e blanche) | **2 machines fonctionnelles** |
| **C — Finalisation** | Corrections, rapport, préparation soutenance | Rapport 17/08 · soutenance 31/08 | **Soutenance finale IUT** |

---

### Partie A — Logiciel sur Geeetech (PoC)

| Phase | Description | Sessions | Durée estimée | Cumul |
|---|---|---|---|---|
| 0 | Identification matériel (caméra, port, firmware Marlin) | 1 session × ~2h | ~2h | ~2h |
| 1 | Caméra de base (`camera.py`) | 1 session × ~2h | ~2h | ~4h |
| 2 | Détection ArUco & calibrage (`vision.py`) | 3 sessions × ~2h | ~6h | ~10h |
| 3 | Communication G-code Marlin (`machine.py`) | 2 sessions × ~2h | ~4h | ~14h |
| 4 | Interface graphique squelette (`gui/`) | 3 sessions × ~2h | ~6h | ~20h |
| 5 | Sélection zone & trajectoire (`path_planner.py`) | 3 sessions × ~2h | ~6h | ~26h |
| 6 | Intégration workflow complet (`main.py`) | 3 sessions × ~2h | ~6h | ~32h |
| 7 | Génération rapport PDF (`reporter.py`) | 2 sessions × ~2h | ~4h | ~36h |
| 8 | Tests, robustesse, finitions (Geeetech) | 3 sessions × ~2h | ~6h | ~42h |
| **Total A** | | **21 sessions** | **~42h** | |

> **Contrainte** : vacances 15–19 juin inclus (aucune session).  
> **Rythme cible** : 3 à 4 sessions/semaine + 1 session le week-end pour tenir fin juin.

> ⚠️ **Point d'attention — semaine du 8 au 14 juin (semaine la plus chargée du projet) :**  
> La phase 4 (interface graphique — 3 sessions) tombe exactement la même semaine que la deadline du premier draft rapport (15 juin).  
> Il faudra gérer les deux en parallèle : sessions de dev en journée, rédaction rapport le soir.  
> La phase 4 peut être légèrement décalée (démarrer le 10, finir les 13–14 en week-end), mais le draft rapport lui ne peut pas attendre — il est dû avant le départ en vacances.  
> **Recommandation** : avancer autant que possible sur le draft rapport dès la semaine du 1er juin, pour n'avoir que la relecture finale à faire le 13–14 juin.

---

### Partie B — Intégration sur CNC cible

| Phase | Description | Type | Durée estimée |
|---|---|---|---|
| 9 | Assemblage mécanique de la CNC cible | **Hardware** | 🔄 Quasi terminé (2026-07-11) — reste câblage capteurs/moteurs (~2-3 j) |
| 9a | — Montage châssis, axes, motorisation | Hardware | ~3–4 jours |
| 9b | — Câblage électrique (moteurs, fin de course, alimentation) | Hardware | ~2–3 jours |
| 9c | — Configuration firmware Marlin (paramètres CNC) | Firmware | ~2 jours |
| 9d | — Tests mécaniques (homing, déplacements manuels) | Test | ~1–2 jours |
| 10 | Portage logiciel : adaptation `config.py` + calibrage caméra | Logiciel | 2 sessions × ~2h |
| 11 | Validation complète du système sur CNC (cycles réels) | Validation | 3 sessions × ~2h |
| **Total B** | | **5 sessions + ~2 sem. hardware** | **~10h + hardware** |

**Jalon B ≈ 07/08 2026 → 2 machines fonctionnelles avant la 3e soutenance blanche (12/08)**

---

### Activité parallèle — Rédaction du rapport (toute la durée du projet)

La rédaction du rapport se fait **en parallèle** du développement, à raison de ~1h/soir en semaine.

| Période | Mode | Charge | Objectif |
|---|---|---|---|
| 27 mai → 14 juin | ~1h/soir | ~3h/semaine | **Premier draft complet → 15 juin** |
| 22 juin → 31 juillet | ~1h/soir + week-end | ~3–5h/semaine | Rapport enrichi après chaque phase |
| 1 août → 24 août | Intensif | Priorité principale | Finalisation, relecture, remise |

> **Jalon intermédiaire : premier draft remis le 15 juin 2026** (avant départ en vacances).  
> Source principale : ce document `CONCEPTION.md` — chaque section correspond à une section du rapport.

---

### Partie C — Finalisation

| Phase | Description | Durée estimée |
|---|---|---|
| 12 | Corrections de bugs (retours soutenance blanche) | ~1 semaine |
| 13 | Finalisation et relecture rapport | ~3 semaines |
| **Total C** | | **~4 semaines** |

**Jalon C ≈ fin août 2026 → SOUTENANCE FINALE**

---

---

### Phase 1 — Environnement & Caméra de base
**Objectif** : Valider la chaîne logicielle de base sur Raspberry Pi  
**Sessions estimées** : 1 session (~2h)  
**Livrables** :
- `modules/camera.py` — classe `Camera` (open, capture, release)
- `tests/test_camera.py` — test de capture basique
- Script `tests/demo_camera.py` — affiche une image en temps réel

**Déroulé suggéré :**
1. Installer les dépendances sur le Raspberry Pi
2. Vérifier que la caméra est reconnue (`ls /dev/video*`)
3. Écrire la classe `Camera` avec les 3 méthodes de base
4. Écrire le script de démo avec `cv2.imshow()`

**Critères de validation :**
- [x] L'image s'affiche en temps réel sans lag visible
- [x] La résolution est configurable via `config.py`
- [x] `camera.release()` ferme proprement le flux (pas de processus zombie)
- [x] Le test `pytest tests/test_camera.py` passe sans erreur

**Attendus mesurables :** Image nette à la résolution configurée, sans artefacts. Temps d'ouverture du flux < 3 secondes.

**Résultats (2026-06-11) :** 4/4 tests passés. Résolution réelle confirmée à 1280×960 (conforme à la config). Philips SPC 1330NC supporte bien 1280×960 sur RPi 3B+.

---

### Phase 2 — Détection ArUco & calibrage géométrique
**Objectif** : Détecter les 4 marqueurs ArUco et produire une image redressée à l'échelle réelle  
**Sessions estimées** : 3 sessions (~6h)
- Session 1 : Théorie homographie + impression marqueurs + détection basique
- Session 2 : Calcul de l'homographie + redressement de l'image
- Session 3 : Validation métrologique + ajustements

**Livrables** :
- `modules/vision.py` — classe `VisionProcessor`
- `tests/test_vision.py` — tests unitaires sur image de référence
- Script `tests/demo_vision.py` — affiche l'image redressée avec marqueurs encadrés

**Déroulé suggéré :**
1. Imprimer les 4 marqueurs ArUco (IDs 0-3, dictionnaire `DICT_4X4_50`)
2. Les disposer aux coins de la zone de travail
3. Détecter les marqueurs avec OpenCV, afficher les contours trouvés
4. Calculer l'homographie (`cv2.findHomography`)
5. Appliquer la transformation (`cv2.warpPerspective`)
6. Valider avec une règle physique dans le champ

**Critères de validation :**
- [x] Les 4 marqueurs sont détectés de manière fiable (> 95% des captures) ✅ confirmé
- [x] L'image redressée est rectangulaire et sans distorsion visible ✅ validé visuellement
- [ ] Une règle de 100 mm dans la zone mesure 100 ± 2 mm sur l'image calibrée — **en attente** : calibration objectif à exécuter chez soi (échiquier à imprimer)
- [x] La fonction `pixel_to_mm()` retourne des coordonnées cohérentes ✅ (distance marqueur-à-marqueur correcte à ±3 mm)
- [x] `pytest tests/test_vision.py` passe — 14/14 tests ✅

**Attendus mesurables :** Précision de conversion pixel → mm ≤ 2 mm sur 100 mm, après calibration objectif.

**Résultat de la validation métrologique (2026-06-12) :**
- Sans calibration : erreur ~10 % (barrel distortion de l'objectif)
- Marqueur 0→1 : 148,8 mm (attendu 151 mm) — écart -2,2 mm (imprécision du clic)
- Marqueur 0→3 : 106,7 mm (attendu 104 mm) — écart +2,7 mm (imprécision du clic)
- Géométrie correcte ; l'écart résiduel vient de la distorsion non corrigée sur les mesures intérieures

---

### Phase 3 — Communication machine (G-code Marlin)
**Objectif** : Piloter la machine depuis Python via G-code série  
**Sessions estimées** : 2 sessions (~4h)
- Session 1 ✅ : Protocole G-code + connexion série + commandes de base + test sur machine réelle
- Session 2 : Test dépose seringue (moteur E à brancher)

**Livrables** :
- `modules/machine.py` ✅ — classe `Machine`
- `tests/demo_machine.py` ✅ — script interactif avec menus étape par étape
- `tests/test_machine.py` ✅ — 10 tests unitaires avec mock série

**Critères de validation :**
- [x] Connexion série établie et stable (pas de timeout sur 60 secondes) ✅ 2026-07-01
- [x] `home()` ramène la machine en position zéro sur les 3 axes ✅ 2026-07-01
- [x] `move_to(30, 30, 5)` déplace la buse à la position voulue ✅ 2026-07-01
- [x] `dispense(10)` avance le piston de 10 mm, `dispense(-10)` rétracte ✅ 2026-07-01
- [x] `emergency_stop()` envoie M112 directement ✅ (testé en mock)
- [x] 10/10 tests unitaires avec mock du port série ✅ 2026-07-01

**Résultats session 1 (2026-07-01) :**
- Port confirmé : `/dev/ttyUSB0` (puce CH340)
- Baudrate confirmé : **250000** (configuré dans l'EEPROM de la Geeetech — différent du défaut Marlin 115200)
- Firmware identifié : Marlin 1.1.8 (compilé 2022-09-25, `M115`)
- Connexion, homing, déplacements XYZ : tous fonctionnels
- Axe E (seringue) : non testé, moteur non encore branché

**Attendus mesurables :** Précision de positionnement ≤ 1 mm (résolution mécanique de la Geeetech I3).

---

### Phase 4 — Interface graphique PyQt5 (squelette)
**Objectif** : Créer la structure de navigation entre les 4 écrans, adaptée au tactile  
**Sessions estimées** : 3 sessions (~6h)
- Session 1 : Bases PyQt5 (fenêtre, layouts, widgets) + écran 1 (capture)
- Session 2 : Écrans 2 et 3 avec données mockées + navigation
- Session 3 : Écran 4 + test tactile sur le Raspberry Pi

**Livrables** :
- `gui/app.py` — fenêtre principale avec `QStackedWidget`
- `gui/screen_capture.py`, `screen_zone.py`, `screen_run.py`, `screen_report.py`
- `main.py` (version stub) — lance la GUI

**Déroulé suggéré :**
1. Créer la fenêtre principale plein écran (800×480)
2. Implémenter le système de navigation avec `QStackedWidget`
3. Créer chaque écran avec des données fictives (images statiques, boutons mockés)
4. Connecter les signaux de navigation (bouton "Valider" → écran suivant)
5. Tester le comportement tactile (taille des boutons ≥ 44×44 px)

**Critères de validation :**
- [ ] Navigation entre les 4 écrans fluide et sans plantage
- [ ] Chaque bouton répond au toucher (taille suffisante pour les doigts)
- [ ] L'application se lance en plein écran sur le Raspberry Pi
- [ ] Le passage d'un écran à l'autre prend < 500 ms
- [ ] Le bouton "Retour" revient à l'écran précédent correctement

**Attendus mesurables :** Application lancée sur le Raspberry Pi, navigation complète sans crash sur 10 cycles consécutifs.

---

### Phase 5 — Sélection de zone & planification de trajectoire
**Objectif** : Permettre à l'utilisateur de dessiner une zone sur l'image et générer une trajectoire de dépose  
**Sessions estimées** : 3 sessions (~6h)
- Session 1 : Widget de dessin sur image dans PyQt5
- Session 2 : Conversion coordonnées pixel → mm + algorithme de hachures
- Session 3 : Affichage de la trajectoire + ajustement quantité de pâte

**Livrables** :
- `modules/path_planner.py` — classe `PathPlanner`
- Intégration dans `gui/screen_zone.py`
- `tests/test_path_planner.py`

**Déroulé suggéré :**
1. Implémenter un `QLabel` cliquable pour tracer un rectangle sur l'image
2. Convertir le rectangle en coordonnées mm via l'homographie (Phase 2)
3. Implémenter le pattern "hachures parallèles" dans `PathPlanner`
4. Afficher la trajectoire superposée à l'image
5. Ajouter un slider pour ajuster la quantité de pâte

**Critères de validation :**
- [ ] L'utilisateur peut dessiner un rectangle sur l'image en glissant le doigt
- [ ] La trajectoire générée couvre entièrement la zone sélectionnée
- [ ] Les coordonnées de la trajectoire sont en mm (vérifiable via logs)
- [ ] Le volume de pâte estimé est proportionnel à la surface de la zone
- [ ] `pytest tests/test_path_planner.py` valide les calculs géométriques

**Attendus mesurables :** Pour une zone rectangulaire de 50×30 mm avec espacement de 5 mm, la trajectoire contient les bonnes lignes de balayage (calculables à la main pour vérifier).

---

### Phase 6 — Intégration du workflow complet
**Objectif** : Assembler tous les modules dans `main.py` avec la machine à états  
**Sessions estimées** : 3 sessions (~6h)
- Session 1 : Machine à états + intégration caméra/vision dans GUI
- Session 2 : Intégration machine + exécution de la trajectoire
- Session 3 : Cycle complet + gestion des erreurs basique

**Livrables** :
- `main.py` — machine à états complète (`IDLE → CAPTURE → CONFIGURE → RUNNING → DONE → IDLE`)
- Intégration de tous les modules dans les écrans GUI

**Déroulé suggéré :**
1. Implémenter la machine à états dans `main.py` avec des signaux PyQt5
2. Connecter `camera.capture()` au bouton de capture de l'écran 1
3. Déclencher la génération de trajectoire depuis l'écran 2
4. Implémenter l'exécution G-code dans `screen_run.py` avec barre de progression
5. Gérer l'état `ERROR` avec message d'alerte à l'utilisateur

**Critères de validation :**
- [ ] Le cycle complet s'exécute sans intervention manuelle une fois lancé
- [ ] La barre de progression de l'écran 3 reflète l'avancement réel
- [ ] Un arrêt d'urgence depuis l'interface déclenche bien `emergency_stop()`
- [ ] Une déconnexion série en cours d'exécution affiche un message d'erreur (pas un crash)
- [ ] Le cycle peut être relancé sans redémarrer l'application

**Attendus mesurables :** Cycle complet photo → sélection → dépose → rapport en moins de 5 minutes (hors temps de dépose variable).

---

### Phase 7 — Génération de rapport PDF
**Objectif** : Produire un rapport PDF horodaté à la fin de chaque cycle  
**Sessions estimées** : 2 sessions (~4h)
- Session 1 : Structure du PDF avec fpdf2 + intégration photos
- Session 2 : Mise en page finale + intégration dans `screen_report.py`

**Livrables** :
- `modules/reporter.py` — classe `Reporter`
- Intégration dans `gui/screen_report.py` (aperçu + bouton télécharger)
- `tests/test_reporter.py`

**Déroulé suggéré :**
1. Créer un PDF basique avec fpdf2 (titre, date, texte)
2. Intégrer les photos avant/après (redimensionnées pour tenir sur une page)
3. Ajouter le tableau des paramètres (pattern, volume, vitesse, durée)
4. Sauvegarder dans `reports/` avec nom horodaté (`rapport_20260519_143022.pdf`)
5. Afficher le PDF généré dans `screen_report.py`

**Critères de validation :**
- [ ] Le PDF est généré en moins de 5 secondes
- [ ] Il contient bien les 2 photos (avant et après dépose)
- [ ] Les paramètres de la session sont lisibles
- [ ] Le fichier est sauvegardé dans `reports/` avec un nom unique
- [ ] `pytest tests/test_reporter.py` valide la génération sans machine connectée

**Attendus mesurables :** PDF d'une page A4 lisible, photos orientées correctement, paramètres exacts.

---

### Phase 8 — Tests, robustesse et finitions
**Objectif** : Rendre le système utilisable en conditions réelles, fiable et maintenable  
**Sessions estimées** : 3 sessions (~6h)
- Session 1 : Suite de tests complète (pytest) pour tous les modules
- Session 2 : Gestion des cas d'erreur + messages utilisateur clairs
- Session 3 : Tests en conditions réelles + corrections finales

**Livrables** :
- Suite `tests/` complète avec couverture ≥ 70% des modules critiques
- Gestion des erreurs dans tous les modules (connexion perdue, caméra absente, marqueurs non détectés)
- `CONCEPTION.md` mis à jour avec le bilan de réalisation

**Déroulé suggéré :**
1. Lancer `pytest --cov=modules tests/` et identifier les zones non couvertes
2. Ajouter les tests manquants (cas nominaux + cas d'erreur)
3. Tester l'application avec des scénarios de panne : débrancher la caméra, couper l'alimentation machine
4. Corriger les crashes identifiés, remplacer par des messages d'erreur clairs
5. Faire un cycle complet de démo avec de vraie pâte thermique

**Critères de validation :**
- [ ] `pytest tests/` passe à 100% (tous les tests verts)
- [ ] Couverture de code ≥ 70% sur `modules/`
- [ ] Aucun crash Python en condition normale d'utilisation (test sur 10 cycles)
- [ ] Chaque erreur prévisible (caméra absente, machine déconnectée, marqueurs non détectés) affiche un message compréhensible à l'utilisateur
- [ ] Un utilisateur non technique peut utiliser l'application sans aide (test avec un tiers)

**Attendus mesurables :** Démo complète réussie devant un tiers sur matériel réel (Geeetech).

---

### Phase 9 — Assemblage de la CNC cible

**Objectif** : Monter et configurer la machine de production (CNC) avec le même firmware Marlin  
**Type** : Hardware — pas de code à écrire, sauf configuration Marlin  
**Durée estimée** : ~2 semaines en juillet 2026

**Étapes :**

#### 9a — Montage mécanique (~3–4 jours)
- Assembler le châssis de la CNC
- Monter les axes X/Y/Z avec les rails et chariots
- Fixer le motoréducteur / actionneur de dépose (remplace l'extrudeur)
- Installer les supports de seringue

#### 9b — Câblage électrique (~2–3 jours)
- Connecter les moteurs Nema 17 à la carte contrôleur
- Câbler les fins de course (homing X/Y/Z)
- Connecter l'alimentation de la carte et des moteurs
- Brancher le Raspberry Pi en USB sur la carte Marlin

#### 9c — Configuration firmware Marlin (~2 jours)
- Identifier la version de Marlin installée (`M115`)
- Configurer les paramètres machine dans Marlin :
  - Dimensions de la zone de travail (X/Y/Z en mm)
  - Sens de déplacement des moteurs
  - Finesse des pas moteurs (steps/mm)
  - Vitesses et accélérations
- Flasher la carte si nécessaire

#### 9d — Tests mécaniques (~1–2 jours)
- Tester le homing (`G28`) sur chaque axe
- Vérifier les déplacements manuels (pas de collision)
- Tester l'actionneur de dépose avec une seringue vide

**Critères de validation :**
- [ ] La CNC effectue un homing propre sur les 3 axes sans collision
- [ ] `G1 X50 Y50 Z5` déplace la buse à la position attendue (±1 mm)
- [ ] L'actionneur de dépose avance et recule sur commande G-code
- [ ] Aucun bruit anormal, vibration excessive ou échauffement moteur

**Attendus mesurables :** Machine opérationnelle mécaniquement, prête à recevoir le logiciel.

---

### Phase 10 — Portage logiciel sur la CNC

**Objectif** : Adapter les paramètres de configuration et valider la connexion logiciel → CNC  
**Sessions estimées** : 2 sessions (~4h)

**Livrables** :
- `modules/config.py` mis à jour avec les paramètres CNC (port série, dimensions zone)
- Recalibrage ArUco pour la nouvelle géométrie caméra/pièce (si la hauteur a changé)

**Déroulé suggéré :**
1. Identifier le port série de la CNC (`ls /dev/tty*`)
2. Mettre à jour `config.py` (port, zone de travail en mm, limites d'axes)
3. Lancer `tests/demo_machine.py` sur la CNC — vérifier homing et déplacements
4. Si la hauteur caméra a changé : recalibrer les ArUco (relancer les étapes Phase 2)
5. Lancer l'application complète en mode test (sans pâte)

**Critères de validation :**
- [ ] `demo_machine.py` fonctionne sur la CNC sans erreur série
- [ ] Les marqueurs ArUco sont détectés correctement avec la nouvelle géométrie
- [ ] L'application se lance et navigue entre les écrans sans crash

**Attendus mesurables :** Connexion logiciel → CNC établie, ArUco calibrés.

---

### Phase 11 — Validation complète sur CNC

**Objectif** : Effectuer des cycles complets de dépose réelle sur la CNC cible  
**Sessions estimées** : 3 sessions (~6h)
- Session 1 : Premier cycle complet sans pâte (vérification trajectoires)
- Session 2 : Cycles avec pâte thermique réelle — réglages quantité
- Session 3 : Validation finale + démonstration (soutenance blanche)

**Livrables** :
- Rapport PDF généré sur la CNC (preuve de fonctionnement)
- `CONCEPTION.md` mis à jour : bilan de la phase d'intégration

**Critères de validation :**
- [ ] Cycle complet photo → sélection → dépose → rapport fonctionne sur CNC
- [ ] La précision de dépose est comparable à la Geeetech (±1 mm)
- [ ] Le rapport PDF contient des photos réelles prises sur la CNC
- [ ] 3 cycles consécutifs réussis sans intervention manuelle

**Attendus mesurables :** Démo live devant le tuteur ou l'équipe — système opérationnel sur CNC.

---

### Phase 12 — Corrections de bugs (post soutenance blanche)

**Objectif** : Traiter les retours et anomalies identifiés lors de la soutenance blanche  
**Durée estimée** : ~1 semaine (début août)

**Déroulé suggéré :**
1. Lister tous les retours de la soutenance blanche (bugs, ergonomie, manques)
2. Prioriser : critique (bloquant) / important / mineur
3. Corriger les bugs critiques et importants en priorité
4. Valider les corrections sur la CNC

**Critères de validation :**
- [ ] Tous les bugs critiques signalés sont corrigés
- [ ] Un cycle de régression vérifie que les corrections n'ont pas cassé l'existant

---

### Phase 13 — Rédaction du rapport de soutenance

**Objectif** : Rédiger le rapport final du projet de stage  
**Durée estimée** : ~3 semaines (août)

**Structure suggérée du rapport :**
1. Introduction et contexte industriel
2. Description du système physique (matériel, synoptique)
3. Architecture logicielle (modules, GUI, machine à états)
4. Développement et résultats par phase
5. Problèmes rencontrés et solutions apportées
6. Bilan et perspectives (améliorations possibles)
7. Conclusion

> `CONCEPTION.md` est la source principale pour les sections 2, 3 et 4 — le maintenir à jour au fil du projet permet de réduire considérablement le travail de rédaction finale.

**Critères de validation :**
- [ ] Rapport relu par le tuteur de stage avant soumission
- [ ] Toutes les figures (synoptique, captures d'écran, photos) sont incluses
- [ ] Les résultats de chaque phase sont documentés avec des mesures réelles

---

## 9. Questions ouvertes / Décisions à prendre

- [x] **Résolution caméra** : ✅ 1280×960 confirmée sur RPi 3B+ (Philips SPC 1330NC, 2026-06-11)
- [x] **Taille des marqueurs ArUco** : ✅ 28 mm × 28 mm — marqueurs imprimés, détection 4/4 confirmée
- [x] **Zone de travail** : ✅ **151 mm × 104 mm** (re-mesuré centre-à-centre marqueurs ArUco, 2026-06-12 — correction de la mesure initiale de 152×106)
- [x] **Hauteur caméra** : ✅ **200 mm** au-dessus de la zone de travail (mesuré 2026-06-12)
- [x] **Distorsion objectif** : ✅ Barrel distortion ~10 % identifiée et traitée via `cv2.calibrateCamera` (2026-06-12). Calibration à exécuter avec l'échiquier imprimé.
- [ ] **Volume de pâte par mm²** : Paramètre de calibrage à déterminer expérimentalement (Q8, tests de dépose)
- [x] **Port série Geeetech** : ✅ `/dev/ttyUSB0` (CH340), 250000 baud (2026-07-01)
- [x] **Firmware Marlin Geeetech** : ✅ Marlin 1.1.8 (`M115`, 2026-07-01)
- [x] **Firmware CNC cible** : ✅ Marlin dernière version (2026-07-11) → portage transparent
- [x] **Calibration objectif** : ✅ Mire **ChArUco** retenue (2026-07-11, remplace l'échiquier)
- [x] **Zones de dépôt** : ✅ **Cordons multiples**, une quantité par cordon (2026-07-11)
- [x] **Persistance des préparations** : ✅ Fichier **JSON** rechargeable/éditable (2026-07-11)
- [ ] **Collision d'IDs ArUco plateau/mire** (2026-07-29) : plateau et mire ChArUco partagent `DICT_4X4_50` sans plage d'IDs séparée → confusion du détecteur quand les deux sont visibles ensemble. Contournement actuel : masquer le plateau pendant la calibration.
- [x] **IDs réels des marqueurs du plateau** : ✅ **résolu le 2026-08-01** — fausse alerte. Le plateau utilise bien `{0,1,2,3}` ; la liste `{0,3,4,5}` observée en v0.1 se décomposait en 2 marqueurs de plateau cadrés (3 et 0, ceux du haut) + les 2 marqueurs de **zone de dépose** (4 et 5). Pas de collision plateau/zone.
- [x] **Disposition des marqueurs du plateau** : ✅ **arrêté le 2026-08-01** — `3`=haut-gauche, `0`=haut-droit, `1`=bas-droit, `2`=bas-gauche (voir section 4.2).
- [x] **Origine et sens du repère plateau** : ✅ **arrêté le 2026-08-01 au soir, LIVRÉ en `v0.4.2` le 2026-08-02** — repère **orthonormé** : origine au centre du tag **2** (bas-gauche), ordonnées vers le tag **3**, abscisses vers le tag **1**, donc **Y vers le haut**. Remplace la convention du matin (origine tag 3, Y vers le bas). Le repère de la **zone** a basculé avec lui : origine au coin bas-gauche, Y montant. Verrouillé par `test_boussole_de_la_convention_du_repere`.
- [x] **Rôle du 4ᵉ tag du plateau** : ✅ **arrêté le 2026-08-01, LIVRÉ en `v0.4.2`** — le tag `0`, rendu redondant par le repère à trois tags, sert de **contrôle de cohérence** (écart position vue / position attendue = indicateur de qualité de montage et de calibration), affiché dans la barre de statut. L'écart est mesuré contre une similitude ajustée sur les tags 2/1/3, et non contre `compute_homography()`, qui l'annulerait par construction.
- [x] **Conversion des préparations enregistrées** : ✅ **arrêté le 2026-08-01, LIVRÉ en `v0.4.2`** — le changement de repère retourne les cordons stockés, donc `FORMAT_VERSION` passe à **2** : les fichiers v1 sont **convertis au chargement** (`y_v2 = hauteur_zone − y_v1`, après relecture des zones puisque la hauteur vient de `size_mm`), le fichier est réécrit en v2, et la conversion est signalée à l'opérateur. Pas de refus sec. Les coins des zones et le signe de leur rotation sont convertis aussi — n'en convertir qu'une partie rendrait le fichier incohérent avec lui-même.
- [x] **Vocabulaire « haut-gauche / bas-droit » des zones** : ✅ **arrêté le 2026-08-02** — **conservé**. L'image affichée restant à l'endroit, ces noms continuent de décrire exactement ce que voit l'opérateur. Les docstrings précisent désormais qu'ils désignent le rendu à l'écran, pas le signe des coordonnées.
- [x] **Nom de produit sans clavier physique** : ✅ **arrêté le 2026-08-01** — saisie libre, ou choix dans la liste des produits déjà enregistrés, ou champ vide → repli `BOITIER_X` où X est le **premier numéro libre**. Ce choix ne conserve aucun état hors du dossier des préparations, donc il fonctionne sur un dépôt fraîchement cloné.
- [ ] **Position de la seringue après homing** (2026-08-01) : remplace `MACHINE_ORIGIN_X/Y`. Devient un **paramètre global en 3D** `(x, y, z)` dans le repère plateau. **X et Y mesurés le 2026-08-02** (action `M2`) : `M114` buse au-dessus du marqueur 2 → `MACHINE_ORIGIN_X = 5.0`, `MACHINE_ORIGIN_Y = 0.0`, en remplacement des 20/50 qui dataient de deux conventions en arrière. Repère de home vérifié conforme (`G28` + `M114` = 0/0, donc ni `X_MIN_POS` non nul ni `M206` en EEPROM — un `M206` effacé par un reset décalerait toute la dépose sans rien signaler). **Reste ouvert** : la hauteur Z (`M3`), la réserve sur Y (`M2 bis`, voir ci-dessous) et le fait que la mesure a été faite **sans le dispositif de seringue**, absent de la Geeetech en dehors de l'entreprise — si le support décale la pointe par rapport à la buse, la valeur devra être corrigée d'autant.
- [ ] **Réserve sur `MACHINE_ORIGIN_Y`** (2026-08-02, action `M2 bis`) : le relevé Y valait `0.00` avec un compteur de pas à **0 exact**, donc l'axe Y n'avait pas bougé depuis le homing. Deux lectures non départagées — soit le marqueur 2 tombait déjà sous la buse, soit le plateau **butait sur la fin de course** et `0` est une limite et non une mesure. Le second cas est plausible : les marqueurs sont aux coins d'un cadre de 220 mm depuis le 2026-07-30, pour une course utile de l'ordre de 200 mm. S'il se confirme, le bord bas du plateau est **hors course** et `MACHINE_ORIGIN_Y` devrait être négatif : il faudra rapprocher le plateau ou acter qu'une bande basse est indéposable. **Premier suspect en cas de dépose décalée en Y.** Note : même si la mesure est juste, une origine à `Y = 0` ne laisse aucune marge avant la fin de course.
- [ ] **Sens des axes machine par rapport aux axes plateau** (2026-08-01) : à établir **en interactif**, machine sous tension, pendant le lot D. Décision explicite de ne pas le déduire sur le papier. → action `M4`.
- [ ] **Taille du plateau** (2026-08-01) : mesure supposée 220×220 mm bord extérieur à bord extérieur des marqueurs → 192 mm centre-à-centre après retrait des 28 mm d'un marqueur. **Devenue un paramètre en `v0.4.2`** (`plateau_size_mm` dans `local_config.json`), servant de valeur de repli quand les 4 tags ne sont pas détectés — c'est-à-dire dans le mode nominal de la Geeetech, où l'origine est donc **extrapolée** (l'IHM le signale). Reste ouvert : **la mesure elle-même**. À confirmer au mètre, toute erreur dessus décale directement toute la dépose. → action `M1`.

> 📌 Les actions en attente qui demandent la machine (mesures, calibration réelle, commissioning
> CNC) sont recensées et suivies dans `CLAUDE.md` **section 7 bis**, rappelée au début de chaque
> session. Cette section-ci garde les **décisions** ; la 7 bis garde les **actions**.

---

## 10. Historique des sessions

| Date | Phase | Ce qui a été fait |
|---|---|---|
| 2026-05-19 | — | Définition de l'architecture et du plan de développement |
| 2026-05-27 | — | Révision plan : ajout machine CNC cible, phases 9-13, planning Excel |
| 2026-06-09 | — | Changement caméra : connecteur CSI RPi défaillant → Philips SPC 1330NC USB (OpenCV index 0, UVC). picamera2 retiré. Toute la documentation mise à jour. |
| 2026-06-11 | Phase 1 | Création `camera.py` (classe Camera : open, capture, release, warm-up). 4/4 tests pytest passés. Résolution 1280×960 confirmée. |
| 2026-06-11 | Phase 2 S1 | Création `vision.py` (VisionProcessor, detect_markers). Fix affichage Wayland → PyQt5. 9/9 tests passés. Détection 4 marqueurs confirmée. |
| 2026-06-11 | Phase 2 S2 | Ajout compute_homography, warp_image, pixel_to_mm. Démo côte à côte validée visuellement. 14/14 tests passés. |
| 2026-06-12 | Phase 2 S3 | Validation métrologique : barrel distortion ~10 % identifiée. Re-mesure zone 151×104 mm, hauteur caméra 200 mm. Création `calibration.py`, `demo_calibration.py`, `demo_validation.py`, `chessboard_calibration.png`. Calibration à exécuter chez soi. |
| 2026-07-11 | — | Révision planning (soutenances blanches 22/07·05/08·12/08, rapport IUT 17/08, soutenance 31/08). CNC quasi assemblée + Marlin confirmé. Cadrage du process de dépose + 4 décisions : calibration **ChArUco**, **cordons multiples** avec quantité/cordon, **fichier de préparation JSON**, **temps de dépose** au rapport. |
| 2026-08-02 | Phase 8 | **v0.4.2 — Lot C2bis : repère plateau orthonormé.** Le repère bascule sur l'origine au tag **2** (bas-gauche) avec **Y vers le haut**, le tag 0 devenant un témoin de cohérence. Le vrai travail n'est pas dans le tableau des coins, qui tient en quatre lignes, mais dans tout ce qui en dépendait implicitement. **(1)** Les trois `warp_*` retournent Y explicitement — sans quoi le repère montant ramenait le miroir vertical corrigé la veille et l'opérateur aurait vu le plateau à l'envers ; c'est cette ligne qui garantit la règle « ce qu'on voit à l'écran est ce qui se passe sur le plateau ». **(2)** Toute la logique de signe de la géométrie des zones s'inverse : le filtre des paires plausibles passe de `(+,+)` à `(+,−)`, l'angle de référence devient `atan2(−h, w)`, le vecteur du côté « hauteur » tourne dans l'autre sens, `rotation_deg` compte désormais dans le sens trigonométrique, et `product_size_mm` reçoit une convention de signe explicite (deux longueurs positives, conversion faite à un seul endroit). **(3)** Le repère de la zone bascule avec, origine au coin bas-gauche : les formules de transfert ne changent pas, seule l'origine change de coin — un changement qu'aucun test de réversibilité ne peut attraper. **(4)** Les fichiers enregistrés changeant de sens, `FORMAT_VERSION` passe à 2 avec conversion au chargement puis réécriture, les deux repères du fichier étant convertis pour ne pas le laisser incohérent avec lui-même. **(5)** Deux ajouts décidés en même temps : la taille du plateau devient un paramètre (`plateau_size_mm`), parce qu'elle sert de repli quand l'origine est extrapolée — le mode nominal de la Geeetech — et le choix « 4 tags → exact / 2-3 tags → approché », jusque-là **dupliqué** dans deux écrans, est regroupé dans `compute_plateau_reference()`, qui retourne la matrice **et** de quoi renseigner la barre de statut (mode, origine extrapolée, écart du tag 0). Un test « boussole » épingle la convention en un seul endroit. Vocabulaire « haut-gauche / bas-droit » conservé : il décrit ce que voit l'opérateur, pas le signe des coordonnées. 163/163 tests hors marqueur `toutes_cameras` (+9 : boussole, conversion v1→v2, orientation du tracé). **Puis, machine sous tension, action `M2` réalisée** : `M114` buse au-dessus du marqueur 2 → `MACHINE_ORIGIN` = 5.0 / 0.0, avec vérification que le repère de home est bien à 0/0. ⚠️ Restent non validés : la **réserve sur `MACHINE_ORIGIN_Y`** (compteur de pas à 0 exact — butée possible plutôt que mesure, action `M2 bis`) et le **sens réel des axes machine** (`M4`). La formule de conversion vers le repère machine est cohérente avec la nouvelle convention mais **non validée sur la machine**. |
| 2026-08-01 (soir) | Phase 8 | **Cadrage du lot C2bis — changement de convention du repère plateau. Aucune ligne de code produite.** Le repère devient orthonormé et défini par trois tags (origine au tag 2, Y vers le haut), le tag 0 passant au rôle de contrôle de cohérence. Motif : aligner le repère logiciel sur le repère physique **avant** d'écrire la construction des commandes machine (lot D), plutôt qu'après. Évaluation de l'impact menée sur le code réel : le tableau des coins est trivial, mais le retournement de Y ramène mécaniquement le miroir vertical corrigé le matin même — d'où un retournement explicite à écrire dans les trois `warp_*`, qui est justement ce qui garantit que l'opérateur continue de voir le plateau à l'endroit. Toute la logique de signe de la géométrie des zones bascule également, ainsi que le repère relatif des zones, ce qui retourne les cordons déjà enregistrés (`FORMAT_VERSION` → 2, conversion au chargement). Trois décisions annexes prises : contrôle de cohérence sur le tag 0, conversion des fichiers v1, repli `BOITIER_X` au premier numéro libre. Chiffrage : 2 sessions. Création d'une **section 7 bis** dans `CLAUDE.md` recensant les 13 actions en attente (9 machine, 4 logiciel), à rappeler au début de chaque session — plusieurs d'entre elles décalent physiquement la dépose et aucun test automatique ne peut les détecter. 155/155 tests (inchangés, aucun code touché). |
| 2026-08-01 | Phase 8 | **v0.4.1 — Lot C2 : tracé des cordons et report sur toutes les zones.** `VisionProcessor.warp_zone()` redresse une zone même inclinée, en composant l'homographie, le passage au repère de la zone et la mise à l'échelle ; l'image obtenue ayant son origine sur le coin haut-gauche de la zone à échelle constante, un clic s'y convertit en millimètres par une simple division. `gui/screen_cordons.py` implémente un écran à deux modes — vue d'ensemble cliquable et zoom de tracé — avec undo/redo de profondeur 1, sélection et suppression d'un cordon, et report visuel des cordons sur toutes les zones du plateau. Le besoin central du projet est ainsi vérifiable à l'œil : un cordon tracé une fois apparaît au même endroit relatif dans chaque zone. Un piège de test a conduit à rendre le traitement du double-clic indépendant de la séquence d'événements de Qt. 155/155 tests, validation manuelle sur machine réelle. |
| 2026-08-01 | Phase 8 | **v0.4.0 — Lot C1 : écran de création de plateau.** Découpage du lot C en trois sous-lots et choix de navigation : le nouvel écran cohabite avec le cycle historique plutôt que de le remplacer, ce dernier étant le seul à mener aujourd'hui jusqu'à la dépose réelle. `gui/screen_plateau.py` rend visible tout le travail des lots A et B : capture, détection des zones, diagnostic du montage matérialisé sur la photo. Un défaut de l'algorithme du lot A a été révélé par les tests de ce lot — le vote sur la longueur de diagonale excluait les paires inversées, ce qui faisait élire des paires fantômes comme zones valides sur un plateau entièrement mal monté ; corrigé, avec une anomalie `format_indeterminable` ajoutée. Premiers tests d'interface avec `pytest-qt`. 130/130 tests, validation sur le plateau réel de l'étudiant. |
| 2026-08-01 | Phase 8 | **v0.3.1 — Stratégie de test du matériel caméra.** Constat de l'étudiant : `pytest` sollicitait la webcam intégrée du PC plutôt que la caméra USB du projet. Au-delà du symptôme, le problème de fond est qu'un index de configuration ne se vérifie pas : s'il est faux, les tests passent en validant le mauvais matériel, sans aucun signal. Critère retenu : **la bonne caméra est celle où l'on détecte un marqueur ArUco**, donc celle qui voit le plateau — objectif, vérifiable à l'exécution, indépendant de toute configuration. Fixture `plateau_capture` de portée session dans `tests/conftest.py` : caméra configurée essayée en premier, repli sur les autres ensuite, 5 captures par caméra, image capturée une seule fois puis réutilisée par toute la suite. Ajout de 4 tests de vision sur image réelle, complétant les tests synthétiques qui restent la référence déterministe. Marqueur `toutes_cameras` pour isoler le seul test qui doit ouvrir toutes les caméras. 115/115 tests. |
| 2026-08-01 | Phase 8 | **v0.3.0 — Lot B : modèle de données et persistance JSON.** Création de `modules/preparation.py` (classes `Cordon`, `Settings`, `Preparation` + couche de persistance) et ajout du transfert de repère `to_plateau_mm()` / `to_zone_mm()` sur `DepositZone`. Choix structurants : cordons rattachés à la préparation et non à une zone, coordonnées en mm relatifs à la zone, quantité de pâte issue de deux paramètres globaux plutôt que d'un attribut par cordon, stratégie à deux fichiers (définitif + autosave) avec écriture atomique, et `format_version` refusant les fichiers plus récents que le logiciel. Formatage du JSON adapté pour rester lisible à l'œil. Voir section 6 pour le détail. 108/108 tests passés (30 nouveaux). |
| 2026-08-01 | Phase 8 | **v0.2.0 — Lot A : géométrie des zones de dépose.** Cadrage complet du besoin avec l'étudiant (plusieurs zones par plateau, plusieurs cordons par zone, cordons définis une fois et appliqués partout, zones vissées à demeure donc sauvegardables). Implémentation de `detect_deposit_zones_mm()` en fonction pure : appariement `(n, n+1)`, tri par signe des composantes, longueur de diagonale de référence, détection des conflits, déduction du format du produit par médiane, reconstruction du rectangle et de sa rotation. Deux règles convenues au départ ont dû être corrigées à l'épreuve des tests (voir section 4.2 bis) : le filtrage par longueur seul laissait passer les paires fantômes d'un plateau en grille, et la règle de la plus petite rotation rendait indétectables les erreurs de montage. Correction au passage d'un défaut des tests caméra, qui ouvraient l'index 0 en dur — donc la webcam intégrée du PC — au lieu de la caméra configurée dans `local_config.json`. 78/78 tests passés (15 nouveaux). |
| 2026-08-01 | Phase 8 | **v0.1.1 — Repère plateau refait + choix du matériel dans l'interface.** Disposition réelle des marqueurs relevée (`3`=haut-gauche, `0`=haut-droit, `1`=bas-droit, `2`=bas-gauche) et origine du repère mm placée sur le marqueur 3, avec Y dirigé vers le bas : coordonnées positives partout, et correction d'un **miroir vertical** de `warp_image()`/`warp_region()` présent depuis la Phase 2 (mis en évidence par le calcul, pas à l'œil). Inversion vers l'axe Y machine concentrée en un seul point (`screen_run.py`). Deux listes déroulantes ajoutées sur l'écran 1 pour choisir le port machine et la caméra, avec `Machine.list_ports()` / `Camera.list_devices()` côté modules et application du changement par `MainApp` (seul propriétaire de `Camera` et `Machine`). `serial_port` et `serial_baudrate` rendus surchargeables via `local_config.json`. Bug corrigé : le scan de caméras cassait le flux en cours en ouvrant un second handle DirectShow sur l'index déjà utilisé (symptôme trompeur « Camera deconnectee ») → `list_devices(exclude=...)`. Question ouverte du 2026-07-29 sur les IDs du plateau close (fausse alerte). 62/62 tests passés. |
| 2026-07-29 | Phase 8 | Détection ChArUco débloquée (2 causes : `camera_index` erroné + `charuco_legacy_pattern` incompatible avec les mires générées par l'appli). Bug OpenCV 5.0 corrigé (`calibrateCameraCharuco` supprimée → remplacée par `board.matchImagePoints()` + `cv2.calibrateCamera()`). Ajout de l'estimation de pose et de la distance caméra↔mire (`estimate_board_pose`, `distance_to_board_normal_mm`, solvePnP). Overlay de debug ArUco/ChArUco ajouté sur les écrans capture et calibration — c'est lui qui a permis d'isoler les deux causes de blocage. `assets/camera_calibration.npz` ajouté au `.gitignore` (spécifique à chaque caméra). `MANUEL_UTILISATEUR.md` et `MANUEL_MAINTENANCE.md` créés. Points ouverts identifiés : collision d'IDs ArUco plateau/mire, IDs réels du plateau à confirmer (`{0,3,4,5}` ?). 45/45 tests passés. |

---

*Document maintenu au fil des sessions de développement.*
