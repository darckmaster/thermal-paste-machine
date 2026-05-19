# Document de Conception — Machine de Dépose de Pâte Thermique

**Projet** : Automatisation de la dépose de pâte thermique sur coques de calculateur automobile  
**Contexte** : Projet d'études — apprentissage progressif  
**Dernière mise à jour** : 2026-05-19  

---

## 1. Description du système physique

### 1.1 Inventaire matériel

| Composant | Référence / Modèle | Rôle |
|---|---|---|
| Ordinateur de contrôle | Raspberry Pi 3B+ | Exécute le logiciel, pilote tous les périphériques |
| Caméra | Module Caméra Raspberry Pi (CSI) — version à confirmer | Capture l'image de la pièce avant et après dépose |
| Interface utilisateur | Écran tactile 7 pouces (800×480) | Affichage de l'IHM, saisie par le toucher |
| Base mécanique | Imprimante 3D Geeetech I3 (axes X/Y/Z) | Déplacement de la buse sur la pièce |
| Actionneur de dépose | Moteur Nema 17 sur axe E (ex-extrudeur) + vis sans fin | Pousse le piston de la seringue de pâte thermique |
| Contrôleur machine | Carte d'origine Geeetech — firmware Marlin (version à confirmer) | Interprète les commandes G-code, pilote les moteurs |
| Pièce à traiter | Coque de calculateur automobile | Support de la dépose de pâte thermique |
| Référentiel géométrique | 4 marqueurs ArUco (DICT_4X4_50, IDs 0–3) | Permettent le calibrage de perspective par vision |

> **Versions à confirmer lors de la première mise en service :**
> - Module caméra RPi : lancer `rpicam-hello --list-cameras` ou lire l'étiquette sur le module
> - Firmware Marlin : envoyer la commande G-code `M115` via terminal série (réponse : `FIRMWARE_NAME:Marlin VERSION:x.x.x`)

---

### 1.2 Connexions entrées/sorties (E/S)

| Interface | Protocole | Connecteur | De | Vers |
|---|---|---|---|---|
| CSI (Camera Serial Interface) | Liaison série MIPI CSI-2 | Nappe 15 broches | RPi 3B+ | Module caméra |
| USB série | UART via CH340 (ou FT232) | USB Type-A → USB Type-B | RPi 3B+ | Carte Geeetech (Marlin) |
| HDMI | HDMI 1.4 | HDMI standard | RPi 3B+ | Écran tactile 7" |
| USB tactile | HID USB | USB Type-A | RPi 3B+ | Contrôleur tactile de l'écran |
| Alimentation | 5 V / 2,5 A min | Micro-USB | Alimentation murale | RPi 3B+ |

> **Note port série :** la carte Geeetech apparaît sous `/dev/ttyUSB0` (puce CH340) ou `/dev/ttyACM0` (puce ATmega USB natif) selon le modèle exact. À identifier lors de la première connexion avec `ls /dev/tty*` avant et après branchement USB.

---

### 1.3 Synoptique matériel

```mermaid
graph LR
    subgraph RPi["🖥️ Raspberry Pi 3B+"]
        SOFT["Logiciel Python\ncaméra · vision · machine\npath_planner · GUI · reporter"]
    end

    CAM["📷 Module Caméra RPi\n(interface CSI, nappe 15 br.)"]
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

    CAM -->|"CSI — nappe 15 br."| RPi
    SCREEN -->|"HDMI + USB"| RPi
    RPi -->|"USB série\nCH340 · 115200 baud\nprotocole G-code"| MACHINE

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
| USB | USB 2.0 ×4 | Débit série largement suffisant (115200 baud = ~11 Ko/s) |
| Interface caméra | CSI-2 (nappe 15 br.) | Requiert `picamera2` ou pilote V4L2 (pas de simple `cv2.VideoCapture()`) |

**Stratégie d'optimisation adoptée :**
- Capture en haute résolution (ex. 1280×960) uniquement pour la photo du rapport
- Traitement ArUco en résolution réduite (640×480) pour la rapidité
- Pas de traitement vidéo temps réel : capture déclenchée sur demande uniquement

#### Module caméra RPi — interface logicielle

Le module caméra Raspberry Pi utilise l'interface CSI (non USB), donc `cv2.VideoCapture(0)` seul ne fonctionne pas sans configuration. Deux approches possibles :

| Approche | Librairie | Avantage | Inconvénient |
|---|---|---|---|
| **V4L2** (recommandée) | `cv2.VideoCapture("/dev/video0")` après `modprobe bcm2835-v4l2` | Unifie l'interface avec le reste du code OpenCV | Nécessite d'activer le pilote V4L2 au démarrage |
| **picamera2** | `picamera2` (MIT) | API native RPi, meilleur contrôle exposition/balance | Code spécifique RPi, non portable sur Windows |

> **Décision à prendre en Phase 1** : choisir l'approche et documenter ici le résultat.

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
│   ├── camera.py            # Capture image et calibrage géométrique
│   ├── vision.py            # Traitement d'image, détection marqueurs
│   ├── machine.py           # Communication série G-code avec Marlin
│   ├── path_planner.py      # Calcul des trajectoires de dépose
│   ├── reporter.py          # Génération de rapport PDF
│   └── config.py            # Paramètres globaux et constantes
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
| Caméra RPi (CSI) | picamera2 | BSD | ≥ 0.3 | API officielle Raspberry Pi, ou V4L2 via OpenCV |
| Communication machine | pyserial | BSD | ≥ 3.5 | Communication USB/UART avec Marlin |
| Rapports PDF | fpdf2 | LGPL | ≥ 2.7 | Simple, pur Python, pas de dépendances lourdes |
| Calcul numérique | numpy | BSD | ≥ 1.24 | Algèbre vectorielle pour les trajectoires |
| Tests | pytest | MIT | ≥ 7.0 | Standard Python |

> *PyQt5 est sous licence GPL v3 pour sa version open source. Dans un contexte d'usage interne (logiciel non distribué à des tiers), cette licence ne pose aucune contrainte. Si le logiciel devait être distribué commercialement, il faudrait envisager PySide6 (LGPL).

### Installation (Raspberry Pi OS — Bullseye ou Bookworm)

```bash
# Dépendances système
sudo apt update && sudo apt install -y python3-pip python3-pyqt5 libatlas-base-dev python3-picamera2

