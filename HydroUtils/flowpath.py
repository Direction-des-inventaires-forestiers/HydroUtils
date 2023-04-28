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

 Liste d'améliorations potentielles
    
 -  

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
from math import floor
import networkx as nx
from operator import itemgetter
import os
import pickle
import shutil
import subprocess

from .sidescripts import *


class flowpath(QgsProcessingAlgorithm):

    script_dir = os.path.dirname(__file__)
    dict_config = get_config(script_dir)

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
                'INPUT_droplet',
                'Point de départ de la goutte',
                [QgsProcessing.TypeVectorPoint]
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
                'INPUT_field_droplet',
                'Identifiant unique des gouttes',
                defaultValue=None,
                parentLayerParameterName="INPUT_droplet"
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                'INPUT_buffer',
                'Rayon de recherche autour de la goutte (m)',
                QgsProcessingParameterNumber.Integer,
                defaultValue=0,
                minValue=0
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                'OUTPUT_flowpath',
                'Trajets des gouttes'
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        roottempdir = self.parameterAsString(parameters, 'INPUT_tempdir', context)
        dird8 = self.parameterAsString(parameters, 'INPUT_d8', context)
        vlayer_droplet_ori = self.parameterAsVectorLayer(parameters, 'INPUT_droplet', context)
        bool_only_selected = self.parameterAsBool(parameters, 'INPUT_only_selected', context)
        field_droplet = self.parameterAsFields(parameters, 'INPUT_field_droplet', context)[0]
        droplet_buffer_width = self.parameterAsInt(parameters, 'INPUT_buffer', context)


        # Validation du type d'entité des gouttes
        #if QgsWkbTypes.isMultiType(vlayer_droplet_ori.wkbType()):
        #    feedback.reportError("Les gouttes de type multi-parties ne peuvent être traitées. Veuillez transformer en parties uniques.\n")
        #    return {}

        # Chargement des écoulement et de l'index d'UD
        path_hydro = glob.glob(os.path.join(dird8, "Hydro_LiDAR_????.gpkg"))
        if len(path_hydro) == 0:
            feedback.reportError(f"Le fichier contenant les écoulements (Hydro_LiDAR_00XX.gpkg) ne semble pas être présent au {dird8}.")
            return {}
        
        udh = path_hydro[0][-9:-5]
        vlayer_streams = QgsVectorLayer(f"{path_hydro[0]}|layername=Hydro_{udh}_l")
        if vlayer_streams.hasFeatures() == 0:
            feedback.reportError(f"La couche d'hydrographie linéaire (Hydro_{udh}_l) ne semble pas être présente ou ne contient aucune entitée.")
            return {}
        
        vlayer_indexUD = QgsVectorLayer(f"{path_hydro[0]}|layername=Index_UD_{udh}_s")
        if vlayer_indexUD.hasFeatures() == 0:
            feedback.reportError(f"La couche d'index des unités de drainage (Index_UD_{udh}_s) ne semble pas être présente ou ne contient aucune entitée.")
            return {}
        
        # Chargement du graphe des écoulements
        # La lecture du fichier pickle est tentée en premier car plus rapide à lire qu'un GML (quelques secondes de différence)
        path_GML = glob.glob(os.path.join(dird8, f"Hydro_{udh}_l.gml"))
        if len(path_GML) == 0:
            feedback.reportError(f"Le graphe d'écoulements (Hydro_{udh}_l.gml) ne semble pas être présent au {dird8}.")
            return {}

        G = nx.read_gml(path_GML[0])

        """
        # J'ai parfois des erreurs bizarres en partant du pickle donc
        # je préfère retirer ça pour le moment
        path_GML_pickle = path_GML[0][:-3] + "pickle"
        try:
            with open(path_GML_pickle, 'rb') as gml_file:
                G = pickle.load(gml_file)
        except:
            G = nx.read_gml(path_GML[0])
        """



        # Création du QgsVectorLayer de sortie contenant les bassins versants de chaque occurrence
        fields_array = [
            vlayer_droplet_ori.fields().field(field_droplet),
            QgsField('UDH', QVariant.String, len=4),
            QgsField('Longeur_km', QVariant.Double, len=15, prec=3)
            ]
        
        fields_flowpath = QgsFields()
        for field in fields_array:
            fields_flowpath.append(field)

        sinkCrs = QgsCoordinateReferenceSystem("EPSG:6622")
        (sink, self.sink_id) = self.parameterAsSink(parameters, 'OUTPUT_flowpath', context, fields_flowpath, QgsWkbTypes.MultiLineString, sinkCrs)


        # Sauvegarde du répertoire par défaut
        self.dict_config["variables"]["tempdir"] = roottempdir
        write_config(self.dict_config, self.script_dir)


        # Chemin d'accès à Whitebox Tools
        path_wbt = os.path.join(self.script_dir, "whitebox_tools.exe")


        # Paramètres pour les appels à subprocess.run()
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags = subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = int(self.dict_config["variables"]["wShowWindow"])


        # Valider que les valeurs de "field_droplet" sont bien uniques
        request = QgsFeatureRequest().setFlags(QgsFeatureRequest().NoGeometry)
        ls_ID = [feature.attribute(field_droplet) for feature in vlayer_droplet_ori.getFeatures(request)]
        if len(ls_ID) != len(set(ls_ID)):
            feedback.reportError(f"Le champ {field_droplet} contient des doublons.")
            return {}
        

        # Fonction pour laisser tomber les valeurs ZM des géométries
        def dropZM(geom):
            return QgsGeometry().fromPolylineXY(geom.asPolyline())


        # Sélection des gouttes à utiliser
        vlayer_droplet = vlayer_droplet_ori.clone()
        if not bool_only_selected:
            vlayer_droplet.selectAll()


        # Validation que les gouttes touchent bel et bien aux UD fournies
        # et reprojection en EPSG:6622
        context.project().addMapLayer(vlayer_droplet, False)
        vlayer_droplet_touched = processing.run("native:extractbylocation", {
            'INPUT':QgsProcessingFeatureSourceDefinition(vlayer_droplet.id(), True),
            'PREDICATE':[0],
            'INTERSECT':vlayer_indexUD,
            'OUTPUT':'TEMPORARY_OUTPUT'
            })["OUTPUT"]
        context.project().removeMapLayer(vlayer_droplet.id())
        
        if vlayer_droplet_touched.hasFeatures() == 0:
            feedback.reportError("Aucune goutte ne touche aux UD.")
            return {}
        
        vlayer_droplet_touched = processing.run("native:reprojectlayer", {
            'INPUT':vlayer_droplet_touched,
            'TARGET_CRS':sinkCrs,
            'OUTPUT':'TEMPORARY_OUTPUT'
            })["OUTPUT"]


        ID_ori = set([str(feature.attribute(field_droplet)) for feature in vlayer_droplet.getSelectedFeatures(request)])
        ID_touched = set([str(feature.attribute(field_droplet)) for feature in vlayer_droplet_touched.getFeatures(request)])
        ID_diff = list(ID_ori.difference(ID_touched))
        if len(ID_diff) > 0:
            if len(ID_diff) > 1:
                accord = "les gouttes sélectionnées suivantes ne seront pas traitées car elles ne touchent"
            else:
                accord = "la goutte sélectionnée suivante ne sera pas traitée car elle ne touche"
            
            feedback.reportError(f"--> Attention, {accord} à aucune UD: {', '.join(ID_diff)}\n")


        # Bouclage pour traiter toutes les gouttes consécutivement
        ls_fids = [(feature.id(), feature.attribute(field_droplet)) for feature in vlayer_droplet_touched.getFeatures(request)]
        ls_fids.sort(key=itemgetter(1))
        nb_droplets = len(ls_fids)
        feedback.setProgress(1)

        for ii, (fid, ID) in enumerate(ls_fids):

            if feedback.isCanceled():
                return {}

            feedback.pushInfo(f"- Goutte {ID} ({ii+1}/{nb_droplets})")

            # Création du répertoire temporaire
            now = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            tempdir = os.path.join(roottempdir, f"HydroUtils_goutte_{ID}_{now[:8]}_{now[8:]}")
            os.makedirs(tempdir)
            print("Répertoire temporaire => " + tempdir)



            # Trouve dans quelle UD la goutte se trouve afin pouvoir sélectionner le traitement
            # approprié par la suite
            context.project().addMapLayer(vlayer_droplet_touched, False)
            vlayer_droplet_touched.selectByIds([fid])
            vlayer_indexUD_touched = processing.run("native:extractbylocation", {
                'INPUT':vlayer_indexUD,
                'PREDICATE':[0],
                'INTERSECT':QgsProcessingFeatureSourceDefinition(vlayer_droplet_touched.id(), True),
                'OUTPUT':'TEMPORARY_OUTPUT'
                })["OUTPUT"]
            droplet_geom = vlayer_droplet_touched.getGeometry(fid)
            droplet_pt = droplet_geom.asPoint()


            ls_ud = [str(feature["NO_UD"]).zfill(3) for feature in vlayer_indexUD_touched.getFeatures(request)]
            if len(ls_ud) > 1:
                feedback.reportError(f"--> Attention, la goutte {ID} ne sera pas traitée car elle tombe dans une zone d'incertitude entre deux unités de drainage.")
                continue

            ud_str = ls_ud[0]

            path_d8 = glob.glob(os.path.join(dird8, f"D8_directions_????_{ud_str}_*.sdat"))
            if len(path_d8) == 0:
                feedback.reportError(f"La matrice de directions de flux pour l'UD {ud_str} ne semble pas disponible.")
                return {}
            
            path_d8 = path_d8[0]
            udh = os.path.basename(path_d8)[14:18]
            dict_d8 = load_raster(path_d8, readArray=False)
            d8Crs = QgsCoordinateReferenceSystem("EPSG:6622")


            # Si un buffer est demandé, alors je cherche le segment le plus près dans le rayon de recherche
            # et j'utilise cet endroit comme nouveau départ
            if droplet_buffer_width > 0:
                droplet_buffer = processing.run("native:buffer", {
                    'INPUT':QgsProcessingFeatureSourceDefinition(vlayer_droplet_touched.id(), True),
                    'DISTANCE':droplet_buffer_width,
                    'SEGMENTS':5,
                    'END_CAP_STYLE':0,
                    'JOIN_STYLE':0,
                    'MITER_LIMIT':2,
                    'DISSOLVE':False,
                    'OUTPUT':'TEMPORARY_OUTPUT'
                    })["OUTPUT"]
                
                vlayer_streams_near = processing.run("native:extractbylocation", {
                    'INPUT':vlayer_streams,
                    'PREDICATE':[0],
                    'INTERSECT':droplet_buffer,
                    'OUTPUT':'TEMPORARY_OUTPUT'
                    })["OUTPUT"]
                
                if vlayer_streams_near.hasFeatures() == 0:
                    feedback.pushInfo(f"Aucun vecteur d'écoulement n'est situé à moins de {droplet_buffer_width} m. La position initiale de la goutte sera utilisée.")
                else:
                    distSqrt_min = droplet_buffer_width**2 + 1
                    stream_pt_min = None
                    for stream in vlayer_streams_near.getFeatures():
                        #stream_pt = (droplet_geom.nearestPoint(stream.geometry())).asPoint()
                        stream_pt = ( stream.geometry().nearestPoint(droplet_geom) ).asPoint()
                        distSqrt = (droplet_pt.x() - stream_pt.x())**2 + (droplet_pt.y() - stream_pt.y())**2
                        if distSqrt < distSqrt_min:
                            stream_pt_min = stream_pt
                    
                    droplet_pt = stream_pt_min
            
            context.project().removeMapLayer(vlayer_droplet_touched.id())


            # Snappe la goutte sur la grille (au milieu d'un pixel) pour regarder ensuite si elle touche directement à un écoulement
            # J'assume une résolution constante en X et Y, ce qui sera toujours le cas avec nos produits
            # Pour simplifier aussi j'assume une résolution de 1, mais il me faudrait une méthode plus générale pour que ça fonctionne
            # avec une autre résolution et un départ qui n'est pas nécessairement à un entier.
            #xmin, res, _, ymax, *_ = dict_d8["georef"]
            half_res = 0.5
            droplet_pt_snap = QgsPointXY(floor(droplet_pt.x()) + half_res, floor(droplet_pt.y()) + half_res)

            # Isolation de la goutte dans son propre QgsVectorLayer pour simplifier les traitement subséquents
            # Une version point et une version polygone (basé sur le pixel) sont créés
            droplet_snap = QgsVectorLayer("point?crs=epsg:6622", "droplet", "memory")
            with edit(droplet_snap):
                f = QgsFeature()
                f.setGeometry(QgsGeometry().fromPointXY(droplet_pt_snap))
                droplet_snap.addFeature(f)
            
            droplet_snap_pixel = QgsVectorLayer("polygon?crs=epsg:6622", "droplet", "memory")
            with edit(droplet_snap_pixel):
                f = QgsFeature()
                x = droplet_pt_snap.x()
                y = droplet_pt_snap.y()
                polygon = QgsGeometry.fromPolygonXY([[
                    QgsPointXY(x - half_res, y - half_res),
                    QgsPointXY(x - half_res, y + half_res),
                    QgsPointXY(x + half_res, y + half_res),
                    QgsPointXY(x + half_res, y - half_res),
                    QgsPointXY(x - half_res, y - half_res)
                    ]])
                f.setGeometry(polygon)
                droplet_snap_pixel.addFeature(f)


            # Vérification pour voir si la goutte tombe exactement sur un écoulement
            # car si c'est le cas l'extraction des segments en aval devra en prendre compte
            processing.run("native:selectbylocation", {
                'INPUT':vlayer_streams,
                'PREDICATE':[0],
                'INTERSECT':droplet_snap_pixel,
                'METHOD':0
                })

            stream_ids = [f.id() for f in vlayer_streams.getSelectedFeatures(request)]


            if len(stream_ids) == 0:
                # Le point ne touche à aucun écoulement et on doit donc extraire le trajet
                # de la goutte avec WhiteboxTools
                print("Extraction avec WBT")

                path_droplet_SHP = os.path.join(tempdir, "droplet_snap.shp")
                processing.run("native:pointtolayer", {
                    'INPUT':f"{droplet_pt_snap.x()},{droplet_pt_snap.y()} [{d8Crs.authid()}]",
                    'OUTPUT':path_droplet_SHP
                    })

                path_flowpath_SDAT = os.path.join(tempdir, "flowpath.sdat")
                run_wbt("TraceDownslopeFlowpaths", {
                    "d8_pntr":path_d8,
                    "seed_pts":path_droplet_SHP,
                    "output":path_flowpath_SDAT
                    }, path_wbt, startupinfo)

                path_flowpath_raster_SHP = os.path.join(tempdir, "flowpath_from_raster.shp")
                run_wbt("RasterStreamsToVector", {
                    "streams":path_flowpath_SDAT,
                    "d8_pntr":path_d8,
                    "output":path_flowpath_raster_SHP
                    }, path_wbt, startupinfo)
                processing.run("qgis:definecurrentprojection", {'INPUT':path_flowpath_raster_SHP, 'CRS':d8Crs})


                # Vérification pour voir si le début du tracé tombe exactement sur un écoulement
                # car si c'est le cas l'extraction des segments en aval devra en prendre compte
                vertex_start = processing.run("native:extractspecificvertices", {
                    'INPUT':path_flowpath_raster_SHP,
                    'VERTICES':'0',
                    'OUTPUT':'TEMPORARY_OUTPUT'
                    })["OUTPUT"]
                
                processing.run("native:selectbylocation", {
                    'INPUT':vlayer_streams,
                    'PREDICATE':[0],
                    'INTERSECT':vertex_start,
                    'METHOD':0
                    })
            
                stream_ids = [f.id() for f in vlayer_streams.getSelectedFeatures()]
                droplet_pt_snap = vertex_start.getFeature(1).geometry().asPoint()


            if len(stream_ids) == 1:
                # Le point de départ se situe directement sur un écoulement
                # L'écoulement sera découpé en deux grâce à une lame constituée du point de départ
                # et d'un deuxième point situé à proximité. Celui-ci est ajouté de façon à ne pas
                # reproduire un angle de 0-45-90° en plus de rester sous la résolution du raster de 1 m
                pt1 = QgsPointXY(droplet_pt_snap.x() - 0.1, droplet_pt_snap.y() - 0.15)
                pt2 = QgsPointXY(droplet_pt_snap.x() + 0.1, droplet_pt_snap.y() + 0.15)
                blade = QgsVectorLayer("linestring?crs=epsg:6622", "blade", "memory")
                with edit(blade):
                    f = QgsFeature()
                    f.setGeometry(QgsGeometry().fromPolylineXY([pt1,pt2]))
                    blade.addFeature(f)

                context.project().addMapLayer(vlayer_streams, False)
                stream_split = processing.run("native:splitwithlines", {
                    'INPUT':QgsProcessingFeatureSourceDefinition(vlayer_streams.id(), True),
                    'LINES':blade,
                    'OUTPUT':'TEMPORARY_OUTPUT'
                    })["OUTPUT"]
                context.project().removeMapLayer(vlayer_streams.id())

                geom_split = stream_split.getFeature(2).geometry()
                geom_upstream = [dropZM(geom_split)]
                stream_id = stream_ids[0]
                
            elif len(stream_ids) > 1:
                # Le point de départ se situe directement sur une intersection
                # On trouve quel ID est celui le plus en aval.
                # ATTENTION, présentement j'assume qu'il y a toujours un seul aval!!
                ls_included = [int(list(G.neighbors(str(stream_id)))[0]) not in stream_ids for stream_id in stream_ids]
                stream_id = stream_ids[ls_included.index(True)]
                vlayer_streams.selectByIds([stream_id])
                geom_upstream = [dropZM(f.geometry()) for f in vlayer_streams.getSelectedFeatures()]

            else:
                # Le point de départ se situe dans le néant
                # On conserve uniquement la première partie du résultat de la différence
                # puisqu'elle représente la partie la plus en amont
                flowpath_diff = processing.run("native:difference", {
                    'INPUT':path_flowpath_raster_SHP,
                    'OVERLAY':vlayer_streams,
                    'OUTPUT':'TEMPORARY_OUTPUT'
                    })["OUTPUT"]

                feat_diff = flowpath_diff.getFeature(1)
                geom_diff = feat_diff.geometry().asGeometryCollection()[0]
                with edit(flowpath_diff):
                    flowpath_diff.changeGeometry(1, geom_diff)

                processing.run("native:selectbylocation", {
                    'INPUT':vlayer_streams,
                    'PREDICATE':[0],
                    'INTERSECT':flowpath_diff,
                    'METHOD':0
                    })
                

                # L'écoulement existant est coupé à l'intersection pour permettre un réseau continu
                context.project().addMapLayer(vlayer_streams, False)
                stream_split = processing.run("native:splitwithlines", {
                    'INPUT':QgsProcessingFeatureSourceDefinition(vlayer_streams.id(), True),
                    'LINES':flowpath_diff,
                    'OUTPUT':'TEMPORARY_OUTPUT'
                    })["OUTPUT"]
                context.project().removeMapLayer(vlayer_streams.id())

                geom_split = stream_split.getFeature(2).geometry()
                geom_upstream = [dropZM(geom_diff), dropZM(geom_split)]
                stream_id = [f.id() for f in vlayer_streams.getSelectedFeatures()][0]


            # Récupération de toutes les géométries en aval
            starting_node = str(stream_id)
            downstream_nodes = [int(node_to) for _, node_to, _ in nx.edge_dfs(G, starting_node, orientation="original")]
            vlayer_streams.selectByIds(downstream_nodes)
            geom_downstream = [dropZM(f.geometry()) for f in vlayer_streams.getSelectedFeatures()]
            ls_geom = geom_downstream if geom_upstream is None else geom_upstream + geom_downstream
            

            # Constitution du trajet complet de la goutte
            geom_trace = QgsGeometry().collectGeometry(ls_geom)
            fet = QgsFeature()
            fet.setGeometry(geom_trace)
            fet.setAttributes([ID, udh, geom_trace.length() / 1000])
            sink.addFeature(fet)
            feedback.setProgress((ii+1) / nb_droplets * 100)
            feedback.pushInfo("")


            # Suppression des fichiers temporaires
            shutil.rmtree(tempdir)

        return {}

 
    def postProcessAlgorithm(self, context, feedback):
        output = QgsProcessingUtils.mapLayerFromString(self.sink_id, context)
        output.loadNamedStyle(os.path.join(self.script_dir, "goutte.qml"))
        output.triggerRepaint()
        return {}

    def name(self):
        return 'flowpath'

    def displayName(self):
        return 'Déterminer le trajet de la goutte'

    def group(self):
        return self.tr(self.groupId())

    def groupId(self):
        return ''

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return flowpath()
