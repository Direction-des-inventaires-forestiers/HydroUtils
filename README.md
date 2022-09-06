<img src="./img/logo_MFFP_couleur.svg" width="200" align="left">

# HydroUtils
Extension QGIS exploitant les produits cartographiques hydrologiques générés à partir de HydroMod

1. [Description](#1-description)
2. [Téléchargement et installation](#2-telechargement-installation)
3. [Principaux outils disponibles](#3-outils-disponibles)


## 1 Description

**HydroUtils** est une extension pour QGIS permettant d'utiliser certains produits cartographiques hydrologiques générés à partir de HydroMod. Plusieurs outils font appel au logiciel WhiteboxTools développé par le professeur [John Lindsay](https://github.com/jblindsay) du [*Geomorphometry and Hydrogeomatics Research Group*](http://www.uoguelph.ca/~hydrogeo/index.html) à [University of Guelph](http://www.uoguelph.ca).


## 2 Téléchargement et installation

- Pour utiliser HydroUtils, le répertoire *HydroUtils* doit être téléchargé et déplacé dans le répertoire des extensions de votre installation de QGIS. Alternativement, le répertoire peut être compressé et ajouté via le *Plugin Manager* intégré à QGIS.
- Présentement, en raison de certains outils spécialisés non disponibles dans la version officielle de WhiteboxTools, vous devrez compiler WhiteboxTools à partir des fichiers sources et de la démarche disponible au https://github.com/jfbourdon/whitebox-tools/tree/production_mffp. Vous devrez ensuite déplacer le fichier *whitebox_tools.exe* directement dans le répertoire racine de l'extension.


## 3 Principaux outils disponibles

- Construction du graphe des écoulements linéaires
- Détermination du trajet de la goutte
- Détermination du bassin versant situé en amont d'un point/ligne/polygone
- Production d'une matrice d'accumulation de flux à partir d'une matrice de direction de flux
