# Document de Conception — Machine de Dépose de Pâte Thermique

**Projet** : Automatisation de la dépose de pâte thermique sur coques de calculateur automobile  
**Contexte** : Projet d'études — apprentissage progressif  
**Dernière mise à jour** : 2026-07-01  

---

## 1. Description du système physique

### 1.1 Stratégie matérielle — deux machines, un seul logiciel

Le projet utilise **deux machines successives** avec le même firmware Marlin, ce qui permet de développer et valider le logiciel sur la machine disponible immédiatement, puis de le transférer sur la machine de production sans réécriture.

| Machine | Rôle | Calendrier |
|---|---|---|
| **Geeetech I3 (imprimante modifiée)** | Proof of concept — développement et validation logicielle | Maintenant → fin juin 2026 |
| **CNC cible** (carte Marlin) | Machine de production finale | Assemblage juillet 2026 |

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
| Base mécanique | CNC (à confirmer) | ⬜ À assembler |
| Contrôleur machine | Carte CNC avec firmware Marlin | ⬜ À identifier |
| Ordinateur de contrôle | Même Raspberry Pi 3B+ | ✅ Réutilisé depuis Geeetech |
| Caméra + écran | Même Philips SPC 1330NC USB + écran 7" | ✅ Réutilisés depuis Geeetech |

> L'assemblage mécanique de la CNC (fixation des axes, câblage moteurs, configuration Marlin) est une étape hardware distincte du développement logiciel. Elle est planifiée en juillet 2026 après validation du logiciel sur la Geeetech.

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
[Plateau reculé] → [Photo de la pièce] → [Choix zone/quantité]
    → [Dépose automatique] → [Photo résultat] → [Rapport PDF]
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
│   ├── machine.py           # ⬜ Phase 3 — communication série G-code avec Marlin
│   ├── path_planner.py      # ⬜ Phase 5 — calcul des trajectoires de dépose
│   ├── reporter.py          # ⬜ Phase 7 — génération de rapport PDF
│   └── config.py            # ✅ Paramètres globaux et constantes
│
├── gui/
│   ├── app.py               # Fenêtre principale PyQt5, gestionnaire d'écrans
│   ├── screen_capture.py    # Écran 1 : prise de photo et validation
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

**Marqueurs** : Dictionnaire `DICT_4X4_50`, IDs 0–3 (coin haut-gauche, haut-droit, bas-droit, bas-gauche). Taille physique : 28 mm × 28 mm. Zone de travail : 151 × 104 mm (centre-à-centre, mesuré le 2026-06-12).

**Interface publique :**
```python
class VisionProcessor:
    def __init__(self, aruco_dict_id, marker_real_size_mm: float)
    def detect_markers(self, image: np.ndarray) -> dict           # {id: corners (4,2)}
    def compute_homography(self, detected_markers: dict) -> np.ndarray  # matrice H 3×3
    def warp_image(self, image, homography, output_size) -> np.ndarray
    def pixel_to_mm(self, px, py, homography) -> tuple[float, float]
```

**Principe de l'homographie :**
`cv2.getPerspectiveTransform` calcule une matrice H (3×3) à partir de 4 paires de points (centres des marqueurs en pixels → positions réelles en mm). Pour tout point `p` dans l'image source, `H·p` donne ses coordonnées en mm dans le repère de la zone de travail.

**Résultats sessions 1 & 2 (2026-06-11) :** 14/14 tests passés. Détection 4 marqueurs simultanée confirmée. Image redressée validée visuellement.

### 4.3 Calibration objectif (`modules/calibration.py`) 🔄 Phase 2 en cours

**Problème** : Les objectifs de webcam bon marché introduisent une **barrel distortion** — les objets au centre de l'image paraissent plus grands qu'ils ne le sont. L'homographie corrige la perspective mais pas cette distorsion, ce qui cause une erreur de mesure d'environ **10 %** sur les distances intérieures à la zone de travail (mesuré le 2026-06-12 avec la Philips SPC 1330NC à 200 mm de hauteur).

**Solution** : Calibration one-shot avec un échiquier imprimé. Les coefficients de distorsion sont calculés avec `cv2.calibrateCamera`, sauvegardés dans `assets/camera_calibration.npz`, et appliqués via `cv2.undistort` avant tout traitement.

