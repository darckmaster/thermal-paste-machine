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

L'interface s'organise en 6 écrans :

```
[Capture] → [Tracé du chemin] → [Dépose en cours] → [Rapport] → (retour à Capture)
    ↕                ↕
[Calibration]   [Créer un plateau] → [Cordons]      (accessibles depuis l'écran Capture)
```

**Deux processus cohabitent pour l'instant.**

Le **cycle historique** (sections 2 à 5) dépose la pâte le long d'**un seul chemin**
tracé sur une photo de la pièce. C'est le seul qui va aujourd'hui jusqu'à la dépose
réelle sur la machine.

Le **nouveau processus multi-zones** (section 7) traite un plateau portant **plusieurs
zones de dépose**, chacune accueillant un exemplaire du même produit, avec des cordons
tracés une seule fois et appliqués à toutes. Il est en cours de construction : à ce
stade il sait reconnaître les zones et diagnostiquer le montage, mais pas encore tracer
ni déposer. Les deux processus fusionneront quand le nouveau sera complet.

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
- **Créer un plateau** : ouvre le nouveau processus multi-zones (voir section 7). Il
  cohabite pour l'instant avec le cycle décrit aux sections 3 à 5, qui reste le seul à
  aller jusqu'à la dépose réelle.
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

## 7. Écran « Créer un plateau » — processus multi-zones

> **En construction.** À ce stade, cet écran reconnaît les zones de dépose et diagnostique
> le montage du plateau. Le tracé des cordons et la dépose viendront ensuite.

### Ce qu'est une zone de dépose

Une **zone de dépose** est l'emplacement d'un produit sur le plateau. Elle est **vissée à
demeure** et repérée par **deux marqueurs ArUco** collés aux deux extrémités de sa
diagonale, du coin **haut-gauche** au coin **bas-droit**.

**Règle de numérotation à respecter au montage** : le marqueur du bas-droit porte l'identifiant
du haut-gauche **plus un**. Une zone `4` en haut à gauche a donc son `5` en bas à droite.
C'est cette règle qui permet au logiciel de dire si une zone a été posée à l'envers.

Les identifiants `0` à `3` sont réservés aux quatre coins du plateau : les zones commencent
donc à `4`. Toutes les zones d'un plateau accueillent le **même produit**, donc ont les
mêmes dimensions.

### Marche à suivre

1. Depuis l'écran 1, appuyer sur **Créer un plateau**.
2. Saisir la **référence du produit**. Elle nomme le fichier de travail et reste affichée
   en haut de l'écran, pour qu'on sache à tout moment sur quoi on travaille.
3. Cadrer le plateau. Le flux en direct entoure chaque marqueur reconnu et affiche leur
   liste sous l'image : c'est le moment de vérifier le cadrage, pas après.
4. **Capturer**. Le logiciel analyse la photo et matérialise son diagnostic :

   | Sur l'image | Signification |
   |---|---|
   | Rectangle **vert** avec `4/5` | Zone reconnue et exploitable |
   | Rectangle **rouge** avec un libellé de défaut | Zone inutilisable — le défaut est nommé |
   | Cercle **orange** autour d'un marqueur | Marqueur sans zone (partenaire absent ou format incohérent) |

5. **Continuer** indique entre parenthèses le nombre de zones exploitables. Il reste
   inactif s'il n'y en a aucune. **Reprendre** permet de refaire une photo, typiquement
   après avoir rectifié le montage.

### Les défauts signalés

| Message | Cause probable | Que faire |
|---|---|---|
| `à l'envers` | Les deux marqueurs sont intervertis, ou la zone est posée retournée | Intervertir les deux marqueurs, ou retourner la zone |
| `format différent` | La zone n'a pas les mêmes dimensions que les autres | Vérifier qu'il s'agit bien du même produit, et que les marqueurs sont bien aux coins |
| `marqueurs ambigus` | Un marqueur est revendiqué par deux zones — impossible de trancher | Renuméroter les zones pour éviter les identifiants qui se suivent d'une zone à l'autre |
| `trop inclinée` | La zone est vissée de travers de plus de 10° | Redresser la zone |
| `format indéterminable` | Plus aucune zone n'est saine et à l'endroit, le logiciel n'a plus de référence | Remettre au moins deux zones correctement, puis reprendre une photo |
| `Marqueurs du plateau insuffisants` | Moins de 2 coins du plateau visibles | Reculer ou recadrer la caméra |

