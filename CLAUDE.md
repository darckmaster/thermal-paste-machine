# CLAUDE.md — Machine de Dépose de Pâte Thermique

## Contexte du projet

Automatisation de la dépose de pâte thermique sur coques de calculateur automobile.  
**Cadre** : Projet de stage — BUT Informatique 3ème année (anciennement DUT).  
**Deadline** : Fin juin 2026.  
**Usage** : Le document de conception (`CONCEPTION.md`) doit rester à jour pour être intégré au rapport de stage et à la soutenance.

**Matériel cible :**
- Imprimante 3D Geeetech I3 modifiée (axes X/Y/Z + piston Nema 17 à la place de l'extrudeur)
- Raspberry Pi (modèle à préciser) + écran tactile 7 pouces
- Module caméra Raspberry Pi
- Firmware Marlin sur la carte Geeetech (communication G-code USB série à 115200 baud)
- Marqueurs ArUco (DICT_4X4_50, IDs 0-3) pour calibrage de perspective

**Document de référence complet :** `CONCEPTION.md` — contient l'architecture, les interfaces, le plan de développement avec estimations et critères de validation.

---

## Mode de collaboration (IMPORTANT)

- **Ne pas tout faire seul.** Le développeur est étudiant en BUT3 — l'objectif est d'apprendre en faisant. Claude guide, explique, propose ; l'étudiant code, teste, valide.
- **Travailler phase par phase.** Ne pas anticiper les phases suivantes ni créer du code pour des phases non démarrées.
- **Enrichir `CONCEPTION.md` au fil de l'eau.** Chaque décision technique, découverte, ou résultat de test doit être documenté dans `CONCEPTION.md` pour alimenter le rapport de stage.
- **Expliquer les choix.** Pour chaque solution proposée, expliquer le pourquoi, pas seulement le comment.

---

## Règles techniques

### Librairies : open source uniquement
Toutes les dépendances doivent être **open source** et utilisables en entreprise sans licence tierce payante (pas de GPL virale si le projet est distribué fermé, préférer MIT/BSD/Apache).

| Librairie | Licence | Rôle |
|---|---|---|
| PyQt5 | GPL v3 / commercial | Interface graphique tactile — acceptable en interne |
| opencv-contrib-python | Apache 2.0 | Vision, détection ArUco, homographie |
| pyserial | BSD | Communication USB/UART avec Marlin |
| fpdf2 | LGPL | Génération PDF |
| numpy | BSD | Calcul vectoriel trajectoires |
| pytest | MIT | Tests |

> **Note PyQt5** : licence GPL v3 pour la version open source. Pour un usage interne (pas de distribution du logiciel), cela ne pose pas de problème. Si le logiciel devait être distribué, envisager PySide6 (LGPL).

### Installation (Raspberry Pi OS / Linux)

```bash
sudo apt update && sudo apt install -y python3-pip python3-pyqt5 libatlas-base-dev
pip3 install opencv-contrib-python pyserial fpdf2 numpy pytest
```

---

## Structure du projet

```
thermal-paste-machine/
├── CONCEPTION.md            # Document de conception (rapport de stage)
├── CLAUDE.md                # Ce fichier — contexte pour Claude
├── main.py                  # Point d'entrée, machine à états principale
├── requirements.txt
├── modules/
│   ├── config.py            # Paramètres globaux et constantes
│   ├── camera.py            # Capture image
│   ├── vision.py            # Traitement d'image, détection ArUco
│   ├── machine.py           # Communication série G-code (Marlin)
│   ├── path_planner.py      # Calcul des trajectoires de dépose
│   └── reporter.py          # Génération de rapport PDF
├── gui/
│   ├── app.py               # Fenêtre principale PyQt5
│   ├── screen_capture.py    # Écran 1 : prise de photo
│   ├── screen_zone.py       # Écran 2 : sélection zone + quantité
│   ├── screen_run.py        # Écran 3 : exécution et monitoring
│   └── screen_report.py     # Écran 4 : rapport
├── assets/
├── reports/                 # PDFs générés (gitignorés)
└── tests/
```

---

## Plan de développement — avancement

| Phase | Module principal | Statut | Sessions réalisées |
|---|---|---|---|
| 1 | `modules/camera.py` — caméra de base | ⬜ À faire | 0/1 |
| 2 | `modules/vision.py` — ArUco & calibrage | ⬜ À faire | 0/3 |
| 3 | `modules/machine.py` — G-code Marlin | ⬜ À faire | 0/2 |
| 4 | `gui/` — interface squelette | ⬜ À faire | 0/3 |
| 5 | `modules/path_planner.py` + zone | ⬜ À faire | 0/3 |
| 6 | `main.py` — intégration complète | ⬜ À faire | 0/3 |
| 7 | `modules/reporter.py` — PDF | ⬜ À faire | 0/2 |
| 8 | Tests, robustesse, finitions | ⬜ À faire | 0/3 |

> Mettre à jour ce tableau à chaque session. Changer ⬜ en 🔄 (en cours) ou ✅ (validé).

---

## Conventions de code

- **Langue des identifiants** : noms de variables/fonctions en anglais (convention Python universelle)
- **Langue des commentaires** : tous les commentaires et docstrings **en français**, sans exception
- **Style** : PEP 8, type hints sur toutes les interfaces publiques
- **Tests** : un fichier `tests/test_<module>.py` par module, lancé avec `pytest`

### Commentaires — règle didactique (IMPORTANT)

Le projet est pédagogique : chaque ligne de code non triviale doit être commentée en français, de façon à ce qu'un lecteur puisse comprendre **ce que fait la ligne ET pourquoi**, sans avoir à consulter la documentation externe.

**Exemple attendu :**
```python
# Ouvrir le flux vidéo depuis la caméra connectée à l'index donné (0 = première caméra USB)
self._cap = cv2.VideoCapture(self._index)

# Vérifier que l'ouverture a réussi (la caméra peut être occupée par un autre processus)
if not self._cap.isOpened():
    raise RuntimeError("Impossible d'ouvrir la caméra")
```

**Exemple à éviter :**
```python
self._cap = cv2.VideoCapture(self._index)  # VideoCapture
```

### Commits — règle d'autoportance (IMPORTANT)

Chaque message de commit doit être **autoporteur** : un développeur qui lit le log git doit comprendre sans ouvrir les fichiers ce qui a été fait et pourquoi. Le message doit contenir :

1. **Une ligne de titre** résumant l'action (ex: `Phase 1 — Implémentation de modules/camera.py`)
2. **Le contexte** : quelle phase, quel objectif, quelle contrainte a motivé le changement
3. **Les ajouts/modifications fonctionnels** : ce que le code fait désormais (comportement, pas syntaxe)
4. **Les fichiers modifiés** listés explicitement

**Exemple de bon commit :**
```
Phase 1 — Implémentation de modules/camera.py

Contexte : Phase 1 du plan de développement — validation de la chaîne
logicielle caméra sur Raspberry Pi.

Ajouts fonctionnels :
- Classe Camera : ouverture du flux, capture d'une image BGR, libération
- Gestion d'erreur si la caméra est absente ou déjà utilisée
- Script de démonstration : affichage temps réel avec cv2.imshow()

Fichiers modifiés :
- modules/camera.py (nouveau)
- tests/demo_camera.py (nouveau)
- tests/test_camera.py (nouveau)
```
