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
| Deadline logiciel (Geeetech) | 17 juillet 2026 — clôture logiciel + MàJ rapport entreprise |
| Soutenances blanches (entreprise) | 22/07, 05/08, 12/08 — partiellement en anglais |
| Machines fonctionnelles (Geeetech + CNC) | avant le 12/08 (3e soutenance blanche) |
| Rapport final (IUT) | 17 août 2026 |
| Soutenance finale (IUT) | 31 août 2026 — démonstration sur Geeetech acceptée |
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

### Le processus de dépose — workflow opérateur (cible)

Le logiciel suit ce déroulé, du point de vue de l'opérateur. **C'est la référence du comportement attendu du produit fini.**

1. **Calibration caméra (une seule fois)** — À l'installation, calibrer la caméra avec une **mire ChArUco** (damier + marqueurs ArUco). Les coefficients de correction de distorsion sont enregistrés dans les paramètres du logiciel (`assets/camera_calibration.npz`) et rechargés à chaque démarrage. À refaire uniquement si la caméra ou l'objectif change.
2. **Mise en place** — L'opérateur pose les boîtiers (coques de calculateur) sur le plateau de la machine. Le plateau porte **4 marqueurs ArUco**, un à chaque coin, qui servent de référentiel géométrique (repère image ↔ repère machine).
3. **Préparation des dépôts** — Sur l'image affichée par la caméra (photo redressée et calibrée), l'opérateur **trace un ou plusieurs cordons de dépôt** (tracés polyline, clic par clic). À **chaque cordon** il associe une **quantité de pâte thermique**. L'ensemble (cordons + quantités) constitue une **préparation**.
4. **Sauvegarde de la préparation** — La préparation est enregistrée dans un **fichier JSON** (cordons, quantités, horodatage). Elle peut être rechargée et modifiée plus tard.
5. **Lancement de la dépose** — L'opérateur lance l'exécution : la machine fait un homing, puis parcourt chaque cordon en déposant la quantité de pâte associée.
6. **Réutilisation** — Si le plateau n'a pas changé, l'opérateur peut **recharger un fichier de préparation existant** (et éventuellement le modifier) avant de relancer la dépose, sans tout retracer.
7. **Rapport** — À la fin de chaque dépose, un **rapport PDF** est généré automatiquement : photo, statut, **temps de dépose**, **quantité totale déposée**, détail par cordon.

