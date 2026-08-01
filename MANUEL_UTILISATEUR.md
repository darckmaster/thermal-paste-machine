# Manuel utilisateur — Machine de Dépose de Pâte Thermique

> Guide opérateur : comment utiliser la machine au quotidien. Pour l'installation,
> la configuration et le dépannage technique, voir `MANUEL_MAINTENANCE.md`.
>
> Ce manuel décrit l'état **actuellement fonctionnel** du logiciel (Phase 8 du projet).
> Certaines fonctionnalités prévues (cordons multiples avec quantité par cordon,
> fichier de préparation JSON rechargeable) ne sont pas encore disponibles — ce manuel
> sera mis à jour au fur et à mesure qu'elles seront livrées.

---

## 1. Vue d'ensemble

L'interface s'organise en 5 écrans, dans l'ordre du cycle de dépose :

```
[Capture] → [Tracé du chemin] → [Dépose en cours] → [Rapport] → (retour à Capture)
    ↕
[Calibration caméra]  (accessible depuis l'écran Capture, à part du cycle normal)
```

Un cycle complet dépose de la pâte thermique le long d'**un seul chemin** tracé par
l'opérateur sur une photo de la pièce, avec une quantité de pâte réglable.

---

## 2. Écran 1 — Capture de la pièce

C'est l'écran de démarrage. Il affiche le flux de la caméra en direct.

