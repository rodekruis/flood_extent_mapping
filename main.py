# polarisations to be processed
polarisations = 'VH'                              # 'VH', 'VV', 'both'

# download image from Copernicus Open Access Hub
download = {
    'imageDownload'     : True,                   # 'True', 'False'
    'period_start'      : [2022, 1, 15],           # format: [Year, Month, Day] DAY AFTER FLOOD HAPPENED -> code will automatically search the most recent image within given period
    'period_stop'       : [2022, 1, 25],           # format: [Year, Month, Day] WEEK AFTER FLOOD HAPPENED
    'username'          : 'jacopo_margutti',             # username for login
    'password'          : 'Room4Copernicus'              # password for login
}

# show intermediate results if set to 'True'
plotResoluts = True                               # 'True', 'False'

#####################################################
###################### IMPORTS ######################
#####################################################

# MODULE                                      # DESCRIPTION
import sys
import matplotlib.pyplot as plt               # create visualizations
import numpy as np                            # scientific comupting
import json                                   # JSON encoder and decoder
import glob                                   # data access
import os                                     # data access
import ipywidgets                             # interactive UI controls
import time                                   # time assessment
import shutil                                 # file operations
import ipyleaflet                             # visualization
import geopandas                              # data analysis and manipulation
import pandas as pd####
import snappy                                 # SNAP Python interface
import jpy                                    # Python-Java bridge
import skimage.filters                        # threshold calculation
import functools                              # higher-order functions and operations
from ipyfilechooser import FileChooser        # file chooser widget
from sentinelsat.sentinel import SentinelAPI, read_geojson, geojson_to_wkt  # interface to Open Access Hub
from datetime import date                     # dates, times and intervalls
from IPython.display import display           # visualization
from osgeo import ogr, gdal, osr              # data conversion
from zipfile import ZipFile                   # file management
from collections import OrderedDict
from processing import *
from writeoutput import *
from helperfunctions import readJSONFromAOI #remove this line when the other function that uses this is moved

#when done check packages are still needed

####################################################
############### FUNCTION DEFINITIONS ###############
####################################################
# plot band and histogram of 'Band'-type input and threshold
# SNAP API: https://step.esa.int/docs/v6.0/apidoc/engine/
def plotBand(band, threshold, binary=False):
    # color stretch
    vmin, vmax = 0, 1
    # read pixel values
    w = band.getRasterWidth()
    h = band.getRasterHeight()
    band_data = np.zeros(w * h, np.float32)
    band.readPixels(0, 0, w, h, band_data)
    band_data.shape = h, w
    # color stretch
    if binary:
        cmap = plt.get_cmap('binary')
    else:
        vmin = np.percentile(band_data, 2.5)
        vmax = np.percentile(band_data, 97.5)
        cmap = plt.get_cmap('gray')
    # plot band
    fig, (ax1, ax2) = plt.subplots(1,2, figsize=(16,6))
    ax1.imshow(band_data, cmap=cmap, vmin=vmin, vmax=vmax)
    ax1.set_title(band.getName())
    # plot histogram
    band_data.shape = h * w 
    ax2.hist(np.asarray(band_data[band_data != 0], dtype='float'), bins=2048)
    ax2.axvline(x=threshold, color='r')
    ax2.set_title('Histogram: %s' % band.getName())
    
    for ax in fig.get_axes():
        ax.label_outer()

####################################################
####################### CODE #######################
####################################################   
# get current working directory
directory = os.getcwd()

print('Initialization done')

####################################################
############### DOWNLOADING ###############
####################################################

# check user input whether image download is requested
if download['imageDownload']:
    dlinfo = download
    try:
        # calls readJSONfromAOI function to get GeoJSON from either JSON, SHP, or KMZ file
        data_json = readJSONFromAOI('%s/AOI' % directory)
    # if no AOI is given, it needs to be uploaded
    except FileNotFoundError:
        print('No area of interest found. Please add one to the AOI map')    
        
    # search for available Sentinel-1 tiles according to JSON data
    footprint = geojson_to_wkt(data_json)
    
    # connect to the API
    api = SentinelAPI(dlinfo['username'], dlinfo['password'], 'https://scihub.copernicus.eu/dhus')
  
    # search Copernicus Open Access Hub for products with regard to input footprint and sensing period
    try:
        # !!! SOMEHOW THIS DOESNT WORK INSIDE A FUNCTION
        products = api.query(footprint,
                             date = (date(dlinfo['period_start'][0], dlinfo['period_start'][1], dlinfo['period_start'][2]),
                                     date(dlinfo['period_stop'][0], dlinfo['period_stop'][1], dlinfo['period_stop'][2])),
                             platformname = 'Sentinel-1',
                             producttype = 'GRD')
        print('Successfully connected to Copernicus Open Access Hub.\n', flush=True)
    except:
        sys.exit('\nLogin data not valid. Please change username and/or password.')

    # convert to dataframe
    products_df = api.to_dataframe(products).sort_values('ingestiondate', ascending=[True])

    # THIS IS NOT WOKRING raise warning that no image is available in given sensing period
    products_json = api.to_geojson(products)
    if not products_json['features']:
        sys.exit('\nNo Sentinel-1 images available. Please change sensing period in user input section.')

    # get product closest to flood date product by id
    firstproduct_id = products_df['uuid'][0]
    print('Sentinel-1 image to download: ' + firstproduct_id)

    productinfo = products_df[["filename", "size", "beginposition", "endposition", "ingestiondate", "footprint"]]
    pd.set_option('display.max_colwidth', None)
    display(productinfo.head(1))


