# -*- coding: utf-8 -*-

"""
/***************************************************************************
 HydroUtils
                                 A QGIS plugin
 Identifie le bassin versant de polygones d'intérêt
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2022-07-14
        copyright            : (C) 2022 by Jean-François Bourdon (MFFP-DIF)
        email                : jean-francois.bourdon@mffp.gouv.qc.ca
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/

 - Il y a un bug présentement dans l'outil Watershed de WBT qui fait en sorte que le raster de pour points doit avoir une valeur de nodata inférieure
   ou égale à zéro sinon le résultat n'est pas bon. C'est probablement à la ligne 381 de watershed.rs que le problème se trouve. À noter que si la
   valuer de NoData spécifiée dans l'en-tête ne se trouve pas en réalité dans le raster, ça ne cause pas problème. En fait, j'ai l'impression
   que la nodata ne sert juste à rien dans cet outil. Toute valeur égale ou inférieure à 0 est considérée NoData, point à la ligne.
"""

__author__ = 'Jean-François Bourdon (MFFP-DIF)'
__date__ = '2022-07-14'
__copyright__ = '(C) 2022 by Jean-François Bourdon (MFFP-DIF)'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import *
from PyQt5.QtCore import *
import processing
from processing.core.Processing import Processing
from qgis.analysis import QgsNativeAlgorithms

import datetime
import glob
import networkx as nx
from operator import itemgetter
import os
import shutil
import subprocess

from .sidescripts import *


