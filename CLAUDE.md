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
| Référentiel plateau | 4 marqueurs **ArUco** DICT_4X4_50 — IDs 0, 1, 2, 3 aux coins. Disposition relevée le 2026-08-01 : `3`=haut-gauche, `0`=haut-droit, `1`=bas-droit, `2`=bas-gauche. Depuis le lot C2bis (2026-08-02) : **origine du repère mm = marqueur 2** (bas-gauche), **Y vers le haut**, marqueur 0 en contrôle de cohérence | ✅ Arrêté |
| Référentiel zone de dépose | 2 marqueurs **ArUco** DICT_4X4_50 — IDs 4 et 5, aux coins opposés (diagonale) de la zone où est posée la pièce | ✅ Arrêté |

#### Machine cible (CNC — production)

| Composant | Modèle / Référence | Statut |
|---|---|---|
| Base mécanique | CNC — châssis + axes | ✅ Montée (2026-07-11) |
| Contrôleur machine | Carte CNC — firmware **Marlin dernière version** (même protocole G-code) | ✅ Intégrée, câblée, sous tension, flashée (2026-07-11) |
| Câblage capteurs + moteurs | Fins de course, caméra, moteurs Nema 17 | 🔄 En cours — reste à câbler |
| Ordinateur de contrôle | Même Raspberry Pi 3B+ | ✅ Réutilisé |
| Écran | Même écran tactile 7" | ✅ Réutilisé |
| Caméra | **DFRobot FIT0729** (autofocus logiciel) — ⚠️ **remplace la Philips SPC1330NC**, décidé au montage CNC (constaté le 2026-08-25, à documenter précisément avec l'étudiant). Montée **décalée** du plateau (pas au-dessus) et à **~45°**, contrairement au montage vertical de la Geeetech | 🔄 Détection ArUco et calibration ChArUco faites ; homographie en cours de validation |

> Le portage logiciel Geeetech → CNC se limite aux paramètres de `config.py` (port série, limites de déplacement, zone de travail) **et à la caméra**, qui n'est plus la même sur les deux machines : la CNC a sa propre géométrie de prise de vue (vue oblique) et son propre fichier de calibration `assets/camera_calibration.npz` (gitignoré, propre à chaque caméra).

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
| ~~Q5~~ | ~~Taille réelle de la zone de travail (en mm)~~ | ✅ **Résolu** — 151 mm × 104 mm (re-mesuré centre-à-centre des marqueurs, 2026-06-12). ⚠️ Périmé depuis le 2026-07-30 : les marqueurs sont aux coins du bâti, soit 192 mm centre-à-centre **supposés** — devenu le paramètre `plateau_size_mm` au lot C2bis, mesure au mètre toujours en attente (action `M1`) |
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
| ~~**M1**~~ | ~~Mesurer le plateau au mètre~~ | ✅ **Fait le 2026-08-04 sur le PoC : 205,5 mm CENTRE À CENTRE** (soit 233,5 bord à bord). La valeur supposée jusque-là — 220 bord à bord, donc 192 centre à centre — était **fausse de 13,5 mm**, ce qui décalait toute la dépose en repli 2 tags, **le mode nominal sur la Geeetech**. Renseignée dans `local_config.json` via les nouvelles clés `work_area_width_mm` / `work_area_height_mm`, qui prennent la mesure **centre à centre directement** : ⚠️ saisir une mesure centre-à-centre dans `plateau_size_mm` retrancherait une seconde fois la largeur d'un marqueur, soit 28 mm d'erreur silencieuse. **Reste à faire pour la CNC**, qui aura son propre plateau |
| ~~**M2**~~ | ~~`M114` buse au-dessus du marqueur 2 (bas-gauche) → origine machine~~ | ✅ **Fait le 2026-08-02** — relevé `X:5.00 Y:0.00 Z:0.00 · Count X:394 Y:0 Z:0` → `MACHINE_ORIGIN_X = 5.0`, `MACHINE_ORIGIN_Y = 0.0`. Repère de home vérifié au passage (`G28` + `M114` immédiat = X:0 Y:0 Count 0/0) : ni `X_MIN_POS` non nul, ni `M206` en EEPROM. ⚠️ **Réserve sur Y** : le compteur Y était à 0 exact, donc l'axe n'avait pas bougé depuis le homing — soit le marqueur 2 tombait déjà sous la buse, soit le plateau butait sur la fin de course et `0` est une limite, pas une mesure. Non départagé. **Premier suspect si la dépose ressort décalée en Y** → voir `M2 bis`. 🔄 **Valeurs REMPLACÉES le 2026-08-03** par le relevé de `M2 bis` (`6.0 / −2.0`, pointe de seringue) : le doute sur Y s'est confirmé. Ligne conservée pour l'historique de la démarche |
| ~~**M2 bis**~~ | ~~Lever la réserve sur `MACHINE_ORIGIN_Y`~~ | ✅ **Levée le 2026-08-03 — et la réserve était FONDÉE.** Erwann a relevé la position de la **pointe de seringue au homing**, exprimée dans le repère plateau : `x = −6 mm`, `y = +2 mm`. Par inversion, `MACHINE_ORIGIN_X = 6.0` et **`MACHINE_ORIGIN_Y = −2.0`**. Le `Y = 0` du 2026-08-02 était donc bien une **butée de fin de course, pas une mesure** — exactement ce que le compteur de pas à 0 exact laissait craindre. **Conséquence à traiter en D1** : `plateau_y` n'est atteignable qu'à partir de **2 mm** — une bande de 2 mm en bas du plateau est **hors course** → contrôle de course obligatoire avant lancement |
| ~~**M2 ter**~~ | ~~Mesurer le décalage buse ↔ pointe de seringue~~ | ✅ **Absorbée le 2026-08-03** : le relevé de `M2 bis` vise directement la **pointe**, plus la buse — le décalage n'a donc plus à être mesuré séparément. Recoupement rassurant avec `M2` (qui visait la buse, sans seringue) : l'écart ressort à `(−1, +2)` mm, ordre de grandeur crédible pour un support de seringue |
| **M3** | **Hauteur Z de la pointe de seringue après homing** | ⚠️ **Recadrée le 2026-08-03 : ne bloque plus que le sous-lot D4** (extrusion réelle). Erwann a confirmé que le **Z du homing est sûr tant qu'on n'extrude pas** — d'où la décision « dépose à blanc » de D1 : `z_travel = z_dispense = Z du homing`, aucun mouvement en Z. D1 à D3, donc la démo de l'oral blanc, n'ont **pas** besoin de `M3`. Demande le dispositif de seringue monté, donc **au boulot** |
| **M4** | **Sens des axes machine vs axes plateau** (X, Y, Z) — à établir **en interactif**, machine sous tension | Décidé le 2026-08-01 : on ne le déduit pas sur le papier. Le relevé de `M2 bis` est **cohérent** avec les deux additions du code (un X vers la droite, un Y qui monte), mais il ne les prouve pas : il a été fait *dans* cette convention. Reste à valider par un mouvement réel — c'est précisément ce que le **passage au zéro de chaque zone** de D1 rendra visible à l'œil |
| **M11** | **Relever la course utile réelle des axes** (`M211`, ou la configuration Marlin) | Créée le 2026-08-03 avec le lot D1. Le contrôle de course s'appuie sur `MACHINE_TRAVEL_X/Y/Z_MAX_MM`, dont les valeurs actuelles (200/200/180) sont les dimensions **catalogue** d'une Geeetech I3 — **jamais relevées**. ⚠️ Une valeur trop **grande** laisse passer un dépassement réel : c'est le sens dangereux, et celui qu'on ne voit pas. Une minute machine sous tension, à grouper avec `M2 bis`/`M4` |
| **M10** | **CNC — coordonnées de prise de vue** `(x, y, z)` et origine plateau | Nouveau le 2026-08-03. Sur la CNC la caméra est **solidaire de la seringue** : la position de prise de vue est une vraie inconnue, sans rapport avec le homing. Sur le POC elle vaut le homing (caméra fixe sur le bâti). À renseigner dans `local_config.json` de la CNC. **Tout reste à mesurer côté CNC** (dixit Erwann, 2026-08-03). 🔄 **Étudiée le 2026-08-25** : le point de vue nominal est identifié et donne une détection 4 marqueurs correcte une fois l'autofocus traité (voir `M12`) — **mais la mesure `(x, y, z)` elle-même n'est toujours pas consignée**, reportée volontairement par l'étudiant |
| **M12** | **CNC — trouver `camera_focus_value`** avec `python tests/demo_camera.py --focus`, à la distance de capture réelle, puis l'enregistrer avec `camera_autofocus_off: true` dans `local_config.json` de la CNC | Créée le 2026-08-25. La caméra CNC (**DFRobot FIT0729**, autofocus logiciel — remplace la Philips) refait le point à chaque capture, ce qui floute transitoirement l'image et rend la détection des 4 marqueurs intermittente en vue oblique à 45°. Voir `MANUEL_MAINTENANCE.md` section 4.11 pour la procédure complète |
| **M5** | **Calibration ChArUco sur le RPi et la caméra Philips réels** (15 poses) | Le pipeline n'a été validé que sur le PC de dev. Cause connue de l'**écart résiduel de ~10 %** (distorsion de l'objectif) |
| **M6** | **Q8 — volume de pâte de référence** (par mm de cordon) | Calibrage expérimental. Alimente la quantité déposée et le volume estimé du rapport PDF |
| **M7** | **Créer `local_config.json` sur le RPi** (`camera_index: 0`, `serial_port: "/dev/ttyUSB0"`, **et surtout `work_area_width_mm` / `work_area_height_mm` = 205.5**) | Fichier gitignoré, donc absent d'un dépôt fraîchement cloné : l'appli démarre sur la mauvaise caméra sans lui. ⚠️ **Devenu critique le 2026-08-04** : sans les deux clés de zone de travail, le RPi déposerait avec la valeur supposée d'avant `M1`, fausse de **13,5 mm** |
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

### 🚩 POINT DE REPRISE — session vision CNC livrée le 2026-08-25 (`v0.6.1`)

> ⚠️ **Écart de journal comblé partiellement le 2026-08-25** : aucune entrée n'existait
> entre le 2026-08-05 et aujourd'hui. Ce qui suit est ce qui a été confirmé **en
> conversation** ce jour-là — **PAS un audit du code ni de la machine**. Le point de
> reprise du 2026-08-05 (D2 jamais essayé sur machine) est **caduc** : l'étudiant a
> confirmé que l'essai a été fait et **validé** depuis. Mais l'état exact de `M4`
> (sens des axes), `M11` (course réelle) et du lot **D4** (extrusion) sur la Geeetech
> n'a **pas** été revérifié en détail cette session — à confirmer en tout début de la
> prochaine, ne pas supposer qu'ils sont clos parce que D2 l'est.
>
> **✅ Confirmé le 2026-08-25** :
> - Rapport final IUT **rendu**.
> - Soutenances blanches **#2 (05/08) et #3 (12/08) faites**. Une **4e soutenance
>   ajoutée le 28/08** (dans 3 jours), **en plus** de la finale IUT du 31/08 (inchangée,
>   dans 6 jours).
> - Lot **D2 validé sur la Geeetech** : la machine parcourt un plateau réel en l'air,
>   du bouton d'accueil au retour à l'accueil.
> - **CNC** : la caméra n'est plus la Philips mais une **DFRobot FIT0729** (autofocus
>   logiciel), montée **décalée** du plateau à **~45°** (pas au-dessus comme sur la
>   Geeetech). Calibration ChArUco déjà refaite pour cette caméra spécifique.
>
> **🔧 Diagnostiqué et traité ce jour** — deux causes superposées à la mauvaise détection
> des zones en vue oblique sur la CNC (détail complet en `CONCEPTION.md` section 4.2 et
> `MANUEL_MAINTENANCE.md` section 4.11) :
> 1. Le mode 2-3 marqueurs (`estimateAffinePartial2D`, une similitude) ne corrige pas la
>    perspective — confirmé sans conséquence en pratique : le mode 4 marqueurs
>    (`compute_homography()`, projectif complet) donne une reconstruction **correcte**
>    une fois les 4 tags détectés. Aucun changement de calcul nécessaire.
> 2. L'autofocus de la FIT0729 refait le point à chaque capture → détection intermittente.
>    Traité : `Camera.set_autofocus()` / `Camera.set_focus()` + clés
>    `camera_autofocus_off` / `camera_focus_value` dans `local_config.json`, et un mode
>    `python tests/demo_camera.py --focus` pour trouver la bonne valeur à l'œil.
>
> **▶️ POUR DÉMARRER LA PROCHAINE SESSION** : action `M12` — sur la CNC, lancer
> `python tests/demo_camera.py --focus` à la distance de capture réelle, trouver la
> valeur nette, l'enregistrer dans `local_config.json`, puis répéter plusieurs fois la
> détection à 4 marqueurs pour vérifier que c'est désormais **fiable et répétable**
> (une seule vérification a été faite jusqu'ici). Une fois stable : mesurer et consigner
> `M10` (position de prise de vue CNC), volontairement reportée par l'étudiant cette
> session.
>
> 📊 **Support de soutenance** : `assets/generate_bilan_soutenance.py` produit 9 planches
> (processus métier, carte des modules, bilan, portage CNC) dans la charte du deck
> existant. Les chiffres y sont **mesurés**, avec la commande de rafraîchissement en
> commentaire — les relancer avant toute nouvelle soutenance plutôt que de recréer les
> planches. Utile pour la soutenance du **28/08**, dans 3 jours.

---

**État du dépôt** : lot C3 **commité, mergé dans `master` et poussé** le 2026-08-02
(rituel de fin de session, branche `v0.4.3`). Vérifier quand même avec `git status` et
`git log --oneline -5`. Note : `preparations/` est désormais **gitignoré** — ce sont des
données de travail liées à une machine, pas du code.

**Ajouté le 2026-08-02 après usage réel** : bouton **« Charger un plateau »** sur l'écran
d'accueil. Le lot C3 ne couvrait que la reprise après plantage ; la **réutilisation** d'un
plateau validé — point 7 du processus cible, section 1 — n'avait été affectée à aucun lot
et le manque n'est apparu qu'en s'en servant. Ajout d'une confirmation d'écrasement au
passage. Puis, sur remarque de l'étudiant, la **capture automatique** au rechargement : la
photo se déclenche seule dès que ≥ 2 marqueurs de coin sont vus (garde-temps 5 s), et
seulement dans ce cas — pas à la création ni après un « Reprendre ».
⚠️ Les boutons de capture du cycle historique sur l'écran 1 restent en place :
c'est **encore le seul chemin validé jusqu'à la dépose réelle**, leur retrait est prévu au
lot D et seulement après validation du nouveau chemin sur machine.

**Tests** : **208** avec `pytest -m "not toutes_cameras"`, **209** avec `pytest` complet
(+48 sur la session). Les tests sur image réelle **se sont exécutés cette fois** (plateau
devant la caméra) : la chaîne complète est donc enfin revalidée depuis le changement de
repère du lot C2bis.

**Deux propositions laissées en suspens le 2026-08-02** — les reproposer *une fois*, sans
insister, mais ne pas les traiter comme neuves :
- étendre la **capture automatique à la création** d'un plateau (aujourd'hui volontairement
  manuelle : l'opérateur y pose les boîtiers et sait seul quand c'est prêt) ;
- **retirer la confirmation d'écrasement** si elle s'avère pesante à l'usage — elle a été
  ajoutée d'initiative, l'étudiant ne l'avait pas demandée.

**Ce qui a été fait le 2026-08-02 (lot C3)** — persistance et paramètres : sauvegarde
automatique toutes les 5 s avec drapeau de modification, bouton d'enregistrement définitif,
reprise d'un travail interrompu au démarrage, fenêtre de paramètres, et saisie de la
référence produit en trois voies. Détail et décisions en `CONCEPTION.md` section 6.1.

**⚠️ Défaut du lot C2bis trouvé et corrigé le 2026-08-02, en essayant le logiciel sur la
machine** : plus aucune zone de dépose n'était détectée, les 4 marqueurs ressortant
« orphelins ». `estimateAffinePartial2D` ajuste une **similitude**, de déterminant positif,
qui **ne sait pas mirroiter** — or le repli 2-3 marqueurs doit passer d'un repère Y-bas
(image) à un repère Y-haut (plateau), ce qui EST un miroir. En repli, `y_mm` croissait donc
vers le bas et toute la logique de signe des zones s'inversait. Corrigé en ajustant la
similitude vers un repère intermédiaire retourné, puis en composant avec le retournement.
**Le repli 2 marqueurs est le mode nominal sur la Geeetech** : le défaut portait sur le
chemin le plus emprunté du logiciel. Détail et leçon de méthode en `CONCEPTION.md`
section 4.2.

**État du dépôt** : lot C2bis **commité, mergé dans `master` et poussé** le 2026-08-02
(rituel de fin de session, section 15), avec la mesure `M2` intégrée à `config.py`.
Vérifier quand même avec `git status` et `git log --oneline -3` avant toute conclusion.

**Tests** : 163/163 avec `pytest -m "not toutes_cameras"`. ⚠️ Le run de clôture a rendu
**152 passés / 12 sautés** : les tests sur image réelle ne se sont pas exécutés, le plateau
— solidaire du lit — s'étant retrouvé hors du champ de la caméra fixe après le `G28`. Ce
n'est pas une régression (la fixture saute proprement quand aucune caméra ne voit de
marqueur), mais **la chaîne complète n'a pas été revalidée sur photo réelle après le
changement de repère**. À refaire dès que le plateau est de nouveau cadré.
**Tests** : 161/161 avec `pytest -m "not toutes_cameras"` (~33 s ; sans le marqueur, la
webcam intégrée du PC s'allume et le run prend ~46 s). +7 tests par rapport au lot C2.

**Ce qui a été fait le 2026-08-02** — lot C2bis complet, les 5 étapes du cadrage :
repère plateau orthonormé (origine tag 2, Y vers le haut), retournement explicite de Y dans
les trois `warp_*`, bascule de toute la logique de signe des zones, repère de zone à
l'origine bas-gauche, `FORMAT_VERSION` → 2 avec conversion des fichiers v1, `plateau_size_mm`
en paramètre, et regroupement du choix d'homographie dans `compute_plateau_reference()`.
Détail complet en `CONCEPTION.md` section 4.2 et dans le journal (dernière ligne).

**⚠️ Ce que le lot C2bis N'A PAS validé** : la formule de conversion vers le repère machine
(`gui/screen_run.py`) est cohérente avec la nouvelle convention — deux additions — mais
**non vérifiée sur la machine**. Le sens réel des axes est l'action `M4`, à établir en
interactif au lot D, et `MACHINE_ORIGIN_X/Y` reste à remesurer (`M2`). Tant que ce n'est pas
fait, la dépose réelle est décalée, et aucun test ne peut le détecter.

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
| `v0.4.2` | **Lot C2bis** — repère plateau orthonormé (voir ci-dessous) |

**➡️ PROCHAINE ÉTAPE : lot C3 (`v0.4.3`) — persistance et paramètres.** Spécifié plus bas
dans cette section, en 4 points, toutes questions tranchées.

---

#### Lot C2bis — changement de convention du repère du plateau ✅ LIVRÉ le 2026-08-02

> **Ce qui suit est la spécification d'origine, conservée telle quelle** : elle documente
> ce qui avait été prévu et pourquoi, ce qui vaut pour le rapport de stage. Le bilan de ce
> qui a réellement été livré, et des trois écarts par rapport à cette spécification, est
> en fin de sous-section.

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
  → **✅ tranché le 2026-08-02 : conservés**, proposition suivie.

*(Les deux autres questions ont été tranchées le 2026-08-01 : tag 0 = contrôle de cohérence,
fichiers v1 = conversion au chargement. Voir ci-dessus.)*

**Garde-fou proposé** : un test « boussole » qui épingle la convention en un seul endroit —
tag 2 → `(0, 0)`, tag 3 → `(0, H)`, image redressée non miroir, diagonale d'une zone saine à
`dy < 0`. Si la convention rebouge un jour, c'est ce test qui doit hurler en premier.
→ **✅ écrit tel quel** : `test_boussole_de_la_convention_du_repere` dans `test_vision.py`.

##### ✅ Bilan de livraison (2026-08-02) — et trois écarts à la spécification

Les 5 étapes ont été livrées **en une seule session** et non deux, et le découpage
« session 1 = étapes 1-2 » n'a pas été tenu — délibérément. Motif : l'étape 3 (repère de
zone) n'est pas une suite de l'étape 2, c'en est la **condition de cohérence**. S'arrêter
après l'étape 2 aurait laissé le plateau en Y montant et les zones en Y descendant, donc
un état intermédiaire faux, qu'aucun test n'aurait pu valider. Le découpage en 2 sessions
était une estimation de charge, pas une frontière de correction.

Trois écarts par rapport à ce qui était écrit ci-dessus, tous dans le sens d'un travail
en plus :

1. **La conversion des fichiers v1 retourne aussi les ZONES**, pas seulement les cordons.
   La spécification ne mentionnait que `y_v2 = hauteur_zone − y_v1`. Mais un fichier
   contient des coordonnées dans les **deux** repères retournés par ce lot : ne convertir
   que les cordons aurait produit un fichier incohérent avec lui-même — pire que de ne
   rien convertir. Les coins passent par `WORK_AREA_HEIGHT_MM` et `rotation_deg` change
   de signe. Limite assumée et documentée : la hauteur de plateau utilisée est celle
   configurée aujourd'hui, sans conséquence pratique (ces coordonnées absolues sont de
   toute façon redétectées à la capture suivante).
