# -*- coding: utf-8 -*-


__author__ = 'Jean-François Bourdon - MFFP (DIF)'
__date__ = '2020-09-01'
__copyright__ = '(C) 2020 by Jean-François Bourdon - MFFP (DIF)'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import *
from qgis.utils import pluginMetadata
from PyQt5.QtCore import *
import processing
from processing.core.Processing import Processing
from qgis.analysis import QgsNativeAlgorithms

import configparser
import datetime
import numpy as np
import os
from osgeo import gdal, ogr
import subprocess
import tempfile
import time



# Récupère les infos dans le fichier config.ini
def get_config(script_dir):
    config_path = os.path.join(script_dir, "config.ini")
    config = configparser.ConfigParser()
    config.optionxform = lambda option: option
    config.read(config_path)
    if config["variables"]["tempdir"] == "":
        config["variables"]["tempdir"] = tempfile.gettempdir()
    return config


# Écrit dans un fichier config.ini les paramètre d'un objet ConfigParser
def write_config(config, script_dir):
    config_path = os.path.join(script_dir, "config.ini")
    with open(config_path, 'w') as configfile:
        config.write(configfile)


# Runner alternatif de WhiteboxTools pour éviter tout bug de l'API officielle
# Avoir une valeur par défaut au paramètre "path_wbt" tirée du config.ini serait bien
def run_wbt(toolname, dict_params, path_wbt, startupinfo=None):
    # Construction des arguments pour les clefs ayant une valeur booléenne
    dict_bool = {key:value for key, value in dict_params.items() if isinstance(value, bool)}
    for key, _ in dict_bool.items():
        del dict_params[key]
    
    bool_params = [f"--{key.lower()}" for key, value in dict_bool.items() if value]

    # Construction des arguments pour les clefs restantes
    ls_params = [f"--{key.lower()}='{value}'" for key, value in dict_params.items()]
    cmd = " ".join([path_wbt, f"--run='{toolname}'"] + ls_params + bool_params)

    # Exécution
    if startupinfo is None:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags = subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        res = subprocess.run(cmd, startupinfo=startupinfo)
    else:
        res = subprocess.run(cmd, startupinfo=startupinfo)

    return res


# Charge un raster GeoTIFF, FLT ou SDAT en tant que numpy array
# Possibilité de seulement extraire les médatonnées pour plus
# de rapidité
def load_raster(path_raster, no_band=1, readArray=True):
    extension = os.path.basename(path_raster).lower().split(".")[-1]
    drivername = ["GTiff", "EHdr", "SAGA"][["tif", "flt", "sdat"].index(extension)]
    
    driver = gdal.GetDriverByName(drivername)
    ds = gdal.Open(path_raster)
    
    proj = ds.GetProjection()
    georef = ds.GetGeoTransform()
    xsize = ds.RasterXSize
    ysize = ds.RasterYSize
    band = ds.GetRasterBand(no_band)
    nodata = band.GetNoDataValue()
    arr = band.ReadAsArray() if readArray else None
    
    return {"array":arr, "proj":proj, "georef":georef, "xsize":xsize, "ysize":ysize, "nodata":nodata}


# Permet de trouver le point d'accumulation maximale à l'intérieur
# d'une zone définie par un masque raster
def find_flowMax(dict_flow_acc, arr_mask):
    arr_flow_acc = np.copy(dict_flow_acc["array"])
    georef = dict_flow_acc["georef"]

    # Détermination du point d'accumulation maximale
    arr_flow_acc = arr_flow_acc * arr_mask
    flow_max = np.max(arr_flow_acc)
    itemIndex = np.where(arr_flow_acc == flow_max)

    dict_flowMax = {}
    dict_flowMax["xarray"] = itemIndex[1][0]
    dict_flowMax["yarray"] = itemIndex[0][0]
    dict_flowMax["xgeoref"] = dict_flowMax["xarray"]*georef[1] + georef[1]/2 + georef[0]
    dict_flowMax["ygeoref"] = dict_flowMax["yarray"]*georef[5] + georef[5]/2 + georef[3]
    dict_flowMax["flow"] = flow_max

    return dict_flowMax


# Conversion en matrice de l'UD polygonale d'origine
# L'initialisation à 0 évite que GDAL mette une valeur réelle de NoData de 255
def rasterize_AOI(vlayer_AOI, epsg_str, georef, xsize, ysize, path_mask):
    if epsg_str != vlayer_AOI.crs().authid():
        vlayer_AOI = processing.run("native:reprojectlayer", {
            'INPUT':vlayer_AOI,
            'TARGET_CRS':QgsCoordinateReferenceSystem(epsg_str),
            'OUTPUT':'TEMPORARY_OUTPUT'
            })["OUTPUT"]
    
    pixel_size = georef[1]
    extent_ref = ",".join([
        str(georef[0]),
        str(georef[0] + xsize * pixel_size),
        str(georef[3] - ysize * pixel_size),
        str(georef[3])
        ]) + f" [{epsg_str}]"

    nodata = 0
    processing.run("gdal:rasterize", {
        'INPUT':vlayer_AOI,
        'FIELD':'',
        'BURN':1,
        'UNITS':1,
        'WIDTH':pixel_size,
        'HEIGHT':pixel_size,
        'EXTENT':extent_ref,
        'NODATA':nodata,
        'OPTIONS':'NBITS=1',
        'DATA_TYPE':0,
        'INIT':nodata,
        'OUTPUT':path_mask
        })
    
    if path_mask[-5:].lower() == ".sdat":
        correct_SGRD(path_mask, nodata=nodata)


def correct_SGRD(filepath, cellsize=None, nodata=None):
    path_SGRD = filepath[:-5] + ".sgrd"
    
    with open(path_SGRD, "r+") as f:
        ls_lines = f.readlines()

        if cellsize is not None:
            idx_ymin = [ii for ii, line in enumerate(ls_lines) if line.find("POSITION_YMIN") == 0][0]
            ls_lines[idx_ymin] = f"POSITION_YMIN\t= {float(ls_lines[idx_ymin].split()[-1]) - cellsize}\n"

            idx_cellsize = [ii for ii, line in enumerate(ls_lines) if line.find("CELLSIZE") == 0][0]
            ls_lines[idx_cellsize] = f"CELLSIZE\t= {cellsize}\n"

        if nodata is not None:
            idx_nodata = [ii for ii, line in enumerate(ls_lines) if line.find("NODATA_VALUE") == 0][0]
            ls_lines[idx_nodata] = f"NODATA_VALUE\t= {nodata}\n"

        f.seek(0)
        f.writelines(ls_lines)