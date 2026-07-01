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
| Deadline logiciel (Geeetech) | Fin juin 2026 |
| Deadline intégration CNC | Fin juillet 2026 (soutenance blanche) |
| Deadline finale | Fin août 2026 (soutenance) |
| Dépôt GitHub | `https://github.com/darckmaster/thermal-paste-machine` |
| Branche principale | `master` |

### Deux machines — rôles distincts

| Machine | Rôle | Statut |
|---|---|---|
| **Geeetech I3 (imprimante modifiée)** | **Proof of concept** — plateforme de développement et validation logicielle | Disponible maintenant |
| **CNC cible** (avec carte Marlin) | **Machine de production** — destination finale du logiciel et du Raspberry Pi | À assembler en juillet |

> **Stratégie** : tout le logiciel est développé et validé sur la Geeetech (même firmware Marlin).  
> Une fois validé, le logiciel et le Raspberry Pi sont portés sur la CNC cible, qui utilise le même protocole G-code.  
> Le portage est quasi transparent côté code — seuls les paramètres machine (zone de travail, port série) changent.

**Enjeux du projet :**
- Le code est **didactique** : il doit pouvoir être relu et compris ligne par ligne, manuellement, par l'étudiant ou son tuteur
- Le `CONCEPTION.md` doit rester à jour à chaque session pour alimenter le **rapport de stage et la soutenance**
- Toutes les librairies utilisées doivent être **open source** et utilisables en entreprise sans licence tierce payante

**Document de référence complet :** `CONCEPTION.md` — architecture détaillée, synoptique matériel, interfaces des classes, plan de développement avec estimations et critères de validation par phase.

---

## 2. Mode de collaboration (IMPORTANT — à respecter à chaque session)

- **Ne pas coder sans expliquer à l'étudiant.** Claude guide, explique, propose un code documenté ; l'étudiant approuve le code, le modifie si nécessaire, teste et valide. C'est en faisant et comprenant qu'on apprend.
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
3. Vérifier le tableau d'avancement (section 9)
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

## 5. Mode de travail dual — chez soi / au boulot

Le projet se déroule dans deux environnements aux contraintes opposées. Le setup logiciel et le découpage des activités doivent en tenir compte.

### 5.1 Les deux environnements

| Lieu | Quand | Matériel | Internet |
|---|---|---|---|
| **Chez soi** | Soir / week-end | PC perso complet + Geeetech *sans* dispositif de seringue | Oui (PC) |
| **Entreprise** | Journée | Téléphone 5G + clavier Bluetooth + Geeetech *avec* dispositif de seringue. PC entreprise sans internet → inutilisable pour Claude Code. | Uniquement via téléphone 5G |

### 5.2 Setup mobile pour les sessions au boulot

Le RPi du projet devient le poste de travail mobile. Il joue trois rôles à la fois : ordinateur de contrôle (rôle final du projet), pont vers Claude Code, et interface avec la Geeetech + caméra CSI.

```
[Téléphone 5G] ──tethering USB──> [RPi 3B+] ──USB──> [Geeetech + seringue]
       ▲                             ▲
       │ SSH (clavier Bluetooth)     │ Caméra CSI
       └─────────────────────────────┘
```

**À transporter au boulot** : RPi 3B+ + alim, module caméra CSI, câble USB vers Geeetech, câble USB pour tethering téléphone → RPi, téléphone + clavier BT + support pliant.

**Outils installés sur le RPi (une fois, à la maison)** :
- `openssh-server` activé
- **Tailscale** (`curl -fsSL https://tailscale.com/install.sh | sh`) — VPN mesh gratuit qui perce les NAT 5G sans config
- **Claude Code** (`npm install -g @anthropic-ai/claude-code`)
- Toutes les dépendances Python du projet (cf. section 12) — pour ne pas brûler la 5G au boulot

**Outils installés sur le téléphone** :
- **Termius** (Play Store) — client SSH avec ergonomie clavier BT
- **Tailscale** (Play Store) — même compte que le RPi
- Tethering USB activé (préférer USB au WiFi hotspot : moins de batterie, plus stable)

### 5.3 Workflow type d'une journée au boulot

```
1. Arrivée : brancher RPi (secteur), USB vers Geeetech, USB tethering au téléphone
2. Activer le partage de connexion du téléphone → le RPi a internet via 5G
3. Termius : SSH vers le RPi (via Tailscale OU IP locale du tethering)
4. cd thermal-paste-machine && git pull && claude
5. Session Claude Code normale, avec accès matériel réel
6. Avant de partir : git push pour synchroniser
```

