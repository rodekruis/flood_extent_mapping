import feedparser
import pandas as pd
from sentinelsat import SentinelAPI
import os
import rasterio as rio
import numpy as np
from rasterio import mask
from rasterio.warp import Resampling
import seaborn as sns
import urllib.request


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


def get_water_threshold_from_local_minimum(im_in):

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


def get_water_threshold_from_water_bodies(water_bodies_in, satellite_in, permanent_water_values=12):
    water_body_values = water_bodies_in.squeeze()
    water_values = satellite_in[water_body_values == permanent_water_values]
    water_values_log = np.log10(water_values[water_values > 0])
    threshold_out = np.percentile(water_values_log, 99)

    return threshold_out


def get_water_body_file_url(bounds_in):

    left_coord = bounds_in.left
    if left_coord < 0:
        lid = (int(-left_coord / 10) + 1) * 10
        lid_str = f'{lid}W'
    else:
        lid = int(left_coord / 10) * 10
        lid_str = f'{lid}E'

    top_coord = bounds_in.top
    if top_coord < 0:
        tid = int(-top_coord / 10) * 10
        tid_str = f'{tid}S'
    else:
        tid = (int(top_coord / 10) + 1) * 10
        tid_str = f'{tid}N'

    base_url = 'https://storage.googleapis.com/global-surface-water/downloads2/seasonality/'
    filename_out = 'seasonality_' + lid_str + '_' + tid_str + '_v1_1.tif'

    return base_url + filename_out, filename_out


def crop_water_body_image(water_body_file_in, bounds_in):
    water_bodies = rio.open(water_body_file_in)
    b = bounds_in
    geojson_dict = {'type': 'Polygon',
                    'coordinates': [[(b.left, b.bottom),
                                     (b.right, b.bottom),
                                     (b.right, b.top),
                                     (b.left, b.top),
                                     (b.left, b.bottom)]]}
    water_bodies_cropped_out, wb_transform = mask.mask(water_bodies, [geojson_dict], crop=True, indexes=1)
    with rio.open(f'{water_body_file_in[:-4]}_cropped.tif', 'w',
                  driver='GTiff', height=water_bodies_cropped_out.shape[0],
                  width=water_bodies_cropped_out.shape[1], count=1,
                  dtype=water_bodies_cropped_out.dtype, crs=water_bodies.crs,
                  transform=wb_transform) as dst:
        dst.write(water_bodies_cropped_out, 1)


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

    # get threshold through local minimum in histogram
    denoised_image = read_in_denoised_image('output/{}_denoised.tif'.format(id_most_recent))
    threshold_loc_min = get_water_threshold_from_local_minimum(denoised_image)
    bin_mask = (denoised_image < (10 ** threshold_loc_min)) & (denoised_image > 0)

    # get threshold by looking at permanent water bodies
    denoised_image = rio.open('output/{}_denoised.tif'.format(id_most_recent))
    water_body_url, filename = get_water_body_file_url(denoised_image.bounds)
    urllib.request.urlretrieve(water_body_url, 'data/water_bodies/' + filename)
    crop_water_body_image('data/water_bodies/' + filename, denoised_image.bounds)

    satellite_values = read_in_denoised_image('output/cropped_denoised.tif')
    water_bodies_cropped = rio.open(f'data/water_bodies/{filename[:-4]}_cropped.tif')
    water_bodies_cropped_upsampled = water_bodies_cropped.read(out_shape=(denoised_image.height, denoised_image.width),
                                                               resampling=Resampling.nearest)
    threshold = get_water_threshold_from_water_bodies(water_bodies_cropped_upsampled, satellite_values)
