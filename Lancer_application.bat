@echo off
rem ===================================================================
rem  Lanceur double-clic de la machine de depose de pate thermique
rem  (Windows uniquement — sur le Raspberry Pi, lancer "python3 main.py")
rem ===================================================================

rem "setlocal" limite les variables definies ici a cette fenetre :
rem rien n'est laisse dans l'environnement de la session Windows.
setlocal

rem Titre de la fenetre console, pour la reconnaitre dans la barre des taches.
title Machine de depose de pate thermique

rem %~dp0 = dossier contenant CE fichier .bat, termine par un antislash.
rem On s'y place (/d autorise aussi le changement de lecteur) : sans cela,
rem un double-clic depuis un raccourci laisserait le repertoire courant
rem ailleurs et "import gui.app" echouerait — et les rapports PDF, les
rem preparations et local_config.json seraient cherches au mauvais endroit.
cd /d "%~dp0"

rem Interpreteur Python de cette machine (chemin donne par l'utilisateur).
set "PYTHON=C:\Users\Erwann\AppData\Local\Programs\Python\Python313\python.exe"

rem Replis successifs si ce chemin n'existe plus (Python reinstalle, mis a
rem jour en 3.14, ou fichier copie sur une autre machine Windows) :
rem   1) le lanceur officiel "py" ; 2) le "python" du PATH.
rem Sans ce filet, un deplacement de l'installation Python rendrait le
rem double-clic muet le jour de la demonstration.
if not exist "%PYTHON%" set "PYTHON=py"
if "%PYTHON%"=="py" where py >nul 2>&1 || set "PYTHON=python"

echo Demarrage de l'application...
echo.

rem Lancement de l'application. La fenetre console reste ouverte en arriere-plan
rem pendant toute la duree d'execution : elle recoit les messages d'erreur Python,
rem ce qui evite un echec silencieux impossible a diagnostiquer devant un jury.
"%PYTHON%" main.py

rem "errorlevel 1" est vrai des que le code de retour est >= 1, donc en cas de
rem plantage. main.py se termine par sys.exit(app.exec_()), qui rend 0 quand
rem l'operateur ferme normalement la fenetre : dans ce cas la console se ferme
rem toute seule. En cas d'erreur, on met en pause pour laisser le temps de LIRE
rem la trace Python avant que la fenetre ne disparaisse.
if errorlevel 1 (
    echo.
    echo ------------------------------------------------------------
    echo  L'application s'est arretee sur une erreur ^(code %errorlevel%^).
    echo  Le detail est affiche juste au-dessus.
    echo ------------------------------------------------------------
    echo.
    pause
)

endlocal