Le soir à la maison : `git pull` sur le PC, on continue sur grand écran.

### 5.4 Répartition optimale des activités

| Quand | Activités idéales |
|---|---|
| **Soir / week-end (chez soi)** | Logique pure : `path_planner.py`, GUI PyQt5, refactor, rédaction du rapport. Tests G-code « à vide » (déplacements XYZ sans extrusion). |
| **Journée (entreprise)** | Tests caméra CSI réels, calibrage ArUco, **tests dépose seringue** (irremplaçables), validation workflow end-to-end. |

> **Bénéfice indirect** : le RPi étant la machine cible finale, on développe *sur* la machine cible dès maintenant. La Phase 0 (identification matériel) et toutes les calibrations doivent de toute façon se faire au boulot.

### 5.5 Points d'attention

- **Conso 5G** : ~50 Mo par session Claude Code. Faire tous les `apt` / `pip install` chez soi.
- **Politique entreprise** : vérifier avec le tuteur qu'apporter le RPi et le brancher à la Geeetech est autorisé.
- **Batterie téléphone** : le tethering USB consomme ; le RPi 3B+ ne recharge pas le téléphone → prévoir une power bank.
- **Si tethering refusé** : repli sur un dongle 4G/5G dédié branché sur le RPi (~20 €). Tailscale fonctionne pareil.

> **Document complet** : voir `assets/setup_travail_mobile.docx` pour le détail des étapes d'installation et la liste des achats.

---

## 6. Matériel — état des connaissances

### Inventaire confirmé

#### Machine PoC (Geeetech I3 — développement et validation)

| Composant | Modèle / Référence | Statut |
|---|---|---|
| Ordinateur de contrôle | Raspberry Pi **3B+** (1 Go RAM, Cortex-A53 ×4 @ 1,4 GHz) | ✅ Confirmé |
| Caméra | **Philips SPC 1330NC** — interface **USB**, détectée par OpenCV index 0 | ✅ Confirmé |
| Interface utilisateur | Écran tactile **7 pouces 800×480** | ✅ Confirmé |
| Base mécanique | Imprimante 3D **Geeetech I3** modifiée | ✅ Confirmé (modèle exact à identifier) |
| Actionneur de dépose | Moteur **Nema 17** sur axe E (ex-extrudeur) + vis sans fin | ✅ Confirmé |
| Contrôleur machine | Carte Geeetech — firmware **Marlin 1.1.8** via USB série **250000 baud** — port `/dev/ttyUSB0` | ✅ Confirmé (2026-07-01, `M115`) |
| Référentiel | 4 marqueurs **ArUco** DICT_4X4_50 — IDs 0, 1, 2, 3 | ✅ Arrêté |

#### Machine cible (CNC — production)

| Composant | Modèle / Référence | Statut |
|---|---|---|
| Base mécanique | CNC (à confirmer) | ⬜ À assembler |
| Contrôleur machine | Carte CNC — firmware **Marlin** (même protocole G-code) | ⬜ À identifier |
| Ordinateur de contrôle | Même Raspberry Pi 3B+ | ✅ Réutilisé |
| Caméra + écran | Même Philips SPC 1330NC USB + écran 7" | ✅ Réutilisés |

> Le portage logiciel Geeetech → CNC se limite aux paramètres de `config.py` (port série, limites de déplacement, zone de travail).

### Connexions E/S

| Interface | Protocole | De | Vers |
|---|---|---|---|
| USB | UVC (webcam standard) | RPi 3B+ | Philips SPC 1330NC (caméra) |
| USB (puce CH340) | UART série **250000 baud** | RPi 3B+ | Carte Geeetech (Marlin 1.1.8) |
| HDMI | HDMI 1.4 | RPi 3B+ | Écran tactile 7" |
| USB | HID (touch) | RPi 3B+ | Contrôleur tactile écran |

> Caméra : détectée sous `/dev/video0`, accessible via `cv2.VideoCapture(0)` sans configuration supplémentaire.  
> Port série Marlin : apparaît sous `/dev/ttyUSB0` (CH340) ou `/dev/ttyACM0` (ATmega natif).  
> Identifier avec `ls /dev/tty*` avant et après branchement USB.

---

## 7. Questions ouvertes (à résoudre avant ou en Phase 1)

