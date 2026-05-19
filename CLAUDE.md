# CLAUDE.md — Machine de Dépose de Pâte Thermique

> **Ce fichier est la source de vérité portable du projet.**  
> Il est lu automatiquement par Claude Code à chaque session, sur n'importe quelle machine.  
> Les mémoires Claude Code étant locales à chaque installation (non synchronisées par git),  
> ce fichier compense : Claude recrée le contexte complet à partir d'ici.

---

## 1. Contexte du projet

| Champ | Valeur |
|---|---|
| Projet | Automatisation de la dépose de pâte thermique sur coques de calculateur automobile |
| Cadre | Projet de stage — BUT Informatique 3ème année (anciennement DUT) |
| Développeur | Étudiant en BUT3, niveau débutant–intermédiaire en Python |
| Deadline | Fin juin 2026 |
| Dépôt GitHub | `https://github.com/darckmaster/thermal-paste-machine` |
| Branche principale | `master` |

**Enjeux du projet :**
- Le code est **didactique** : il doit pouvoir être relu et compris ligne par ligne, manuellement, par l'étudiant ou son tuteur
- Le `CONCEPTION.md` doit rester à jour à chaque session pour alimenter le **rapport de stage et la soutenance**
- Toutes les librairies utilisées doivent être **open source** et utilisables en entreprise sans licence tierce payante

**Document de référence complet :** `CONCEPTION.md` — architecture détaillée, synoptique matériel, interfaces des classes, plan de développement avec estimations et critères de validation par phase.

---

## 2. Mode de collaboration (IMPORTANT — à respecter à chaque session)

- **Ne pas coder à la place de l'étudiant.** Claude guide, explique, propose des pistes ; l'étudiant écrit le code, teste, valide. C'est en faisant qu'on apprend.
- **Travailler phase par phase.** Ne pas anticiper les phases suivantes ni créer du code pour des phases non encore démarrées.
- **Expliquer chaque choix.** Pour toute solution proposée, expliquer le *pourquoi*, pas seulement le *comment*.
- **Enrichir `CONCEPTION.md`** à chaque décision technique, découverte ou résultat de test — ce document nourrit le rapport de stage.
- **Mettre à jour ce fichier** (`CLAUDE.md`) à chaque fin de session : questions ouvertes, décisions prises, agenda de la prochaine session.

---

## 3. Démarrer une session — checklist

À faire **au début de chaque session**, dans cet ordre :

```
1. git pull origin master           ← synchroniser avant tout
2. Lire la section "Prochaine session" de ce fichier
3. Vérifier le tableau d'avancement (section 8)
4. Ouvrir CONCEPTION.md pour le contexte technique détaillé
5. Commencer par un bref résumé oral de là où on en est
```

---

## 4. Configuration git (première fois sur une nouvelle machine)

### Cloner le projet

```bash
git clone https://github.com/darckmaster/thermal-paste-machine.git
cd thermal-paste-machine
```

### Configurer l'identité git (obligatoire avant le premier commit)

```bash
git config user.name "darckmaster"
git config user.email "guichard.erwann@gmail.com"
```

### Faire un commit (Linux / bash)

Sur Linux, le heredoc fonctionne normalement :

