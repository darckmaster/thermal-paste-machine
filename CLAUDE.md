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
2. **Mise en place** — Le plateau porte **4 marqueurs ArUco** à ses coins (IDs 0-3), qui servent de référentiel géométrique (repère image ↔ repère machine). Il porte aussi **plusieurs zones de dépose vissées à demeure**, chacune accueillant un exemplaire du **même produit**. Chaque zone est repérée par **2 marqueurs ArUco** posés aux extrémités de sa diagonale haut-gauche → bas-droit, avec la convention `id(bas-droit) = id(haut-gauche) + 1` (IDs ≥ 4). L'opérateur pose un boîtier dans chaque zone.
3. **Création du plateau** — L'opérateur saisit le **nom du produit** (qui sert de nom de fichier et reste affiché en permanence), le logiciel capture une image, identifie les zones et **contrôle la cohérence du montage** : zone à l'envers, tag non apparié, diagonale hors norme, angle excessif, paires en conflit. Les anomalies sont matérialisées sur l'image, et l'opérateur choisit de continuer avec les seules zones saines ou d'abandonner pour rectifier le plateau.
4. **Tracé des cordons** — L'opérateur **clique une zone**, l'IHM zoome dessus, et il y trace un ou plusieurs **cordons** (polylines, clic par clic, double-clic pour clore, undo/redo de profondeur 1). Les cordons sont mémorisés en **mm relatifs à la zone** : ils sont donc **appliqués automatiquement à toutes les autres zones**, qui accueillent le même produit.
5. **Sauvegarde** — Enregistrement automatique dans un fichier temporaire toutes les 5 s (filet anti-plantage, proposé au redémarrage), et enregistrement définitif en **JSON** sur action de l'opérateur.
6. **Lancement de la dépose** — Homing, puis parcours de chaque cordon de chaque zone. La quantité de pâte résulte de deux **paramètres globaux** — vitesse de déplacement et vitesse d'extrusion — réglables dans une fenêtre de paramètres et enregistrés dans le JSON.
7. **Réutilisation** — Les zones étant vissées à demeure, un fichier de plateau existant peut être rechargé et rejoué autant de fois que nécessaire, sans rien retracer.
8. **Rapport** — À la fin de chaque dépose, un **rapport PDF** est généré automatiquement : photo, statut, **temps de dépose**, **quantité totale déposée**, détail par cordon.

---

## 2. Mode de collaboration (IMPORTANT — à respecter à chaque session)

- **Ne pas coder sans expliquer à l'étudiant.** Claude guide, explique, propose un code documenté ; l'étudiant approuve le code, le modifie si nécessaire, teste et valide. C'est en faisant et comprenant qu'on apprend.
- **Travailler phase par phase.** Ne pas anticiper les phases suivantes ni créer du code pour des phases non encore démarrées.
- **Expliquer chaque choix.** Pour toute solution proposée, expliquer le *pourquoi*, pas seulement le *comment*.
- **Enrichir `CONCEPTION.md`** à chaque décision technique, découverte ou résultat de test — ce document nourrit le rapport de stage.
- **Mettre à jour ce fichier** (`CLAUDE.md`) à chaque fin de session : questions ouvertes, décisions prises, agenda de la prochaine session. Le rituel formel de fin de session (tests, manuels, doc, branche/push/merge) est détaillé en **section 15** — déclenché uniquement sur demande explicite de l'étudiant.

---

## 3. Démarrer une session — checklist

À faire **au début de chaque session**, dans cet ordre :

```
1. git pull origin master           ← synchroniser avant tout
2. Lire la section "Prochaine session" de ce fichier
3. Vérifier le tableau d'avancement (section 9)
4. Ouvrir CONCEPTION.md pour le contexte technique détaillé
5. RAPPELER LES ACTIONS EN ATTENTE (section 7 bis) — obligatoire
6. Commencer par un bref résumé oral de là où on en est
```

> **L'étape 5 n'est pas facultative.** Ces actions se perdent parce qu'elles sont petites,
> pas parce qu'elles sont secondaires : plusieurs d'entre elles décalent physiquement la
> dépose tant qu'elles ne sont pas faites. Voir section 7 bis pour la règle complète.

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
| Référentiel plateau | 4 marqueurs **ArUco** DICT_4X4_50 — IDs 0, 1, 2, 3 aux coins. Disposition relevée le 2026-08-01 : `3`=haut-gauche (origine du repère mm), `0`=haut-droit, `1`=bas-droit, `2`=bas-gauche | ✅ Arrêté |
| Référentiel zone de dépose | 2 marqueurs **ArUco** DICT_4X4_50 — IDs 4 et 5, aux coins opposés (diagonale) de la zone où est posée la pièce | ✅ Arrêté |

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

## 7 bis. Actions en attente — à rappeler à CHAQUE début de session

> **Règle, demandée par l'étudiant le 2026-08-01.** Claude doit :
> 1. **énoncer ce tableau au début de chaque session** (étape 5 de la checklist section 3) ;
> 2. **signaler spontanément une ligne dès que le travail en cours la touche** — par exemple,
>    ne pas laisser écrire une conversion vers le repère machine sans rappeler que `M2` et
>    `M4` ne sont pas faites, donc que le résultat ne sera pas vérifiable sur la machine.
>
> Ces actions se perdent parce qu'elles sont **petites**, pas parce qu'elles sont
> secondaires : `M1`, `M2` et `M4` décalent physiquement la dépose tant qu'elles ne sont pas
> faites, et aucun test automatique ne peut les détecter — elles vivent hors du code.
>
> **Quand une action est faite** : la barrer ici avec sa date et sa valeur mesurée, et
> reporter le résultat dans `CONCEPTION.md`. Ne pas supprimer la ligne — la valeur mesurée
> et sa date font partie de l'historique du projet.

### 🏭 À faire sur la machine (au boulot, matériel sous la main)

