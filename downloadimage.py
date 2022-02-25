import sys
import pandas as pd
import os                                     # data access
import glob                                   # data access
from collections import OrderedDict
from sentinelsat.sentinel import SentinelAPI, read_geojson, geojson_to_wkt  # interface to Open Access Hub
from datetime import date                     # dates, times and intervalls
from IPython.display import display

def get_first_product_id(api, footprint, downloadinfo):
    # search Copernicus Open Access Hub for products with regard to input footprint and sensing period
    try: 
        # !!! SOMEHOW THIS DOESNT WORK INSIDE A FUNCTION because the package datatime is missing... 
        products = api.query(footprint,
                             date = (date(downloadinfo['period_start'][0], downloadinfo['period_start'][1], downloadinfo['period_start'][2]),
                                     date(downloadinfo['period_stop'][0], downloadinfo['period_stop'][1], downloadinfo['period_stop'][2])),
                             platformname = 'Sentinel-1',
                             producttype = 'GRD')
        print('Successfully connected to Copernicus Open Access Hub.\n', flush=True)
    except:
        sys.exit('\nLogin data not valid. Please change username and/or password.')

    # THIS IS NOT WOKRING raise warning that no image is available in given sensing period
    products_json = api.to_geojson(products)
    if not products_json['features']:
        sys.exit('\nNo Sentinel-1 images available. Please change sensing period in user input section.')

        # convert to dataframe to show product information
    products_df = api.to_dataframe(products).sort_values('ingestiondate', ascending=[True])
    # get product closest to flood date product by id
    firstproduct_id = products_df['uuid'][0]
    print('Sentinel-1 image to download: ' + firstproduct_id)
    productinfo = products_df[["filename", "size", "beginposition", "endposition", "ingestiondate", "footprint"]]
    pd.set_option('display.max_colwidth', None)
    display(productinfo.head(1))
    
    firstproduct = products.popitem(last=True)
    firstproductdict = OrderedDict([firstproduct])
    firstproduct_json = api.to_geojson(firstproductdict)
    
    return(firstproduct_id, firstproduct_json)
    
def downloadproduct(api, firstproduct_id, directory):
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
        print('Downloading done.')
    else:
        print('\nProduct %s is not online. Must be requested manually.\n' % tile_id, flush=True)
    