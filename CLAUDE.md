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
| Contrôleur machine | Carte Geeetech — firmware **Marlin** via USB série 115200 baud | ✅ Confirmé (version à identifier) |
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
| USB (puce CH340 ou ATmega) | UART série 115200 baud | RPi 3B+ | Carte Geeetech (Marlin) |
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
| Q2 | Version exacte du firmware Marlin | Envoyer `M115` via terminal série (ex: `screen /dev/ttyUSB0 115200`) |
| Q3 | Port série Geeetech : `/dev/ttyUSB0` ou `/dev/ttyACM0` | `ls /dev/tty*` avant/après branchement USB |
| ~~Q4~~ | ~~Choix interface caméra : V4L2 ou picamera2~~ | ✅ **Résolu** — `cv2.VideoCapture(0)` direct via USB (UVC), pas de picamera2 |
| Q5 | Taille réelle de la zone de travail (en mm) | Mesurer sur la machine physique |
| Q6 | Distance caméra → pièce (hauteur en mm) | Mesurer sur la machine physique |
| Q7 | Taille des marqueurs ArUco à imprimer (en mm) | Dépend de la distance caméra/pièce — à calculer |
| Q8 | Volume de pâte par mm² (quantité de référence) | Calibrage expérimental lors des tests de dépose |

---

## 8. Prochaine session — agenda

**Séance de conception hardware (avant Phase 1)**

- [x] ~~Identifier la version du module caméra (Q1)~~ → Philips SPC 1330NC USB, OpenCV index 0
- [x] ~~Choix interface caméra (Q4)~~ → `cv2.VideoCapture(0)`, pas de picamera2
- [ ] Identifier la version Marlin via M115 (Q2)
- [ ] Identifier le port série Geeetech (Q3)
- [ ] Mesurer la zone de travail et la distance caméra/pièce (Q5, Q6)
- [ ] Calculer la taille des marqueurs ArUco à imprimer (Q7)
- [ ] Tester la Philips SPC 1330NC : vérifier résolution max, `cv2.VideoCapture(0)` sur RPi
- [ ] Créer le synoptique Draw.io (sauvegarder dans `assets/synoptique.drawio`)
- [ ] Mettre à jour `CONCEPTION.md` et `CLAUDE.md` avec toutes ces réponses
- [ ] Si tout est clarifié : démarrer **Phase 1** (`modules/camera.py`)

---

## 9. Plan de développement — avancement

### Partie A — Logiciel sur Geeetech (PoC) · deadline fin juin 2026

| Phase | Module principal | Statut | Sessions |
|---|---|---|---|
| 0 | Identification matériel (caméra, port série, firmware) | ⬜ À faire | 0 / 1 |
| 1 | `modules/camera.py` — caméra de base | ⬜ À faire | 0 / 1 |
| 2 | `modules/vision.py` — ArUco & calibrage | ⬜ À faire | 0 / 3 |
| 3 | `modules/machine.py` — G-code Marlin | ⬜ À faire | 0 / 2 |
| 4 | `gui/` — interface graphique squelette | ⬜ À faire | 0 / 3 |
| 5 | `modules/path_planner.py` + zone | ⬜ À faire | 0 / 3 |
| 6 | `main.py` — intégration workflow complet | ⬜ À faire | 0 / 3 |
| 7 | `modules/reporter.py` — rapport PDF | ⬜ À faire | 0 / 2 |
| 8 | Tests, robustesse, finitions (Geeetech) | ⬜ À faire | 0 / 3 |

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
| Communication machine | USB série, 115200 baud, protocole G-code Marlin | Imposé par le firmware de la Geeetech |
| Résolution capture | 1280×960 pour photos rapport, 640×480 pour traitement ArUco | Compromis performance RPi 3B+ / précision |
| Fins de ligne | LF sur toutes les machines (`.gitattributes`) | Compatibilité Linux/RPi |
| Licence des librairies | Open source uniquement (MIT/BSD/Apache/LGPL/GPL usage interne) | Utilisabilité en entreprise sans coût |
| Interface PyQt5 | Fenêtre 800×480 plein écran | Correspond à la résolution de l'écran tactile 7" |
| Langue du code | Identifiants en anglais, commentaires en français | Convention Python + lisibilité pour le rapport |
| Caméra | **Philips SPC 1330NC USB** — `cv2.VideoCapture(0)` | Connecteur CSI du RPi défaillant ; webcam USB fonctionnelle, pilote UVC standard, aucune config supplémentaire |

**Décisions en attente :** résolution max de la Philips SPC 1330NC à confirmer sur le RPi (Q6, Q7 dépendent de la résolution réelle).

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

> L'historique détaillé (par phase) est dans `CONCEPTION.md` section 10.