Ces points doivent être documentés dans `CONCEPTION.md` dès qu'ils sont résolus.

| # | Question | Comment y répondre |
|---|---|---|
| ~~Q1~~ | ~~Version du module caméra RPi~~ | ✅ **Résolu** — caméra Philips SPC 1330NC USB (OpenCV index 0) |
| ~~Q2~~ | ~~Version exacte du firmware Marlin~~ | ✅ **Résolu** — Marlin 1.1.8 (compilé 2022-09-25, confirmé 2026-07-01) |
| ~~Q3~~ | ~~Port série Geeetech : `/dev/ttyUSB0` ou `/dev/ttyACM0`~~ | ✅ **Résolu** — `/dev/ttyUSB0` (puce CH340), baudrate **250000** |
| ~~Q4~~ | ~~Choix interface caméra : V4L2 ou picamera2~~ | ✅ **Résolu** — `cv2.VideoCapture(0)` direct via USB (UVC), pas de picamera2 |
| ~~Q5~~ | ~~Taille réelle de la zone de travail (en mm)~~ | ✅ **Résolu** — 151 mm × 104 mm (re-mesuré centre-à-centre des marqueurs, 2026-06-12) |
| ~~Q6~~ | ~~Distance caméra → pièce (hauteur en mm)~~ | ✅ **Résolu** — 200 mm (20 cm, re-mesuré 2026-06-12) |
| ~~Q7~~ | ~~Taille des marqueurs ArUco à imprimer (en mm)~~ | ✅ **Résolu** — 28 mm × 28 mm (marqueurs imprimés, détection confirmée) |
| Q8 | Volume de pâte par mm² (quantité de référence) | Calibrage expérimental lors des tests de dépose |

**Écart de distance résiduel (~10 %)** : confirmé encore présent lors du test PDF cycle complet du 2026-07-01. Cause connue = distorsion de l'objectif (barrel distortion), sera corrigé par la calibration échiquier (Q8 / section 8 agenda).

---

## 8. Prochaine session — agenda

**Phases 4–7 ✅ validées — Phase 8 à démarrer**

Phase 2 — Vision ✅ (3 sessions) + calibration optique en attente :
- [x] ArUco, homographie, pixel→mm validés
- [x] `modules/calibration.py` créé — à exécuter avec échiquier imprimé
- [ ] **Calibration optique** : imprimer échiquier 9×6 (25 mm/carré), capturer 15 poses, valider erreur < 2 mm
  → Reporter avec `python3 tests/demo_calibration.py` dès que le plateau est disponible

Phase 3 ✅ :
- [x] machine.py validé — Marlin 1.1.8, port ttyUSB0, baudrate 250000, axe E confirmé

Phase 4 ✅ :
- [x] GUI 4 écrans complet — navigation validée sur RPi + écran tactile
- [x] Bouton **Homing (G28)** ajouté sur screen_capture (thread séparé, non bloquant)

Phase 5 ✅ :
- [x] Tracé polyline (clic-par-clic) sur screen_zone — ArUco détecté sur la photo
- [x] `modules/path_planner.py` — `generate_path_from_line()` validé

Phase 6 ✅ :
- [x] Intégration machine dans screen_run (QThread RunWorker)
- [x] **Fix repère ArUco ↔ machine** : marqueur 0 = bas-gauche confirmé (2026-07-01)
- [x] Offset machine mesuré : X=20 mm, Y=50 mm (M114 au-dessus du marqueur 0)
- [x] Tracé en W reproduit correctement sur la machine ✅

Phase 7 ✅ :
- [x] `modules/reporter.py` — génération PDF (fpdf2) : photo + résumé statut/longueur/volume
- [x] screen_report.py mis à jour — données réelles + bouton PDF fonctionnel
- [x] **Test PDF cycle complet** validé sur machine réelle (homing → capture → tracé → dépose → rapport) — 2026-07-01