# get product information
product_info = api.get_product_odata(firstproduct_id)
# check whether product is available
if product_info['Online']:
    # check if input folder exists, if not create input folder
    input_path = os.path.join(directory, 'input')
    if not os.path.isdir(input_path):
        os.mkdir(input_path)
    # change into 'input' subfolder for storing product
    os.chdir(input_path)
    # status update
    print('\nProduct %s is online. Starting download.' % firstproduct_id, flush=True)
    # download product
    api.download(firstproduct_id)
    # change back to previous working directory
    os.chdir(directory)
# error message when product is not available
else:
    print('\nProduct %s is not online. Must be requested manually.\n' % tile_id, flush=True)
    
print('Downloading done.')

####################################################
############### FUNCTION DEFINITIONS ###############
####################################################

# create S1 product
def getScene(path):
    # set correct path of input file and create S1 product
    if len(files) == 1:
        file_path = path
    else:
        file_path = path.selected
    S1_source = snappy.ProductIO.readProduct(file_path)

    # read geographic coordinates from Sentinel-1 image meta data
    meta_data = S1_source.getMetadataRoot().getElement('Abstracted_Metadata')
    # refines center of map according to Sentinel-1 image
    center = (meta_data.getAttributeDouble('centre_lat'), meta_data.getAttributeDouble('centre_lon'))
    locations = [[{'lat' : meta_data.getAttributeDouble('first_near_lat'), 'lng' : meta_data.getAttributeDouble('first_near_long')},
                  {'lat' : meta_data.getAttributeDouble('last_near_lat'),  'lng' : meta_data.getAttributeDouble('last_near_long')},
                  {'lat' : meta_data.getAttributeDouble('last_far_lat'),   'lng' : meta_data.getAttributeDouble('last_far_long')},
                  {'lat' : meta_data.getAttributeDouble('first_far_lat'),  'lng' : meta_data.getAttributeDouble('first_far_long')}]]
    
    # check whether AOI file is given and convert to JSON in order to show AOI on map
    try:
        # calls readJSONfromAOI function to get GeoJSON from either JSON, SHP, or KMZ file
        data_json = readJSONFromAOI('%s/AOI' % directory)
        # apply subset according to JSON data
        footprint = geojson_to_wkt(data_json)
        # run processing process
        scene = processing(S1_source, footprint)
        return(scene)
    
    except:
        print('Processing failed') 
        return('failed')

####################################################
####################### CODE #######################
####################################################

# filter required polarisation(s) and set output file name accordingly
if polarisations == 'both':
    sourceBands = 'Amplitude_VH,Intensity_VH,Amplitude_VV,Intensity_VV'
    out_ext   = 'processed_VHVV'
elif polarisations == 'VH':
    sourceBands = 'Amplitude_VH,Intensity_VH'
    out_ext   = 'processed_VH'
elif polarisations == 'VV':
    sourceBands = 'Amplitude_VV,Intensity_VV'
    out_ext   = 'processed_VV'

# path of Sentinel-1 .zip input file
input_path = os.path.join(directory, 'input')

# empty string array to store Sentinel-1 files in 'input' subfolder
files = []

# add files to list
for file in glob.glob1(input_path, '*.zip'):
    files.append(file)

# select input file and start processing if there is only one available Sentinel-1 file
input_name = files[0]
print('Selected:  %s\n' % input_name, flush=True)

# apply subset according to JSON data
S1floodmask = getScene('%s/%s' % (input_path, input_name)) # i feel like this should be split up in clearer steps instead of these nested functions 
print(S1floodmask)

# GeoTIFF_path = os.path.join(output_path, 'GeoTIFF')
# floodmask = snappy.ProductIO.writeProduct(S1floodmask, '%s/%s_%s' % (GeoTIFF_path, os.path.splitext(input_name)[0], output_extensions), 'GeoTIFF')

writingoutput(S1floodmask, directory, input_name, out_ext)