2. **`load_preparation()` réécrit le fichier converti**, ce que la spécification demandait
   (« réenregistré en v2 ») sans dire où. Le choix : dans la fonction qui touche déjà au
   disque, pas dans `from_dict()`, qui doit rester utilisable en mémoire.
3. **L'écart du tag 0 est mesuré contre une similitude ajustée sur les tags 2/1/3**, et
   non contre la matrice de `compute_homography()`. Découvert en écrivant le code : avec
   exactement 4 points, `getPerspectiveTransform` ajuste **sans résidu**, et le contrôle
   aurait été nul par construction quelle que soit la réalité du plateau — un indicateur
   qui n'indique rien. Point à ressortir pour le rapport : la décision « le tag 0 devient
   un contrôle de cohérence » était juste, mais sa mise en œuvre naïve l'aurait vidée de
   son sens.

**Ce que le lot n'a pas validé, et ne pouvait pas valider** : la formule de conversion
vers le repère machine (`screen_run.py`) est passée de « addition + soustraction » à deux
additions, cohérente avec la nouvelle convention. Elle n'est **pas vérifiée sur la
machine** — actions `M2` (remesurer `MACHINE_ORIGIN` au-dessus du marqueur **2**) et `M4`
(sens réel des axes, en interactif au lot D).