**Prochaine session : Phase 8 — Tests, robustesse, finitions**
- [x] Corriger `tests/test_vision.py::test_pixel_to_mm_coins_de_la_zone` (résidu du fix de repère ArUco — marqueurs synthétiques pas mis à jour pour la convention ID0=bas-gauche) — 2026-07-01, 45/45 tests passent
- [ ] Calibration optique (échiquier)
- [ ] Tests tactiles : vérifier boutons ≥ 44×44 px
- [ ] **Gestion des cas d'erreur** — reportée à une session ultérieure (décidé le 2026-07-01). Audit déjà fait, à reprendre directement sans re-auditer :
  - Déjà bien géré ✅ : caméra absente/déconnectée (`screen_capture.py`), erreurs Homing/dépose remontées via signaux Qt (`HomingWorker`, `RunWorker`), vision/ArUco insuffisants (`screen_zone.py`)
  - Trou #1 (priorité sécurité) : `app.py::closeEvent` (ligne ~175) ne libère que la caméra — si l'app est fermée pendant une dépose, le thread `RunWorker` continue en arrière-plan et l'opérateur perd l'accès à l'arrêt d'urgence
  - Trou #2 : un seul objet `Machine` partagé sans verrou entre l'écran Homing (`screen_capture.py`) et l'écran Run (`screen_run.py`) (`app.py` lignes 90-91/122/160) — risque d'écriture série concurrente si un thread Homing traîne encore
  - Trou #3 (mineur) : messages d'erreur bruts (ex. `[Errno 2] could not open port /dev/ttyUSB0`) au lieu d'un message clair pour l'opérateur
- [ ] Vérifier que `pytest` passe toujours après les modifications de cette session

---

## 9. Plan de développement — avancement

### Partie A — Logiciel sur Geeetech (PoC) · deadline fin juin 2026

| Phase | Module principal | Statut | Sessions |
|---|---|---|---|
| 0 | Identification matériel (caméra, port série, firmware) | ✅ Validé | 1 / 1 |
| 1 | `modules/camera.py` — caméra de base | ✅ Validé | 1 / 1 |
| 2 | `modules/vision.py` — ArUco & calibrage | 🔄 En cours | 3 / 4 |
| 3 | `modules/machine.py` — G-code Marlin | ✅ Validé | 1 / 2 |
| 4 | `gui/` — interface graphique squelette | ✅ Validé | 2 / 3 |
| 5 | `modules/path_planner.py` + zone polyline | ✅ Validé | 1 / 3 |
| 6 | Intégration workflow complet (screen_run + offset machine) | ✅ Validé | 1 / 3 |
| 7 | `modules/reporter.py` — rapport PDF | ✅ Validé | 1 / 2 |
| 8 | Tests, robustesse, finitions (Geeetech) | 🔄 En cours | 1 / 3 |

**Sous-total Partie A : 21 sessions × ~2h = ~42h**  
**Jalon A : Logiciel validé sur Geeetech ≈ début juillet 2026**

> **En parallèle de toute la Partie A** : rédaction du rapport (~1h/soir en semaine, chez soi)  
> **Jalon intermédiaire : premier draft rapport → 15 juin 2026** (à remettre avant les vacances)

### Partie B — Intégration sur CNC cible · deadline fin juillet 2026

| Phase | Description | Statut | Durée estimée |
|---|---|---|---|
| 9 | Assemblage de la CNC cible (mécanique + câblage) | ⬜ À faire | ~2 semaines (hardware) |
| 10 | Portage logiciel : adaptation `config.py` + tests sur CNC | ⬜ À faire | 0 / 2 sessions |
| 11 | Validation complète du système sur CNC cible | ⬜ À faire | 0 / 3 sessions |

**Jalon B : Système validé sur CNC ≈ fin juillet → SOUTENANCE BLANCHE**

### Partie C — Finalisation · deadline fin août 2026

| Phase | Description | Statut | Durée estimée |
|---|---|---|---|
| 12 | Corrections de bugs (retours soutenance blanche) | ⬜ À faire | ~1 semaine |
| 13 | Finalisation et relecture rapport | ⬜ À faire | ~3 semaines |

**Jalon C : Rapport remis → SOUTENANCE FINALE fin août 2026**

### Rédaction rapport — activité en parallèle (fil conducteur du projet)

| Période | Mode | Charge | Objectif |
|---|---|---|---|
| 27 mai → 14 juin | ~1h/soir en semaine | ~3h/semaine | **Draft complet → 15 juin** (avant vacances) |
| 22 juin → 31 juillet | ~1h/soir + week-ends | ~3–5h/semaine | Rapport à jour après chaque phase validée |
| 1 août → 24 août | Mode intensif | Priorité principale | Finalisation, relecture, figures, remise |

> **Jalon intermédiaire critique : premier draft du rapport remis le 15 juin 2026** (jour du départ en vacances).  
> Le `CONCEPTION.md` est le brouillon permanent — le maintenir à jour après chaque session réduit fortement le travail de rédaction finale.

