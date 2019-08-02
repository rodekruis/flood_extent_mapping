import feedparser
import pandas as pd
from sentinelsat import SentinelAPI
import os
import rasterio as rio
import matplotlib.pyplot as plt
import numpy as np

import sys
sys.path.append('/Users/rodekruis/Library/Python/3.7/bin')
import seaborn as sns
import urllib.request, sys, getopt, os


def retrieve_all_gdacs_events():
    """
    Reads in the RSS feed from GDACS and returns all current events in a pandas data frame
    """

    feed = feedparser.parse('http://www.gdacs.org/xml/rss.xml')
    events_out = pd.DataFrame(feed.entries)
    return events_out


def get_specific_events(gdacs_events_in, event_code_in):
    """
    Filters the GDACS events by type of event. Available event codes:
    EQ: earthquake
    TC: tropical cyclone
    DR: drought
    ??: flood
    ??: volcano
    Requires a pandas data frame as input. Returns a pandas data frame
    """
    return gdacs_events_in.query("gdacs_eventtype == '{}'".format(event_code_in))


def get_coordinates_for_event(event_in):
    """
    Takes a pandas series for one event as input and returns:
    - lists with bounding box coordinates: [long_min, long_max, lat_min, lat_max]
    - list with coordinates of event point: [long, lat]
    """

    bbox_coordinates_str = event_in.gdacs_bbox.split()
    bbox_coordinates_out = [float(i) for i in bbox_coordinates_str]
    point_coordinates_out = [event_in.geo_long, event_in.geo_lat]
    return bbox_coordinates_out, point_coordinates_out


def create_polygon_from_bbox(bbox_in):
    """
    Turns a list of bounding box coordinates into a list of polygon points
    """
    return [(bbox_in[0], bbox_in[2]),
            (bbox_in[1], bbox_in[2]),
            (bbox_in[1], bbox_in[3]),
            (bbox_in[0], bbox_in[3]),
            (bbox_in[0], bbox_in[2])]


def connect_to_sentinel_api():
    return SentinelAPI('wouteroosterheert', 'rodekruis', 'https://scihub.copernicus.eu/dhus')


# TODO select image with most overlap
def get_available_satellite_images(api_in, coordinates_in, coordinates_type='POLY'):
    """
    Queries the sentinel api for available images in the past 30 days for a specified region for Sentinel-1.
    Region can be specified either by the coordinates of a point (coordinates_type='POINT') or a list of polygon points.
    The area in the query needs to be provided as in:
    https://en.wikipedia.org/wiki/Well-known_text_representation_of_geometry
    After querying it filters for the GRD images and sorts them by ingestion date
    Function returns a dataframe with all the available image id's and their properties
    """

    if coordinates_type == 'POLY':
        poly = coordinates_in
        area = "POLYGON(({}))".format(",".join(["{} {}".format(p[0], p[1]) for p in poly]))
    else:
        point = coordinates_in
        area = "POINT({} {})".format(point[0], point[1])

    products = api_in.query(date=('NOW-30DAYS', 'NOW'),
                            platformname='Sentinel-1',
                            area=area)

    products_df = api_in.to_dataframe(products)
    grd_df = products_df.query('producttype =="GRD"')
    grd_df.sort_values('ingestiondate', ascending=False, inplace=True)
    return grd_df


def download_satellite_image(api_in, image_id_in, savedir_in):
    """
    Downloads one image specified by its ID and stores it in the specified savedir
    """
    download_out = api_in.download(image_id_in, directory_path=savedir_in)
    return download_out


def remove_noise_using_snap(path_in, path_out, path_graph, path_to_gpt='/Applications/snap/bin/gpt'):
    """
    Runs the graph processing tool from SNAP to perform denoising using a predefined processing graph.
    """
    os.system("{} -t {} {} {}".format(path_to_gpt, path_out, path_graph, path_in))


def read_in_denoised_image(path_in):

    with rio.open(path_in) as src:
        im_out = src.read(1)

    return im_out


def get_water_threshold(im_in):

    im = im_in[im_in > 0]
    im_log = np.log10(im)
    data = im_log.ravel()
    p = sns.kdeplot(data, shade=True)
    x, y = p.get_lines()[0].get_data()
    hist_df = pd.DataFrame({'x': x, 'y': y})
    hist_df = hist_df.query('-3 < x < 0')
    hist_df['prev'] = hist_df.y.diff(periods=1).values
    hist_df['next'] = hist_df.prev.shift(-1).values
    hist_df['loc_min'] = (hist_df.prev < 0) & (hist_df.next > 0)
    loc_minima = hist_df.query('loc_min')
    if len(loc_minima) > 1:
        loc_minima = loc_minima.query('-2 < x < -1')

    if len(loc_minima) != 1:
        print('cannot find local minimum, please identify manually')
        return None
    else:
        return loc_minima.iloc[0].x


if __name__ == '__main__':

    api = connect_to_sentinel_api()
    gdacs_events = retrieve_all_gdacs_events()
    drought_events = get_specific_events(gdacs_events, 'DR')
    bbox, location = get_coordinates_for_event(drought_events.iloc[0])
    polygon = create_polygon_from_bbox(bbox)
    images = get_available_satellite_images(api, polygon)
    # images = get_available_satellite_images(api, location, coordinates_type='POINT')
    id_most_recent = images.iloc[0].name
    download = download_satellite_image(api, id_most_recent, 'output')
    graph = 'denoiseGraph.xml'
    remove_noise_using_snap(download['path'], 'output/{}_denoised.tif'.format(id_most_recent), graph)
    denoised_image = read_in_denoised_image('output/{}_denoised.tif'.format(id_most_recent))
    threshold = get_water_threshold(denoised_image)

    bin_mask = (denoised_image < (10 ** threshold)) & (denoised_image > 0)

    import urllib.request, sys, getopt, os


    DATASET_NAME = 'Transitions'
    longs = [str(w) + "W" for w in range(180, 0, -10)]
    longs.extend([str(e) + "E" for e in range(0, 180, 10)])
    lats = [str(s) + "S" for s in range(50, 0, -10)]
    lats.extend([str(n) + "N" for n in range(0, 90, 10)])
    fileCount = len(longs) * len(lats)
    counter = 1
    for lng in longs:
        for lat in lats:
            filename = DATASET_NAME + "_" + str(lng) + "_" + str(lat) + ".tif"
            if os.path.exists(DESTINATION_FOLDER + filename):
                print(DESTINATION_FOLDER + filename + " already exists - skipping")
            else:
                url = "http://storage.googleapis.com/global-surface-water/downloads2/" + DATASET_NAME + "/" + filename
                code = urllib.request.urlopen(url).getcode()
                if (code != 404):
                    print("Downloading " + url + " (" + str(counter) + "/" + str(fileCount) + ")")
                    urllib.request.urlretrieve(url, DESTINATION_FOLDER + filename)
                else:
                    print(url + " not found")
            counter += 1

    filename = 'transitions_120E_20N_v1_1.tif'
    url = "https://storage.googleapis.com/global-surface-water/downloads2/transitions/" + filename
    code = urllib.request.urlopen(url).getcode()
    urllib.request.urlretrieve(url, 'data/water_bodies/' + filename)