Une zone en défaut **n'empêche pas** de travailler sur les autres : le message indique
combien de zones restent exploitables, et l'opérateur décide de continuer ou de rectifier
son plateau.

### Ce que dit la barre de statut sur le repère

Le début du message décrit la façon dont le logiciel s'est repéré sur le plateau. Trois
mentions peuvent y apparaître :

| Mention | Ce que ça veut dire | Que faire |
|---|---|---|
| `Repère exact (4 marqueurs)` | Les quatre coins sont vus, la perspective est corrigée. C'est le meilleur cas | Rien |
| `⚠ Précision réduite` | Seuls 2 ou 3 coins sont visibles. **C'est la situation normale sur la Geeetech**, dont la caméra ne peut pas cadrer les quatre coins : ce n'est pas une panne, seulement un rappel que la conversion en millimètres est moins précise | Rien sur la Geeetech. Sur la CNC, reculer la caméra pour voir les 4 coins |
| `origine extrapolée` | Le marqueur **2** (coin bas-gauche), qui sert d'origine, n'est pas dans le champ. Sa position est **déduite** de la taille de plateau réglée dans les paramètres | Vérifier que cette taille correspond bien au plateau **mesuré au mètre** : une erreur dessus décale toute la dépose |
| `tag 0 : X mm d'écart` | Le marqueur 0 sert de témoin : le logiciel compare où il le voit et où il devrait être. C'est un indicateur de la qualité du montage | Un petit écart est normal. S'il grandit (⚠ au-delà de 5 mm), vérifier qu'aucun marqueur ne se décolle et que le plateau n'est pas déformé |

> L'écart du tag 0 mélange plusieurs causes sans savoir les distinguer : inclinaison de la
> caméra, déformation de l'objectif, plateau voilé, marqueur mal collé. Il sert à repérer
> une dérive, pas à mesurer une précision.

### Deux points à connaître

- Le rectangle tracé s'appuie sur le **centre** des marqueurs, il est donc légèrement en
  retrait du contour physique du produit. C'est cette surface-là qui servira de zone de
  tracé.
- Le **format du produit** affiché est déduit de l'ensemble des zones. Avec une seule zone
  saine, il vaut simplement les dimensions de cette zone et ne constitue aucun contrôle :
  il faut au moins deux zones pour que la comparaison ait un sens.

## 8. Écran « Cordons » — tracer les dépôts

> **En construction.** Le tracé fonctionne, mais l'enregistrement et le lancement de la
> dépose ne sont pas encore disponibles.

On y arrive en appuyant sur **Continuer** depuis l'écran de création de plateau. Cet écran
a **deux modes**, entre lesquels on fait des allers-retours.

### Mode vue d'ensemble

La photo du plateau, avec les zones exploitables entourées en vert.

- **Appuyer sur une zone** pour y tracer les cordons. La première zone choisie devient la
  zone de **référence** : c'est dans son repère que les cordons sont mémorisés.
- **Modifier les cordons** ramène à cette zone de référence pour compléter ou corriger le
  tracé. Le bouton reste inactif tant qu'aucune zone n'a été choisie.
- Une fois des cordons tracés, ils apparaissent **en orange sur toutes les zones** : c'est
  la vérification visuelle que le report s'est bien fait.

### Mode tracé

La zone choisie, affichée **redressée et agrandie** — même si elle est vissée légèrement
de travers, elle apparaît droite.

| Geste | Effet |
|---|---|
| Appui | Pose un point. Le premier appui démarre un cordon |
| Double-appui | Pose le dernier point et **termine** le cordon |
| Appui sur un cordon existant | Le **sélectionne** (il passe en jaune épais) |
| Appui à l'écart | Démarre un nouveau cordon |

Un cordon en cours de tracé est **vert** ; les cordons terminés sont **orange**. À la
souris, un trait pointillé suit le curseur pour montrer le segment en préparation — ce
confort n'existe pas au doigt, l'écran tactile n'ayant pas de survol.

| Bouton | Rôle |
|---|---|
| **Annuler** | Défait la dernière action : un point posé, un cordon terminé, ou une suppression |
| **Refaire** | Rejoue ce qui vient d'être annulé |
| **Supprimer** | Efface le cordon sélectionné, en entier |
| **Valider** | Termine et revient à la vue d'ensemble |

