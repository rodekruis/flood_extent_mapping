import sys
import json                                   # JSON encoder and decoder
import os                                     # data access
import shutil                                 # file operations
import functools                              # higher-order functions and operations
from osgeo import ogr, gdal, osr              # data conversion
from sentinelsat.sentinel import SentinelAPI, read_geojson, geojson_to_wkt  # interface to Open Access Hub
from processing import *
from writeoutput import *
from helperfunctions import *
from showmaps import *
from downloadimage import *


def mapflood(polarisations, dlinfo, showmaps):
    directory = os.getcwd()

    try:
        # get GeoJSON from either JSON, SHP, or KMZ file
        data_json = readJSONFromAOI('%s/AOI' % directory)
    except FileNotFoundError:
        sys.exit('\nNo area of interest found. Please add one to the AOI map.')

    # Download image
    footprint = geojson_to_wkt(data_json)
    api = SentinelAPI(dlinfo['username'], dlinfo['password'], 'https://scihub.copernicus.eu/dhus')

    firstproduct = get_first_product_id(api, footprint, dlinfo)
    firstproduct_id = firstproduct[0]
    firstproduct_json = firstproduct[1]

    if showmaps:
        plotdownloadmap(data_json, firstproduct_json)

    downloadproduct(api, firstproduct_id, directory)
    
    # Prepare for processing
    sourceBands = set_sourcebands(polarisations)
    out_ext = set_output_extensions(polarisations)
    input_path = os.path.join(directory, 'input')
    input_name = get_input_name(input_path)
    ### !!! MAKE SURE THAT ALWAYS THE RIGHT S1 PRODUCT IS USED (IN CASE THERE ARE MULTIPLE IN THE INPUT FILE)
    S1_source = snappy.ProductIO.readProduct('%s/%s' % (input_path, input_name))
    
    if showmaps:
        plotbasicmap(S1_source, data_json)
        
    # Image processing
    S1_crop = make_subset(S1_source, footprint, sourceBands)
    S1_Orb = apply_orbit_file(S1_crop)
    S1_Thm = thermal_noise_removal(S1_Orb)
    S1_Cal = radiometric_calibration(S1_Thm)
    S1_Spk = speckle_filtering(S1_Cal)
    S1_Spk_db = convert_to_db(S1_Spk)
    S1_TC = terrain_correction(S1_Spk_db)
    S1_floodMask = binarization(S1_TC, S1_Spk_db)
    S1_floodMask_Spk = speckle_filtering(S1_floodMask)
    
    
    # Wite output
    writingoutput(S1_floodMask_Spk, directory, input_name, out_ext, polarisations)

    if showmaps:
        plotfloodmap(input_name, polarisations, directory, out_ext)

        
################################################
##################### CODE #####################
################################################

# polarisations to be processed
polarisations = 'VH'                              # 'VH', 'VV', 'both'

# download image from Copernicus Open Access Hub
dlinfo = {
    'period_start'      : [2022, 1, 15],           # format: [Year, Month, Day] e.g. DAY AFTER FLOOD HAPPENED 
    'period_stop'       : [2022, 1, 25],           # format: [Year, Month, Day] e.g. WEEK AFTER FLOOD HAPPENED
    'username'          : 'username',             # username for login
    'password'          : 'password'              # password for login
}

# show intermediate results if set to 'True'
showmaps = True                               # 'True', 'False'

mapflood(polarisations, dlinfo, showmaps)