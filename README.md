# Machine de Dépose de Pâte Thermique

Automatisation de la dépose de pâte thermique sur coques de calculateur automobile.  
Projet de stage — BUT Informatique 3ème année.

---

## Documentation

- **[CONCEPTION.md](CONCEPTION.md)** — Architecture complète, interfaces des modules, plan de développement avec estimations par session et critères de validation.
- **[CLAUDE.md](CLAUDE.md)** — Contexte et règles pour les sessions de développement assistées par Claude Code.

---

## Changer de machine (Windows ↔ Linux / Raspberry Pi)

### Prérequis communs

- Git installé et configuré
- Python 3.10+
- Accès au dépôt GitHub : `https://github.com/darckmaster/thermal-paste-machine`

---

### Cloner le projet (première fois sur une nouvelle machine)

```bash
git clone https://github.com/darckmaster/thermal-paste-machine.git
cd thermal-paste-machine
```

Configurer son identité Git si ce n'est pas déjà fait :

```bash
git config user.name "darckmaster"
git config user.email "guichard.erwann@gmail.com"
```

---

### Installer les dépendances

**Sur Linux / Raspberry Pi OS :**

```bash
sudo apt update && sudo apt install -y python3-pip python3-pyqt5 libatlas-base-dev
pip3 install opencv-contrib-python pyserial fpdf2 numpy pytest
```

> PyQt5 est installé via `apt` sur Raspberry Pi (la version pip peut poser des problèmes de compatibilité avec l'écran tactile).

**Sur Windows (développement/test sans matériel) :**

```bash
pip install -r requirements.txt
# PyQt5 est inclus dans requirements.txt sous Windows
```

---

### Reprendre le travail au quotidien

Avant de commencer à coder, **toujours synchroniser** :

```bash
git pull origin master
```

Après avoir codé, **sauvegarder son travail** :

```bash
git add <fichiers modifiés>
git commit -m "Description claire des modifications"
git push origin master
```

> Voir les règles de commit dans [CLAUDE.md](CLAUDE.md) — les messages doivent être autoporteurs (contexte + ajouts fonctionnels + fichiers modifiés).

---

### Différences entre les environnements

| Paramètre | Windows (dev) | Linux / Raspberry Pi (prod) |
|---|---|---|
| Port série machine | `COM3`, `COM4`… | `/dev/ttyUSB0` ou `/dev/ttyACM0` |
| Index caméra | `0` (généralement) | `0` (généralement) |
| Affichage GUI | Fenêtre normale | Plein écran 800×480 (écran tactile) |
| Installation PyQt5 | `pip install PyQt5` | `sudo apt install python3-pyqt5` |

Tous ces paramètres sont centralisés dans **`modules/config.py`** — c'est le seul fichier à adapter selon la machine.

---

### Vérifier que tout fonctionne

```bash
# Lancer les tests (tous les modules)
pytest tests/ -v

# Vérifier la caméra seule (Phase 1)
python tests/demo_camera.py

# Vérifier la connexion à la machine (Phase 3)
python tests/demo_machine.py
```

---

### En cas de problème de fin de ligne (LF/CRLF)

Le projet est configuré pour utiliser LF (Linux) sur toutes les machines grâce à `.gitattributes`.  
Si des problèmes de fin de ligne apparaissent malgré tout :

```bash
git add --renormalize .
git commit -m "Renormalisation des fins de ligne"
```

---

## Stack technique (open source uniquement)

| Librairie | Licence | Usage |
|---|---|---|
| opencv-contrib-python | Apache 2.0 | Vision, détection ArUco |
| pyserial | BSD | Communication G-code avec Marlin |
| fpdf2 | LGPL | Génération de rapports PDF |
| numpy | BSD | Calcul vectoriel des trajectoires |
| PyQt5 | GPL v3 | Interface graphique tactile |
| pytest | MIT | Tests unitaires |