⚠️ **Annuler ne remonte que d'un seul cran.** Il n'y a pas d'historique : après une
annulation, il n'y a plus rien à annuler. Toute nouvelle action rend le « Refaire »
caduc.

⚠️ **Valider reste inactif tant qu'un cordon est en cours de tracé.** Il faut d'abord le
terminer par un double-appui, sinon il serait perdu sans avertissement.

### Deux points à connaître

- Un cordon d'un seul point est **abandonné** : sans second point, il n'a aucun segment,
  donc rien à déposer.
- Ouvrir une **autre** zone que celle de référence y affiche les mêmes cordons, mais ne
  change pas le repère de travail. Changer de repère déplacerait les cordons déjà tracés.

### Enregistrer son travail

| Bouton | Rôle |
|---|---|
| **Paramètres** | Règle les 2 vitesses et les 2 seuils de contrôle du montage |
| **Enregistrer** | Enregistre définitivement le plateau. Inactif tant qu'aucun cordon n'est tracé — un plateau sans cordon ne permet de rien déposer |

**Le travail est sauvegardé tout seul toutes les 5 secondes.** Il n'y a donc rien à faire
pour se protéger d'une coupure de courant ou d'un plantage : au prochain démarrage,
l'application proposera de reprendre là où vous en étiez.

Cette sauvegarde automatique **n'inclut jamais un cordon en cours de tracé** : tant que
vous n'avez pas fait le double-appui qui le termine, il n'existe pas pour elle. C'est
voulu — un cordon coupé au milieu, rechargé plus tard, ressemblerait à un cordon que vous
auriez voulu court.

Le bouton **Enregistrer** reste utile : il valide le travail, et c'est lui qui supprime la
sauvegarde automatique. Tant que vous n'avez pas enregistré, l'application continuera de
vous proposer de reprendre ce plateau à chaque démarrage.

### Reprendre un travail interrompu

Au démarrage, si un travail n'a pas été enregistré, l'application le propose :

> *Un travail non enregistré a été trouvé pour « BOITIER_3 ». Le reprendre ?*

- **Oui** → les cordons déjà tracés sont restaurés, et vous arrivez directement sur
  l'écran de création de plateau pour **reprendre une photo**.
- **Non** → l'application démarre normalement. Le fichier est **conservé** : la question
  sera reposée au prochain démarrage.

⚠️ **Reprendre une photo ne fait perdre aucun tracé.** Les cordons sont mémorisés par
rapport à la zone, pas par rapport à la photo : même si la caméra a bougé entre-temps, ils
se replacent au bon endroit. C'est aussi pour ça que la photo elle-même n'est pas
enregistrée — elle se refait en un appui.

### Recharger un plateau déjà enregistré

Les zones étant vissées à demeure, un plateau enregistré se rejoue autant de fois que
nécessaire — **sans rien retracer**.

Sur l'écran d'accueil, appuyer sur **« Charger un plateau »**. La liste affiche, pour
chaque plateau enregistré, son nom, son nombre de cordons et la date du dernier
enregistrement — de quoi répondre à « est-ce bien celui d'hier ? » sans ouvrir le fichier.

Après le chargement, une photo du plateau est reprise — **automatiquement**. Vous n'avez
rien à appuyer : dès que les marqueurs de coin du plateau sont vus, la photo se déclenche
seule et le diagnostic s'affiche. La barre de statut indique l'attente en cours :

> *Capture automatique — recherche du plateau… (1/2 marqueurs de coin)*

Cette nouvelle photo ne fait perdre aucun tracé : les cordons se replacent tout seuls sur
les zones détectées.

Si le plateau n'est pas reconnu au bout de quelques secondes, l'application rend la main :

> *Plateau non reconnu automatiquement — vérifier le cadrage, puis appuyer sur Capturer*

Vérifiez alors qu'au moins deux marqueurs de coin sont dans le champ — rien ne doit les
masquer, votre main comprise — et appuyez sur **Capturer**.

> La capture automatique ne concerne que le **rechargement**. À la création d'un plateau,
> c'est toujours vous qui déclenchez : vous êtes en train d'y poser les boîtiers, et c'est
> vous qui savez quand c'est prêt. De même après un **« Reprendre »** : vous venez de voir
> un défaut de montage, redéclencher tout seul vous renverrait au même diagnostic avant
> que vous ayez pu rectifier quoi que ce soit.