> Mettre à jour après chaque session : ⬜ À faire → 🔄 En cours → ✅ Validé

---

## 10. Décisions techniques arrêtées

Ces choix sont actés — ne pas les remettre en question sans raison documentée.

| Décision | Choix retenu | Justification |
|---|---|---|
| Marqueurs ArUco | DICT_4X4_50, IDs 0–3 | Standard, robuste, bien supporté par OpenCV |
| Communication machine | USB série, **250000 baud**, protocole G-code Marlin | Confirmé 2026-07-01 — Geeetech configurée à 250000 (pas 115200) |
| Résolution capture | 1280×960 pour photos rapport, 640×480 pour traitement ArUco | Compromis performance RPi 3B+ / précision |
| Fins de ligne | LF sur toutes les machines (`.gitattributes`) | Compatibilité Linux/RPi |
| Licence des librairies | Open source uniquement (MIT/BSD/Apache/LGPL/GPL usage interne) | Utilisabilité en entreprise sans coût |
| Interface PyQt5 | Fenêtre 800×480 plein écran | Correspond à la résolution de l'écran tactile 7" |
| Langue du code | Identifiants en anglais, commentaires en français | Convention Python + lisibilité pour le rapport |
| Caméra | **Philips SPC 1330NC USB** — `cv2.VideoCapture(0)` | Connecteur CSI du RPi défaillant ; webcam USB fonctionnelle, pilote UVC standard, aucune config supplémentaire |
| Correction distorsion objectif | `cv2.calibrateCamera` + `cv2.undistort` (échiquier 9×6, 25 mm/carré) | Barrel distortion mesurée à ~10 % d'erreur sans correction ; calibration one-shot sauvegardée dans `assets/camera_calibration.npz` |

**Résolution confirmée :** Philips SPC 1330NC supporte 1280×960 sur RPi 3B+ (confirmé le 2026-06-11). Hauteur caméra : 200 mm. Zone de travail : 151×104 mm (re-mesuré 2026-06-12).

| Repère ArUco ↔ machine | Marqueur 0 = **bas-gauche** de l'image. X+ machine = droite image. Y+ machine = haut image. Offset mesuré : X=20 mm, Y=50 mm (M114, 2026-07-01) | Nécessaire pour convertir coordonnées ArUco → G-code machine |
| Terminal série RPi | `picocom -b 250000 --imap lfcrlf --echo /dev/ttyUSB0` | `screen` non installé ; `minicom` ne supporte pas 250000 baud |

---

## 11. Structure du projet

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
│   ├── camera.py            # ✅ Phase 1 — capture image via USB
│   ├── vision.py            # 🔄 Phase 2 — détection ArUco, homographie
│   ├── calibration.py       # 🔄 Phase 2 — calibration objectif, undistortion
│   ├── machine.py           # ✅ Phase 3 — communication G-code Marlin
│   ├── path_planner.py      # ✅ Phase 5 — calcul des trajectoires (polyline)
│   └── reporter.py          # ✅ Phase 7 — génération PDF
│
├── gui/
│   ├── app.py               # ✅ Phase 4 — fenêtre principale PyQt5
│   ├── screen_capture.py    # ✅ Phase 4 — écran 1 : prise de photo + bouton Homing
│   ├── screen_zone.py       # ✅ Phase 4/5 — écran 2 : tracé polyline + ArUco
│   ├── screen_run.py        # ✅ Phase 4/6 — écran 3 : exécution (QThread + offset machine)
│   └── screen_report.py     # ✅ Phase 4/7 — écran 4 : rapport + export PDF
│
├── assets/                  # Ressources statiques (synoptique Draw.io, icônes...)
├── reports/                 # PDFs générés à l'exécution (gitignorés)
├── tests/                   # Tests unitaires et scripts de démonstration
└── main.py                  # ⬜ Phase 6 — point d'entrée, machine à états
```

---

## 12. Règles techniques

### Librairies — open source uniquement

| Librairie | Licence | Rôle | RPi | Windows |
|---|---|---|---|---|
| PyQt5 | GPL v3* | Interface graphique tactile | `apt` | `pip` |
| opencv-contrib-python | Apache 2.0 | Vision, ArUco, homographie, capture USB | `pip` | `pip` |
| pyserial | BSD | Communication G-code Marlin | `pip` | `pip` |
| fpdf2 | LGPL | Génération PDF | `pip` | `pip` |
| numpy | BSD | Calcul vectoriel trajectoires | `pip` | `pip` |
| pytest | MIT | Tests unitaires | `pip` | `pip` |

> *PyQt5 GPL v3 : acceptable pour un usage interne non distribué. Si distribution commerciale → PySide6 (LGPL).

### Installation complète (Raspberry Pi OS Bullseye / Bookworm)

```bash
# Dépendances système
sudo apt update && sudo apt install -y \
    python3-pip python3-pyqt5 libatlas-base-dev

