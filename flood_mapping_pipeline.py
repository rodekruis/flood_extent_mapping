import feedparser
import pandas as pd
from sentinelsat import SentinelAPI
import os
import rasterio as rio
import numpy as np
from rasterio import mask
from rasterio.warp import Resampling
import urllib.request
from zipfile import ZipFile
from geopy.distance import distance
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt


def retrieve_all_gdacs_events():
    """
    Reads in the RSS feed from GDACS and returns all current events in a pandas data frame
    """

    feed = feedparser.parse('feed://gdacs.org/xml/rss.xml')
    events_out = pd.DataFrame(feed.entries)
    return events_out


def get_specific_events(gdacs_events_in, event_code_in):
    """
    Filters the GDACS events by type of event. Available event codes:
    EQ: earthquake
    TC: tropical cyclone
    DR: drought
    FL: flood
    VO: volcano
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


# def get_water_threshold_from_local_minimum(im_in):
#
#     im = im_in[im_in > 0]
#     im_log = np.log10(im)
#     data = im_log.ravel()
#     p = sns.kdeplot(data, shade=True)
#     x, y = p.get_lines()[0].get_data()
#     hist_df = pd.DataFrame({'x': x, 'y': y})
#     hist_df = hist_df.query('-3 < x < 0')
#     hist_df['prev'] = hist_df.y.diff(periods=1).values
#     hist_df['next'] = hist_df.prev.shift(-1).values
#     hist_df['loc_min'] = (hist_df.prev < 0) & (hist_df.next > 0)
#     loc_minima = hist_df.query('loc_min')
#     if len(loc_minima) > 1:
#         loc_minima = loc_minima.query('-2 < x < -1')
#
#     if len(loc_minima) != 1:
#         print('cannot find local minimum, please identify manually')
#         return None
#     else:
#         return loc_minima.iloc[0].x


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
        lid_str = '{}W'.format(lid)
    else:
        lid = int(left_coord / 10) * 10
        lid_str = '{}E'.format(lid)

    top_coord = bounds_in.top
    if top_coord < 0:
        tid = int(-top_coord / 10) * 10
        tid_str = 'S'.format(tid)
    else:
        tid = (int(top_coord / 10) + 1) * 10
        tid_str = '{}N'.format(tid)

    base_url = 'https://storage.googleapis.com/global-surface-water/downloads2/seasonality/'
    filename_out = 'seasonality_' + lid_str + '_' + tid_str + '_v1_1.tif'

    return base_url + filename_out, filename_out


def crop_image(image_file_in, bounds_in):
    image_to_crop = rio.open(image_file_in)
    b = bounds_in
    geojson_dict = {'type': 'Polygon',
                    'coordinates': [[(b.left, b.bottom),
                                     (b.right, b.bottom),
                                     (b.right, b.top),
                                     (b.left, b.top),
                                     (b.left, b.bottom)]]}
    image_out, transform_out = mask.mask(image_to_crop, [geojson_dict], crop=True, indexes=1)
    with rio.open('{}_cropped.tif'.format(image_file_in[:-4]), 'w',
                  driver='GTiff', height=image_out.shape[0],
                  width=image_out.shape[1], count=1,
                  dtype=image_out.dtype, crs=image_to_crop.crs,
                  transform=transform_out) as dst:
        dst.write(image_out, 1)


def story_binary_mask(satellite_in, water_threshold_in, slopes_in, slope_threshold_in, crs_in, transform_in, id_in):
    mask_out = np.asarray((satellite_in < (10 ** water_threshold_in)) &
                          (satellite_in > 0) &
                          (slopes_in < slope_threshold_in)).astype('float')

    with rio.open('output/{}_bin_water_mask.tif'.format(id_in), 'w',
                  driver='GTiff', height=mask_out.shape[0],
                  width=mask_out.shape[1], count=1,
                  dtype=mask_out.dtype, crs=crs_in,
                  transform=transform_in) as dst:
        dst.write(mask_out, 1)

    return mask_out


def get_altitude_file_url(bounds_in):
    base_url = "http://srtm.csi.cgiar.org/wp-content/uploads/files/srtm_5x5/TIFF/"

    tile_x = int((bounds_in[0] + 180) // 5) + 1
    tile_y = int((60 - bounds_in[3]) // 5) + 1

    if tile_x > 9:
        x = str(tile_x)
    else:
        x = "0" + str(tile_x)
    if tile_y > 9:
        y = str(tile_y)
    else:
        y = "0" + str(tile_y)

    filename_out = 'srtm_' + x + '_' + y + '.zip'

    return base_url + filename_out, filename_out


def extract_altitude_file(file_in):
    with ZipFile('data/altitude/' + file_in, 'r') as zipObj:
        zipObj.extractall(file_in[:-4])

    return 'data/altitude/' + file_in[:-4] + '/' + file_in[:-4] + '.tif'


def calculate_slopes(altitudes_in, bounds_in):

    height_px, width_px = altitudes_in.shape

    coords_lb = (bounds_in.bottom, bounds_in.left)
    coords_rb = (bounds_in.bottom, bounds_in.right)
    coords_lt = (bounds_in.top, bounds_in.left)
    coords_rt = (bounds_in.top, bounds_in.right)

    height_m = distance(coords_lb, coords_lt).km * 1000
    width_m = (distance(coords_lb, coords_rb).km + distance(coords_lt, coords_rt).km) / 2 * 1000

    cellsize_x = width_m / width_px
    cellsize_y = height_m / height_px
    z = np.zeros((height_px + 2, width_px + 2))
    z[1:-1, 1:-1] = altitudes_in.copy()
    z[z == -32768] = np.nan
    dx = (z[1:-1, 2:] - z[1:-1, :-2]) / (2*cellsize_x)
    dy = (z[2:, 1:-1] - z[:-2, 1:-1]) / (2*cellsize_y)
    slope_deg = np.arctan(np.sqrt(dx*dx + dy*dy)) * (180 / np.pi)

    return slope_deg


if __name__ == '__main__':

    api = connect_to_sentinel_api()
    gdacs_events = retrieve_all_gdacs_events()
    flood_events = get_specific_events(gdacs_events, 'FL')
    bbox, location = get_coordinates_for_event(flood_events.iloc[0])
    polygon = create_polygon_from_bbox(bbox)
    images = get_available_satellite_images(api, polygon)
    # images = get_available_satellite_images(api, location, coordinates_type='POINT')
    id_most_recent = images.iloc[0].name
    download = download_satellite_image(api, id_most_recent, 'output')
    graph = 'denoiseGraph.xml'
    remove_noise_using_snap(download['path'], 'output/{}_denoised.tif'.format(id_most_recent), graph)

    # get threshold by looking at permanent water bodies in ROI
    denoised_image = rio.open('output/{}_denoised.tif'.format(id_most_recent))
    water_body_url, wb_filename = get_water_body_file_url(denoised_image.bounds)
    urllib.request.urlretrieve(water_body_url, 'data/water_bodies/' + wb_filename)
    crop_image('data/water_bodies/' + wb_filename, denoised_image.bounds)

    satellite_values = read_in_denoised_image('output/{}_denoised.tif'.format(id_most_recent))
    water_bodies_cropped = rio.open('data/water_bodies/{}_cropped.tif'.format(wb_filename[:-4]))
    water_bodies_cropped_upsampled = water_bodies_cropped.read(out_shape=(denoised_image.height, denoised_image.width),
                                                               resampling=Resampling.nearest)
    water_threshold = get_water_threshold_from_water_bodies(water_bodies_cropped_upsampled, satellite_values)

    # get slope information for ROI
    altitude_file_url, al_filename = get_altitude_file_url(denoised_image.bounds)
    urllib.request.urlretrieve(altitude_file_url, 'data/altitude/' + al_filename)
    altitude_tif_file = extract_altitude_file(al_filename)
    crop_image(altitude_tif_file, denoised_image.bounds)
    altitudes_cropped = rio.open('data/altitude/{}/{}_cropped.tif'.format(al_filename[:-4], al_filename[:-4]))
    altitudes_cropped_upsampled = altitudes_cropped.read(out_shape=(denoised_image.height, denoised_image.width),
                                                         resampling=Resampling.bilinear)
    slopes = calculate_slopes(altitudes_cropped_upsampled[0], altitudes_cropped.bounds)
    slope_threshold = 10     # degrees

    # store binary mask
    bin_mask = story_binary_mask(satellite_values, water_threshold, slopes, slope_threshold,
                                 denoised_image.crs, denoised_image.transform, id_most_recent)
    plt.imshow(bin_mask)