# Activer le pilote V4L2 pour la caméra CSI (si approche OpenCV retenue)
echo "bcm2835-v4l2" | sudo tee /etc/modules-load.d/bcm2835-v4l2.conf

# Dépendances Python
pip3 install opencv-contrib-python pyserial fpdf2 numpy pytest
```

### Installation (Windows — développement sans matériel)

```bash
pip install opencv-contrib-python pyserial fpdf2 numpy pytest PyQt5
# picamera2 non disponible sur Windows — la classe Camera devra être mockée pour les tests
```

---

## 4. Module : Caméra & Vision (Phase 1 & 2)

### 4.1 Capture (`modules/camera.py`)

**Responsabilité** : Ouvrir le flux caméra, capturer une image sur demande.

**Interface publique :**
```python
class Camera:
    def __init__(self, device_index: int = 0)
    def capture(self) -> np.ndarray          # Retourne image BGR
    def release(self)
```

### 4.2 Calibrage ArUco (`modules/vision.py`)

**Principe** : 4 marqueurs ArUco de dictionnaire connu sont placés aux coins de la zone de travail. La détection de leurs coins permet de calculer une transformation de perspective (homographie) qui redresse l'image.

**Marqueurs recommandés** : Dictionnaire `DICT_4X4_50`, IDs 0, 1, 2, 3 (coin haut-gauche, haut-droit, bas-droit, bas-gauche).

**Interface publique :**
```python
class VisionProcessor:
    def __init__(self, aruco_dict_id, marker_real_size_mm: float)
    def detect_markers(self, image: np.ndarray) -> dict      # {id: corners}
    def compute_homography(self, detected_markers) -> np.ndarray
    def warp_image(self, image, homography, output_size) -> np.ndarray
    def pixel_to_mm(self, px, py, homography) -> tuple[float, float]
```

**Principe de la transformation de perspective :**
OpenCV permet de calculer une matrice H (3×3) telle que pour tout point `p` dans l'image source, `H·p` donne sa position dans l'image redressée à l'échelle réelle.

---

## 5. Module : Communication Machine (Phase 3)

### Protocole G-code (Marlin)

La Geeetech I3 utilise le firmware **Marlin** et communique via USB série (115200 baud par défaut).

**Commandes clés :**

| Commande | Description |
|---|---|
| `G28` | Homing (remise à zéro tous les axes) |
| `G1 X{x} Y{y} Z{z} F{vitesse}` | Déplacement linéaire |
| `G1 E{val} F{vitesse}` | Avance du piston (axe E = extrudeur → piston) |
| `M114` | Demande position courante |
| `M0` | Pause |

**Interface publique :**
```python
class MachineController:
    def __init__(self, port: str, baudrate: int = 115200)
    def connect(self) -> bool
    def send_gcode(self, command: str) -> str    # Retourne la réponse "ok"
    def home(self)
    def move_to(self, x: float, y: float, z: float, feedrate: int = 1000)
    def dispense(self, amount_mm: float, feedrate: int = 100)
    def emergency_stop(self)
    def disconnect(self)
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