> ⚠️ **« Charger un plateau » et « Reprendre un travail interrompu » ne sont pas la même
> chose.** La reprise proposée au démarrage concerne un travail **jamais enregistré**,
> interrompu par un plantage. Le chargement concerne un plateau que vous avez **validé**
> avec le bouton « Enregistrer ».

### Attention à ne pas écraser un plateau

Le nom du produit sert de nom de fichier. Si vous créez un **nouveau** plateau en
reprenant le nom d'un plateau existant, l'enregistrement remplacerait l'ancien.

L'application vous prévient dans ce cas :

> *Un plateau « AIVC » est déjà enregistré. Il contient 2 cordon(s)… L'enregistrer
> maintenant le remplacera définitivement.*

Le bouton par défaut est **Non** : un appui distrait n'écrase rien. Pour repartir d'un
plateau existant sans risque, passer par **« Charger un plateau »**.

Aucune question n'est posée quand vous réenregistrez un plateau que vous venez de
charger — c'est le déroulé normal de la réutilisation.

### Nommer un plateau — trois façons

Il n'y a pas de clavier sur le boîtier de commande. À l'ouverture d'un nouveau plateau,
vous avez donc trois moyens d'indiquer la référence du produit :

1. **taper la référence** dans le champ ;
2. **appuyer sur une référence de la liste** des produits déjà enregistrés — le champ se
   remplit, vous pouvez encore le corriger avant de valider. C'est le moyen le plus sûr
   pour reprendre un produit connu, sans risque de faute de frappe ;
3. **valider en laissant le champ vide** → le plateau s'appellera `BOITIER_1`, `BOITIER_2`,
   etc., en prenant le premier numéro libre. C'est le geste le plus rapide quand le nom
   n'a pas d'importance.

### Si un ancien plateau est signalé « converti »

Un message peut apparaître à l'ouverture d'un plateau enregistré avec une version
antérieure du logiciel : la façon dont les coordonnées sont mesurées a changé, et le
fichier a été **converti automatiquement**. Rien n'est perdu, et le fichier est
réenregistré au nouveau format — le message n'apparaîtra donc qu'une fois.

⚠️ **Vérifier le tracé avant de lancer une dépose sur un plateau converti.** La conversion
est vérifiée par des tests, mais un coup d'œil coûte moins cher qu'une pièce ratée.

---

## 9. Écran « Lancer une dépose » — le cycle multi-zones

C'est le chemin normal au quotidien : un seul bouton depuis l'écran d'accueil, et le
logiciel vous guide jusqu'au bout. Les deux boutons voisins servent à **préparer** un
plateau ; celui-ci sert à **l'exécuter**.

### Ce que fait la machine, dans l'ordre

1. Vous appuyez sur **« Lancer une dépose »**.
2. La machine fait un **homing**, se dégage en hauteur, puis se place en **position de
   prise de vue**. Comptez de 30 à 60 secondes.
3. Le logiciel vous demande **quel plateau exécuter**, parmi ceux que vous avez
   enregistrés.
4. Il prend une **photo** et vous montre le plateau avec ses zones.
5. Vous **désignez les zones où se trouve un produit**.
6. Vous validez ; une fenêtre récapitule ce qui va se passer et demande confirmation.
7. La machine refait un **homing**, puis dépose zone par zone.
8. Une fenêtre suit l'avancement. À la fin, un **bilan** s'affiche.

### Désigner les zones

Les zones apparaissent dans trois états :

| Aspect | Signification |
|---|---|
| Contour **gris fin** | Zone utilisable, **pas encore choisie** |
| Contour **vert épais**, cordons dessinés dedans | Zone **choisie** — c'est là qu'on déposera |
| Contour **rouge** | Zone **écartée**, non sélectionnable — le motif est écrit à côté |

**Un appui sélectionne, un second désélectionne.** Rien n'est coché au départ : c'est
volontaire, déposer sur une zone vide gaspille de la pâte et salit le plateau. Sur un
plateau plein, le bouton **« Tout sélectionner »** évite d'appuyer six fois.

Les **cordons se dessinent dans les zones choisies** : vous voyez exactement ce qui va
être déposé, et où, avant que la machine ne bouge.

Une zone peut être écartée pour un **format qui ne correspond pas au produit** : les
cordons ont été tracés pour un boîtier d'une certaine taille, sur un autre ils
déborderaient.