---

**➡️ lot C3 (`v0.4.3`) ✅ LIVRÉ le 2026-08-02** — persistance et paramètres. Tout le modèle
était déjà écrit et testé (lot B), il s'agissait essentiellement de câblage :

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

##### ✅ Bilan de livraison du lot C3 (2026-08-02)

Les 4 points livrés, plus la saisie du nom de produit. Ce qui a demandé plus que du
câblage — à connaître avant de toucher à ce code :

- **La sauvegarde automatique n'écrit que si quelque chose a changé** (drapeau levé par
  `cordons_modified`, abaissé après écriture réussie). Sans ce drapeau, le fichier serait
  réécrit toutes les 5 s indéfiniment : sur la **carte SD** du RPi, c'est de l'usure
  gratuite. Le coût du filet doit rester proportionnel au risque couvert.
- **La reprise ne restaure pas la photo** — le fichier n'en contient pas. On recharge les
  cordons, les paramètres et la zone de référence, puis on reprend une capture. Rien n'est
  perdu : c'est exactement ce que permet le choix du lot B de mémoriser les cordons en mm
  **relatifs à la zone**.
- ⚠️ **La zone de RÉFÉRENCE doit être restaurée AVANT tout affichage.** Si la première
  zone rouverte devenait la nouvelle référence, les cordons seraient réinterprétés dans un
  repère qui n'est pas le leur et se retrouveraient décalés **sans aucun signal**. Même
  famille de faute silencieuse que le miroir vertical du lot C2bis.
- **`SettingsDialog` rend un objet neuf** plutôt que de modifier celui reçu : c'est ce qui
  rend « Annuler » réellement sans effet.
- **`propose_resume()` est appelée depuis `main.py` après `show()`**, jamais depuis
  `__init__` — une modale pendant la construction s'afficherait sans sa fenêtre.

Nouveau fichier : `gui/dialogs.py` (`ProductNameDialog`, `SettingsDialog`). 193 tests
(+32), dont `tests/test_dialogs.py` créé.

**Convention de numérotation** : lot C en `v0.4.x` — C1 = `.0`, C2 = `.1`, **C2bis = `.2`**,
**C3 = `.3`**. Le lot D ouvrira `v0.5.0` : il change le point d'entrée du logiciel, ce
n'est plus une itération du lot C.

---

#### Lot D — exécution multi-zones — ✅ SPÉCIFICATION COMPLÈTE (cadrée le 2026-08-03)

> **Session du 2026-08-03 : cadrage seul, aucune ligne de code**, à la demande explicite de
> l'étudiant. Il a décrit le processus qu'il veut ; les points ambigus ont été relevés et
> tranchés au fil de l'échange. **Il ne reste rien à redemander** — la prochaine session
> commence directement par `D1`, point 0.

##### A. Le processus cible, de bout en bout

1. L'opérateur clique sur **« Lancer une dépose »** depuis l'écran d'accueil.
2. La machine fait un **homing** (`G28`).
3. La machine se place en **position de prise de vue** `(x, y, z)`.
4. L'opérateur **choisit le fichier de préparation** à exécuter.
5. La machine fait une **acquisition caméra** et affiche les zones **valides et invalides**
   du plateau, avec le motif de chaque invalidité.
6. L'opérateur **sélectionne les zones où se trouve réellement un produit** : un clic
   sélectionne, un second désélectionne. Chaque zone sélectionnée est nettement identifiée
   — **on y dessine les cordons**, ce qui montre du même coup ce qui va être déposé.
7. Il **acquitte** sa sélection, ou **annule** et revient à l'écran d'accueil.
8. Une **modale de confirmation** rappelle ce qui va se passer : nombre de zones
   sélectionnées et nom du produit. « Annuler » **revient à l'étape 6**, pas à l'accueil.
9. S'il confirme : **nouveau homing**, puis la dépose.
10. Pendant la dépose, une **modale de progression** : barre d'avancement, zones faites,
    temps écoulé, bouton **Pause** et bouton **Stop**. **Aucun contrôle caméra** pendant la
    dépose.
11. À la fin : retour en **position de prise de vue**, **acquisition**, et une **modale de
    fin** montrant la vue et le bilan. Un bouton **imprime un rapport PDF** reprenant les
    mêmes informations, vue comprise. Un autre bouton **acquitte** le travail.
12. Une fois acquitté : **homing**, puis retour à l'écran principal.

**Le détail de l'étape 9 — comment une zone est déposée :**

- Les zones sont parcourues **par rangées** (voir décision D2 ci-dessous).
- Pour **chaque zone** : la buse va d'abord au **`(0,0)` du repère de la zone**, à hauteur
  de transit, et y marque un temps.