### Estimation globale

| Phase | Description | Sessions | Durée estimée | Cumul |
|---|---|---|---|---|
| 1 | Environnement & Caméra de base | 1 session × ~2h | ~2h | ~2h |
| 2 | Détection ArUco & calibrage | 3 sessions × ~2h | ~6h | ~8h |
| 3 | Communication machine (G-code) | 2 sessions × ~2h | ~4h | ~12h |
| 4 | Interface graphique (squelette PyQt5) | 3 sessions × ~2h | ~6h | ~18h |
| 5 | Sélection de zone & trajectoire | 3 sessions × ~2h | ~6h | ~24h |
| 6 | Intégration du workflow complet | 3 sessions × ~2h | ~6h | ~30h |
| 7 | Génération de rapport PDF | 2 sessions × ~2h | ~4h | ~34h |
| 8 | Tests, robustesse, finitions | 3 sessions × ~2h | ~6h | ~40h |
| **Total** | | **20 sessions** | **~40h** | |

> **Contexte deadline** : Fin juin 2026 (≈ 6 semaines depuis mi-mai). Rythme cible : **3 à 4 sessions par semaine** pour tenir le planning.

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
- [ ] L'image s'affiche en temps réel sans lag visible
- [ ] La résolution est configurable via `config.py`
- [ ] `camera.release()` ferme proprement le flux (pas de processus zombie)
- [ ] Le test `pytest tests/test_camera.py` passe sans erreur

**Attendus mesurables :** Image nette à la résolution configurée, sans artefacts. Temps d'ouverture du flux < 3 secondes.

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
- [ ] Les 4 marqueurs sont détectés de manière fiable (> 95% des captures)
- [ ] L'image redressée est rectangulaire et sans distorsion visible
- [ ] Une règle de 100 mm dans la zone mesure 100 ± 2 mm sur l'image calibrée
- [ ] La fonction `pixel_to_mm()` retourne des coordonnées cohérentes
- [ ] `pytest tests/test_vision.py` passe sur une image de référence fournie

**Attendus mesurables :** Précision de conversion pixel → mm ≤ 2% sur toute la zone de travail.

---

### Phase 3 — Communication machine (G-code Marlin)
**Objectif** : Piloter la machine depuis Python via G-code série  
**Sessions estimées** : 2 sessions (~4h)
- Session 1 : Protocole G-code + connexion série + commandes de base
- Session 2 : Test sur machine réelle + commandes de dépose

**Livrables** :
- `modules/machine.py` — classe `MachineController`
- Script `tests/demo_machine.py` — REPL interactif (saisir des commandes G-code à la main)
- `tests/test_machine.py` — tests unitaires avec mock série

**Déroulé suggéré :**
1. Connecter la Geeetech en USB, identifier le port (`/dev/ttyUSB0` ou `/dev/ttyACM0`)
2. Tester la connexion avec un terminal série (`screen` ou `minicom`)
3. Implémenter `connect()` et `send_gcode()` avec lecture de la réponse "ok"
4. Tester `home()`, `move_to()` avec des déplacements manuels
5. Tester `dispense()` avec une seringue vide (sans pâte)

> ⚠️ **Sécurité machine** : toujours vérifier la position avant un `home()`, ne jamais envoyer de commande de déplacement sans connaître la position courante. Avoir le bouton d'arrêt d'urgence à portée.

**Critères de validation :**
- [ ] Connexion série établie et stable (pas de timeout sur 60 secondes)
- [ ] `home()` ramène la machine en position zéro sur les 3 axes
- [ ] `move_to(50, 50, 5)` déplace la buse à la position mesurée (±1 mm)
- [ ] `dispense(5)` avance le piston de 5 mm (vérifiable à l'œil)
- [ ] `emergency_stop()` arrête immédiatement tout mouvement
- [ ] Tests unitaires avec un mock du port série passent sans matériel

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

**Attendus mesurables :** Démo complète réussie devant un tiers sur matériel réel.

---

## 9. Questions ouvertes / Décisions à prendre

- [ ] **Résolution caméra** : À définir selon la taille de la pièce et la précision voulue
- [ ] **Taille des marqueurs ArUco** : À définir selon la distance caméra/pièce
- [ ] **Volume de pâte par mm²** : Paramètre de calibrage à déterminer expérimentalement
- [ ] **Port série** : `/dev/ttyUSB0` ou `/dev/ttyACM0` selon le branchement
- [ ] **Modèle Raspberry Pi** : Impact sur les performances OpenCV temps réel

---

## 10. Historique des sessions

| Date | Phase | Ce qui a été fait |
|---|---|---|
| 2026-05-19 | — | Définition de l'architecture et du plan de développement |

---

*Document maintenu au fil des sessions de développement.*