**Procédure de calibration (une seule fois) :**
1. Imprimer `assets/chessboard_calibration.png` sur A4 paysage (25 mm/carré)
2. Lancer `tests/demo_calibration.py` et capturer 15+ frames sous différents angles
3. Les coefficients sont sauvegardés automatiquement dans `assets/camera_calibration.npz`

**Interface publique :**
```python
generate_chessboard_image(output_path)                       # génère le PNG à imprimer
calibrate(images, chessboard_size, square_size_mm)           # → (camera_matrix, dist_coeffs, error)
undistort(image, camera_matrix, dist_coeffs)                 # → image corrigée (mêmes dimensions)
save_calibration(path, camera_matrix, dist_coeffs)           # sauvegarde .npz
load_calibration(path)                                       # → (camera_matrix, dist_coeffs) ou (None, None)
```

**Critère de qualité :** erreur de reprojection < 1.0 px (acceptable), < 0.5 px (excellent).

**Précision attendue après calibration :** ≤ 2 mm sur 100 mm (vs ~10 mm sans calibration).

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

L'utilisateur dessine une zone sur l'image calibrée (en pixels). Il faut :
1. Convertir les coordonnées pixel → coordonnées réelles (mm)
2. Calculer une trajectoire de remplissage (pattern de hachures ou spirale)
3. Traduire en liste de commandes G-code

### Patterns de dépose supportés (à implémenter progressivement)

- **Point unique** : dépôt en un seul point (le plus simple)
- **Ligne** : dépôt linéaire
- **Hachures parallèles** : remplissage d'une zone rectangulaire
- **Spirale** (avancé)

**Interface publique :**
```python
class PathPlanner:
    def __init__(self, mm_per_pixel: float, z_height: float)
    def generate_path(self, zone_polygon_px, pattern: str, paste_volume_mm3) -> list[dict]
    # Retourne : [{"type": "move", "x": x, "y": y}, {"type": "dispense", "amount": v}, ...]
```

---

## 7. Module : Rapport (Phase 7)

### Contenu du rapport PDF

1. **En-tête** : date, heure, numéro de session
2. **Photo avant** : image calibrée avec zone sélectionnée annotée
3. **Paramètres** : pattern choisi, volume de pâte, vitesse
4. **Photo après** : image post-dépose
5. **Résumé** : temps d'exécution, quantité déposée

---

## 8. Plan de développement

### Vue d'ensemble — trois parties

| Partie | Objectif | Deadline | Jalon |
|---|---|---|---|
| **A — Logiciel sur Geeetech** | Développer et valider tout le logiciel sur le PoC | Fin juin 2026 | Logiciel fonctionnel sur Geeetech |
| **B — Intégration CNC** | Assembler la CNC cible et porter le logiciel | Fin juillet 2026 | **Soutenance blanche** |
| **C — Finalisation** | Corrections, rapport, préparation soutenance | Fin août 2026 | **Soutenance finale** |

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
| 9 | Assemblage mécanique de la CNC cible | **Hardware** | ~2 semaines (juillet) |
| 9a | — Montage châssis, axes, motorisation | Hardware | ~3–4 jours |
| 9b | — Câblage électrique (moteurs, fin de course, alimentation) | Hardware | ~2–3 jours |
| 9c | — Configuration firmware Marlin (paramètres CNC) | Firmware | ~2 jours |
| 9d | — Tests mécaniques (homing, déplacements manuels) | Test | ~1–2 jours |
| 10 | Portage logiciel : adaptation `config.py` + calibrage caméra | Logiciel | 2 sessions × ~2h |
| 11 | Validation complète du système sur CNC (cycles réels) | Validation | 3 sessions × ~2h |
| **Total B** | | **5 sessions + ~2 sem. hardware** | **~10h + hardware** |

**Jalon B ≈ fin juillet 2026 → SOUTENANCE BLANCHE**

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
- [ ] `dispense(1)` avance le piston de 1 mm — **en attente** : moteur E à brancher
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
- [ ] **Volume de pâte par mm²** : Paramètre de calibrage à déterminer expérimentalement (Phase 3/5)
- [ ] **Port série** : `/dev/ttyUSB0` ou `/dev/ttyACM0` selon le branchement (Phase 3)
- [ ] **Version firmware Marlin** : À confirmer avec `M115` (Phase 3)

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

---

*Document maintenu au fil des sessions de développement.*