- Pour **chaque cordon** de la zone : aller au premier point à hauteur de transit →
  descendre à hauteur de dépose → **amorçage** (extruder à l'arrêt pendant `N` secondes) →
  suivre la polyline en extrudant → **couper l'extrusion `X` mm avant la fin** et finir le
  tracé à vide → remonter à hauteur de transit.
- **Entre deux cordons, tout déplacement se fait à hauteur de transit.** Jamais de
  déplacement XY à hauteur de dépose : la buse traînerait dans la pâte.

> **Pourquoi les deux tempos.** La pâte thermique est très visqueuse. Au démarrage elle met
> un temps à sortir : sans amorçage, le début du cordon est vide. À l'arrêt elle continue de
> sortir sous la pression accumulée dans la seringue : sans anticipation, le cordon bave en
> fin de tracé. Les deux réglages compensent la même inertie, aux deux bouts.

##### B. Les quatorze points tranchés le 2026-08-03

Chaque décision est notée **avec son motif** : le motif est ce qui empêche de la
« corriger » plus tard en croyant réparer un oubli.

| # | Point | Décision | Motif |
|---|---|---|---|
| **D1** | Coordonnées de prise de vue | Paramètre `(x, y, z)` dans `local_config.json`, **valeur par défaut = le homing** `(0,0,0)` | C'est une caractéristique de la **machine**, pas du produit : caméra fixe sur le bâti (POC) contre caméra solidaire de la seringue (CNC). Elle n'a donc rien à faire dans le fichier de préparation. Sur le POC le défaut convient ; sur la CNC c'est l'action `M10` |
| **D2** | Ordre des zones | **Par rangées** : tri par `y` croissant, puis `x` croissant à `y` égal. Égalité **à une tolérance près**, paramétrable | Lecture directe de la consigne « balayage croissant x puis y ». La tolérance n'est pas un détail : la vision ne rendra **jamais** deux `y` exactement égaux, donc une comparaison stricte ferait un tri en escalier imprévisible. Regrouper en rangées si l'écart en `y` est inférieur à la moitié d'une hauteur de zone |
| **D3** | Stop | Arrêt immédiat des actionneurs, puis la **modale de fin en mode interrompu** (zones faites / zone interrompue / non commencées, rapport PDF possible), puis retour à l'accueil | Concilie les deux consignes de l'étudiant — « stop renvoie à l'accueil » et « l'opérateur voit où on s'est arrêté ». Sans ce bilan, plus rien ne dit quelles pièces ont reçu de la pâte : inacceptable en traçabilité automobile |
| **D4** | Découpage | **Cinq sous-lots D1 → D5**, extrusion réelle isolée en D4 | Soutenance blanche le 05/08 : il faut du **montrable** avant. Et l'extrusion demandera des essais visuels à répétition — la laisser dans le chemin critique bloquerait tout le reste |
| **D5** | Forme des tempos | Amorçage en **secondes**, anticipation de fin en **mm** | Chaque bout est exprimé dans l'unité où on l'observe : on regarde la pâte sortir (durée), on regarde le cordon dépasser (longueur). Une anticipation exprimée en secondes se **décalerait toute seule** dès qu'on changerait la vitesse de dépose |
| **D6** | Où vivent les tempos | Dans **`Settings`**, donc enregistrés **par préparation** et réglables dans la fenêtre de paramètres existante | Ils dépendent de la pâte et du produit, pas de la machine. Un produit à cordons courts n'a pas les mêmes réglages qu'un produit à longs cordons |
| **D7** | Cohérence fichier ↔ photo | **La photo fait foi**, avec **contrôle de taille produit** : une zone vue dont la taille s'écarte de `product_size_mm` au-delà de la tolérance est marquée **non sélectionnable**, motif affiché | La géométrie fraîche est la seule vérité — le plateau a pu bouger ou être remonté. Mais les cordons ont été tracés pour **ce** produit : sur un autre format, ils débordent. Le contrôle protège sans figer |
| **D8** | Zéro de zone | **Vrai mouvement visible** : la buse s'y rend à hauteur de transit et y marque un temps | Coûte ~1 s par zone et rend visible à l'œil la justesse de la conversion zone → plateau → machine — **qui n'a jamais été validée sur machine** (`M4`). C'est le seul contrôle disponible tant que la dépose se fait sans pâte, et il est parlant en démonstration |
| **D9** | Rapport PDF | **Global en nominal** (vue de fin, produit, nombre de zones, temps total) ; **détail par zone uniquement si interrompu** | En nominal, un tableau où toutes les lignes disent « fait » n'apporte rien et noie l'information. Après un arrêt, c'est exactement l'inverse |
| **D10** | Sélection par défaut | **Aucune zone présélectionnée** | Déposer sur une zone vide gaspille de la pâte et salit le plateau. La sélection doit être un acte délibéré, pas un défaut qu'on oublie de corriger |
| **D11** | Pause | La buse **reste en place**, on assume que la pâte s'écoule un peu ; rien n'en est tenu compte à la reprise | Choix explicite de l'étudiant. Relever la buse ajouterait deux mouvements et un état à gérer, pour un gain qu'il juge inutile |
| **D12** | Contrôle de course | **Avant** de lancer le moindre mouvement, vérifier que toutes les coordonnées machine sont dans le domaine atteignable. Sinon : échec du lancement avec un message **nommant la zone fautive** | Conséquence directe de `M2 bis` : `MACHINE_ORIGIN_Y = −2.0` rend la bande des **2 mm bas du plateau hors course**. Sans ce contrôle, Marlin rognerait les coordonnées **en silence** et la dépose sortirait déformée sans que rien ne le signale |
| **D13** | Barre de progression | Fondée sur la **longueur déposée cumulée / longueur totale**, pas sur le nombre de steps | Les steps n'ont pas la même durée : un cordon de 80 mm et un déplacement de 2 mm comptent pareil. Une barre en steps avancerait par à-coups et mentirait sur le temps restant |
| **D14** | Temps affiché | **Chronomètre réel**, pas une estimation | C'est ce que demande l'étudiant (« temps total écoulé »), et une estimation exigerait un modèle d'accélération de la machine qu'on n'a pas |

##### C. Nouveaux paramètres et où ils vivent

| Paramètre | Emplacement | Défaut | Remarque |
|---|---|---|---|
| `photo_position_x/y/z` | `local_config.json` + `config.py` | `(0, 0, 0)` = homing | POC : convient tel quel. CNC : action `M10` |
| `MACHINE_ORIGIN_X` | `config.py` | **`6.0`** | ⚠️ remplace `5.0` — **point 0 de D1** |
| `MACHINE_ORIGIN_Y` | `config.py` | **`−2.0`** | ⚠️ remplace `0.0` — **point 0 de D1** |
| `machine_travel_x/y_max_mm` | `local_config.json` | course de la machine | Pour le contrôle de course (D12) |
| `priming_seconds` | `Settings` (préparation) | `0.0` | Amorçage. `0` = comportement actuel, donc D1 ne change rien tant qu'on ne règle pas |
| `end_anticipation_mm` | `Settings` (préparation) | `0.0` | Anticipation de fin de cordon |
| `retract_mm` | `Settings` (préparation) | `0.0` | Rétraction entre deux cordons. Prévu mais **non utilisé avant D4** — à évaluer avec la pâte réelle |
| `row_tolerance_mm` | `Settings` (préparation) | moitié d'une hauteur de zone | Regroupement en rangées (D2) |

##### D. Découpage en cinq sous-lots

> ### ✅ BILAN DE LIVRAISON D3 (2026-08-04, `v0.5.2`)
>
> **300 tests** (+22). Photo de fin, rapport PDF multi-zones selon la décision D9, bouton
> d'impression qui ne ferme pas le bilan.
>
> **Choix de conception** : le CONTENU du rapport est séparé du RENDU
> (`reporter.plateau_report_lines()`). La règle D9 est une règle de contenu — la vérifier
> à travers un PDF compressé aurait été fragile.
>
> **Point de sûreté** : après un ARRÊT, la machine n'est **pas** redéplacée. `M112` met
> Marlin hors service jusqu'au redémarrage ; on photographie là où elle s'est arrêtée, et
> le rapport dit que le cadrage n'est pas celui de référence — sans quoi on comparerait
> deux rapports en croyant comparer deux plateaux.
>
> **Trois défauts existants trouvés en chemin**, tous silencieux :
> 1. **Couleurs inversées dans TOUS les rapports depuis la Phase 7** : `cvtColor(BGR2RGB)`
>    avant `cv2.imwrite`, qui fait déjà la conversion.
> 2. **Deux rapports d'une même seconde s'écrasaient** — nom de fichier horodaté à la
>    seconde. Sur un document de traçabilité, perdre un rapport sans le dire est
>    inacceptable : on suffixe désormais.
> 3. **Dossier de sortie relatif** (`"reports"`), qui suivait le répertoire courant. Un
>    lancement par raccourci ou par service dispersait les rapports. Devenu
>    `config.REPORTS_DIR`, absolu, comme `PREPARATIONS_DIR`.
>
> **Vérification par mutation** reconduite : 7 mutations, toutes attrapées.

> ### ✅ BILAN DE LIVRAISON D1 + D2 (2026-08-04, `v0.5.1`)
>
> Les deux sous-lots sont **livrés**, avec **278 tests** (+70 sur la session). La
> spécification ci-dessous est conservée telle quelle — elle documente ce qui était prévu.
> Écarts et découvertes :
>
> **Écart de périmètre assumé.** D1 devait ne toucher aucun fichier de `gui/`.
> `gui/dialogs.py` a été modifié : `SettingsDialog` reconstruisait un `Settings` neuf à
> partir de ses seuls widgets et **effaçait silencieusement les quatre nouveaux
> réglages**. Inoffensif aujourd'hui (ils valent 0), destructeur dès D4.
>
> **La progression suit le CHEMIN, pas la longueur déposée** (décision D13 affinée). Les
> déplacements à vide prennent du temps eux aussi : les ignorer ferait stagner la barre.
>
> **Quatre découvertes machine**, toutes du même genre — un résultat plausible qui ne
> l'est pas :
> 1. `Machine.move_to()` envoie `G1 X Y` **puis** `G1 Z`. Un déplacement XY a donc lieu à
>    la hauteur du step **précédent**. Deux conséquences : la remontée de fin de cordon est
>    indispensable, et il a fallu un `move_z()` pour se dégager après le homing — sans quoi
>    la buse traversait le plateau à la hauteur du homing. **L'invariant I2 visait la
>    mauvaise hauteur** et ne détectait pas la traînée ; corrigé.
> 2. **Marge de dégagement** en dépose à blanc (`DRY_RUN_Z_CLEARANCE_MM`, 2 mm) : la
>    hauteur du homing seule passe trop près des zones.
> 3. **`M1` faite** : 205,5 mm centre à centre, soit **13,5 mm d'écart** avec la valeur
>    supposée. Nouvelles clés `work_area_*_mm` pour saisir la mesure centre-à-centre
>    directement — saisir cette grandeur dans `plateau_size_mm` retrancherait une seconde
>    fois les 28 mm du marqueur.
> 4. **Photo périmée** : `Camera.capture()` rendait une image du tampon vieille de tout le
>    homing. Photo nette, marqueurs dedans, diagnostic vert, zones fausses. Corrigé par un
>    vidage du tampon.
>
> **Homing avant TOUTE capture** (demandé le 2026-08-04) : les trois écrans qui
> photographient partagent `gui/workers.py::PhotoPositionWorker`. ⚠️ Coût réel : 30 à 60 s
> par photo, y compris pour un simple « Reprendre ». Une variante moins chère existe —
> homer à l'**entrée** de l'écran puis se contenter d'un retour en position — à basculer
> si l'usage le demande. L'écran de calibration ChArUco est **volontairement exclu** : la
> mire est tenue à la main, 15 poses × 45 s pour aucun gain.
>
> **Méthode employée, à reconduire** : chaque batterie de tests a été validée par
> **mutation** — on casse volontairement le code pour vérifier que les tests réagissent.
> Trois défauts de test ont ainsi été trouvés alors que tout était vert : l'invariant I2
> inopérant, une docstring qui attribuait à une ligne un rôle qu'elle n'avait pas, et un
> avertissement écrit puis écrasé avant d'être lu.

**🔵 D1 — Le planner multi-zones et la dépose à blanc** (`v0.5.0`) — *aucune IHM touchée*

0. **`config.py` : `MACHINE_ORIGIN_X = 6.0`, `MACHINE_ORIGIN_Y = −2.0`.** Réécrire le pavé
   de commentaire : la réserve sur Y est levée, et elle était fondée. **À faire en premier.**
1. `PathPlanner.generate_plateau_path(zones, cordons, settings, dry_run)` → la liste de
   steps de **tout le plateau**, zones × cordons.
2. L'ordre de balayage par rangées, avec la tolérance de regroupement (D2).
3. Le passage au zéro de chaque zone (D8).
4. Amorçage et anticipation de fin (D5) — codés, mais neutres tant que les paramètres
   valent `0`.
5. **Le mode « dépose à blanc »** : `amount = 0` partout et `z_travel = z_dispense = Z du
   homing`, donc **aucun mouvement en Z**. C'est ce qui rend la démonstration sûre sans
   `M3`, et c'est utile bien au-delà de l'oral (essayer un nouveau plateau sans gâcher de
   pâte).
6. `check_machine_limits(steps)` → la liste des dépassements, avec la zone fautive (D12).
7. Les nouveaux paramètres de la section C.

**Critère de fin** : `pytest` vert, aucun fichier de `gui/` modifié.

**🟢 D2 — L'écran d'exécution** (`v0.5.1`) — ***c'est le livrable de la soutenance blanche***

Le parcours complet des étapes 1 à 12, dans un nouvel écran `gui/screen_execution.py` :
choix du fichier, acquisition, affichage valides/invalides, sélection au clic avec les
cordons dessinés, modale de confirmation, modale de progression (barre, zones faites,
chronomètre, Pause, Stop), retour à l'accueil. Le `RunWorker` existant est étendu — pause,
stop, et progression en longueur déposée.

**Critère de fin** : la machine parcourt un plateau réel **en l'air**, du bouton d'accueil
jusqu'au retour à l'accueil, sans une goutte de pâte.

**🟡 D3 — Photo de fin et rapport PDF** (`v0.5.2`)

Retour en position de prise de vue, acquisition, modale de fin, et le PDF selon D9 —
global en nominal, détaillé par zone si interrompu.

**🟠 D4 — L'extrusion réelle** (`v0.5.3`) — *session à l'atelier, avec la pâte*

Activer l'extrusion, régler `priming_seconds` et `end_anticipation_mm` à l'œil, évaluer
`retract_mm`. **Demande `M3`** (hauteur Z de la pointe). Prévoir des essais à répétition :
c'est le sous-lot le moins prévisible, d'où son isolement.

**🔴 D5 — Bascule du point d'entrée et retrait de `screen_zone.py`** (`v0.6.0`)

⚠️ **Seulement après que D2 a été validé sur machine.** `screen_zone.py` est encore
aujourd'hui **le seul chemin qui dépose vraiment** : le retirer avant aurait pour effet
qu'un échec de D2 laisserait le projet sans aucun chemin fonctionnel.

##### E. Les invariants à tester — le filet anti-régression

L'étudiant demande une batterie de tests par sous-lot, la dépose étant la fonction
critique de la machine. Les invariants ci-dessous sont **des propriétés du résultat**, pas
des redites du code : ils survivent à une réécriture interne.

| # | Invariant | Ce qu'il attrape |
|---|---|---|
| **I1** | Aucun step `dispense` à une hauteur autre que `z_dispense` | Une dépose en l'air, ou dans la pièce |
| **I2** | Entre la fin d'un cordon et le début du suivant, **tout** déplacement XY est à `z_travel` | La buse qui traîne dans la pâte déjà posée — le défaut le plus coûteux visuellement |
| **I3** | Chaque zone sélectionnée apparaît **exactement une fois** | Une zone oubliée, ou déposée deux fois |
| **I4** | L'ordre de balayage est le même quel que soit l'ordre dans lequel les zones sont fournies | Un tri qui dépendrait de l'ordre de détection de la vision, donc instable d'une photo à l'autre. **Tester avec une liste volontairement mélangée** |
| **I5** | En dépose à blanc : aucun step n'a `amount > 0`, et **aucun step ne change Z** | Une extrusion ou une descente accidentelle pendant la démonstration |
| **I6** | Longueur déposée = (somme des longueurs de cordons − anticipations) × nombre de zones | Une erreur de facteur, un cordon compté deux fois |
| **I7** | Un cordon qui descend sous `plateau_y = 2` fait **échouer le lancement**, avec un message nommant la zone | Le silence de Marlin qui rogne les coordonnées hors course |
| **I8** | La conversion zone → plateau → machine est vérifiée sur un **point intérieur d'un cordon**, jamais sur un coin de zone | ⚠️ **Règle de méthode du 2026-08-02** : un ajustement retombe toujours juste sur ses propres points d'appui. Un test sur les coins ne prouverait rien — c'est exactement ainsi que le défaut du lot C2bis avait échappé à 193 tests verts |
| **I9** | Test « boussole » : une zone plus à droite sur le plateau donne un X machine **plus grand** ; plus haut donne un Y machine **plus grand** | Une inversion de signe, un miroir. Assertif sur le **sens**, pas sur une valeur |
| **I10** | **Test doré** : un plateau de référence (3 zones × 2 cordons) produit une séquence de steps figée | Le filet le plus large. C'est lui qui protégera les sessions D3, D4 et D5 des régressions sur D1 |

⚠️ **`M4` reste ouverte** : `I9` épingle la convention *du logiciel*, pas le sens réel des
axes de la machine. C'est le passage au zéro de chaque zone (D8), observé à l'œil pendant
D2, qui la lèvera.

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
- [x] **`MACHINE_ORIGIN_X/Y` remesuré** (2026-08-02, action `M2`) : `M114` buse au-dessus du marqueur **2** → `X = 5.0`, `Y = 0.0` (remplace 20/50, qui dataient de deux conventions en arrière). Repère de home vérifié : pas de `X_MIN_POS` ni de `M206`. ⚠️ Réserve sur Y non levée (compteur de pas à 0 exact → butée possible) → action `M2 bis` en section 7 bis
- [x] **Étape 2 — LOT A livré (v0.2.0, 2026-08-01)** : géométrie des zones de dépose dans `vision.py` (`detect_deposit_zones_mm`, `PlateauLayout`, `DepositZone`). Détail des règles en `MANUEL_MAINTENANCE.md` section 1 et `CONCEPTION.md` section 4.2 bis
- [x] **Étape 2 — LOT B livré (v0.3.0, 2026-08-01)** : `modules/preparation.py` (`Cordon`, `Settings`, `Preparation` + persistance) et transfert de repère `to_plateau_mm`/`to_zone_mm` sur `DepositZone`. Format documenté en `CONCEPTION.md` section 6 et `MANUEL_MAINTENANCE.md` section 6.1. Les deux seuils de zone ont été mis dans `Settings` (donc enregistrés par plateau) — question du rituel v0.2.0 tranchée dans ce sens
- [x] **Étape 2 — LOT C1 livré (v0.4.0, 2026-08-01)** : `gui/screen_plateau.py` — écran « Créer un plateau », saisie du produit, capture, détection des zones, restitution visuelle du diagnostic, choix continuer/abandonner. 13 tests `pytest-qt`. Navigation : bouton sur l'écran 1, cohabitation avec le cycle historique (option **a**, la bascule en point d'entrée principal se fera au lot D)
- [x] **Étape 2 — LOT C2bis livré (v0.4.2, 2026-08-02)** : repère plateau orthonormé — origine au marqueur **2** (bas-gauche), **Y vers le haut**, tag 0 en contrôle de cohérence. Retournement explicite de Y dans les trois `warp_*`, bascule de toute la logique de signe des zones, repère de zone à l'origine bas-gauche, `FORMAT_VERSION` → 2 avec conversion des fichiers v1, `plateau_size_mm` en paramètre, choix de l'homographie regroupé dans `compute_plateau_reference()`. 161 tests (+7). Détail et bilan de livraison ci-dessus dans cette section ; conception en `CONCEPTION.md` section 4.2 ; maintenance en `MANUEL_MAINTENANCE.md` section 1
- [x] **Étape 2 — LOT C2 livré (v0.4.1, 2026-08-01)** : `VisionProcessor.warp_zone()` (redresse une zone **tournée**) + `gui/screen_cordons.py` — vue d'ensemble cliquable, zoom, tracé des polylines, undo/redo de profondeur 1, sélection/suppression, report sur toutes les zones. 25 tests. Validé à la main sur machine réelle par l'étudiant
- [x] **Étape 2 — LOT C3 livré (v0.4.3, 2026-08-02)** : autosave 5 s (hors polyline en cours, avec drapeau de modification pour ne pas user la carte SD), bouton d'enregistrement définitif, reprise d'un travail interrompu au démarrage (zone de référence restaurée — point critique), fenêtre de paramètres (2 vitesses + 2 seuils), et saisie de la référence produit en 3 voies. Nouveau fichier `gui/dialogs.py`. 193 tests (+32). Détail en `CONCEPTION.md` section 6.1
- [x] **LOT D cadré (2026-08-03)** — session de spécification, **aucune ligne de code**. Processus d'exécution décrit par l'étudiant, 14 points ambigus tranchés avec leurs motifs, découpage en 5 sous-lots `D1`→`D5` et 10 invariants de test. Spécification complète en section 8. Au passage : `M2 bis` levée (la réserve était fondée — `MACHINE_ORIGIN` devient `6.0 / −2.0`), `M2 ter` absorbée, `M3` recadrée sur le seul sous-lot D4, nouvelle action `M10` côté CNC
- [x] **LOT D1 livré (`v0.5.0`, 2026-08-04)** : `generate_plateau_path()` — parcours zones × cordons, ordre par rangées avec tolérance, passage visible au zéro de zone, tempos d'extrusion, **mode dépose à blanc**, contrôle de course. 37 tests, dont 10 invariants et un test doré. Un écart de périmètre assumé (`gui/dialogs.py`, perte silencieuse de réglages)
- [x] **LOT D2 livré (`v0.5.1`, 2026-08-04)** : `gui/screen_execution.py` + `gui/workers.py` — le parcours complet du bouton d'accueil au retour à l'accueil, 3 modales, worker de dépose avec pause et arrêt. 27 tests. ⚠️ **Critère de fin NON validé** : jamais essayé sur la machine
- [x] **LOT D3 livré (`v0.5.2`, 2026-08-04)** : retour en position de prise de vue, photo de fin, bilan avec vue, rapport PDF multi-zones (global en nominal, détail par zone si interrompu). 22 tests. Trois défauts existants corrigés au passage : couleurs inversées dans les rapports depuis la Phase 7, rapports d'une même seconde qui s'écrasaient, dossier de sortie relatif au répertoire courant
- [ ] **LOT D4** (`v0.5.3`) : extrusion réelle, réglage des tempos à l'œil — session atelier, demande `M3`
- [ ] **LOT D5** (`v0.6.0`) : bascule du point d'entrée et retrait de `screen_zone.py` — **seulement après validation de D2 sur machine**
- [x] **Saisie du nom de produit sur écran tactile** — ✅ **résolu le 2026-08-02 (lot C3)** : `ProductNameDialog` offre trois voies (saisie libre, choix dans la liste des produits enregistrés, champ vide → `BOITIER_X` au premier numéro libre). L'ancienne remarque : passe par une boîte de dialogue clavier. **Sans clavier physique sur le RPi, inutilisable.** À trancher avant le lot C3 — clavier virtuel système, ou sélection dans une liste de produits existants
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