class watershed(QgsProcessingAlgorithm):

    script_dir = os.path.dirname(__file__)
    dict_config = get_config(script_dir)
    success = True

    def initAlgorithm(self, config):
        self.addParameter(
            QgsProcessingParameterFile(
                'INPUT_tempdir',
                'Répertoire temporaire',
                QgsProcessingParameterFile.Folder,
                defaultValue=self.dict_config["variables"]["tempdir"]
            )
        )

        self.addParameter(
            QgsProcessingParameterFile(
                'INPUT_d8',
                'Répertoire contenant les écoulements et les D8',
                QgsProcessingParameterFile.Folder
            )
        )

        self.addParameter(
            QgsProcessingParameterVectorLayer(
                'INPUT_occurrences',
                'occurrences',
                [QgsProcessing.TypeVectorPoint, QgsProcessing.TypeVectorPolygon, QgsProcessing.TypeVectorLine]
            )
        )
        
        self.addParameter(
            QgsProcessingParameterBoolean(
                'INPUT_only_selected',
                'Utiliser uniquement les entitées sélectionnées',
                defaultValue=False
            )
        )
    
        self.addParameter(
            QgsProcessingParameterField(
                'INPUT_field_occurrences',
                'Identifiant unique des occurrences',
                defaultValue=None,
                parentLayerParameterName="INPUT_occurrences"
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                'OUTPUT_watershed',
                'Bassins versants des occurrences'
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        roottempdir = os.path.normpath(self.parameterAsString(parameters, 'INPUT_tempdir', context))
        dird8 = os.path.normpath(self.parameterAsString(parameters, 'INPUT_d8', context))
        vlayer_occurrences_ori = self.parameterAsVectorLayer(parameters, 'INPUT_occurrences', context)
        bool_only_selected = self.parameterAsBool(parameters, 'INPUT_only_selected', context)
        field_occurrences = self.parameterAsFields(parameters, 'INPUT_field_occurrences', context)[0]


        # Chargement de l'index d'UD et des écoulements linéaires
        path_index = glob.glob(os.path.join(dird8, f"Hydro_LiDAR_????.gpkg"))
        if len(path_index) == 0:
            self.success = False
            feedback.reportError(f"Le fichier contenant les écoulements (Hydro_LiDAR_00XX.gpkg) ne semble pas être présent au {dird8}.\n")
            return {}
        
        udh = path_index[0][-9:-5]
        vlayer_streams = QgsVectorLayer(f"{path_index[0]}|layername=RH_L")
        if vlayer_streams.hasFeatures() == 0:
            self.success = False
            feedback.reportError(f"La couche d'hydrographie linéaire (RH_L) ne semble pas être présente ou ne contient aucune entitée.\n")
            return {}
        
        vlayer_indexUD = QgsVectorLayer(f"{path_index[0]}|layername=S_UDH")
        if vlayer_indexUD.hasFeatures() == 0:
            self.success = False
            feedback.reportError(f"La couche d'index des sous-unités de découpage hydrique (S_UDH) ne semble pas être présente ou ne contient aucune entitée.\n")
            return {}


        # Création du QgsVectorLayer de sortie contenant les bassins versants de chaque occurrence
        fields_array = [
            vlayer_occurrences_ori.fields().field(field_occurrences),
            QgsField('UDH', QVariant.String, len=4),
            QgsField('Superficie_ha', QVariant.Double, len=15, prec=2)
            ]
        
        fields_watershed = QgsFields()
        for field in fields_array:
            fields_watershed.append(field)

        sinkCrs = QgsCoordinateReferenceSystem("EPSG:6622")
        (sink, self.sink_id) = self.parameterAsSink(parameters, 'OUTPUT_watershed', context, fields_watershed, QgsWkbTypes.MultiPolygon, sinkCrs)


        # Sauvegarde du répertoire par défaut
        self.dict_config["variables"]["tempdir"] = roottempdir
        write_config(self.dict_config, self.script_dir)


        # Chemin d'accès à Whitebox Tools
        path_wbt = os.path.join(self.script_dir, "whitebox_tools.exe")


        # Paramètres pour les appels à subprocess.run()
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags = subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = int(self.dict_config["variables"]["wShowWindow"])


        # Valider que les valeurs de "field_occurrences" sont bien uniques
        request = QgsFeatureRequest().setFlags(QgsFeatureRequest().NoGeometry)
        ls_ID = [feature.attribute(field_occurrences) for feature in vlayer_occurrences_ori.getFeatures(request)]
        if len(ls_ID) != len(set(ls_ID)):
            feedback.reportError(f"Le champ {field_occurrences} contient des doublons.")
            return {}


        # Sélection des occurrences à utiliser
        vlayer_occurrences = vlayer_occurrences_ori.clone()
        if not bool_only_selected:
            vlayer_occurrences.selectAll()


        # Validation que les occurrences touchent bel et bien aux UD fournies
        context.project().addMapLayer(vlayer_occurrences, False)
        vlayer_occurrences_touched = processing.run("native:extractbylocation", {
            'INPUT':QgsProcessingFeatureSourceDefinition(vlayer_occurrences.id(), True),
            'PREDICATE':[0],
            'INTERSECT':vlayer_indexUD,
            'OUTPUT':'TEMPORARY_OUTPUT'
            })["OUTPUT"]
        context.project().removeMapLayer(vlayer_occurrences.id())
        
        if vlayer_occurrences_touched.hasFeatures() == 0:
            self.success = False
            feedback.reportError("Aucune occurrence ne touche aux à l'UDH.\n")
            return {}

        ID_ori = set([str(feature.attribute(field_occurrences)) for feature in vlayer_occurrences.getSelectedFeatures(request)])
        ID_touched = set([str(feature.attribute(field_occurrences)) for feature in vlayer_occurrences_touched.getFeatures(request)])
        ID_diff = list(ID_ori.difference(ID_touched))
        if len(ID_diff):
            if len(ID_diff) > 1:
                accord = "les occurrences sélectionnées suivantes ne seront pas traitées car elles ne touchent"
            else:
                accord = "l'occurrence sélectionnée suivante ne sera pas traitée car elle ne touche"
            
            feedback.pushInfo(f"--> Attention, {accord} à pas l'UDH: {', '.join(ID_diff)}\n")


        # Avertissement si les occurrences sont multipart
        if QgsWkbTypes.isMultiType(vlayer_occurrences_touched.wkbType()):
            feedback.pushInfo("--> Attention, la couche d'occurrences étant de type multi-parties, vous pourriez obtenir des bassins versants disjoints.\n")


        # Bouclage pour traiter toutes occurrences consécutivement
        ls_fids = [(feature.id(), feature.attribute(field_occurrences)) for feature in vlayer_occurrences_touched.getFeatures(request)]
        ls_fids.sort(key=itemgetter(1))
        nb_occurrences = len(ls_fids)
        feedback.setProgress(1)

        for ii, (fid, ID) in enumerate(ls_fids):

            if feedback.isCanceled():
                return {}

            feedback.pushInfo(f"- occurrence {ID} ({ii+1}/{nb_occurrences})")

            # Création du répertoire temporaire
            now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            tempdir = os.path.join(roottempdir, f"HydroUtils_occurrence_{ID}_{now}")
            os.makedirs(tempdir)
            print("Répertoire temporaire => " + tempdir)


            # Détermine quelles sont les UD touchées par l'occurrence
            vlayer_occurrences_touched.selectByIds([fid])
            vlayer_occurrence_selected = processing.run("native:saveselectedfeatures", {
                'INPUT':vlayer_occurrences_touched,
                'OUTPUT':'TEMPORARY_OUTPUT'
                })["OUTPUT"]
            
            vlayer_indexUD_touched = processing.run("native:extractbylocation", {
                'INPUT':vlayer_indexUD,
                'PREDICATE':[0],
                'INTERSECT':vlayer_occurrence_selected,
                'OUTPUT':'TEMPORARY_OUTPUT'
                })["OUTPUT"]


            # Bouclage pour extraire le bassin versant pour chaque UD touchée par l'occurrence
            ls_ud = [feature["S_UDH"] for feature in vlayer_indexUD_touched.getFeatures(request)]
            ls_path_watershed = []
            for ud in ls_ud:
                ud_str = str(ud).zfill(3)
                feedback.pushInfo(f"Calcul du bassin versant dans la sous-unité de découpage hydrique {ud_str}")

                # Rasterisation de l'occurrence dans la projection de l'UD
                path_d8 = glob.glob(os.path.join(dird8, f"D8_directions_????_{ud_str}_*.sdat"))
                if len(path_d8) == 0:
                    self.success = False
                    feedback.reportError(f"La matrice de directions de flux pour la sous-unité de découpage hydrique {ud_str} ne semble pas disponible.\n")
                    return {}
                
                path_d8 = path_d8[0]
                udh = os.path.basename(path_d8)[14:18]
                dict_d8 = load_raster(path_d8, readArray=False)
                d8Crs = QgsCoordinateReferenceSystem("EPSG:6622")

                path_occurrence_mask = os.path.join(tempdir, f"mask_occurrence_{ud_str}.sdat")
                rasterize_AOI(vlayer_occurrence_selected, d8Crs.authid(), dict_d8["georef"], dict_d8["xsize"], dict_d8["ysize"], path_occurrence_mask)


                # Extraction du bassin versant via le masque
                path_watershed_SDAT = os.path.join(tempdir, f"watershed_{ud_str}.sdat")
                run_wbt("Watershed", {
                    "d8_pntr":path_d8,
                    "pour_pts":path_occurrence_mask,
                    "output":path_watershed_SDAT
                    }, path_wbt, startupinfo)
                

                # Conversion de l'aire de drainage matricielle en polygone
                path_watershed_temp_SHP = os.path.join(tempdir, f"watershed_polygonize_{ud_str}.shp")
                processing.run("gdal:polygonize", {
                    'INPUT':path_watershed_SDAT,
                    'BAND':1,
                    'FIELD':'DN',
                    'EIGHT_CONNECTEDNESS':False,
                    'OUTPUT':path_watershed_temp_SHP
                    })
                

                # Réparation des géométries, ajout de la projection et 
                # transformation en multi-parties pour couvrir les cas d'un pixel (ou groupe de pixels)
                # ne touchant au polygon principal que par une diagonale.
                # Normalement, le paramètre 'EIGHT_CONNECTEDNESS':True de gdal:polygonize
                # devrait justement s'en charger, mais j'ai eu un cas où ça n'a pas fonctionné comme prévu.
                path_watershed_SHP = os.path.join(tempdir, f"watershed_fixed_{ud_str}.shp")
                vlayer_watersehd_fixed = processing.run("native:fixgeometries", {'INPUT':path_watershed_temp_SHP, 'OUTPUT':'TEMPORARY_OUTPUT'})["OUTPUT"]
                processing.run("native:collect", {'INPUT':vlayer_watersehd_fixed,'FIELD':['DN'],'OUTPUT':path_watershed_SHP})
                processing.run("qgis:definecurrentprojection", {'INPUT':path_watershed_SHP, 'CRS':d8Crs})

                ls_path_watershed.append(path_watershed_SHP)
            

            # Fusion des bassins versants initiaux
            vlayer_watershed = processing.run("native:mergevectorlayers", {
                'LAYERS':ls_path_watershed,
                'OUTPUT':'TEMPORARY_OUTPUT'
                })["OUTPUT"]


            ## Ajout des UD en amont si le bassin versant initial touche à des exutoires en amont

            # Création de la liste des UD immédiatement en amont
            # La démarche fonctionne pour le moment car les matrices de direction de flux ont un buffer et
            # débordent donc chez les voisines. Ce sera à revoir lorsque les matrices s'imbriqueront parfaitement
            vlayer_perimeter = processing.run("native:polygonstolines", {
                'INPUT':vlayer_watershed,
                'OUTPUT':'TEMPORARY_OUTPUT'
                })["OUTPUT"]

            context.project().addMapLayer(vlayer_streams, False)
            processing.run("native:selectbylocation", {
                'INPUT':vlayer_streams,
                'PREDICATE':[0],
                'INTERSECT':vlayer_perimeter,
                'METHOD':0
                })
            
            vlayer_streams.selectByExpression(f'"PERENNITE" = \'P\'', QgsVectorLayer.IntersectSelection)

            processing.run("native:selectbylocation", {
                'INPUT':vlayer_indexUD,
                'PREDICATE':[0],
                'INTERSECT':QgsProcessingFeatureSourceDefinition(vlayer_streams.id(), True),
                'METHOD':0
                })
            context.project().removeMapLayer(vlayer_streams.id())

            set_ud_intersect = set([feature["S_UDH"] for feature in vlayer_indexUD.getSelectedFeatures()])
            set_ud_ori = set(ls_ud)
            ls_ud_upstream = list(set_ud_intersect.difference(set_ud_ori))
            print(ls_ud_upstream)

            if len(ls_ud_upstream):
                # Analyse du réseau
                G = nx.DiGraph()
                G.add_edges_from([(feature["S_UDH"], feature["S_UDH_AVAL"]) for feature in vlayer_indexUD.getFeatures() if feature["S_UDH_AVAL"] != None])
                upstream_nodes = ls_ud_upstream + [node_from for node_from, *_ in nx.edge_dfs(G, ls_ud_upstream, orientation="reverse")]
                upstream_nodes = set(str(x) for x in upstream_nodes)
                print(upstream_nodes)


                # Extraction et fusion des UD pertinentes
                upstream_watersheds = processing.run("native:extractbyexpression", {
                    'INPUT':vlayer_indexUD,
                    'EXPRESSION':f'"S_UDH" IN ({",".join(upstream_nodes)})',
                    'OUTPUT':'TEMPORARY_OUTPUT'
                    })["OUTPUT"]

                vlayer_watershed = processing.run("native:mergevectorlayers", {
                    'LAYERS':[vlayer_watershed, upstream_watersheds],
                    'OUTPUT':'TEMPORARY_OUTPUT'
                    })["OUTPUT"]


            vlayer_watershed = processing.run("native:dissolve", {
                'INPUT':vlayer_watershed,
                'FIELD':[],
                'OUTPUT':'TEMPORARY_OUTPUT'
                })["OUTPUT"]
            
            # Retrait des trous entre UD... éventuellement il faudrait plutôt que je règle ce problème à la
            # source en ayant des matrices de direction de flux qui s'imbriqueent parfaitement. Il faut donc
            # régler le problème d'incertitude en modélisation adjacente
            vlayer_watershed = processing.run("native:deleteholes", {
                'INPUT':vlayer_watershed,
                'MIN_AREA':2000,
                'OUTPUT':'TEMPORARY_OUTPUT'
                })["OUTPUT"]


            # Ajouter la géométrie au sink en faisant suivre le numéro de l'occurrence ainsi que le numéro d'UDH
            geom = vlayer_watershed.getFeature(1).geometry()
            geom.transform( QgsCoordinateTransform(vlayer_watershed.crs(), sinkCrs, QgsProject.instance()) )

            fet = QgsFeature()
            fet.setGeometry(geom)
            fet.setAttributes([ID, udh, geom.area() / 10000])
            sink.addFeature(fet)
            feedback.setProgress((ii+1) / nb_occurrences * 100)
            feedback.pushInfo("")


            # Suppression des fichiers temporaires
            shutil.rmtree(tempdir)

        return {}

 
    def postProcessAlgorithm(self, context, feedback):
        if self.success:
            output = QgsProcessingUtils.mapLayerFromString(self.sink_id, context)
            output.loadNamedStyle(os.path.join(self.script_dir, "bv.qml"))
            output.triggerRepaint()

        return {}

    def name(self):
        return 'watershed'

    def displayName(self):
        return 'Déterminer les bassins versants d\'occurrences'

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return ''

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return watershed()