- **Choisir le matériel** (ligne du haut, sous l'image) : deux listes déroulantes.
  - **Machine** : port série de la carte de commande. Choisir celui dont la description
    mentionne un port série USB (puce CH340) — sous Windows, ne pas confondre avec les
    ports Bluetooth, qui apparaissent aussi dans la liste.
  - **Caméra** : caméra utilisée pour l'aperçu et la photo. Celle en service est suffixée
    `(en cours)`.
  - **Rafraichir** : re-scanne le matériel présent, sans redémarrer l'application. À
    utiliser après avoir branché la carte ou la caméra.
  - ⚠️ Ces choix ne sont **pas conservés** au redémarrage : l'application repart des
    valeurs enregistrées dans sa configuration (voir `MANUEL_MAINTENANCE.md` section 2
    pour les y inscrire définitivement).
- **Positionner la pièce** : poser le boîtier à déposer sur le plateau, à l'intérieur
  de la zone délimitée par les 2 marqueurs ArUco de zone (IDs 4 et 5, placés en
  diagonale aux coins opposés de la zone de dépose).
- **Vérifier les marqueurs** : le flux vidéo dessine un carré vert autour de chaque
  marqueur ArUco détecté, avec son numéro (ID). Sous l'image, un message indique
  lesquels sont vus (ex. `Marqueurs détectés : [0, 3, 4, 5]`). Il faut :
  - **au moins 2 marqueurs du plateau** parmi les IDs 0, 1, 2, 3 (les coins) ;
  - **les 2 marqueurs de zone** 4 et 5.

  Sur la Geeetech, la caméra est trop proche pour cadrer les 4 coins du plateau à la
  fois : voir seulement les 2 marqueurs du haut (IDs 3 et 0) est le fonctionnement
  **normal**, pas une anomalie. La précision est simplement un peu moindre, et l'écran
  suivant le signale.
- **Homing (G28)** : envoie la machine à sa position de référence (butées mécaniques).
  À faire avant tout nouveau cycle si ce n'est pas automatique. Prend 30 à 60 secondes ;
  l'interface reste utilisable pendant ce temps.
- **Calibration caméra** : ouvre l'écran de calibration ChArUco (voir section 6) —
  normalement une opération ponctuelle à l'installation, pas à chaque pièce.
- **Capturer** : fige l'image du flux vidéo.
- **Valider** : passe à l'écran suivant avec cette photo. **Reprendre** : annule et
  relance le flux en direct si la photo n'est pas satisfaisante.

## 3. Écran 2 — Tracer le chemin de dépose

Affiche la photo capturée, **zoomée et redressée sur la zone de dépose** (le rectangle
délimité par les marqueurs 4 et 5) : on ne trace pas sur toute la photo, mais sur un
gros plan vu du dessus de la seule zone utile. Le message sous l'image indique la taille
réelle de cette zone, par exemple `Zone de dépose 60×40 mm`.

L'opérateur trace le chemin de dépose en tapant/cliquant directement dessus.

- **Ajouter un point** : cliquer/toucher sur la photo. Un cercle vert marque le premier
  point (départ), un cercle rouge le dernier (arrivée), des cercles orange les points
  intermédiaires. Les points sont reliés par une ligne orange.
- **Annuler dernier** : retire le dernier point ajouté.
- **Effacer tout** : recommence le tracé à zéro.
- **Quantité** : curseur réglant la quantité de pâte déposée, en mm d'axe d'extrusion
  par mm de déplacement (de 0,01 à 0,10 mm/mm). Plus la valeur est élevée, plus le
  cordon de pâte sera épais.
- **Lancer** : disponible dès 2 points tracés (minimum pour former un segment). Convertit
  le tracé en coordonnées réelles (mm) et passe à l'exécution.

Messages d'avertissement possibles sous l'image, du moins grave au plus grave :

| Message | Signification | Que faire |
|---|---|---|
| `⚠ Précision réduite (2-3 marqueurs plateau...)` | Seuls 2 ou 3 coins du plateau sont visibles. La correction de perspective ne peut pas être calculée, la conversion en mm est approximative. **Situation normale sur la Geeetech.** | Le tracé fonctionne. Pour plus de précision, reculer la caméra si c'est possible. |
| `Plateau détecté, mais zone de dépose non trouvée (marqueurs 4/5 manquants)` | Le zoom sur la zone est impossible : le tracé se fait sur la photo entière. | Vérifier que les 2 marqueurs de zone sont bien posés et visibles, puis reprendre une photo. |
| `Attention : marqueurs du plateau insuffisants (.../4 détectés, 2 minimum) — conversion pixels→mm indisponible` | Moins de 2 coins du plateau vus : aucune conversion en mm n'est possible. | Retourner à l'écran 1 et reprendre une photo avec au moins 2 marqueurs de coin visibles. |

## 4. Écran 3 — Dépose en cours

Exécution automatique : homing, puis parcours du chemin tracé avec dépose de pâte.

- **Barre de progression** : avance étape par étape (chaque segment du chemin = 2 étapes,
  déplacement puis dépose).
- **Message d'état** : affiche l'étape en cours (connexion, homing, coordonnées du
  déplacement/dépose en cours).
- **ARRÊT D'URGENCE** : bouton rouge, toujours actif pendant l'exécution. Envoie
  immédiatement la commande d'arrêt à la machine (M112) et stoppe le programme après
  l'étape en cours. **Redémarrer la machine avant le prochain cycle après un arrêt
  d'urgence.**
- **Voir le rapport** : actif une fois la dépose terminée (succès, erreur, ou arrêt
  d'urgence) — passe à l'écran de rapport.

## 5. Écran 4 — Rapport

Résumé du cycle qui vient de se terminer :

- Icône verte "OK" (succès) ou rouge "!" (erreur / arrêt d'urgence).
- Statut, nombre de points tracés, longueur totale du chemin (mm), quantité réglée,
  volume de pâte estimé.
- **Exporter PDF** : génère un rapport PDF (photo de la pièce + résumé) dans le dossier
  `reports/`. Disponible si une photo a été prise pendant le cycle.
- **Nouvelle pièce** : retourne à l'écran 1 pour démarrer un nouveau cycle.

## 6. Écran calibration caméra (ChArUco)

Opération ponctuelle, à refaire uniquement si la caméra ou l'objectif change (voir
`MANUEL_MAINTENANCE.md` pour les détails techniques). Accessible depuis l'écran 1,
bouton "Calibration caméra".

1. Générer et imprimer la mire ChArUco (bouton "Générer la mire" → fichier
   `assets/charuco_calibration.png`, à imprimer **à taille réelle**, sans ajustement
   d'échelle par l'imprimante).
2. Présenter la mire imprimée devant la caméra, sous des **angles et distances variés**
   (pas juste à plat face caméra) — plus la variété est grande, meilleure est la
   calibration.
3. Le panneau de droite affiche en direct :
   - **Détection** : nombre de coins de mire reconstruits (✓ vert = bon, △ orange =
     tags vus mais mire non reconstruite, ✗ rouge = rien détecté).
   - **Distance** : distance en mm entre la caméra et le plan de la mire — utile pour
     vérifier que la hauteur caméra correspond à celle attendue (~200 mm au-dessus
     du plateau).
4. **Capturer cette pose** : actif dès que la mire est bien détectée (✓ vert). Répéter
   pour au moins 15 poses différentes (compteur affiché en haut à droite).
5. **Calibrer** : actif à partir de 15 poses capturées. Calcule les coefficients de
   distorsion de l'objectif. L'erreur de reprojection affichée doit être **< 1,0 px**
   (excellente) ou au pire **< 2,0 px** (acceptable) pour être exploitable.
6. **Sauvegarder** : enregistre les coefficients dans `assets/camera_calibration.npz`
   (actif seulement si l'erreur est acceptable).
7. **Recommencer** : efface les poses capturées pour refaire l'opération depuis le début.