### La dépose à blanc

La fenêtre de confirmation propose une case **« Dépose à blanc »**, **cochée par
défaut**.

En dépose à blanc, la machine parcourt **exactement le même chemin**, mais n'extrude rien
et ne descend pas : elle reste en hauteur. C'est le mode à utiliser pour :

- vérifier un plateau neuf sans gâcher de pâte ;
- montrer le cycle complet ;
- contrôler que la machine vise juste — c'est le passage de la buse au coin de chaque
  zone qui le dit.

⚠️ **Décochez-la pour déposer réellement.** Tant que les réglages d'extrusion n'ont pas
été faits, laissez-la cochée.

### Pendant la dépose

La fenêtre de suivi affiche l'avancement, la zone en cours, le nombre de zones terminées
et le temps écoulé. Deux boutons :

- **Pause** — la machine s'arrête entre deux mouvements. La pâte peut continuer de
  s'écouler légèrement : c'est normal, ce n'est pas rattrapé à la reprise.
- **ARRÊT** — coupe tous les actionneurs. Une confirmation est demandée, car c'est
  irréversible : **la machine doit être redémarrée** avant le cycle suivant.

⚠️ **Cette fenêtre ne se ferme ni par la croix ni par Échap.** Tant que la machine bouge,
la seule sortie est le bouton d'arrêt — pour qu'il reste toujours accessible.

### Le bilan de fin

À la fin du cycle, la machine **revient en position de prise de vue et photographie le
plateau**. Le bilan affiche cette vue, puis rappelle le produit, le nombre de zones
déposées et le temps total.

**Après un arrêt**, il détaille en plus **zone par zone** ce qui a été déposé et ce qui ne
l'a pas été. ⚠️ Une zone interrompue en cours de cordon a reçu une **dose partielle** :
la vérifier avant de relancer.

⚠️ **Après un arrêt, la machine n'est pas redéplacée** pour la photo. L'arrêt la met hors
service jusqu'au redémarrage : on photographie donc là où elle s'est immobilisée. Le
bilan et le rapport le signalent — le cadrage n'est pas celui des autres rapports, et
deux vues ne sont alors pas comparables.

### Imprimer le rapport

Le bouton **« Imprimer le rapport »** produit un PDF. Il **ne ferme pas** le bilan : vous
pouvez imprimer, relire, et réimprimer si besoin. Le chemin du fichier s'affiche sous les
boutons.

Les rapports sont écrits dans le dossier **`reports/` à la racine du projet**, quel que
soit l'endroit d'où l'application a été lancée. Deux rapports produits dans la même
seconde ne s'écrasent pas : le second reçoit un suffixe.

Le PDF contient la vue de fin, le produit, le nombre de zones, le temps total et la
longueur tracée. En cas d'interruption, il ajoute le détail par zone. En dépose à blanc,
il l'annonce en tête : **le rapport atteste d'un parcours, pas d'une dépose**.

### Si la dépose est refusée avant de démarrer

Un message peut annoncer que des points **sortent de la course de la machine**, en
nommant la zone fautive. Le lancement est alors annulé et **rien ne bouge**.

Ce contrôle existe parce que la machine ne signalerait rien d'elle-même : elle ramènerait
silencieusement les points hors course à sa limite, et la dépose sortirait déformée sans
explication.

Le remède est mécanique : rapprocher le plateau, ou retracer les cordons plus loin du
bord.

---

## 10. Les photos et la position de la machine

Depuis le 2026-08-04, **toute photo du plateau est précédée d'un homing** et d'une mise en
position de prise de vue. Cela vaut pour les trois écrans qui photographient : l'accueil,
« Créer un plateau », et le cycle de dépose.

**Pourquoi** : sur la Geeetech, le plateau est solidaire du lit qui bouge en Y.
Photographier là où la machine se trouve donnerait un cadrage différent à chaque fois, et
deux plateaux créés à deux moments ne seraient pas comparables.

**Conséquence à connaître** : chaque photo coûte de 30 à 60 secondes. Un « Reprendre »
pour corriger un cadrage repart pour un homing complet.

Si aucune machine n'est disponible, le logiciel **demande** s'il faut photographier quand
même — « Non » par défaut. Vous pouvez accepter : la photo sera prise à la position
actuelle, et le message vous le rappellera à côté du diagnostic.