| # | Action | Pourquoi ça compte / ce que ça bloque |
|---|---|---|
| **M1** | **Mesurer le plateau au mètre** : bord extérieur à bord extérieur des 4 tags (supposé 220×220 mm → 192 mm centre-à-centre) | Devient le paramètre `plateau_size_mm` (lot C2bis). En repli 2 tags — **le mode nominal sur la Geeetech** — l'origine est *extrapolée* à partir de cette valeur : toute erreur dessus décale toute la dépose |
| **M2** | **`M114` buse au-dessus du marqueur 2** (bas-gauche) → origine machine | Les valeurs actuelles (20/50) datent de deux conventions en arrière. **Tant que ce n'est pas refait, la dépose réelle est décalée** |
| **M3** | **Hauteur Z de la pointe de seringue après homing** | Le paramètre de position après homing devient **3D** `(x, y, z)` au lot D. M2 ne donne que X et Y |
| **M4** | **Sens des axes machine vs axes plateau** (X, Y, Z) — à établir **en interactif**, machine sous tension | Décidé le 2026-08-01 : on ne le déduit pas sur le papier. Bloque la validation réelle du lot D |
| **M5** | **Calibration ChArUco sur le RPi et la caméra Philips réels** (15 poses) | Le pipeline n'a été validé que sur le PC de dev. Cause connue de l'**écart résiduel de ~10 %** (distorsion de l'objectif) |
| **M6** | **Q8 — volume de pâte de référence** (par mm de cordon) | Calibrage expérimental. Alimente la quantité déposée et le volume estimé du rapport PDF |
| **M7** | **Créer `local_config.json` sur le RPi** (`camera_index: 0`, `serial_port: "/dev/ttyUSB0"`) | Fichier gitignoré, donc absent d'un dépôt fraîchement cloné : l'appli démarre sur la mauvaise caméra sans lui |
| **M8** | **Tests tactiles** : vérifier que tous les boutons font ≥ 44×44 px sur l'écran 7" réel | Ne se teste pas au clic de souris sur le PC de dev |
| **M9** | **CNC** : finir le câblage capteurs/moteurs, 1er power-on, puis commissioning (sens moteurs, Vref, `M92` steps/mm) | **Bloque les phases 10 et 11**, donc la contrainte « 2 machines fonctionnelles avant le 12/08 » |

### 🏠 Dettes logicielles ouvertes (chez soi, sans matériel)

| # | Action | Pourquoi ça compte |
|---|---|---|
| **L1** | **Collision d'IDs ArUco plateau ↔ mire ChArUco** : même `DICT_4X4_50` sans plage d'IDs séparée | Contournement actuel : masquer le plateau avec du papier pendant la calibration. Correction propre : plage d'IDs réservée ou dictionnaire distinct pour la mire. Détail en `MANUEL_MAINTENANCE.md` § 4.4b |
| **L2** | **3 trous de gestion d'erreur** — audit déjà fait, à reprendre sans re-auditer (détail en section 8) : `app.py::closeEvent`, absence de verrou sur l'objet `Machine` partagé, messages d'erreur bruts | Le trou #1 est un point de **sécurité** : fermer l'appli pendant une dépose laisse le `RunWorker` tourner et retire à l'opérateur l'accès à l'arrêt d'urgence |
| **L3** | **Afficher la résolution réelle de la caméra** sur l'écran 1, à côté de son nom | Rendrait visible un écart entre la configuration et le matériel réellement utilisé — c'est précisément ce défaut qui a coûté deux sessions de diagnostic ChArUco |
| **L4** | **Persistance du choix matériel** (optionnel) : écrire la sélection des listes déroulantes dans `local_config.json` | Les clés `serial_port` / `camera_index` existent déjà, il ne manque que l'écriture |

---

## 8. Prochaine session — agenda

---

### 🚩 POINT DE REPRISE — session de cadrage close le 2026-08-01 au soir (`v0.4.2`)

> **▶️ POUR DÉMARRER LA PROCHAINE SESSION, IL SUFFIT DE DIRE : « on lance le lot C2bis ».**
> Tout est cadré ci-dessous, toutes les questions ont été tranchées, il n'y a **rien à
> redemander à l'étudiant** avant d'écrire du code — sauf l'unique question de vocabulaire
> signalée plus bas, qui a déjà une réponse retenue (on garde haut-gauche/bas-droit).
> Ne pas refaire l'évaluation d'impact : elle est faite et détaillée en 5 étapes.
>
> Ordre de démarrage : checklist section 3 → **rappeler la section 7 bis** (actions en
> attente) → attaquer l'étape 1 du lot C2bis.

**État du dépôt** : branche `v0.4.2` créée et mergée dans `master`, working tree propre, tout
est poussé sur GitHub. La branche `v0.4.2` **reste ouverte** : le code du lot C2bis s'écrit
dessus, le cadrage n'en est que le premier commit.
**Tests** : 155/155 (`pytest`, 46 s). Ajouter `-m "not toutes_cameras"` pour éviter d'ouvrir
la webcam intégrée du PC (~41 s).

**Ce qui a été fait le 2026-08-01 au soir** — session de cadrage, **aucune ligne de code** :
décision du changement de repère, évaluation de son impact sur le code réel, spécification du
lot C2bis, trois décisions annexes (tag 0, fichiers v1, `BOITIER_X`), et création du registre
des actions en attente (section 7 bis).

**Ce qui a été fait le 2026-08-01 dans la journée** — six releases :

| Version | Contenu |
|---|---|
| `v0.1.1` | Repère du plateau refait (origine = marqueur 3, Y vers le bas) + choix du matériel dans l'IHM |
| `v0.2.0` | **Lot A** — géométrie des zones de dépose (`detect_deposit_zones_mm`) |
| `v0.3.0` | **Lot B** — modèle `Preparation` + persistance JSON |
| `v0.3.1` | Sélection de la caméra de test par détection ArUco |
| `v0.4.0` | **Lot C1** — écran « Créer un plateau » : capture, détection, diagnostic |
| `v0.4.1` | **Lot C2** — écran « Cordons » : zoom, tracé, report sur toutes les zones |

**➡️ PROCHAINE ÉTAPE : lot C2bis (`v0.4.2`) — repère plateau orthonormé.** Le lot C3 est
décalé en `v0.4.3` : la convention de repère change, et tout ce qui serait écrit avant
serait à réécrire après.

---

#### Lot C2bis — changement de convention du repère du plateau

**Décidé le 2026-08-01 (soir).** Le repère du plateau devient **orthonormé et défini par
trois tags** :

```
  3 ─────── 0            Y
  │         │            ↑
  2 ─────── 1            └──→ X   (origine sur le tag 2)
```

- origine = centre du tag **2** (bas-gauche)
- axe des **ordonnées** = vers le centre du tag **3** (haut-gauche) → **Y vers le HAUT**
- axe des **abscisses** = vers le centre du tag **1** (bas-droit)
- le tag **0** devient redondant → **décidé : on s'en sert comme contrôle de cohérence.**
  Sa position vue est comparée à sa position attendue ; l'écart est un indicateur de qualité
  (calibration optique, plateau déformé, tag décollé ou mal collé) à remonter à l'opérateur

C'est l'**inverse** de la convention posée en `v0.1.1` le matin même (origine tag 3, Y vers
le bas). Le motif du changement : aligner le repère logiciel sur le repère physique dans
lequel on raisonne devant la machine, avant d'écrire la construction des commandes machine
(lot D). Mieux vaut payer ce retournement maintenant, sur 155 tests verts, que plus tard
avec le G-code par-dessus.

**⚠️ Ce n'est PAS un changement de 4 lignes.** Le repère actuel a été choisi *parce que* Y
vers le bas est le sens des lignes d'une image. Détail de l'impact, dans l'ordre où il faut
le traiter :

> **🔍 Le point le plus subtil du lot — le miroir vertical.** Règle posée par l'étudiant :
> *la convention sert à faciliter les calculs, elle ne doit RIEN changer pour l'opérateur —
> ce qu'il voit à l'écran est ce qui se passe sur le plateau.* Le retournement Y décrit à
> l'étape 1 est justement **ce qui garantit cette règle**, pas une entorse.
>
> Pourquoi : une image a son origine en haut à gauche et son Y qui **descend** (ligne 0 =
> ligne du haut), et aucune convention de notre côté ne change ça. Aujourd'hui le Y en mm
> descend lui aussi, donc `y = 0 mm` tombe sur la ligne 0 et le haut du plateau s'affiche en
> haut — ça marche par coïncidence. Avec le nouveau repère, `y = 0 mm` est le **bas** du
> plateau : sans rien d'autre, ce bas atterrirait sur la ligne 0, donc **en haut de
> l'écran**, et l'opérateur verrait le plateau à l'envers. D'où la ligne à écrire dans les
> trois `warp_*` : `y_pixel = (hauteur_mm − y_mm) × échelle`.
>
> Ce miroir a déjà existé dans ce projet, **de la Phase 2 jusqu'au 2026-08-01**, sans que
> personne ne le voie à l'œil : il a été démasqué par le calcul. Un plateau à peu près
> symétrique ne trahit pas son propre retournement — d'où le test de non-miroir.

**Étape 1 — `modules/vision.py`, le repère lui-même**
- `_plateau_corner_positions_mm()` : `2=(0,0)`, `1=(W,0)`, `0=(W,H)`, `3=(0,H)`.
  `compute_homography()` et `compute_homography_approx()` suivent sans modification, elles
  lisent cette table — seuls leurs docstrings sont à réécrire.
- **Les trois `warp_*` doivent retourner Y explicitement.** `warp_image`, `warp_region` et
  `warp_zone` composent mm → pixels avec une échelle positive : en repère Y montant, elles
  produisent une image tête-en-bas. C'est le point le plus facile à rater.
  `test_warp_image_orientation_non_miroir` est le garde-fou — ne pas l'affaiblir.

**Étape 2 — `modules/vision.py`, la géométrie des zones (toute la logique de signe)**
- filtre des paires plausibles : `d[0] > 0 and d[1] > 0` → `d[0] > 0 and d[1] < 0`
- `_rectangle_from_diagonal()` : `atan2(hauteur, largeur)` → `atan2(-hauteur, largeur)`, et
  le vecteur `v` (le côté « hauteur ») tourne d'un quart de tour dans l'autre sens
- étape 5 de `detect_deposit_zones_mm()` : la médiane des composantes sort un `dy` négatif
  → fixer la convention de signe de `product_size_mm` et s'y tenir
- **le signe de `rotation_deg` change de sens** (positif = sens trigonométrique désormais) →
  se propage à `to_plateau_mm`, `to_zone_mm` et `warp_zone`
- `ANOMALIE_INVERSEE` repose entièrement sur ces signes : la vérifier en premier

**Étape 3 — repère de zone et fichiers JSON**
- Le repère relatif à la zone bascule lui aussi en Y montant, origine sur le coin
  **bas-gauche** de la zone. Garder deux conventions opposées réintroduirait exactement la
  confusion que ce lot supprime.
- Conséquence : **les cordons déjà enregistrés changent de sens** → `FORMAT_VERSION` passe
  à **2** dans `modules/preparation.py`. Aujourd'hui le chargeur ne refuse que les fichiers
  *plus récents* que le logiciel : un fichier v1 serait relu **silencieusement à l'envers**.
- **Décidé : conversion des fichiers v1 au chargement**, pas de refus. Un fichier v1 est
  relu, ses coordonnées Y retournées (`y_v2 = hauteur_zone − y_v1`), et il est réenregistré
  en v2. Deux précautions : la conversion a besoin de la **hauteur de la zone**, qui est dans
  le fichier (`size_mm`) — donc convertir *après* avoir relu les zones, pas au fil de la
  lecture ; et tracer la conversion pour l'opérateur, un cordon qui bouge tout seul sans
  explication est plus inquiétant qu'un message.

**Étape 4 — IHM (peu de points d'appel, c'est la bonne nouvelle)**
- `screen_cordons.py` : clic → mm de zone devient `(px / échelle, (h_px - py) / échelle)`
- `screen_run.py:164` : la conversion vers le repère machine. **Ne pas deviner le signe** —
  il sera déterminé en interactif sur la machine au lot D. Laisser la formule cohérente avec
  la nouvelle convention et le commentaire qui dit qu'elle reste à valider.
- `screen_zone.py` : le clipping `0..WORK_AREA` reste valide, l'origine restant sur un coin.
  L'argument « toutes les coordonnées du plateau restent positives » qui avait motivé Y-bas
  est **préservé** par le choix du coin bas-gauche.

**Étape 5 — deux ajouts décidés en même temps**
- **Taille du plateau en paramètre** (surchargeable dans `local_config.json`, aujourd'hui
  constante `WORK_AREA_*` calculée en dur `220 - 28`). Elle sert de **valeur de repli quand
  les 4 tags ne sont pas détectés** — c'est-à-dire dans le mode nominal de la Geeetech, où
  seuls 2 tags sont cadrés et où l'origine doit donc être extrapolée.
- **Avertir l'opérateur quand l'origine est extrapolée** (barre d'état). Le choix
  « 4 tags → `compute_homography`, sinon → `compute_homography_approx` » est aujourd'hui
  **dupliqué** dans `screen_plateau.py:287` et `screen_zone.py:251`. Le regrouper dans une
  seule méthode de `VisionProcessor` qui retourne la matrice **et** de quoi renseigner la
  barre d'état (mode exact/approché, IDs utilisés, origine extrapolée oui/non).

**Chiffrage : 2 sessions.** Session 1 = étapes 1 et 2 + tests de `test_vision.py`.
Session 2 = étapes 3 à 5 + `test_screen_cordons`, `test_screen_plateau`,
`test_preparation` + `CONCEPTION.md`, `MANUEL_MAINTENANCE.md` (sections 1 et 6.1),
`MANUEL_UTILISATEUR.md`. Une release à la fin, pas une par session.

**Tests et documentation = la moitié du travail, pas une finition.** ~25 tests de
`test_vision.py` portent des valeurs attendues qui dépendent du sens de Y. Et `vision.py`
est un fichier dont la moitié des docstrings **explique pourquoi Y descend** : les laisser
en l'état donnerait du commentaire menteur, ce qui est pire que du code faux.

**Reste à trancher en début de session** — une seule question :
- Vocabulaire : les zones sont nommées « haut-gauche / bas-droit ». L'image affichée reste à
  l'endroit, donc ces noms continuent de décrire ce que voit l'opérateur — proposition :
  **on les garde**, et on précise dans les docstrings qu'ils désignent le rendu à l'écran,
  pas le signe des coordonnées.

*(Les deux autres questions ont été tranchées le 2026-08-01 : tag 0 = contrôle de cohérence,
fichiers v1 = conversion au chargement. Voir ci-dessus.)*

**Garde-fou proposé** : un test « boussole » qui épingle la convention en un seul endroit —
tag 2 → `(0, 0)`, tag 3 → `(0, H)`, image redressée non miroir, diagonale d'une zone saine à
`dy < 0`. Si la convention rebouge un jour, c'est ce test qui doit hurler en premier.

---

**➡️ ENSUITE : lot C3 (`v0.4.3`)** — persistance et paramètres. Tout le modèle est déjà
écrit et testé (lot B), il s'agit essentiellement de câblage :

1. Autosave toutes les 5 s via un `QTimer` → `preparation.save_autosave()`, **en excluant
   la polyline en cours** (`ScreenCordons.cordons` ne retourne déjà que les cordons
   terminés — brancher sur le signal `cordons_modified`)
2. Bouton d'enregistrement → `preparation.save_preparation()` (supprime l'autosave)
3. Au démarrage : `preparation.list_autosaves()` → proposer de reprendre un travail
   interrompu
4. Fenêtre de paramètres : 2 vitesses + 2 seuils, tous déjà dans `preparation.Settings`

**✅ Saisie du nom de produit — tranchée le 2026-08-01** : trois voies dans le même écran,
puisque le clavier physique n'existe pas sur le RPi.
- saisie libre (clavier virtuel), **ou**
- choix dans la liste des produits déjà enregistrés (`preparation.list_preparations()`),
  ce qui évite aussi les fautes de frappe sur une référence, **ou**
- champ laissé vide à la validation → repli automatique **`BOITIER_X`**, où X est le
  **premier numéro libre** parmi les préparations existantes (décidé le 2026-08-01). Motif :
  aucun état à conserver ailleurs que dans le dossier des préparations lui-même, donc le
  mécanisme fonctionne **tel quel sur un dépôt fraîchement cloné**, sans compteur à
  initialiser ni fichier de séquence à sauvegarder.

**Convention de numérotation** : lot C en `v0.4.x` — C1 = `.0`, C2 = `.1`, **C2bis = `.2`**,
**C3 = `.3`**.

**Reste ouvert côté machine** → **voir la section 7 bis**, qui recense désormais TOUTES les
actions en attente (`M1` à `M9` côté machine, `L1` à `L4` côté logiciel) et doit être
rappelée au début de chaque session. Ne pas les redupliquer ici : deux listes finissent
toujours par diverger, et c'est celle qu'on ne relit pas qui reste à jour.

Les plus directement liées aux lots C2bis / D : **M1** (mesure du plateau, qui devient la
valeur de repli quand l'origine est extrapolée), **M2** et **M3** (position de la seringue
après homing, désormais en 3D et sur le marqueur **2**), **M4** (sens des axes, à établir en
interactif machine sous tension).

**Contexte acté pour le lot D (à préparer plus tard, pas dans C2bis)** :
- Geeetech (PoC) : caméra **fixe sur le bâti** — elle ne constate que les déplacements en Y,
  éventuellement en Z par la taille apparente des tags.
- CNC : caméra **solidaire de la seringue** — elle constate les déplacements sur tous les
  axes, mais son champ se déplace pendant le travail.
- Après homing, la pointe de seringue est en `(x, y, z)` dans le repère plateau, valeurs
  **configurables en paramètres globaux**.

---

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
- [x] **Détection ChArUco débloquée** (2026-07-29, session v0.1) — deux causes distinctes trouvées et corrigées :
  1. `camera_index` dans `local_config.json` pointait sur la webcam intégrée du PC (pas l'USB) — corrigé (voir aussi section 10)
  2. `charuco_legacy_pattern: true` incompatible avec les mires générées par l'appli (`board.generateImage()` ignore ce réglage et produit toujours le format "nouveau", alors que `detectBoard()` le respecte côté détection) — corrigé à `false`. Détail complet en `MANUEL_MAINTENANCE.md` section 4.2
  - **Overlay de debug ajouté** : `screen_capture.py` (écran 1) et `screen_calibration.py` affichent maintenant les marqueurs ArUco/ChArUco détectés en surimpression en direct — c'est cet overlay qui a permis d'isoler les deux causes ci-dessus
- [x] **Bug OpenCV 5.0 corrigé** (2026-07-29) — `cv2.aruco.calibrateCameraCharuco()` n'existe plus en OpenCV 5.0 ; remplacé par `board.matchImagePoints()` + `cv2.calibrateCamera()` dans `modules/calibration.py::calibrate_charuco`. Détail en `MANUEL_MAINTENANCE.md` section 4.3
- [x] **Distance caméra↔mire** (2026-07-29) — `modules/calibration.py::estimate_board_pose()` + `distance_to_board_normal_mm()` (solvePnP + distance perpendiculaire au plan de la mire), affichée en direct dans l'écran calibration
- [ ] **⚠️ NOUVEAU — Collision d'IDs ArUco plateau/mire, non corrigée** (2026-07-29) : le plateau et la mire ChArUco partagent le même dictionnaire `DICT_4X4_50` sans plage d'IDs séparée → confusion du détecteur quand les deux sont visibles ensemble (cas normal en calibration). Contournement actuel : masquer le plateau avec du papier pendant la calibration. Détail en `MANUEL_MAINTENANCE.md` section 4.4b
- [x] **IDs réels des marqueurs du plateau** — ✅ **résolu le 2026-08-01** : fausse alerte. Le plateau utilise bien `{0,1,2,3}` ; les `{0,3,4,5}` observés = 2 marqueurs de plateau cadrés (3 et 0, ceux du haut) + les 2 marqueurs de zone de dépose (4 et 5). Enseignement : le **repli à 2 marqueurs est le mode nominal** sur la Geeetech. Détail en `MANUEL_MAINTENANCE.md` section 4.5
- [x] **Repère du plateau refait** (2026-08-01) — origine sur le marqueur 3 (haut-gauche), Y vers le bas. Corrige au passage un miroir vertical de `warp_image()`/`warp_region()` présent depuis la Phase 2. Inversion vers l'axe Y machine concentrée dans `screen_run.py`
- [x] **Choix du matériel dans l'interface** (2026-08-01) — 2 listes déroulantes (port machine + caméra) + bouton Rafraichir sur l'écran 1. `serial_port` et `serial_baudrate` rendus surchargeables via `local_config.json`
- [ ] **⚠️ `MACHINE_ORIGIN_X/Y` à remesurer** (2026-08-01) : les valeurs actuelles (20/50) correspondent à l'ancienne position du marqueur 0. `M114` à refaire buse au-dessus du **marqueur 3**. Tant que ce n'est pas fait, la dépose réelle sera décalée
- [x] **Étape 2 — LOT A livré (v0.2.0, 2026-08-01)** : géométrie des zones de dépose dans `vision.py` (`detect_deposit_zones_mm`, `PlateauLayout`, `DepositZone`). Détail des règles en `MANUEL_MAINTENANCE.md` section 1 et `CONCEPTION.md` section 4.2 bis
- [x] **Étape 2 — LOT B livré (v0.3.0, 2026-08-01)** : `modules/preparation.py` (`Cordon`, `Settings`, `Preparation` + persistance) et transfert de repère `to_plateau_mm`/`to_zone_mm` sur `DepositZone`. Format documenté en `CONCEPTION.md` section 6 et `MANUEL_MAINTENANCE.md` section 6.1. Les deux seuils de zone ont été mis dans `Settings` (donc enregistrés par plateau) — question du rituel v0.2.0 tranchée dans ce sens
- [x] **Étape 2 — LOT C1 livré (v0.4.0, 2026-08-01)** : `gui/screen_plateau.py` — écran « Créer un plateau », saisie du produit, capture, détection des zones, restitution visuelle du diagnostic, choix continuer/abandonner. 13 tests `pytest-qt`. Navigation : bouton sur l'écran 1, cohabitation avec le cycle historique (option **a**, la bascule en point d'entrée principal se fera au lot D)
- [x] **Étape 2 — LOT C2 livré (v0.4.1, 2026-08-01)** : `VisionProcessor.warp_zone()` (redresse une zone **tournée**) + `gui/screen_cordons.py` — vue d'ensemble cliquable, zoom, tracé des polylines, undo/redo de profondeur 1, sélection/suppression, report sur toutes les zones. 25 tests. Validé à la main sur machine réelle par l'étudiant
- [ ] **Étape 2 — LOT C3** : autosave 5 s (hors polyline en cours), bouton d'enregistrement, reprise au démarrage si un autosave existe, fenêtre de paramètres (2 vitesses + 2 seuils)
- [ ] **LOT D** : exécution multi-zones (adapter `path_planner` et `screen_run` pour parcourir zones × cordons avec les 2 vitesses), puis bascule de la création de plateau en point d'entrée principal et retrait de `screen_zone.py`
- [ ] **⚠️ Saisie du nom de produit sur écran tactile** : passe par une boîte de dialogue clavier. **Sans clavier physique sur le RPi, inutilisable.** À trancher avant le lot C3 — clavier virtuel système, ou sélection dans une liste de produits existants
- [ ] **Afficher la résolution réelle de la caméra** sur l'écran 1, à côté de son nom — rendrait visible un écart entre configuration et matériel réellement utilisé (idée née du défaut de fixture corrigé en v0.2.0)
- [ ] **Persistance du choix matériel** (optionnel) : faire écrire la sélection des listes déroulantes dans `local_config.json`, maintenant que les clés `serial_port`/`camera_index` existent
- [x] **Manuels créés** (2026-07-29) — `MANUEL_UTILISATEUR.md` et `MANUEL_MAINTENANCE.md` à la racine, mis à jour à chaque rituel de fin de session (section 15)
- [ ] Calibration optique — capturer les 15 poses en conditions réelles machine (fait sur PC de dev cette session pour valider le pipeline, à refaire sur le Raspberry Pi/Philips SPC1330NC réel)
- [ ] Tests tactiles : vérifier boutons ≥ 44×44 px
- [ ] **Gestion des cas d'erreur** — reportée à une session ultérieure (décidé le 2026-07-01). Audit déjà fait, à reprendre directement sans re-auditer :
  - Déjà bien géré ✅ : caméra absente/déconnectée (`screen_capture.py`), erreurs Homing/dépose remontées via signaux Qt (`HomingWorker`, `RunWorker`), vision/ArUco insuffisants (`screen_zone.py`)
  - Trou #1 (priorité sécurité) : `app.py::closeEvent` (ligne ~175) ne libère que la caméra — si l'app est fermée pendant une dépose, le thread `RunWorker` continue en arrière-plan et l'opérateur perd l'accès à l'arrêt d'urgence
  - Trou #2 : un seul objet `Machine` partagé sans verrou entre l'écran Homing (`screen_capture.py`) et l'écran Run (`screen_run.py`) (`app.py` lignes 90-91/122/160) — risque d'écriture série concurrente si un thread Homing traîne encore
  - Trou #3 (mineur) : messages d'erreur bruts (ex. `[Errno 2] could not open port /dev/ttyUSB0`) au lieu d'un message clair pour l'opérateur
- [ ] Vérifier que `pytest` passe toujours après les modifications de cette session
- [x] ~~Ajouter `openpyxl` et `python-pptx` à `requirements.txt`~~ — fait le 2026-08-01 avec le lot C1 (`pytest-qt` ajouté au passage)

> 📌 Les actions en attente qui vivaient dispersées dans cette section (mesures machine,
> calibration réelle, dettes logicielles) sont désormais recensées **en section 7 bis** et
> rappelées au début de chaque session.

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
| 8 | Tests, robustesse, finitions (Geeetech) | 🔄 En cours | 5 / 3 (dépassement — ChArUco + zones de dépose + repère plateau, refait deux fois le 2026-08-01) |

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
| Repère du plateau (2026-08-01) | Origine = marqueur **3** (haut-gauche), X+ à droite, **Y+ vers le bas**. Table dans `vision.py::_plateau_corner_positions_mm()` | Coordonnées positives partout (le clipping de `screen_zone` en dépend) + corrige le miroir vertical de `warp_image()`/`warp_region()`. Contrepartie : Y opposé à l'axe machine, inversé en **un seul point** (`screen_run.py`) |
| Choix du matériel (2026-08-01) | 2 listes déroulantes sur l'écran 1. Les écrans émettent `camera_selected`/`machine_port_selected` ; **seul `MainApp` applique** le changement | `MainApp` est propriétaire de `Camera` et `Machine` partagées. Si un écran les remplaçait lui-même, deux endroits ouvriraient la caméra et un handle finirait non libéré |
| Scan des caméras | `Camera.list_devices(exclude=...)` ne sonde **jamais** un index déjà ouvert | Un second handle DirectShow sur le même périphérique casse le flux du premier à son `release()` — symptôme trompeur « Camera deconnectee » (2026-08-01) |
| Zones de dépose (2026-08-01) | 2 marqueurs par zone, `id(bas-droit) = id(haut-gauche) + 1`, IDs ≥ 4. Ambiguïté d'appariement levée par la **longueur de diagonale la plus représentée**, les zones portant toutes le même produit | Aucun moyen local de savoir si le tag 5 clôt `(4,5)` ou ouvre `(5,6)`. L'invariante « même produit partout » est la seule information globale disponible |
| Tri par signe des diagonales | Composantes `(+,+)` = zone plausible · `(−,−)` = zone inversée signalée · **signes mixtes = paire fantôme écartée** | Sur un plateau en grille, la paire fantôme entre deux zones voisines a la **même longueur** que les vraies (symétrie) : le filtrage par longueur seul laissait un plateau sain devenir inexploitable par conflit |
| Rotation d'une zone | `θ = angle(diagonale) − angle(w, h)`, **solution unique**. Pas de choix entre solutions symétriques | Le format `(w, h)` étant déduit de la médiane sur toutes les zones, il est *orienté* : l'ambiguïté n'existe plus. Retenir « la plus petite rotation » ferait ressortir une zone à 25° comme étant à 2°, rendant l'anomalie de montage indétectable |
| Appartenance des cordons | Les cordons appartiennent à la **préparation**, pas à une zone. `reference_zone_id` mémorise celle sur laquelle ils ont été tracés | Toutes les zones portent le même produit : les dupliquer par zone créerait autant de copies à maintenir cohérentes pour zéro information supplémentaire |
| Zone de référence figée | La **première** zone ouverte devient le repère de travail. En ouvrir une autre y affiche les mêmes cordons sans changer de repère | Les cordons sont exprimés dans ce repère : en changer les déplacerait |
| Règle d'interaction du tracé | Tracé en cours → tout clic ajoute un point · hors tracé → clic près d'un cordon = sélection, ailleurs = nouveau tracé | Permet de tout faire au clic sans bouton de mode. Sans la priorité au tracé en cours, un point posé près d'un cordon existant le sélectionnerait au lieu de continuer |
| Double-clic indépendant de Qt | Le double-clic pose le point **seulement s'il n'est pas déjà le dernier** | En usage réel un `press` précède le double-clic et a posé le point ; `QTest.mouseDClick` n'envoie que le double-clic. Le garde-fou rend le résultat identique dans les deux cas et insensible aux versions de Qt |
| Coordonnées des cordons | **mm relatifs à la zone** (origine au coin haut-gauche), jamais en pixels ni en mm plateau | Rend le même cordon applicable à toutes les zones, et insensible à un déplacement de la caméra |
| Quantité de pâte | Deux **paramètres globaux** — vitesse de déplacement et vitesse d'extrusion — et non un attribut par cordon | C'est le rapport des deux qui fixe l'épaisseur du boudin ; un réglage par cordon serait une complexité sans usage identifié |
| Persistance | 2 fichiers : `<produit>.json` (validé) et `<produit>.autosave.json` (toutes les 5 s). L'enregistrement définitif supprime l'autosave. Écriture **atomique** | Un autosave présent au démarrage signale un travail interrompu, et rien d'autre. Une écriture non atomique coupée en cours laisserait un fichier tronqué — un filet anti-plantage qui ne protège de rien |
| Compatibilité des fichiers | `format_version` : version future **refusée**, clé manquante = valeur par défaut | Sur des coordonnées de dépose, une lecture silencieusement fausse enverrait la buse au mauvais endroit. Mieux vaut refuser franchement |
| Format du produit | Médiane des composantes de diagonale des zones saines — **aucune saisie opérateur** | Une zone bien montée a pour diagonale `(w, h)` ; la médiane absorbe les zones isolées de travers |
| Caméra des tests | Choisie par **vérification**, pas par configuration : la fixture `plateau_capture` retient celle où des **marqueurs ArUco sont détectés**. Essai de la caméra configurée d'abord, repli sur les autres ensuite. Une seule capture par session | Un index configuré ne prouve rien : s'il est faux, les tests valident le mauvais matériel en silence. Le projet s'est fait piéger deux fois (ChArUco le 2026-07-29, fixture en dur le 2026-08-01). La webcam intégrée ne voit jamais le plateau, donc jamais de marqueur |
| Marqueur `toutes_cameras` | Le seul test qui ouvre toutes les caméras est marqué, et exclu par `pytest -m "not toutes_cameras"` | Il vérifie que la liste déroulante ne propose pas de caméras fantômes : il doit donc toutes les ouvrir. Le marqueur évite d'allumer la webcam du PC quand ce n'est pas nécessaire |
| Paramètres série | `serial_port` et `serial_baudrate` surchargeables dans `local_config.json` | Le port diffère par OS (`/dev/ttyUSB0` vs `COM3`) et le baudrate par carte (250000 Geeetech). Prépare le portage CNC sans toucher au code |
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
│   ├── preparation.py       # ✅ Lot B (2026-08-01) — modèle plateau/zones/cordons + JSON
│   └── reporter.py          # ✅ Phase 7 — génération PDF
│
├── gui/
│   ├── app.py               # ✅ Phase 4 — fenêtre principale + caméra partagée
│   ├── screen_capture.py    # ✅ Phase 4 — écran 1 : photo + Homing + accès calibration
│   ├── screen_zone.py       # ✅ Phase 4/5 — écran 2 : tracé polyline + ArUco
│   ├── screen_run.py        # ✅ Phase 4/6 — écran 3 : exécution (QThread + offset machine)
│   ├── screen_report.py     # ✅ Phase 4/7 — écran 4 : rapport + export PDF
│   ├── screen_calibration.py # ✅ 2026-07-25 — écran 5 : calibration ChArUco (DetectionThread)
│   ├── screen_plateau.py    # ✅ Lot C1 (2026-08-01) — écran 6 : création de plateau multi-zones
│   └── screen_cordons.py    # ✅ Lot C2 (2026-08-01) — écran 7 : tracé des cordons + report
│
├── assets/                  # Ressources statiques (synoptique Draw.io, icônes...)
├── preparations/            # Fichiers de préparation JSON (plateau : zones + cordons)
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

Le message de commit doit contenir **au minimum 3 parties**, dans cet ordre :

```
<Titre court et explicite>

Résumé fonctionnel :
<1 à 3 phrases — ce qui change du point de vue de l'utilisateur / du fonctionnement de
la machine. Pas de jargon technique : ce que ça change concrètement pour l'opérateur
ou pour le comportement du produit fini.>

Résumé technique :
<comment c'est implémenté — mécanismes, choix techniques, pourquoi ce choix plutôt
qu'un autre. C'est ici que va le "comment" et le "pourquoi" détaillé.>

Fichiers modifiés :
- <fichier> (nouveau / modifié / supprimé) : <brève description du changement dans ce fichier>
- ...

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
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
| 2026-07-29 | **Session 🏠 — Détection ChArUco débloquée + fix OpenCV 5.0 + distance mire + manuels.** Deux causes cumulées trouvées et corrigées pour le blocage de `CharucoDetector.detectBoard()` constaté le 2026-07-25 : (1) `camera_index` de `local_config.json` pointait sur la webcam intégrée du PC, pas l'USB ; (2) `charuco_legacy_pattern: true` incompatible avec les mires générées par l'appli (`board.generateImage()` ignore ce réglage, `detectBoard()` non — corrigé à `false`). `cv2.aruco.calibrateCameraCharuco()` (supprimée en OpenCV 5.0) remplacée par `board.matchImagePoints()` + `cv2.calibrateCamera()` dans `modules/calibration.py::calibrate_charuco`. Ajout de `estimate_board_pose()` et `distance_to_board_normal_mm()` (solvePnP) affichant la distance caméra↔mire en direct dans l'écran calibration. Overlay de debug ArUco/ChArUco ajouté sur `screen_capture.py` et `screen_calibration.py` (`detect_charuco` retourne désormais aussi `marker_count`) — c'est cet overlay qui a permis d'isoler les deux causes ci-dessus. `assets/camera_calibration.npz` ajouté au `.gitignore` (spécifique à chaque caméra/objectif, ne doit pas être partagé entre machines). `MANUEL_UTILISATEUR.md` et `MANUEL_MAINTENANCE.md` créés (guide opérateur 5 écrans + guide technique installation/config/dépannage). Rituel de fin de session formalisé en section 15 de ce fichier. | 45/45 tests passés. Points ouverts identifiés cette session : collision d'IDs ArUco plateau/mire (même dictionnaire `DICT_4X4_50` sans plage séparée — contournement : masquer le plateau pendant la calibration), et IDs réels du plateau à confirmer (`{0,3,4,5}` suspecté au lieu de `{0,1,2,3}`). Calibration optique à refaire sur le Raspberry Pi/caméra réels (pipeline validé sur PC de dev cette session). |
| 2026-08-01 (soir) | **Session 🏠 (v0.4.2) — Cadrage du lot C2bis : changement de convention du repère plateau. Aucune ligne de code.** Nouvelle convention posée par l'étudiant : repère **orthonormé** défini par trois tags — origine au centre du tag **2** (bas-gauche), ordonnées vers le tag **3**, abscisses vers le tag **1**, donc **Y vers le haut** ; le tag **0**, devenu redondant, sert de **contrôle de cohérence**. Motif : aligner le repère logiciel sur le repère physique dans lequel on raisonne devant la machine **avant** d'écrire les commandes machine du lot D. Évaluation d'impact conduite sur le code réel plutôt que de mémoire : le tableau des coins est trivial, mais le retournement de Y **ramène mécaniquement le miroir vertical** corrigé le matin même en `v0.1.1` — d'où un `y_pixel = (hauteur_mm − y_mm) × échelle` à écrire explicitement dans les trois `warp_*`. Point pédagogique tranché avec l'étudiant : cette ligne n'est pas une entorse à la règle « l'opérateur voit ce qui se passe sur le plateau », elle en est **la garantie**. Bascule également : toute la logique de signe de la géométrie des zones, le repère relatif des zones, et donc les cordons déjà enregistrés (`FORMAT_VERSION` → 2). Trois décisions annexes : contrôle de cohérence sur le tag 0, **conversion** des fichiers v1 au chargement (pas de refus), repli `BOITIER_X` au **premier numéro libre** (aucun état hors du dossier des préparations, donc fonctionne sur un dépôt fraîchement cloné). Lot C2bis spécifié en 5 étapes, chiffré à 2 sessions ; C3 décalé en `v0.4.3`. **Création de la section 7 bis** — registre des 13 actions en attente (`M1`-`M9` machine, `L1`-`L4` logiciel), à rappeler au début de chaque session et dès qu'un travail en cours en touche une, à la demande de l'étudiant. | 155/155 tests (inchangés). Manuels volontairement inchangés : rien de visible pour l'opérateur, et documenter maintenant un repère non encore implémenté induirait en erreur celui qui dépanne demain. Une seule question laissée ouverte, avec réponse retenue : garder le vocabulaire « haut-gauche / bas-droit » pour les coins de zone. |
| 2026-08-01 | **Session 🏠 (v0.4.1) — Étape 2, lot C2 : tracé des cordons et report sur toutes les zones.** Brique préalable dans `vision.py` : `warp_zone()` redresse une zone même vissée de travers, en composant homographie + passage au repère de la zone + mise à l'échelle. Conséquence exploitée par tout l'éditeur : l'image obtenue a son origine sur le coin haut-gauche de la zone à échelle constante, donc un clic se convertit en millimètres par une simple division. Création de `gui/screen_cordons.py`, un écran à **deux modes** dans une pile (vue d'ensemble cliquable / zoom et tracé) plutôt que deux écrans, l'aller-retour entre les deux étant le geste central de cette étape. Trois règles d'interaction tranchées hors spécification : priorité au tracé en cours pour capter les clics, sélection d'un cordon par clic à proximité hors tracé, et « Valider » inactif tant qu'un cordon est ouvert pour ne pas le perdre en silence. Undo/redo de profondeur 1 sur les 3 actions convenues, la suppression restaurant le cordon **à sa place** dans la liste. **Piège rencontré** : `QTest.mouseDClick` n'envoie que l'événement de double-clic, sans le `press` qui le précède en usage réel — c'est le CODE qui a été corrigé, pas le test, en rendant le comportement indépendant de la séquence d'événements Qt. | 155/155 tests (25 nouveaux, dont 22 pilotant de vrais événements souris). Validé à la main par l'étudiant : deux cordons tracés sur la zone 4/5 se retrouvent au même endroit relatif sur la 6/7. **Observation reportée au lot D** : les deux zones n'ont pas exactement la même taille à l'écran, signature de l'homographie approchée sans correction de perspective — l'erreur de report croît avec l'éloignement des marqueurs de référence, à corriger par la calibration ChArUco puis le recul de caméra sur la CNC. |
| 2026-08-01 | **Session 🏠 (v0.4.0) — Étape 2, lot C1 : écran de création de plateau.** Découpage du lot C en trois sous-lots (C1 vue globale et diagnostic, C2 zoom et tracé, C3 persistance et paramètres), un rituel par sous-lot. Décision de navigation : le nouvel écran **cohabite** avec le cycle historique via un bouton sur l'écran 1 (option a), la bascule en point d'entrée principal étant reportée au lot D — on ne casse pas le seul cycle qui va aujourd'hui jusqu'à la dépose. Création de `gui/screen_plateau.py` : saisie du produit avec bandeau permanent, flux caméra avec overlay des marqueurs, capture, analyse, restitution visuelle du diagnostic (rectangles verts/rouges étiquetés, cercles orange sur les marqueurs orphelins), message de statut borné à 2 zones détaillées pour ne pas manger la place de l'image en 800×480. Ajout de `mm_to_pixels()` dans `vision.py` pour la reprojection. **Défaut trouvé par les tests** : la longueur de diagonale de référence était votée sur les seules paires d'orientation plausible, si bien qu'un plateau intégralement monté à l'envers faisait élire des paires fantômes comme zones valides tandis que les vraies passaient pour orphelines — corrigé, le vote inclut désormais les paires inversées. Nouvelle anomalie `format_indeterminable`, distincte de `diagonale_hors_norme` qui était trompeuse dans ce cas. `pytest-qt`, `openpyxl` et `python-pptx` ajoutés à `requirements.txt`. | 130/130 tests (15 nouveaux, dont 13 `pytest-qt` qui pilotent réellement les widgets). Validé sur matériel réel par l'étudiant : les 2 zones de son plateau sont reconnues, format déduit 58 × 45 mm. Mesuré en 800×480 : 311 px restent pour l'image. **Point ouvert bloquant pour le lot C3** : la saisie du nom de produit passe par une boîte de dialogue clavier, inutilisable sur l'écran tactile du RPi sans clavier physique. |
| 2026-08-01 | **Session 🏠 (v0.3.1) — Sélection de la caméra de test par détection ArUco.** L'étudiant constate que `pytest` sollicite toujours la webcam intégrée du PC. Deux causes : le seul test qui balaie tous les index le fait par construction, et surtout se fier à `CAMERA_INDEX` ne prouve rien puisque c'est précisément cet index qui peut être faux. Critère proposé par l'étudiant et retenu : **la bonne caméra est celle qui voit un marqueur ArUco**. Création de `tests/conftest.py` avec la fixture `plateau_capture` (scope session) : essai de la caméra configurée d'abord — donc aucune autre caméra n'est ouverte dans le cas nominal — puis repli sur les autres ; 5 captures tentées par caméra pour absorber le temps de stabilisation d'une webcam ; image copiée avant le `release()`. L'image ainsi capturée est réutilisée par toute la session, ce qui rend les tests plus rapides et surtout déterministes. Ajout de 4 tests de vision **sur image réelle** (reproductibilité de la détection, coins dans les limites de l'image, homographie plausible, cohérence des zones), qui complètent les tests synthétiques sans les remplacer. Le test de balayage complet reçoit le marqueur `toutes_cameras`, déclaré dans un nouveau `pytest.ini`. | 115/115 tests (7 nouveaux). Caméra retenue : index 1, 1280×960, marqueurs `[0, 3, 4, 5, 6, 7]` — le plateau porte donc désormais **3 zones** (4/5, 6/7 et deux coins). Durées : ~65 s pour la suite complète, ~41 s avec `-m "not toutes_cameras"`. |
| 2026-08-01 | **Session 🏠 (v0.3.0) — Étape 2, lot B : modèle de données et persistance JSON.** Création de `modules/preparation.py` : classes `Cordon`, `Settings` et `Preparation`, plus une couche de persistance (`save_preparation`, `save_autosave`, `load_preparation`, `has_autosave`, `discard_autosave`, `list_autosaves`, `list_preparations`). Ajout du transfert de repère `to_plateau_mm()` / `to_zone_mm()` sur `DepositZone` — c'est l'opération qui matérialise « un cordon tracé une fois s'applique à toutes les zones ». Le format initialement esquissé le 2026-07-11 (points en pixels, quantité par cordon) est remplacé : points en mm relatifs à la zone, quantité issue de deux paramètres globaux. Écriture atomique des fichiers, `format_version` refusant les fichiers plus récents que le logiciel, assainissement du nom de fichier sans altérer le nom de produit affiché. Formatage du JSON retravaillé pour garder les paires de coordonnées sur une seule ligne : sans ça un plateau réaliste ferait plusieurs centaines de lignes de crochets quasi vides, alors que le fichier est un livrable qu'on doit pouvoir relire. | 108/108 tests passés (30 nouveaux). Manuel utilisateur toujours inchangé — le lot B n'a rien de visible pour l'opérateur, les copies d'écran viendront avec le lot C. Question du rituel précédent tranchée : les deux seuils de zone sont dans `Settings`, donc enregistrés par plateau, car ils qualifient la qualité de montage de ce plateau-ci. Reste documenté pour le lot C : le rythme de 5 s de l'autosave et la règle « ne pas enregistrer la polyline en cours » sont à la charge de l'IHM. |
| 2026-08-01 | **Session 🏠 (v0.2.0) — Étape 2, lot A : géométrie des zones de dépose.** Cadrage complet du besoin avec l'étudiant : plusieurs zones par plateau, plusieurs cordons par zone, cordons tracés une fois et appliqués à toutes les zones, zones vissées à demeure donc sauvegardables. Découpage du chantier en 3 lots (A géométrie, B modèle+JSON, C IHM), chacun clos par un rituel et une release. Lot A implémenté dans `vision.py` : `detect_deposit_zones_mm()` en fonction pure (testable sans caméra) + `VisionProcessor.detect_deposit_zones()` qui ne fait que le passage pixels→mm, avec les classes `PlateauLayout` et `DepositZone`. Deux règles convenues au cadrage ont dû être corrigées à l'épreuve des tests : (1) le filtrage par longueur de diagonale laissait passer les paires fantômes d'un plateau en grille, qui ont la même longueur par symétrie et invalidaient les vraies zones par conflit → ajout d'un tri par signe des composantes ; (2) la règle « garder la plus petite rotation parmi les solutions symétriques » faisait ressortir une zone à 25° comme étant à 2°, rendant `ANOMALIE_ANGLE` inopérante → solution unique, l'ambiguïté n'existant pas puisque le format médian est orienté. Correction au passage d'un défaut des tests caméra signalé par l'étudiant : la fixture ouvrait l'index 0 en dur, donc la webcam intégrée du PC, au lieu de la caméra configurée. | 78/78 tests passés (15 nouveaux pour le lot A). Manuel utilisateur volontairement inchangé : le lot A n'a rien de visible pour l'opérateur, les copies d'écran viendront avec le lot C. Questions ouvertes : remonter ou non `ZONE_DIAGONAL_TOLERANCE_MM` / `ZONE_MAX_ROTATION_DEG` dans la fenêtre de paramètres du lot B ; afficher la résolution réelle à côté du nom de la caméra sur l'écran 1. |
| 2026-08-01 | **Session 🏠 (v0.1.1) — Repère du plateau refait + choix du matériel dans l'interface.** Disposition réelle des marqueurs relevée avec l'étudiant (`3`=haut-gauche, `0`=haut-droit, `1`=bas-droit, `2`=bas-gauche) ; origine du repère mm placée sur le marqueur **3**, axe **Y dirigé vers le bas** (option retenue après comparaison explicite avec l'option « Y vers le haut », qui aurait rendu tout le plateau négatif). Effet de bord découvert et corrigé au passage : `warp_image()`/`warp_region()` renvoyaient un **miroir vertical** depuis la Phase 2 (le haut de la photo ressortait en bas de l'image redressée) — mis en évidence par le calcul, pas à l'œil, et verrouillé par `test_warp_image_orientation_non_miroir`. Inversion vers l'axe Y machine concentrée dans `screen_run.py` (`MACHINE_ORIGIN_Y - y`). Ajout de deux listes déroulantes sur l'écran 1 pour choisir le port machine et la caméra (+ bouton Rafraichir) : énumération dans les modules (`Machine.list_ports()`, `Camera.list_devices()`), application du changement par `MainApp` seul. `serial_port` et `serial_baudrate` rendus surchargeables via `local_config.json`. Bug trouvé et corrigé pendant le test opérateur : le scan des caméras cassait le flux en cours (second handle DirectShow sur l'index déjà ouvert) → `list_devices(exclude=...)`. | 62/62 tests passés. Question ouverte du 2026-07-29 sur les IDs du plateau **close** (fausse alerte : `{0,3,4,5}` = 2 marqueurs plateau cadrés + 2 marqueurs de zone). Enseignement : le repli à 2 marqueurs est le **mode nominal** sur la Geeetech, pas un cas dégradé. Reste ouvert : `MACHINE_ORIGIN_X/Y` à remesurer au M114 au-dessus du marqueur 3, et l'étape 2 (fichier de préparation JSON) pas commencée. |
| 2026-07-25 | **Session 🏠 — Écran calibration ChArUco + refonte config locale + optimisations caméra.** Création complète de `gui/screen_calibration.py` : flux caméra live, détection ChArUco en overlay (marqueurs ArUco + coins), capture guidée de N poses, calcul de calibration en QThread, sauvegarde `assets/camera_calibration.npz`, bouton "Générer la mire". Ajout des fonctions ChArUco dans `modules/calibration.py` (`create_charuco_board`, `generate_charuco_image`, `detect_charuco`, `calibrate_charuco`) — utilise `cv2.aruco.CharucoBoard` avec `setLegacyPattern(True)` pour compatibilité générateurs externes (calib.io, kalibr). Mise en place du système **`local_config.json`** (gitignoré) chargé par `config.py` : `camera_index`, `calibration_min_images`, `charuco_cols/rows/square_mm/marker_mm/dict/legacy_pattern`. Optimisations perfs : (1) **caméra unique partagée** entre `screen_capture` et `screen_calibration` (créée dans `MainApp.__init__`, passée via `set_camera()`) — plus de release+reopen à chaque changement d'écran ; (2) backend **CAP_DSHOW** sur Windows avec validation stricte (5 lectures test, fallback CAP_ANY si échec) ; (3) fenêtre en `showMaximized()` au lieu de `setFixedSize`. Correctifs : (a) `QSizePolicy.Ignored` sur les labels caméra pour éviter la croissance infinie du layout ; (b) `DetectionThread` (sous-classe `QThread`) crée son propre `CharucoDetector` dans `run()` pour éviter les problèmes de thread-safety ; (c) `drawDetectedMarkers/CornersCharuco` enrobés dans try/except (formats variables selon versions OpenCV). | Screen calibration navigable, thread OK. **Non validé** : détection ChArUco d'une mire externe échoue (basic `detectMarkers` OK, `detectBoard` KO) — piste privilégiée : tester avec la mire générée par l'app (bouton "Générer la mire" + impression). **À vérifier demain** aussi : présence de l'aperçu caméra après les changements du backend. |

> L'historique détaillé (par phase) est dans `CONCEPTION.md` section 10.

---

## 15. Rituel de fin de session

> **Déclenché uniquement sur demande explicite** de l'étudiant (ex. "lance le rituel de fin de
> session", "on clôture", "fin de session"). Jamais automatique, jamais en fin de session par
> défaut — Claude ne doit pas l'exécuter sans que l'étudiant l'ait demandé. Cette demande vaut
> autorisation explicite pour les étapes de push/merge décrites ci-dessous : pas besoin de
> reconfirmer chaque commande git une par une pendant le déroulé du rituel.

**Avant de commencer** : l'étudiant indique le numéro de version de la session (convention
`vX.Y`, ex. `v0.3` ; une session de correctifs mineurs incrémente le dernier chiffre, ex.
`v0.2.1`). Si aucun numéro n'a été donné avant le déclenchement du rituel, le demander avant
de continuer — ne pas en inventer un.

**Déroulé, dans cet ordre** :

1. **Tests de non-régression** — lancer `pytest`. Si un test échoue, **arrêter le rituel ici**
   et signaler l'échec à l'étudiant en détail. Ne jamais commit ni push du code qui casse des
   tests existants — corriger (ou faire corriger) avant de reprendre le rituel depuis le début.
2. **Manuels** — mettre à jour `MANUEL_UTILISATEUR.md` et `MANUEL_MAINTENANCE.md` (racine du
   projet ; les créer s'ils n'existent pas encore) avec les changements de la session :
   nouvelles fonctionnalités côté opérateur, procédures modifiées, points de dépannage
   découverts. Commit dédié (format section 13).
3. **Documentation d'avancement** — mettre à jour `CLAUDE.md` (agenda "Prochaine session"
   section 8, tableau d'avancement section 9, historique section 14) et `CONCEPTION.md`
   (décisions techniques, résultats de tests, découvertes). Commit dédié (format section 13).
4. **Branche, push, merge** :
   - Créer (ou continuer, si déjà créée en cours de session) la branche de travail nommée
     `vX.Y` (ou `vX.Y.Z`) donnée par l'étudiant à l'étape précédente.
   - Committer les changements de code restants sur cette branche, s'il y en a (format
     section 13).
   - `git push -u origin <branche>` — publier la branche sur le dépôt distant.
   - `git checkout master && git pull origin master` — remettre master à jour avant de merger.
   - `git merge <branche>` — merge direct (pas de Pull Request GitHub), fast-forward si
     possible.
   - `git push origin master` — publier master à jour.

Tous les commits produits pendant ce rituel (manuels, documentation, code restant) suivent le
gabarit à 3 parties minimum décrit en section 13 (résumé fonctionnel, résumé technique, liste
des fichiers modifiés).