```bash
git commit -m "$(cat <<'EOF'
Titre du commit

Contexte : ...

Ajouts fonctionnels :
- ...

Fichiers modifiés :
- ... (nouveau / modifié)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

### Faire un commit (Windows / PowerShell)

PowerShell ne supporte pas le heredoc bash. Workaround avec fichier temporaire :

```powershell
# 1. Écrire le message dans un fichier temporaire
# (le créer manuellement ou laisser Claude le faire)
git commit -F .commit_msg.txt
Remove-Item .commit_msg.txt
```

---

## 5. Matériel — état des connaissances

### Inventaire confirmé

| Composant | Modèle / Référence | Statut |
|---|---|---|
| Ordinateur de contrôle | Raspberry Pi **3B+** (1 Go RAM, Cortex-A53 ×4 @ 1,4 GHz) | ✅ Confirmé |
| Caméra | Module Caméra Raspberry Pi — interface **CSI** (nappe 15 br.) | ✅ Confirmé (version à identifier) |
| Interface utilisateur | Écran tactile **7 pouces 800×480** | ✅ Confirmé |
| Base mécanique | Imprimante 3D **Geeetech I3** modifiée | ✅ Confirmé (modèle exact à identifier) |
| Actionneur de dépose | Moteur **Nema 17** sur axe E (ex-extrudeur) + vis sans fin | ✅ Confirmé |
| Contrôleur machine | Carte Geeetech — firmware **Marlin** via USB série 115200 baud | ✅ Confirmé (version à identifier) |
| Référentiel | 4 marqueurs **ArUco** DICT_4X4_50 — IDs 0, 1, 2, 3 | ✅ Arrêté |

### Connexions E/S

| Interface | Protocole | De | Vers |
|---|---|---|---|
| CSI (nappe 15 broches) | MIPI CSI-2 | RPi 3B+ | Module caméra |
| USB (puce CH340 ou ATmega) | UART série 115200 baud | RPi 3B+ | Carte Geeetech (Marlin) |
| HDMI | HDMI 1.4 | RPi 3B+ | Écran tactile 7" |
| USB | HID (touch) | RPi 3B+ | Contrôleur tactile écran |

> Port série : apparaît sous `/dev/ttyUSB0` (CH340) ou `/dev/ttyACM0` (ATmega natif).  
> Identifier avec `ls /dev/tty*` avant et après branchement USB.

---

## 6. Questions ouvertes (à résoudre avant ou en Phase 1)

Ces points doivent être documentés dans `CONCEPTION.md` dès qu'ils sont résolus.

| # | Question | Comment y répondre |
|---|---|---|
| Q1 | Version du module caméra RPi (v1 / v2 / v3 / NoIR) | `rpicam-hello --list-cameras` sur le RPi, ou lire l'étiquette du module |
| Q2 | Version exacte du firmware Marlin | Envoyer `M115` via terminal série (ex: `screen /dev/ttyUSB0 115200`) |
| Q3 | Port série Geeetech : `/dev/ttyUSB0` ou `/dev/ttyACM0` | `ls /dev/tty*` avant/après branchement USB |
| Q4 | Choix interface caméra : **V4L2** ou **picamera2** | À décider en Phase 1 selon tests de performance |
| Q5 | Taille réelle de la zone de travail (en mm) | Mesurer sur la machine physique |
| Q6 | Distance caméra → pièce (hauteur en mm) | Mesurer sur la machine physique |
| Q7 | Taille des marqueurs ArUco à imprimer (en mm) | Dépend de la distance caméra/pièce — à calculer |
| Q8 | Volume de pâte par mm² (quantité de référence) | Calibrage expérimental lors des tests de dépose |

---

## 7. Prochaine session — agenda

**Séance de conception hardware (avant Phase 1)**

- [ ] Identifier la version du module caméra (Q1)
- [ ] Identifier la version Marlin via M115 (Q2)
- [ ] Identifier le port série Geeetech (Q3)
- [ ] Mesurer la zone de travail et la distance caméra/pièce (Q5, Q6)
- [ ] Calculer la taille des marqueurs ArUco à imprimer (Q7)
- [ ] Créer le synoptique Draw.io (sauvegarder dans `assets/synoptique.drawio`)
- [ ] Mettre à jour `CONCEPTION.md` et `CLAUDE.md` avec toutes ces réponses
- [ ] Si tout est clarifié : démarrer **Phase 1** (`modules/camera.py`)

---

## 8. Plan de développement — avancement

| Phase | Module principal | Statut | Sessions |
|---|---|---|---|
| 1 | `modules/camera.py` — caméra de base | ⬜ À faire | 0 / 1 |
| 2 | `modules/vision.py` — ArUco & calibrage | ⬜ À faire | 0 / 3 |
| 3 | `modules/machine.py` — G-code Marlin | ⬜ À faire | 0 / 2 |
| 4 | `gui/` — interface graphique squelette | ⬜ À faire | 0 / 3 |
| 5 | `modules/path_planner.py` + zone | ⬜ À faire | 0 / 3 |
| 6 | `main.py` — intégration workflow complet | ⬜ À faire | 0 / 3 |
| 7 | `modules/reporter.py` — rapport PDF | ⬜ À faire | 0 / 2 |
| 8 | Tests, robustesse, finitions | ⬜ À faire | 0 / 3 |

**Total estimé : 20 sessions × ~2h = ~40h**  
**Rythme cible : 3 à 4 sessions/semaine pour tenir la deadline fin juin 2026**

> Mettre à jour après chaque session : ⬜ À faire → 🔄 En cours → ✅ Validé

---

## 9. Décisions techniques arrêtées

Ces choix sont actés — ne pas les remettre en question sans raison documentée.

| Décision | Choix retenu | Justification |
|---|---|---|
| Marqueurs ArUco | DICT_4X4_50, IDs 0–3 | Standard, robuste, bien supporté par OpenCV |
| Communication machine | USB série, 115200 baud, protocole G-code Marlin | Imposé par le firmware de la Geeetech |
| Résolution capture | 1280×960 pour photos rapport, 640×480 pour traitement ArUco | Compromis performance RPi 3B+ / précision |
| Fins de ligne | LF sur toutes les machines (`.gitattributes`) | Compatibilité Linux/RPi |
| Licence des librairies | Open source uniquement (MIT/BSD/Apache/LGPL/GPL usage interne) | Utilisabilité en entreprise sans coût |
| Interface PyQt5 | Fenêtre 800×480 plein écran | Correspond à la résolution de l'écran tactile 7" |
| Langue du code | Identifiants en anglais, commentaires en français | Convention Python + lisibilité pour le rapport |

**Décisions en attente :** interface caméra (V4L2 vs picamera2) — à trancher en Phase 1.

---

## 10. Structure du projet

```
thermal-paste-machine/
├── CONCEPTION.md            # Document de conception — rapport de stage
├── CLAUDE.md                # Ce fichier — contexte portable pour Claude
├── README.md                # Guide de prise en main et switch Windows/Linux
├── requirements.txt         # Dépendances Python (sans PyQt5 sur RPi)
├── .gitignore
├── .gitattributes           # Force LF sur toutes les machines
│
├── modules/
│   ├── config.py            # ✅ Créé — paramètres globaux (caméra, machine, ArUco)
│   ├── camera.py            # ⬜ Phase 1 — capture image via CSI/V4L2
│   ├── vision.py            # ⬜ Phase 2 — détection ArUco, homographie
│   ├── machine.py           # ⬜ Phase 3 — communication G-code Marlin
│   ├── path_planner.py      # ⬜ Phase 5 — calcul des trajectoires
│   └── reporter.py          # ⬜ Phase 7 — génération PDF
│
├── gui/
│   ├── app.py               # ⬜ Phase 4 — fenêtre principale PyQt5
│   ├── screen_capture.py    # ⬜ Phase 4 — écran 1 : prise de photo
│   ├── screen_zone.py       # ⬜ Phase 4/5 — écran 2 : sélection zone
│   ├── screen_run.py        # ⬜ Phase 4/6 — écran 3 : exécution
│   └── screen_report.py     # ⬜ Phase 4/7 — écran 4 : rapport
│
├── assets/                  # Ressources statiques (synoptique Draw.io, icônes...)
├── reports/                 # PDFs générés à l'exécution (gitignorés)
├── tests/                   # Tests unitaires et scripts de démonstration
└── main.py                  # ⬜ Phase 6 — point d'entrée, machine à états
```

---

## 11. Règles techniques

### Librairies — open source uniquement

| Librairie | Licence | Rôle | RPi | Windows |
|---|---|---|---|---|
| PyQt5 | GPL v3* | Interface graphique tactile | `apt` | `pip` |
| opencv-contrib-python | Apache 2.0 | Vision, ArUco, homographie | `pip` | `pip` |
| picamera2 | BSD | Caméra CSI native RPi | `apt` | ✗ non dispo |
| pyserial | BSD | Communication G-code Marlin | `pip` | `pip` |
| fpdf2 | LGPL | Génération PDF | `pip` | `pip` |
| numpy | BSD | Calcul vectoriel trajectoires | `pip` | `pip` |
| pytest | MIT | Tests unitaires | `pip` | `pip` |

> *PyQt5 GPL v3 : acceptable pour un usage interne non distribué. Si distribution commerciale → PySide6 (LGPL).

### Installation complète (Raspberry Pi OS Bullseye / Bookworm)

```bash
# Dépendances système
sudo apt update && sudo apt install -y \
    python3-pip python3-pyqt5 libatlas-base-dev python3-picamera2