# Dépendances Python
pip3 install opencv-contrib-python pyserial fpdf2 numpy pytest
```

> La caméra Philips SPC 1330NC est une webcam USB standard (pilote UVC, intégré au noyau Linux).  
> Aucune configuration système supplémentaire n'est nécessaire — `cv2.VideoCapture(0)` fonctionne directement.

### Installation (Windows — dev sans matériel)

```bash
pip install opencv-contrib-python pyserial fpdf2 numpy pytest PyQt5
# La Camera peut être mockée pour les tests sans matériel
```

---

## 13. Conventions de code

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

## 14. Historique des sessions

| Date | Contenu | Résultat |
|---|---|---|
| 2026-05-19 | Session 0 — Initialisation : architecture, CONCEPTION.md, CLAUDE.md, dépôt GitHub, synoptique hardware, règles de dev | Dépôt créé et poussé. Toutes les règles posées. Questions ouvertes identifiées. |
| 2026-05-27 | Révision plan de développement : ajout machine CNC cible, phases 9-13 (assemblage, portage, validation CNC, corrections, rapport), planning Excel généré | CLAUDE.md et CONCEPTION.md mis à jour. Fichier `assets/planning.xlsx` créé avec jalons. |
| 2026-05-28 | Conception du mode de travail dual chez soi / au boulot : RPi mobile au boulot piloté en SSH depuis téléphone 5G + clavier BT (Termius + Tailscale), répartition des activités logiciel/matériel selon le lieu | Nouvelle section 5 dans CLAUDE.md. Document détaillé `assets/setup_travail_mobile.docx` créé. |
| 2026-06-09 | Changement de caméra : connecteur CSI du RPi défaillant → remplacement par webcam **Philips SPC 1330NC USB** détectée sous OpenCV index 0. Décision : `cv2.VideoCapture(0)` sans picamera2 ni pilote V4L2. | CLAUDE.md et CONCEPTION.md mis à jour. Q1 et Q4 résolus. picamera2 retiré des dépendances. |
| 2026-06-11 | **Phase 1** — Création de `modules/camera.py` (classe `Camera` : open, capture, release), `tests/test_camera.py` (4 tests pytest), `tests/demo_camera.py` (flux temps réel), `conftest.py`. Résolution 1280×960 confirmée sur RPi. | 4/4 tests passés. Phase 1 ✅ validée. |
| 2026-06-11 | **Phase 2 Session 1** — Création de `modules/vision.py` (classe `VisionProcessor`, `detect_markers()`), `tests/test_vision.py` (5 tests), `tests/demo_vision.py` (détection ArUco temps réel PyQt5). Fix affichage : `cv2.imshow` cassé sous Wayland → migration vers PyQt5 pour les démos. Q6 et Q7 résolus : caméra à 100–110 mm, marqueurs 28×28 mm. | 9/9 tests passés. Détection 4 marqueurs simultanée confirmée. |
| 2026-06-11 | **Phase 2 Session 2** — Ajout `compute_homography()`, `warp_image()`, `pixel_to_mm()` dans `vision.py`. Démo côte à côte (original + redressé). Q5 résolu : zone de travail 152×106 mm (mesuré). | 14/14 tests passés. Image redressée validée visuellement. |
| 2026-06-12 | **Phase 2 Session 3** — Validation métrologique sur machine réelle à 200 mm de hauteur. Diagnostic : barrel distortion ~10 % d'erreur. Re-mesure physique : 151×104 mm. Implémentation `modules/calibration.py` + `tests/demo_calibration.py` + `tests/demo_validation.py`. Échiquier 9×6 généré pour calibration. | Code calibration implémenté. Calibration elle-même à effectuer chez soi (impression échiquier requise). |
| 2026-07-01 | **Phase 3 — Complète** — Firmware Marlin 1.1.8, port ttyUSB0, baudrate 250000. `modules/machine.py` (connexion, G90, M302 S0, home, move_to, dispense, emergency_stop). Fix protection extrusion à froid (M302 S0). Validation complète sur machine réelle : XYZ + axe E (dispense ±10 mm). | 10/10 tests passés. Tous les axes validés. Phase 3 ✅. |
| 2026-07-01 | **Phase 4 Session 1** — Création GUI PyQt5 complète : `gui/app.py` (MainWindow + QStackedWidget + navigation signaux), `gui/screen_capture.py` (flux caméra live 10fps, capture, validation), `gui/screen_zone.py` / `screen_run.py` / `screen_report.py` (placeholders navigables), `main.py`. | Navigation 4 écrans validée sur RPi + écran tactile. Écran 1 caméra fonctionnel. Placeholders 2-4 opérationnels. |
| 2026-07-01 | **Phases 5 & 6** — `screen_zone.py` : sélection de zone par tracé polyline (clic-par-clic, overlay coloré, ArUco détecté sur la photo). `path_planner.py` : `generate_path_from_line()`. `screen_run.py` : exécution G-code réelle via QThread (RunWorker). Premier test réel : tracé en W dessiné → déplacement machine incorrect (repère ArUco non aligné avec repère machine). | Phases 5 & 6 implémentées. Bug repère identifié. |
| 2026-07-01 | **Fix repère ArUco ↔ machine** — Diagnostic : marqueur 0 = bas-gauche (non haut-gauche comme codé). Mesuré avec M114 : X=20, Y=50 mm depuis home. `vision.py` : dst_pts corrigé (ID0=BL, ID1=TL, ID2=TR, ID3=BR). `config.py` : MACHINE_ORIGIN_X=20, MACHINE_ORIGIN_Y=50. `screen_run.py` : offset appliqué + homing G28 ajouté. Terminal série : `picocom -b 250000 --imap lfcrlf --echo`. | Tracé en W reproduit correctement sur la machine ✅. Écart distances résiduel (~10 %) = distorsion objectif, sera corrigé par calibration échiquier. |
| 2026-07-01 | **Phase 7** — `modules/reporter.py` (fpdf2 : photo + résumé statut/longueur/volume estimé). `screen_report.py` mis à jour avec données réelles + export PDF fonctionnel. `screen_run.py` : signal `run_finished(str)` avec statut. `app.py` : stockage image/points/quantité pour le rapport. | Phase 7 ✅. Test PDF cycle complet à finaliser lors de la prochaine session. |
| 2026-07-01 | **Bouton Homing** — `screen_capture.py` : bouton "Homing (G28)" avec `HomingWorker` (QThread). Fix GC : worker stocké en attribut d'instance (`self._homing_worker`) pour éviter la destruction prématurée par Python. Homing validé sur machine réelle. | Bouton Homing fonctionnel ✅. |
| 2026-07-01 | **Phase 8 (début) — Test PDF cycle complet** — Validation de `reporter.py` en deux temps : (1) `tests/demo_reporter.py` créé (image + tracé synthétiques, sans matériel) — PDF vérifié via `pdftotext`/`pdfimages` (calculs longueur/volume exacts, image JPEG bien intégrée, statut succès/urgence correct) ; (2) cycle complet réel sur la Geeetech au boulot (homing → capture → tracé → dépose → export PDF) — fonctionnel de bout en bout. Écart de distance résiduel (~10 %) toujours présent, cause connue (distorsion objectif), en attente de la calibration échiquier. Résidu identifié à corriger : `test_pixel_to_mm_coins_de_la_zone` échoue (marqueurs synthétiques du test pas mis à jour après le fix de repère ID0=bas-gauche). | Test PDF cycle complet ✅. Phase 8 démarrée (1/3). |
| 2026-07-01 | **Fix test ArUco résiduel** — Confirmé au préalable que l'échec de `test_pixel_to_mm_coins_de_la_zone` était déterministe (2 essais identiques) et sans lien avec la caméra (test 100% synthétique, aucun `cv2.VideoCapture`). `tests/test_vision.py::_marqueurs_synthetiques()` remis dans l'ordre ID0=bas-gauche/ID1=haut-gauche/ID2=haut-droit/ID3=bas-droit (aligné sur la convention réelle de `vision.py`), assertions de coins ajustées en conséquence. | 45/45 tests passent ✅. |

> L'historique détaillé (par phase) est dans `CONCEPTION.md` section 10.