### 📅 Calendrier des échéances 2026 (mis à jour 2026-08-25)

| Échéance | Date | Type | Statut |
|---|---|---|---|
| MàJ rapport entreprise | **17/07** (ven) | Rapport | ✅ |
| Soutenance blanche #1 (partie en anglais) | **22/07** (mer) | Entreprise | ✅ (confirmée 2026-08-25) |
| Soutenance blanche #2 | **05/08** (mer) | Entreprise | ✅ (confirmée 2026-08-25) |
| **2 machines fonctionnelles (Geeetech + CNC)** | **avant le 12/08** | Contrainte | ⚠️ non confirmé — voir Phase 10 §9, à revérifier |
| Soutenance blanche #3 | **12/08** (mer) | Entreprise | ✅ (confirmée 2026-08-25) |
| Rapport final | **17/08** (lun) | IUT | ✅ rendu (confirmé 2026-08-25) |
| **Soutenance blanche #4 (ajoutée)** | **28/08** (ven) | Entreprise | ⬜ à venir dans 3 jours |
| Soutenance finale (démo Geeetech acceptée) | **31/08** (lun) | IUT | ⬜ à venir dans 6 jours, inchangée |

> Calendrier initial du 2026-07-11 confirmé dans les grandes lignes le 2026-08-25, avec un
> ajout (soutenance #4 le 28/08) et une inconnue (le jalon des 2 machines fonctionnelles,
> non revérifié — voir la remarque en section 9, Partie B).

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
| **Ven 28** | 🎤 | **Soutenance blanche #4 (ajoutée)** — non prévue au calendrier initial du 11/07, confirmée le 2026-08-25 |
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
| 8 | Tests, robustesse, finitions (Geeetech) | 🔄 En cours | 7 / 3 (dépassement — ChArUco + zones de dépose lots A→C3 + repère plateau, refait deux fois le 2026-08-01 puis corrigé sur machine le 2026-08-02) |

**Sous-total Partie A : 21 sessions × ~2h = ~42h** (+ ~5,5 sessions pour les fonctionnalités actées le 2026-07-11 : ChArUco, cordons multiples, JSON, temps rapport)  
**Jalon A : Logiciel validé sur Geeetech ≈ 17 juillet 2026** (clôture Phase 8 + nouvelles fonctionnalités)

> **En parallèle de toute la Partie A** : rédaction du rapport (~1h/soir en semaine, chez soi)  
> **Jalon intermédiaire : premier draft rapport → 15 juin 2026** (à remettre avant les vacances)

### Partie B — Intégration sur CNC cible · deadline fin juillet 2026

| Phase | Description | Statut | Durée estimée |
|---|---|---|---|
| 9 | Assemblage de la CNC cible (mécanique + câblage) | 🔄 Quasi terminé (méca + carte + Marlin flashé) — reste câblage capteurs/moteurs | ~2-3 jours |
| 10 | Portage logiciel : adaptation `config.py` + tests sur CNC | 🔄 En cours — caméra CNC choisie (FIT0729), détection ArUco et calibration ChArUco faites, diagnostic homographie en vue oblique traité le 2026-08-25 (voir point de reprise §8) | 1+ / 2 sessions |
| 11 | Validation complète du système sur CNC cible | ⬜ À faire | 0 / 3 sessions |