# Activer le pilote V4L2 pour accès caméra via OpenCV (si approche V4L2 retenue)
echo "bcm2835-v4l2" | sudo tee /etc/modules-load.d/bcm2835-v4l2.conf

# Dépendances Python
pip3 install opencv-contrib-python pyserial fpdf2 numpy pytest
```

### Installation (Windows — dev sans matériel)

```bash
pip install opencv-contrib-python pyserial fpdf2 numpy pytest PyQt5
# picamera2 indisponible sur Windows — mocker la classe Camera pour les tests
```

---

## 12. Conventions de code

### Commentaires — règle didactique (CRITIQUE)

Chaque ligne non triviale doit être commentée **en français**, en expliquant **ce que fait la ligne ET pourquoi** — pas seulement ce qu'elle fait. Le lecteur ne doit pas avoir à consulter la documentation externe pour comprendre.

**Exemple correct :**
```python
# Ouvrir le flux vidéo depuis la caméra à l'index donné (0 = première caméra détectée)
self._cap = cv2.VideoCapture(self._index)

# Vérifier que l'ouverture a réussi — la caméra peut être occupée par un autre processus
if not self._cap.isOpened():
    raise RuntimeError("Impossible d'ouvrir la caméra")

# Lire une image depuis le flux (ret = booléen succès, frame = image numpy BGR)
ret, frame = self._cap.read()
```

**Exemple incorrect (trop vague, inutile) :**
```python
self._cap = cv2.VideoCapture(self._index)  # VideoCapture
if not self._cap.isOpened():               # vérification
    raise RuntimeError("erreur")
```

### Commits — règle d'autoportance (CRITIQUE)

Le message de commit doit contenir 4 éléments, dans cet ordre :

```
<Titre court et explicite>

Contexte : <phase concernée, objectif, contrainte ayant motivé le changement>

Ajouts fonctionnels :
- <ce que le code fait maintenant — comportement, pas syntaxe>
- ...

Fichiers modifiés :
- <fichier.py> (nouveau / modifié / supprimé)
- ...

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

### Style général

- PEP 8 — indentation 4 espaces, lignes ≤ 88 caractères
- Type hints sur toutes les signatures de méthodes publiques
- Un fichier `tests/test_<module>.py` par module, exécuté avec `pytest`
- Un fichier `tests/demo_<module>.py` par module pour les tests manuels

---

## 13. Historique des sessions

| Date | Contenu | Résultat |
|---|---|---|
| 2026-05-19 | Session 0 — Initialisation : architecture, CONCEPTION.md, CLAUDE.md, dépôt GitHub, synoptique hardware, règles de dev | Dépôt créé et poussé. Toutes les règles posées. Questions ouvertes identifiées. |

> L'historique détaillé (par phase) est dans `CONCEPTION.md` section 10.