> **Note « plateau inchangé »** : le logiciel ne peut pas garantir seul que le plateau est identique. Le rechargement d'une préparation est donc sous la responsabilité de l'opérateur (évolution possible : comparer la position des ArUco pour alerter en cas d'écart).

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
| Base mécanique | CNC — châssis + axes | ✅ Montée (2026-07-11) |
| Contrôleur machine | Carte CNC — firmware **Marlin dernière version** (même protocole G-code) | ✅ Intégrée, câblée, sous tension, flashée (2026-07-11) |
| Câblage capteurs + moteurs | Fins de course, caméra, moteurs Nema 17 | 🔄 En cours — reste à câbler |
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
| ~~Q9~~ | ~~Firmware CNC : Marlin ou GRBL ?~~ | ✅ **Résolu (2026-07-11)** — Marlin dernière version → portage transparent, seul `config.py` change |

**Écart de distance résiduel (~10 %)** : confirmé encore présent lors du test PDF cycle complet du 2026-07-01. Cause connue = distorsion de l'objectif (barrel distortion), sera corrigé par la calibration échiquier (Q8 / section 8 agenda).

---

## 8. Prochaine session — agenda

**Phases 4–7 ✅ validées — CNC quasi assemblée (Marlin confirmé) — Phase 8 en cours + nouvelles fonctionnalités décidées le 2026-07-11.**

> 📅 **Le planning détaillé jour par jour (11/07 → 31/08) est en section 9.** Cette section 8 conserve le détail technique de l'agenda Phase 8.
>
> **Nouvelles fonctionnalités actées le 2026-07-11** (voir le process complet en section 1) :
> - Calibration caméra sur mire **ChArUco** (remplace l'échiquier)
> - **Zones = cordons multiples**, une quantité de pâte par cordon (aujourd'hui : un seul tracé global)
> - **Fichier de préparation JSON** : sauvegarde / rechargement / édition
> - **Temps de dépose** ajouté au rapport PDF
>
> **Semaine 1 (11→17/07) — priorité : MàJ rapport entreprise le 17/07 + finir câblage CNC :**
> - 🏠 Phase 8 gestion d'erreur (3 trous : `closeEvent`, verrou `Machine`, messages opérateur)
> - 🏠 Tests tactiles (boutons ≥ 44 px) + non-régression `pytest`
> - 🏠 Réécrire `calibration.py` en **ChArUco** ; ajouter le temps de dépose au rapport
> - 🏭 Finir câblage CNC (fins de course, moteurs, caméra) + 1er power-on ; capturer les poses ChArUco (Geeetech) ; Q8 volume pâte

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
- [x] **Écran calibration ChArUco créé** (2026-07-25) — `gui/screen_calibration.py` complet : flux caméra, détection ChArUco en thread séparé (`DetectionThread`), capture de poses, bouton "Générer la mire", calcul de calibration en thread, sauvegarde
- [x] **Système local_config.json** (2026-07-25) — paramètres par machine hors git : `camera_index`, `calibration_min_images`, `charuco_cols/rows/square_mm/marker_mm/dict`, `charuco_legacy_pattern`. Ne pas oublier de créer ce fichier sur le RPi (index caméra = 0)
- [x] **Optimisations perfs** (2026-07-25) — caméra unique partagée entre `screen_capture` et `screen_calibration` (fin des release/reopen) ; backend `CAP_DSHOW` sur Windows avec fallback vérifié
- [ ] **⚠️ EN COURS — Débloquer la détection ChArUco** (2026-07-25) :
  - Symptôme : `detectMarkers` (basic ArUco) trouve bien les marqueurs de la mire externe, mais `CharucoDetector.detectBoard` échoue → aucun coin ChArUco détecté → calibration bloquée
  - Cause probable : la mire externe utilise un ordre d'IDs / une orientation différente de ce qu'OpenCV attend
  - **Étape 1 à faire demain** : cliquer sur "Générer la mire" dans l'écran de calibration → imprimer `assets/charuco_calibration.png` à taille réelle → tester la détection avec CETTE mire. Si ça marche, on sait que le code est bon et le problème vient du format de la mire externe.
  - **Étape 2 (si nécessaire)** : essayer `"charuco_legacy_pattern": false` dans `local_config.json`
  - **Étape 3 (si nécessaire)** : soit adapter les paramètres au format exact de la mire externe, soit se rabattre sur celle générée par l'appli
- [ ] **⚠️ À vérifier demain** — L'aperçu caméra affiche-t-il bien l'image après tous les changements ? Dernière piste testée : validation stricte de `CAP_DSHOW` (5 lectures test avant validation) + retry × 3 dans `capture()` + warmup 10 frames. Si toujours pas d'image, penser à afficher exactement quoi est visible (message d'erreur, écran noir, "Demarrage camera...") et vérifier la console pour un `[MainApp] Camera non disponible`
- [ ] Calibration optique — attendre que la détection ChArUco soit débloquée avant de capturer les 15 poses
- [ ] Tests tactiles : vérifier boutons ≥ 44×44 px
- [ ] **Gestion des cas d'erreur** — reportée à une session ultérieure (décidé le 2026-07-01). Audit déjà fait, à reprendre directement sans re-auditer :
  - Déjà bien géré ✅ : caméra absente/déconnectée (`screen_capture.py`), erreurs Homing/dépose remontées via signaux Qt (`HomingWorker`, `RunWorker`), vision/ArUco insuffisants (`screen_zone.py`)
  - Trou #1 (priorité sécurité) : `app.py::closeEvent` (ligne ~175) ne libère que la caméra — si l'app est fermée pendant une dépose, le thread `RunWorker` continue en arrière-plan et l'opérateur perd l'accès à l'arrêt d'urgence
  - Trou #2 : un seul objet `Machine` partagé sans verrou entre l'écran Homing (`screen_capture.py`) et l'écran Run (`screen_run.py`) (`app.py` lignes 90-91/122/160) — risque d'écriture série concurrente si un thread Homing traîne encore
  - Trou #3 (mineur) : messages d'erreur bruts (ex. `[Errno 2] could not open port /dev/ttyUSB0`) au lieu d'un message clair pour l'opérateur
- [ ] Vérifier que `pytest` passe toujours après les modifications de cette session
- [ ] Ajouter `openpyxl` et `python-pptx` à `requirements.txt` (utilisés par `assets/generate_planning.py` et `assets/generate_presentation.py`)

---

## 9. Plan de développement — avancement

### 📅 Calendrier des échéances 2026 (mis à jour 2026-07-11)

| Échéance | Date | Type |
|---|---|---|
| MàJ rapport entreprise | **17/07** (ven) | Rapport |
| Soutenance blanche #1 (partie en anglais) | **22/07** (mer) | Entreprise |
| Soutenance blanche #2 | **05/08** (mer) | Entreprise |
| **2 machines fonctionnelles (Geeetech + CNC)** | **avant le 12/08** | Contrainte |
| Soutenance blanche #3 | **12/08** (mer) | Entreprise |
| Rapport final | **17/08** (lun) | IUT |
| Soutenance finale (démo Geeetech acceptée) | **31/08** (lun) | IUT |

> Les autres échéances de rapport (entreprise) seront communiquées **après le 17/07** — à insérer ici dès réception.

### 🗓️ Planning détaillé jour par jour (11/07 → 31/08)

**Légende** : 🏠 maison (soir/week-end — logique, GUI, rapport, G-code à vide) · 🏭 boulot (journée — caméra, ArUco, dépose seringue, CNC) · 📄 rapport · 🎤 soutenance

**Semaine 1 — 11→17/07 · Clôture logiciel Geeetech + features de base + MàJ rapport (17/07)**

| Jour | Lieu | Tâche |
|---|---|---|
| Sam 11 | 🏠 | Phase 8 — gestion d'erreur (3 trous : `closeEvent`, verrou `Machine`, messages opérateur) |
| Dim 12 | 🏠📄 | Tests tactiles (≥44 px) + non-régression `pytest` ; démarrer MàJ rapport |
| Lun 13 | 🏭 · 🏠 | 🏭 Finir câblage CNC (fins de course, moteurs, caméra) + 1er power-on ; 🏠 soir réécrire `calibration.py` en ChArUco |
| Mar 14 | 🏠📄 | *Férié* — rédaction rapport ; ajouter le temps de dépose au rapport (`reporter.py`) |
| Mer 15 | 🏭 | Calibration optique ChArUco : capturer 15 poses (Geeetech), valider erreur < 2 mm ; Q8 volume pâte |
| Jeu 16 | 🏭📄 | Validation Phase 8 Geeetech end-to-end ; finaliser MàJ rapport |
| Ven 17 | 📄 | **Remise MàJ rapport entreprise** ✅ |

**Semaine 2 — 18→24/07 · Cordons multiples + Soutenance blanche #1 (22/07) + commissioning CNC**

| Jour | Lieu | Tâche |
|---|---|---|
| Sam 18 | 🏠 | Feature cordons multiples (1/2) : modèle de données + tracé de plusieurs cordons (`screen_zone`) |
| Dim 19 | 🏠🎤 | Cordons multiples (2/2) : `path_planner` + `screen_run` par cordon ; slides soutenance #1 |
| Lun 20 | 🏭🎤 | Répétition démo Geeetech ; commissioning CNC (sens moteurs, Vref, steps/mm `M92`) |
| Mar 21 | 🏠🎤 | Filage anglais + répétition |
| **Mer 22** | 🎤 | **Soutenance blanche #1** (démo Geeetech, partie en anglais) |
| Jeu 23 | 🏭 | Commissioning CNC : homing propre + déplacements sans collision |
| Ven 24 | 🏭 · 🏠 | 🏭 Q8 dépose Geeetech (calibrage volume) ; 🏠 soir fichier prépa JSON (1/2) |

**Semaine 3 — 25→31/07 · Fichier JSON + Portage CNC (Phase 10)**

| Jour | Lieu | Tâche |
|---|---|---|
| Sam 25 | 🏠 | Fichier de préparation JSON (2/2) : sauvegarde + chargeur/éditeur GUI |
| Dim 26 | 🏠📄 | Intégration + tests des nouvelles features ; `pytest` ; rapport |
| Lun 27 | 🏭 | Phase 10 : `config.py` CNC (port, zone, offsets) + tests à vide (homing, XYZ) |
| Mar 28 | 🏭 | Phase 10 : recalibration ArUco sur le plateau CNC |
| Mer 29 | 🏭 | Phase 10 : tests dépose seringue sur CNC |
| Jeu 30 | 🏭 | Tampon Phase 10 |
| Ven 31 | 🏭 | Phase 11 : premier cycle complet CNC sans pâte |

**Semaine 4 — 01→07/08 · Validation CNC (Phase 11) + Soutenance blanche #2 (05/08)**

| Jour | Lieu | Tâche |
|---|---|---|
| Sam 01–Dim 02 | 🏠🎤📄 | Prépa soutenance #2 ; `pytest` régression ; rapport |
| Lun 03 | 🏭 | Phase 11 : cycle complet CNC avec pâte |
| Mar 04 | 🏭🎤 | Réglages + répétition démo #2 |
| **Mer 05** | 🎤 | **Soutenance blanche #2** (Geeetech + CNC en cours) |
| Jeu 06 | 🏭 | Phase 11 : réglages quantité, 3 cycles consécutifs |
| Ven 07 | 🏭 | **Validation CNC finale → les 2 machines fonctionnelles** ✅ |

**Semaine 5 — 08→12/08 · Tampon + Soutenance blanche #3 (12/08, 2 machines)**

| Jour | Lieu | Tâche |
|---|---|---|
| Sam 08–Dim 09 | 🏠🎤📄 | Prépa soutenance #3 ; rapport |
| Lun 10 | 🏭 | Tampon / robustesse / corrections |
| Mar 11 | 🏭🎤 | Répétition démo des 2 machines |
| **Mer 12** | 🎤 | **Soutenance blanche #3** — 2 machines fonctionnelles ✅ |

**Semaine 6 — 13→17/08 · Rapport final IUT (17/08)**

| Jour | Lieu | Tâche |
|---|---|---|
| Jeu 13–Dim 16 | 🏠📄 | Finalisation rapport intensif : résultats CNC, figures, relecture, retours des 3 blanches |
| **Lun 17** | 📄 | **Remise rapport final IUT** ✅ |

**Semaines 7-8 — 18→31/08 · Corrections (Phase 12) + prépa soutenance finale**

| Jour | Lieu | Tâche |
|---|---|---|
| 18→28 | 🏠🏭 | Phase 12 : corrections de bugs (retours blanches) ; prépa démo Geeetech (acceptée IUT) ; slides finaux ; répétitions |
| **Lun 31** | 🎤 | **Soutenance finale IUT** ✅ |

> **Marge** : la CNC étant déjà quasi assemblée, la contrainte « 2 machines avant le 12/08 » vise une CNC fonctionnelle **dès le 07/08** — les 10-12/08 servent de tampon de sécurité.

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

**Sous-total Partie A : 21 sessions × ~2h = ~42h** (+ ~5,5 sessions pour les fonctionnalités actées le 2026-07-11 : ChArUco, cordons multiples, JSON, temps rapport)  
**Jalon A : Logiciel validé sur Geeetech ≈ 17 juillet 2026** (clôture Phase 8 + nouvelles fonctionnalités)

> **En parallèle de toute la Partie A** : rédaction du rapport (~1h/soir en semaine, chez soi)  
> **Jalon intermédiaire : premier draft rapport → 15 juin 2026** (à remettre avant les vacances)

### Partie B — Intégration sur CNC cible · deadline fin juillet 2026

| Phase | Description | Statut | Durée estimée |
|---|---|---|---|
| 9 | Assemblage de la CNC cible (mécanique + câblage) | 🔄 Quasi terminé (méca + carte + Marlin flashé) — reste câblage capteurs/moteurs | ~2-3 jours |
| 10 | Portage logiciel : adaptation `config.py` + tests sur CNC | ⬜ À faire | 0 / 2 sessions |
| 11 | Validation complète du système sur CNC cible | ⬜ À faire | 0 / 3 sessions |

**Jalon B : Système validé sur CNC ≈ 07/08 (avant la 3e soutenance blanche du 12/08)**

### Partie C — Finalisation · deadline fin août 2026

| Phase | Description | Statut | Durée estimée |
|---|---|---|---|
| 12 | Corrections de bugs (retours soutenance blanche) | ⬜ À faire | ~1 semaine |
| 13 | Finalisation et relecture rapport | ⬜ À faire | ~3 semaines |

**Jalon C : Rapport final remis le 17/08 → SOUTENANCE FINALE le 31/08 (démo Geeetech)**

### Rédaction rapport — activité en parallèle (fil conducteur du projet)

| Période | Mode | Charge | Objectif |
|---|---|---|---|
| 27 mai → 14 juin | ~1h/soir en semaine | ~3h/semaine | **Draft complet → 15 juin** (avant vacances) |
| 22 juin → 31 juillet | ~1h/soir + week-ends | ~3–5h/semaine | Rapport à jour après chaque phase validée |
| 1 août → 17 août | Mode intensif | Priorité principale | Finalisation, relecture, figures → **remise IUT le 17/08** |
| 18 août → 31 août | Prépa soutenance | Répétitions + corrections | Slides, démo Geeetech, filage → **soutenance 31/08** |

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
| Correction distorsion objectif | `cv2.calibrateCamera` + `cv2.undistort` — mire **ChArUco** (damier + ArUco) | Barrel distortion ~10 % sans correction. ChArUco choisi (plus robuste aux vues partielles que l'échiquier). Calibration one-shot dans `assets/camera_calibration.npz` |
| Zones de dépôt | **Cordons** (tracés polyline), plusieurs par préparation, une quantité de pâte par cordon | Adapté à la pâte thermique (boudin le long d'un chemin) ; plus simple et fiable qu'un remplissage de surface |
| Fichier de préparation | **JSON** (cordons + quantités + horodatage) dans `preparations/`, rechargeable et éditable | Permet de rejouer une préparation sans retracer si le plateau est inchangé |
| Firmware CNC cible | **Marlin dernière version** (confirmé 2026-07-11) | Même dialecte G-code que la Geeetech → portage transparent (seul `config.py` change) |

**Résolution confirmée :** Philips SPC 1330NC supporte 1280×960 sur RPi 3B+ (confirmé le 2026-06-11). Hauteur caméra : 200 mm. Zone de travail : 151×104 mm (re-mesuré 2026-06-12).

| Repère ArUco ↔ machine | Marqueur 0 = **bas-gauche** de l'image. X+ machine = droite image. Y+ machine = haut image. Offset mesuré : X=20 mm, Y=50 mm (M114, 2026-07-01) | Nécessaire pour convertir coordonnées ArUco → G-code machine |
| Terminal série RPi | `picocom -b 250000 --imap lfcrlf --echo /dev/ttyUSB0` | `screen` non installé ; `minicom` ne supporte pas 250000 baud |
| Configuration par machine | Fichier `local_config.json` à la racine (gitignoré). Modèle : `local_config.json.example` (tracké). Chargé au démarrage par `modules/config.py` — surcharge les défauts | Le PC et le RPi ont des paramètres différents (index caméra, port série) qui ne doivent pas transiter par git |
| Caméra partagée | Une seule instance `Camera` créée dans `MainApp.__init__` et passée aux écrans via `set_camera()`. Les écrans arrêtent/redémarrent leur QTimer mais ne libèrent jamais la caméra | Le release+reopen prenait 1-2 s à chaque changement d'écran ; désormais instantané. Libération unique dans `closeEvent` |
| Backend caméra Windows | `CAP_DSHOW` (DirectShow) avec **validation stricte** (5 lectures test avant validation, sinon fallback `CAP_ANY`) | `isOpened()` peut retourner `True` sans que le backend délivre de frames — d'où la vérification par lecture réelle |
| Détection ChArUco temps-réel | `DetectionThread` (sous-classe `QThread`) avec son propre `CharucoDetector` créé dans `run()`. Le thread principal soumet les frames via `submit()` et reçoit les résultats via signal `result_ready` | `cv2.aruco.CharucoDetector` n'est pas thread-safe si partagé. Le pattern `worker + moveToThread` posait aussi des soucis — ce QThread subclass est plus simple et robuste |
| Mire ChArUco (défauts) | 4×4 cases, 15 mm/case, 12 mm/marqueur, DICT_4X4_50, `setLegacyPattern(True)` | Legacy = compatible calib.io, kalibr et l'app elle-même. Tous ces paramètres surchargeables dans `local_config.json` (`charuco_cols/rows/square_mm/marker_mm/dict/legacy_pattern`) |

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
├── local_config.json        # 🔒 gitignoré — paramètres propres à chaque machine
├── local_config.json.example # ✅ modèle à copier
│
├── modules/
│   ├── config.py            # ✅ Créé — paramètres globaux + chargement local_config.json
│   ├── camera.py            # ✅ Phase 1 — capture image via USB (CAP_DSHOW+fallback sur Win)
│   ├── vision.py            # 🔄 Phase 2 — détection ArUco, homographie
│   ├── calibration.py       # ✅ Phase 2 + ChArUco (2026-07-25) — undistortion + calibration mire
│   ├── machine.py           # ✅ Phase 3 — communication G-code Marlin
│   ├── path_planner.py      # ✅ Phase 5 — calcul des trajectoires (polyline)
│   └── reporter.py          # ✅ Phase 7 — génération PDF
│
├── gui/
│   ├── app.py               # ✅ Phase 4 — fenêtre principale + caméra partagée
│   ├── screen_capture.py    # ✅ Phase 4 — écran 1 : photo + Homing + accès calibration
│   ├── screen_zone.py       # ✅ Phase 4/5 — écran 2 : tracé polyline + ArUco
│   ├── screen_run.py        # ✅ Phase 4/6 — écran 3 : exécution (QThread + offset machine)
│   ├── screen_report.py     # ✅ Phase 4/7 — écran 4 : rapport + export PDF
│   └── screen_calibration.py # ✅ 2026-07-25 — écran 5 : calibration ChArUco (DetectionThread)
│
├── assets/                  # Ressources statiques (synoptique Draw.io, icônes...)
├── preparations/            # Fichiers de préparation JSON (cordons + quantités)
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
| 2026-07-11 | **Révision planning + cadrage fonctionnel** — Nouvelles contraintes calendaires : 3 soutenances blanches entreprise (22/07, 05/08, 12/08, partie en anglais), rapport final IUT le 17/08, soutenance finale IUT le 31/08 (démo Geeetech acceptée), MàJ rapport entreprise le 17/07. CNC déjà quasi assemblée (mécanique + carte + firmware Marlin dernière version flashés ; reste câblage capteurs/moteurs) → Q9 résolue, chemin critique dé-risqué. Cadrage du process de dépose complet et actage de 4 fonctionnalités : calibration **ChArUco**, **cordons multiples** avec quantité par cordon, **fichier de préparation JSON**, **temps de dépose** au rapport. Planning détaillé jour par jour (11/07→31/08) ajouté en section 9. | CLAUDE.md + CONCEPTION.md mis à jour. Planning validé. Aucune ligne de code produite ce jour. |
| 2026-07-25 | **Session 🏠 — Écran calibration ChArUco + refonte config locale + optimisations caméra.** Création complète de `gui/screen_calibration.py` : flux caméra live, détection ChArUco en overlay (marqueurs ArUco + coins), capture guidée de N poses, calcul de calibration en QThread, sauvegarde `assets/camera_calibration.npz`, bouton "Générer la mire". Ajout des fonctions ChArUco dans `modules/calibration.py` (`create_charuco_board`, `generate_charuco_image`, `detect_charuco`, `calibrate_charuco`) — utilise `cv2.aruco.CharucoBoard` avec `setLegacyPattern(True)` pour compatibilité générateurs externes (calib.io, kalibr). Mise en place du système **`local_config.json`** (gitignoré) chargé par `config.py` : `camera_index`, `calibration_min_images`, `charuco_cols/rows/square_mm/marker_mm/dict/legacy_pattern`. Optimisations perfs : (1) **caméra unique partagée** entre `screen_capture` et `screen_calibration` (créée dans `MainApp.__init__`, passée via `set_camera()`) — plus de release+reopen à chaque changement d'écran ; (2) backend **CAP_DSHOW** sur Windows avec validation stricte (5 lectures test, fallback CAP_ANY si échec) ; (3) fenêtre en `showMaximized()` au lieu de `setFixedSize`. Correctifs : (a) `QSizePolicy.Ignored` sur les labels caméra pour éviter la croissance infinie du layout ; (b) `DetectionThread` (sous-classe `QThread`) crée son propre `CharucoDetector` dans `run()` pour éviter les problèmes de thread-safety ; (c) `drawDetectedMarkers/CornersCharuco` enrobés dans try/except (formats variables selon versions OpenCV). | Screen calibration navigable, thread OK. **Non validé** : détection ChArUco d'une mire externe échoue (basic `detectMarkers` OK, `detectBoard` KO) — piste privilégiée : tester avec la mire générée par l'app (bouton "Générer la mire" + impression). **À vérifier demain** aussi : présence de l'aperçu caméra après les changements du backend. |

> L'historique détaillé (par phase) est dans `CONCEPTION.md` section 10.