**Jalon B : Système validé sur CNC ≈ 07/08 (avant la 3e soutenance blanche du 12/08)** — ⚠️
**date dépassée sans confirmation que le jalon est atteint** ; état réel du câblage/homing CNC
non revérifié le 2026-08-25, à faire en tout début de prochaine session plutôt que supposer.

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
| ~~Repère du plateau (2026-08-01)~~ | ~~Origine = marqueur 3 (haut-gauche), Y+ vers le bas~~ | **Remplacé le 2026-08-02 par la ligne ci-dessous.** Conservé pour l'historique : ce repère avait été choisi pour de bonnes raisons *locales* (coordonnées positives, correction du miroir vertical), et c'est en regardant le problème depuis la machine — pour le lot D — que le bon critère est apparu |
| Repère du plateau (2026-08-02, lot C2bis) | **Orthonormé, défini par trois tags** : origine = marqueur **2** (bas-gauche), X+ vers le tag 1, **Y+ vers le HAUT** vers le tag 3. Tag 0 = contrôle de cohérence. Table dans `vision.py::_plateau_corner_positions_mm()` | Aligne le repère logiciel sur le repère physique de la machine **avant** d'écrire le G-code (lot D) : la conversion vers le repère machine devient deux additions, plus une inversion isolée qu'il faut penser à écrire. Les coordonnées restent positives, l'origine étant toujours sur un coin. Contrepartie payée une fois : les trois `warp_*` doivent retourner Y explicitement, sans quoi le plateau s'affiche à l'envers |
| Capture automatique au rechargement (2026-08-02) | La photo se déclenche seule **dès que ≥ 2 marqueurs de coin sont vus**, avec un garde-temps de 5 s puis retour à la main. Uniquement au rechargement — jamais à la création ni après un « Reprendre » | Caméra fixe sur le bâti + zones vissées à demeure = cadrage toujours identique : l'appui sur « Capturer » ne fait prendre aucune décision, c'est un geste de plus sur un tactile. Attendre les MARQUEURS et non un simple délai : une temporisation aveugle déclencherait sur la première image venue (main dans le champ, exposition non stabilisée) et produirait un diagnostic à refaire. À la création l'opérateur pose les boîtiers, après un « Reprendre » il rectifie un défaut — dans les deux cas c'est lui qui sait quand c'est prêt |
| Recharger un plateau enregistré (2026-08-02) | Bouton **« Charger un plateau »** sur l'écran d'accueil, **distinct** de « Créer un plateau ». Ne liste que les préparations validées, jamais les autosaves | Créer et recharger sont deux intentions différentes : les confondre ferait risquer d'écraser un plateau en croyant en ouvrir un nouveau. Manque révélé par l'usage réel — le lot C3 ne couvrait que la reprise après plantage, pas la réutilisation du point 7 du processus cible |
| Origine plateau dans le repère machine (2026-08-03) | **`MACHINE_ORIGIN_X = 6.0`, `MACHINE_ORIGIN_Y = −2.0`** — déduits du relevé « pointe de seringue au homing = plateau `(−6, +2)` ». Remplace `5.0 / 0.0` du 2026-08-02 | Le `Y = 0` du 02/08 était une **butée de fin de course, pas une mesure** : le compteur de pas à 0 exact l'avait fait soupçonner, le relevé le confirme. La valeur vise désormais la **pointe** et non la buse, ce qui absorbe `M2 ter`. Recoupement : l'écart buse↔pointe ressort à `(−1, +2)` mm. **Conséquence acquise : une bande de 2 mm en bas du plateau est hors course** |
| Position de prise de vue (2026-08-03) | Coordonnées `(x, y, z)` où la machine se place avant toute acquisition, **paramètre de machine** (`local_config.json`), défaut = le homing | La caméra est **fixe sur le bâti** sur le POC et **solidaire de la seringue** sur la CNC : le point où l'on photographie n'est pas la même chose sur les deux machines. En faire un paramètre est ce qui rend le portage CNC transparent — sinon la position serait câblée dans le code de l'écran |
| Ordre de balayage des zones (2026-08-03) | **Par rangées** : tri `y` croissant puis `x` croissant, l'égalité en `y` étant appréciée **à une tolérance** (moitié d'une hauteur de zone) | Ordre prévisible pour l'opérateur, qui voit une pièce se finir avant la suivante et peut la retirer. La tolérance est indispensable : la vision ne rend jamais deux `y` exactement égaux, et une comparaison stricte produirait un tri en escalier changeant d'une photo à l'autre. Un parcours « au plus court » a été écarté : gain négligeable (les déplacements à vide sont rapides), ordre imprévisible, code nettement plus lourd |
| Dépose à blanc (2026-08-03) | Mode où l'extrusion est neutralisée (`amount = 0`) **et** où `z_travel = z_dispense = Z du homing`, donc aucun mouvement en Z | Permet de valider tout le parcours — vision, sélection, conversion de repères, mouvement — **sans `M3` et sans gâcher de pâte**. Né d'une contrainte de calendrier (soutenance blanche du 05/08), mais garde sa valeur ensuite : c'est le moyen d'essayer un plateau neuf sans risque |
| Contrôle de course avant lancement (2026-08-03) | Toutes les coordonnées machine sont vérifiées **avant** le premier mouvement ; un dépassement fait échouer le lancement avec un message nommant la zone fautive | Marlin **rogne les coordonnées hors course en silence** : sans ce contrôle, une dépose déformée passerait pour une erreur de vision ou de calibration. Rendu nécessaire par l'origine `Y = −2.0`, qui met le bas du plateau hors d'atteinte |
| Confirmation d'écrasement (2026-08-02) | Demandée si un plateau du même nom existe et provient d'un **autre** travail (comparaison sur `created_at`). **« Non » par défaut**. Aucune question pour le même travail | Le nom du produit sert de nom de fichier et le dialogue de création propose les produits existants : reprendre un nom par mégarde est facile, et l'écriture est un simple remplacement. Mais demander à chaque enregistrement en ferait un réflexe validé sans lire — une protection qui ne protège plus |
| Repli 2-3 marqueurs et miroir (2026-08-02) | La similitude est ajustée vers un repère intermédiaire **retourné en Y**, puis composée avec une matrice de retournement (déterminant −1) pour revenir au repère plateau | `estimateAffinePartial2D` ajuste une similitude, de déterminant toujours positif : elle **ne sait pas mirroiter**. Or passer du repère image (Y bas) au repère plateau (Y haut) EST un miroir. Sans cette parade, le repli — **mode nominal sur la Geeetech** — rendait un repère à l'ancienne convention et plus aucune zone n'était détectée. Défaut trouvé sur la machine le 2026-08-02, invisible à 193 tests verts |
| Test d'une transformation géométrique (2026-08-02) | **Toujours vérifier sur un point qui n'a PAS servi à l'ajustement** | Leçon du défaut ci-dessus : les tests du repli ne contrôlaient que les points d'appui, qui retombent juste quelle que soit l'orientation — c'est la définition d'un ajustement. Un ajustement qui retombe sur ses propres points ne prouve rien |
| Repère d'une zone (2026-08-02) | Origine = coin **bas-gauche** (`DepositZone.origin_mm` = `corners_mm[3]`), Y montant — même convention que le plateau | Garder deux conventions opposées réintroduirait exactement la confusion que le lot C2bis supprime. Les formules de `to_plateau_mm`/`to_zone_mm` sont inchangées : seule l'origine change de coin, ce qu'aucun test de réversibilité ne peut attraper |
| Contrôle de cohérence du plateau (2026-08-02) | Écart entre la position vue du tag 0 et sa position attendue, mesuré contre une **similitude ajustée sur les tags 2/1/3** | Avec 4 points, `getPerspectiveTransform` ajuste sans résidu : mesurer l'écart sur la matrice de `compute_homography()` le donnerait **nul par construction**, quelle que soit la réalité du plateau. L'indicateur n'indiquerait rien |
| Choix de l'homographie (2026-08-02) | Une seule méthode, `compute_plateau_reference()`, qui retourne la matrice **et** la qualité du repère (mode, origine extrapolée, écart du tag 0) | La règle « 4 tags → exact, 2-3 → approché » était écrite **deux fois** (`screen_plateau.py`, `screen_zone.py`). Deux copies divergent toujours, et c'est celle qu'on ne relit pas qui reste juste. Retourner une matrice nue obligerait par ailleurs chaque appelant à redéduire ce qu'il doit dire à l'opérateur |
| Taille du plateau (2026-08-02) | `plateau_size_mm` surchargeable dans `local_config.json` (220 mm par défaut) | Sert de **repli quand les 4 tags ne sont pas détectés**, donc dans le mode nominal de la Geeetech où l'origine est extrapolée. Toute erreur dessus décale toute la dépose et aucun test ne peut le détecter → action `M1` |
| Fichiers de préparation v1 (2026-08-02) | `FORMAT_VERSION` → 2, fichiers v1 **convertis au chargement** puis réécrits, conversion signalée à l'opérateur | Le contrôle de version ne refusait que les fichiers plus RÉCENTS : un v1 aurait été relu silencieusement à l'envers. Refuser sec ferait perdre à l'opérateur un plateau déjà tracé pour une raison purement interne au logiciel |
| Choix du matériel (2026-08-01) | 2 listes déroulantes sur l'écran 1. Les écrans émettent `camera_selected`/`machine_port_selected` ; **seul `MainApp` applique** le changement | `MainApp` est propriétaire de `Camera` et `Machine` partagées. Si un écran les remplaçait lui-même, deux endroits ouvriraient la caméra et un handle finirait non libéré |
| Scan des caméras | `Camera.list_devices(exclude=...)` ne sonde **jamais** un index déjà ouvert | Un second handle DirectShow sur le même périphérique casse le flux du premier à son `release()` — symptôme trompeur « Camera deconnectee » (2026-08-01) |
| Zones de dépose (2026-08-01) | 2 marqueurs par zone, `id(bas-droit) = id(haut-gauche) + 1`, IDs ≥ 4. Ambiguïté d'appariement levée par la **longueur de diagonale la plus représentée**, les zones portant toutes le même produit | Aucun moyen local de savoir si le tag 5 clôt `(4,5)` ou ouvre `(5,6)`. L'invariante « même produit partout » est la seule information globale disponible |
| Tri par signe des diagonales | Composantes `(+,−)` = zone plausible · `(−,+)` = zone inversée signalée · **signes identiques = paire fantôme écartée**. ⚠️ Signes inversés au lot C2bis (c'était `(+,+)` pour une zone plausible) | Sur un plateau en grille, la paire fantôme entre deux zones voisines a la **même longueur** que les vraies (symétrie) : le filtrage par longueur seul laissait un plateau sain devenir inexploitable par conflit. C'est le premier filtre à basculer quand l'axe Y change de sens |
| Rotation d'une zone | `θ = angle(diagonale) − angle(w, −h)` (signe moins depuis le lot C2bis), **solution unique**, positive dans le sens trigonométrique. Pas de choix entre solutions symétriques | Le format `(w, h)` étant déduit de la médiane sur toutes les zones, il est *orienté* : l'ambiguïté n'existe plus. Retenir « la plus petite rotation » ferait ressortir une zone à 25° comme étant à 2°, rendant l'anomalie de montage indétectable |
| Appartenance des cordons | Les cordons appartiennent à la **préparation**, pas à une zone. `reference_zone_id` mémorise celle sur laquelle ils ont été tracés | Toutes les zones portent le même produit : les dupliquer par zone créerait autant de copies à maintenir cohérentes pour zéro information supplémentaire |
| Zone de référence figée | La **première** zone ouverte devient le repère de travail. En ouvrir une autre y affiche les mêmes cordons sans changer de repère | Les cordons sont exprimés dans ce repère : en changer les déplacerait |
| Règle d'interaction du tracé | Tracé en cours → tout clic ajoute un point · hors tracé → clic près d'un cordon = sélection, ailleurs = nouveau tracé | Permet de tout faire au clic sans bouton de mode. Sans la priorité au tracé en cours, un point posé près d'un cordon existant le sélectionnerait au lieu de continuer |
| Double-clic indépendant de Qt | Le double-clic pose le point **seulement s'il n'est pas déjà le dernier** | En usage réel un `press` précède le double-clic et a posé le point ; `QTest.mouseDClick` n'envoie que le double-clic. Le garde-fou rend le résultat identique dans les deux cas et insensible aux versions de Qt |
| Coordonnées des cordons | **mm relatifs à la zone** (origine au coin **bas-gauche** depuis le lot C2bis), jamais en pixels ni en mm plateau | Rend le même cordon applicable à toutes les zones, et insensible à un déplacement de la caméra |
| Quantité de pâte | Deux **paramètres globaux** — vitesse de déplacement et vitesse d'extrusion — et non un attribut par cordon | C'est le rapport des deux qui fixe l'épaisseur du boudin ; un réglage par cordon serait une complexité sans usage identifié |
| Persistance | 2 fichiers : `<produit>.json` (validé) et `<produit>.autosave.json` (toutes les 5 s). L'enregistrement définitif supprime l'autosave. Écriture **atomique** | Un autosave présent au démarrage signale un travail interrompu, et rien d'autre. Une écriture non atomique coupée en cours laisserait un fichier tronqué — un filet anti-plantage qui ne protège de rien |
| Autosave conditionnelle (2026-08-02) | Le timer bat toutes les 5 s mais **n'écrit que si un drapeau de modification est levé**, abaissé seulement après une écriture réussie | Écrire à chaque battement réécrirait le fichier indéfiniment, y compris à l'arrêt : sur la **carte SD** du RPi, usure gratuite. Abaisser le drapeau avant l'écriture ferait perdre la période en cas d'échec |
| Reprise d'un travail interrompu (2026-08-02) | Recharge cordons + paramètres + **zone de référence**, puis demande une **nouvelle photo**. L'image n'est pas persistée | Les cordons étant en mm relatifs à la zone, une nouvelle photo ne les invalide pas — persister l'image ajouterait une gestion de fichiers annexes pour rien. ⚠️ La zone de référence doit être restaurée AVANT tout affichage, sinon les cordons sont réinterprétés dans un repère qui n'est pas le leur, en silence |
| Réponse « Non » à la reprise | **Conserve** le fichier d'autosave ; la question est reposée au démarrage suivant | On ne détruit pas un travail sur une réponse hâtive à une question posée au lancement |
| Nom de produit par défaut (2026-08-02) | `BOITIER_X` au **premier numéro libre**, autosaves compris. Calculé à la lecture de `product_name`, pas à l'ouverture du dialogue | Aucun état hors du dossier des préparations → fonctionne sur un dépôt fraîchement cloné. Le calculer à l'ouverture ferait avancer la numérotation à chaque dialogue annulé ; ignorer les autosaves ferait écraser un travail inachevé |
| Dialogue de paramètres | Rend un **nouvel** objet `Settings` au lieu de modifier celui reçu | C'est ce qui rend le bouton « Annuler » réellement sans effet |
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
```

> **Pas de signature Claude.** Aucune ligne `Co-Authored-By: Claude ...` dans les commits,
> ni aucune mention/signature Claude dans un document écrit (`CLAUDE.md`, `CONCEPTION.md`,
> manuels...) — demandé explicitement le 2026-08-25.

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
| 2026-08-25 | **Session (`v0.6.1`) — Diagnostic vision CNC : deux causes superposées à la mauvaise détection des zones en vue oblique, et resynchronisation d'un écart de journal de 20 jours.** Reprise après un vide de journal (dernière entrée : 2026-08-05) : confirmé en conversation que le rapport final IUT est rendu, que les soutenances blanches #2 et #3 ont eu lieu (une 4e ajoutée le 28/08, en plus de la finale du 31/08), et que **le lot D2 est désormais validé sur machine réelle** — le point de reprise du 05/08 (jamais essayé) était donc caduc. Sur la CNC (caméra changée pour une **DFRobot FIT0729** montée décalée du plateau à ~45°, au lieu du montage vertical de la Geeetech), les zones détectées ne correspondaient plus au plateau. Diagnostic mené par élimination avec l'étudiant plutôt que par lecture de code : (1) le mode 2-3 marqueurs (`estimateAffinePartial2D`, une similitude) ne peut pas corriger une perspective, quel que soit l'angle — confirmé sans conséquence pratique, le mode 4 marqueurs (`compute_homography()`, projectif) reconstruit correctement une fois les tags détectés ; (2) l'autofocus de la FIT0729 refait le point à chaque capture, floutant transitoirement les coins ArUco — négligeable en vue verticale, amplifié en vue oblique. Traité par deux nouvelles méthodes `Camera.set_autofocus()`/`Camera.set_focus()`, deux clés `local_config.json` (désactivées par défaut, sans effet sur la Philips), et un mode `tests/demo_camera.py --focus` pour trouver la valeur à l'œil. **Demande explicite de l'étudiant, traitée en fin de session** : retrait de toute signature Claude (`Co-Authored-By`) des commits et des documents — gabarit de commit de `CLAUDE.md` section 13 corrigé en conséquence. | 197 passés (+5), 12 sautés (matériel absent sur cette machine de dev), 97 erreurs préexistantes et confirmées indépendantes de la session (`pytest-qt` absent de cet environnement précis, vérifié par comparaison avant/après changement). Action `M12` créée (trouver `camera_focus_value` sur la CNC) ; `M10` (position de prise de vue CNC) toujours non mesurée, reportée par choix de l'étudiant. |
| 2026-08-05 | **Session 🏠 — Planches de soutenance et audit des mémoires. Aucun code applicatif touché.** Neuf planches produites dans la charte du deck existant (`assets/generate_bilan_soutenance.py`, qui **réutilise** les helpers et la palette de `generate_presentation.py` plutôt que de les redéfinir — une retouche de style se propage ainsi aux deux decks). Contenu : synoptique du processus métier, carte des 20 modules, bilan de l'acquis et du reste à faire, effort de portage CNC. **Tous les chiffres sont MESURÉS sur le dépôt**, avec la commande de rafraîchissement en commentaire au-dessus de chaque constante : c'est ce qui permet de les défendre en question. **Deux constats importants faits en préparant ces planches.** (1) Les descriptions de modules de l'ancienne présentation étaient **périmées** et décrivaient des choix abandonnés — caméra CSI au lieu d'USB, trajectoires en hachures au lieu de cordons, machine à états dans `main.py` alors que la navigation vit dans `app.py`. Les défendre en soutenance aurait obligé à justifier des décisions justement corrigées depuis. (2) L'argument central du portage CNC a été **vérifié et non supposé** : hors `config.py`, les seules occurrences de `/dev/ttyUSB0`, `COM3` ou `250000` dans le code sont dans des **commentaires**. 25 paramètres sont déjà externalisés hors du code, et il reste 9 valeurs numériques à ajuster, soit 0,09 % du code applicatif, pour zéro ligne de logique. **Audit des mémoires longues** demandé en cours de session : trois affirmations **fausses** trouvées dans le bloc de faits stables, celui qu'une session future lit en premier — zone de travail annoncée « 192×192 supposés, jamais mesurée » alors que `M1` est faite à 205,5 mm, dépose à blanc décrite sans sa marge de 2 mm, et actions listées `M1`–`M9` au lieu de `M1`–`M11`. La première contredisait frontalement une autre ligne du même fichier. Méthode employée : **confronter chaque affirmation chiffrée au code par un import réel**, et non relire — une mémoire qu'on relit sans exécuter se confirme elle-même. | 300 tests, inchangés. Géométrie des planches vérifiée par script après génération (débordements ET chevauchements) : deux défauts invisibles à la génération mais flagrants à la projection ont été attrapés ainsi. ⚠️ **Le critère de fin de D2 n'est toujours pas validé sur la machine** — c'est la priorité, devant D4 qui demande de toute façon l'atelier. |
| 2026-08-04 | **Session 🏠 (`v0.5.2`) — Lot D3 : photo de fin et rapport PDF multi-zones.** En fin de cycle nominal, la machine revient en position de prise de vue et photographie le plateau ; le bilan affiche cette vue et un bouton produit un PDF. **Point de sûreté tranché en écrivant** : après un ARRÊT, la machine n'est **pas** redéplacée — `M112` met Marlin hors service jusqu'au redémarrage, et lui demander de bouger échouerait en faisant attendre l'opérateur devant une machine bloquée. On photographie donc là où elle s'est immobilisée, et le rapport **dit** que le cadrage n'est pas celui de référence : sans ce mot, on comparerait deux rapports en croyant comparer deux plateaux. **Choix de conception** : le CONTENU du rapport est séparé de son RENDU (`plateau_report_lines()`), parce que la règle qui le gouverne — détail par zone uniquement si interrompu, décision D9 — est une règle de contenu, et que la vérifier à travers un PDF compressé aurait été fragile. **Trois défauts existants trouvés en chemin, tous silencieux.** (1) `reporter.py` appelait `cvtColor(BGR2RGB)` avant `cv2.imwrite`, qui fait déjà la conversion : **tous les rapports produits depuis la Phase 7 avaient le rouge et le bleu échangés** — peu visible sur un plateau grisâtre, mais faux. (2) Le nom de fichier n'ayant qu'un horodatage à la seconde, deux rapports produits dans la même seconde s'écrasaient ; réimprimer aussitôt après est pourtant un geste normal, et perdre un rapport sans le dire est inacceptable sur un document de traçabilité. (3) Le dossier de sortie était le chemin **relatif** `"reports"`, qui suit le répertoire courant : un lancement par raccourci, par service au démarrage du RPi ou par double-clic aurait dispersé les rapports sans que rien ne le signale — devenu `config.REPORTS_DIR`, absolu, sur le modèle de `PREPARATIONS_DIR`. La leçon vaut au-delà : **tout chemin de sortie doit être calculé depuis `os.path.dirname(__file__)`**, un fichier écrit au mauvais endroit ne provoquant aucune erreur. **Vérification par mutation reconduite** : 7 mutations, toutes attrapées — dont celle qui prouve que le test d'emplacement ne se contente pas de vérifier qu'un chemin est absolu (il pourrait l'être à partir du dossier courant, ce qui reproduirait le défaut) mais change réellement de répertoire courant. | 300 tests (+22). ⚠️ **Le critère de fin de D2 n'est TOUJOURS pas validé** : le cycle n'a jamais tourné sur la machine, et D3 s'empile dessus. Trois sous-lots reposent désormais sur du code qu'aucun test ne peut valider — le sens réel des axes (`M4`) reste inconnu. C'est la priorité, devant D4. |
| 2026-08-04 | **Session 🏠 (`v0.5.1`) — Lots D1 et D2 livrés : le planner multi-zones et l'écran d'exécution.** D1 rend `generate_plateau_path()`, qui produit la liste de steps de tout le plateau en coordonnées machine — ordre par rangées avec tolérance (la vision ne rend jamais deux ordonnées égales, un tri strict donnerait un ordre changeant d'une photo à l'autre), passage **visible** au zéro de chaque zone, tempos d'extrusion, mode **dépose à blanc**, contrôle de course. Aucun fichier de `gui/` n'était censé bouger ; `gui/dialogs.py` a dû l'être, `SettingsDialog` reconstruisant un `Settings` neuf à partir de ses seuls widgets et **effaçant silencieusement** les quatre nouveaux réglages — inoffensif tant qu'ils valent 0, destructeur dès D4. D2 ajoute `gui/screen_execution.py` et `gui/workers.py` : le cycle complet du bouton d'accueil au retour à l'accueil, trois modales, et un worker de dépose avec pause et arrêt. **La méthode a compté autant que le code : chaque batterie de tests a été validée par MUTATION** — on casse volontairement le code pour vérifier que les tests réagissent. Trois défauts de test ont ainsi été trouvés alors que tout était vert : l'invariant I2, censé attraper la buse qui traîne dans la pâte, regardait la hauteur du step qui bouge alors que `move_to()` envoie `G1 X Y` **puis** `G1 Z` — le déplacement XY a donc lieu à la hauteur du step PRÉCÉDENT ; une docstring attribuait à `self._paused = False` un rôle que la condition de boucle assurait déjà ; et un avertissement de cadrage était écrit dans la barre de statut puis **écrasé** par le diagnostic avant d'avoir été lu. **Quatre découvertes machine dans la foulée**, toutes de la même famille — un résultat plausible qui ne l'est pas. (1) La buse traversait le plateau à la hauteur du homing avant de monter : d'où `Machine.move_z()`, qui ne bouge que Z, et un dégagement systématique après chaque homing. (2) Marge de 2 mm ajoutée à la dépose à blanc, la hauteur du homing passant trop près des zones. (3) **`M1` faite : 205,5 mm centre à centre**, soit **13,5 mm d'écart** avec la valeur supposée — sur le repli 2 tags, le mode nominal de la Geeetech, cet écart décalait toute la dépose. Nouvelles clés `work_area_*_mm` pour saisir directement la mesure centre-à-centre : la mettre dans `plateau_size_mm` retrancherait une seconde fois les 28 mm du marqueur, en silence. (4) La photo analysée au second cycle était celle de la **fin du cycle précédent** — le tampon du pilote rend la plus ANCIENNE image, et personne ne lisait la caméra pendant les 30 à 60 s de homing. Photo nette, marqueurs dedans, diagnostic vert, zones fausses. Enfin, à la demande de l'étudiant, **toute capture d'image est désormais précédée d'un homing** et d'une mise en position, partagée entre les trois écrans concernés via `gui/workers.py` — au prix de 30 à 60 s par photo, y compris pour un « Reprendre ». L'écran de calibration ChArUco en est volontairement exclu : la mire est tenue à la main, 15 poses × 45 s pour aucun gain. | 278 tests (+70 sur la session), dont 37 pour D1 et 27 pour D2. ⚠️ **Le critère de fin de D2 n'est PAS validé** : « la machine parcourt un plateau réel en l'air » n'a jamais été essayé, la session s'étant faite à la maison. C'est la priorité absolue avant la soutenance du 05/08, avec `M11` (course réelle des axes), `M4` (sens des axes, qui se lève à l'œil au passage au zéro de zone) et `M7` (reporter la mesure du plateau sur le RPi). |
| 2026-08-03 | **Session 🏠 — Cadrage du lot D, aucune ligne de code** (demandé explicitement par l'étudiant). Il a décrit le processus d'exécution qu'il veut, de bout en bout ; onze points sous-définis ont été relevés et tranchés au fil de l'échange, plus trois décidés d'office et validés. **Deux contradictions ont été levées** : le bouton Stop devait « renvoyer à l'accueil » alors qu'il avait été acté la veille que l'opérateur voie où la dépose s'était arrêtée — réconcilié par une modale de bilan en mode interrompu, puis retour à l'accueil ; et la position de prise de vue ne peut pas valoir le homing sur les deux machines, la caméra étant fixe sur le bâti d'un côté et solidaire de la seringue de l'autre — devenue un paramètre de machine. **Résultat le plus important de la session : `M2 bis` levée, et la réserve était fondée.** L'étudiant a relevé la position de la pointe de seringue au homing dans le repère plateau — `(−6, +2)` mm — d'où `MACHINE_ORIGIN = (6.0, −2.0)`. Le `Y = 0` du 02/08 était donc bien une **butée de fin de course et non une mesure**, exactement ce que le compteur de pas à 0 exact laissait craindre ; il s'ensuit qu'une bande de 2 mm en bas du plateau est **hors course**, d'où la décision d'un contrôle de course avant lancement — Marlin rogne en silence. Le relevé visant la pointe et non la buse, `M2 ter` est absorbée (recoupement cohérent : écart buse↔pointe de `(−1, +2)` mm). **Découpage en 5 sous-lots** contraint par la soutenance blanche du 05/08 : l'extrusion réelle est isolée en D4, et un **mode « dépose à blanc »** (extrusion neutralisée, `z_travel = z_dispense = Z du homing`) permet de montrer tout le parcours en mouvement sans `M3` et sans gâcher de pâte — né d'une contrainte de calendrier, mais gardé ensuite pour essayer un plateau neuf sans risque. `M3` s'en trouve recadrée sur le seul D4, et une action `M10` est créée côté CNC. **10 invariants de test** consignés, dont la vérification de la conversion de repères sur un **point intérieur de cordon** et non sur un coin de zone — application directe de la leçon du 02/08. Spécification complète en section 8 |
| 2026-08-02 | **Session 🏠 (v0.4.3) — Étape 2, lot C3 : persistance et paramètres.** Câblage du modèle du lot B dans l'IHM, plus trois points qui ont demandé de vraies décisions. **(1)** La sauvegarde automatique bat toutes les 5 s mais n'écrit que si un drapeau de modification est levé, abaissé seulement après une écriture réussie : écrire à chaque battement userait gratuitement la carte SD du RPi, et abaisser le drapeau trop tôt ferait perdre une période en cas d'échec. Le tracé en cours reste exclu par construction. **(2)** Reprendre un travail interrompu ne restaure pas la photo — le fichier n'en contient pas : on recharge cordons, paramètres et zone de référence, puis on reprend une capture. C'est exactement ce que permet le choix du lot B de mémoriser les cordons en mm relatifs à la zone. Le piège identifié en écrivant le code : la zone de RÉFÉRENCE doit être restaurée avant tout affichage, sinon la première zone rouverte devient la nouvelle référence et les cordons sont réinterprétés dans un repère qui n'est pas le leur, **sans aucun signal** — même famille de faute silencieuse que le miroir vertical du lot C2bis. **(3)** La référence produit se saisit de trois façons (libre, liste des produits existants, ou champ vide → `BOITIER_X` au premier numéro libre), le clavier physique n'existant pas sur le RPi. Le numéro n'est calculé qu'à la validation, pour qu'un dialogue annulé n'en consomme aucun. Nouveau fichier `gui/dialogs.py`. **Puis, à l'essai sur la machine, trois suites imprévues.** **(a)** Aucune zone de dépose n'était plus détectée : `estimateAffinePartial2D` ajuste une **similitude**, de déterminant positif, qui **ne sait pas mirroiter** — or le repli 2-3 marqueurs doit passer d'un repère Y-bas (image) à un repère Y-haut (plateau), ce qui EST un miroir. Le repli rendait donc l'ANCIENNE convention et le filtre de signe écartait les vraies zones comme fantômes. Corrigé en ajustant la similitude vers un repère intermédiaire retourné, puis en composant avec le retournement. Défaut invisible à 193 tests verts, sur le chemin le plus emprunté du logiciel : les tests du repli ne vérifiaient que les points AYANT SERVI à l'ajustement, qui retombent juste quelle que soit l'orientation. **Règle qui en découle : vérifier une transformation sur un point qui n'a pas servi à l'ajuster.** **(b)** Manque révélé par l'usage : après un enregistrement définitif, plus rien ne menait au fichier validé — le lot C3 ne couvrait que la reprise après plantage, pas la **réutilisation** du point 7 du processus cible. Ajout d'un bouton « Charger un plateau », et d'une confirmation d'écrasement (avec « Non » par défaut) puisque le dialogue de création propose justement les noms existants. **(c)** Sur remarque de l'étudiant, la photo se prend désormais **seule** au rechargement — plateau vissé et caméra fixe, l'appui n'apportait aucune décision. Déclenchée sur la VUE des marqueurs et non sur un délai, avec garde-temps de 5 s ; volontairement pas à la création ni après un « Reprendre », où l'opérateur seul sait quand la scène est prête. | 209 passés (`pytest` complet, +48 sur la session), dont `tests/test_dialogs.py` créé. Les tests sur image réelle se sont exécutés cette fois (plateau devant la caméra) : la chaîne complète est enfin revalidée depuis le changement de repère du lot C2bis. Vérification à chaud de `MainApp` hors pytest : construction et chemin de reprise OK. |
| 2026-08-02 | **Session 🏠 + 🏭 (v0.4.2) — Lot C2bis livré : repère plateau orthonormé, et mesure `M2` sur la Geeetech.** Les 5 étapes du cadrage livrées en une seule session au lieu de deux — délibérément, l'étape 3 (repère de zone) étant la condition de cohérence de l'étape 2 et non sa suite : s'arrêter entre les deux aurait laissé le plateau en Y montant et les zones en Y descendant, un état faux qu'aucun test n'aurait pu valider. Le tableau des coins tient en 4 lignes ; tout le travail est dans ce qui en dépendait implicitement — retournement explicite de Y dans les trois `warp_*` (sans quoi le miroir vertical corrigé la veille revenait), bascule de toute la logique de signe des zones, repère de zone à l'origine bas-gauche, `FORMAT_VERSION` → 2 avec conversion des fichiers v1, `plateau_size_mm` en paramètre, et regroupement du choix d'homographie dans `compute_plateau_reference()`. Trois écarts à la spécification, tous documentés en section 8. **Puis, machine sous tension : action `M2` faite** — `M114` buse au-dessus du marqueur 2 → `MACHINE_ORIGIN` = 5.0 / 0.0, avec vérification que le repère de home est bien à 0/0 (ni `X_MIN_POS`, ni `M206`). | 152 passés, 12 sautés (les tests sur image réelle n'ont pas tourné : le plateau, solidaire du lit, était hors du champ caméra après `G28`). Sans le marqueur `toutes_cameras`, 163/163 plus tôt dans la session. ⚠️ Réserve sur `MACHINE_ORIGIN_Y` non levée (compteur de pas à 0 exact → butée possible) → action `M2 bis`. Sens des axes machine toujours à établir (`M4`). |
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
