import feedparser
import pandas as pd
from sentinelsat import SentinelAPI
import os
from shapely.geometry import Polygon # needs to be imported before rasterio to prevent kernel from dying
import rasterio as rio
import numpy as np
from rasterio import mask
from zipfile import ZipFile
from geopy.distance import distance


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


def get_current_flood_events():
    current_events = retrieve_all_gdacs_events()
    flood_events = get_specific_events(current_events, 'FL')
    return flood_events


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


# TODO calculate overlap with ROI using footprint metadata
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

    products_df = api_in.to_dataframe(products).copy()
    grd_df = products_df.query('producttype =="GRD"').copy()
    grd_df['overlap_with_roi'] = grd_df.footprint.apply(get_overlap_with_roi, args=[coordinates_in])
    grd_df.sort_values(['overlap_with_roi', 'ingestiondate'], ascending=False, inplace=True)
    return grd_df


def get_overlap_with_roi(footprint_in, roi_in):
    roi_poly = Polygon(roi_in)
    sat_poly_coord = [tuple(map(float, x.strip(' ').split(' ')))
                      for x in footprint_in.split('(((')[1].strip(')))').split(',')]
    sat_poly = Polygon(sat_poly_coord)
    intersection = roi_poly.intersection(sat_poly)
    return intersection.area / roi_poly.area


def download_satellite_image(api_in, image_id_in, savedir_in):
    """
    Downloads one image specified by its ID and stores it in the specified savedir
    """
    download_out = api_in.download(image_id_in, directory_path=savedir_in)
    return download_out


def get_most_recent_image_for_roi(polygon_in):

    api = connect_to_sentinel_api()
    images = get_available_satellite_images(api, polygon_in)
    id_most_recent = images.iloc[0].name
    download = download_satellite_image(api, id_most_recent, 'output')
    return download


def extract_satellite_image(file_in):
    with ZipFile(file_in, 'r') as zipObj:
        zipObj.extractall(file_in[:-4])

    return file_in[:-4] + '/' + file_in[:-4].split('/')[-1] + '.SAFE'


def crop_satellite_image(roi_in, path_in, path_out, path_to_gpt='/Applications/snap/bin/gpt'):
    area = "POLYGON(({}))".format(",".join(["{} {}".format(p[0], p[1]) for p in roi_in]))
    os.system("{} Subset -PgeoRegion='{}' -PcopyMetadata=true -t {} {}".format(path_to_gpt, area, path_out, path_in))


def preprocess_using_snap(path_in, path_out, path_graph, path_to_gpt='/Applications/snap/bin/gpt'):
    """
    Runs the graph processing tool from SNAP to perform denoising using a predefined processing graph.
    """
    os.system("{} {} -t {} {}".format(path_to_gpt, path_graph, path_out, path_in))


def get_water_threshold_from_water_bodies(water_bodies_in, satellite_in, permanent_water_value_in=12):
    water_body_values = water_bodies_in.squeeze()
    water_values = satellite_in[water_body_values == permanent_water_value_in]
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


def create_binary_mask(satellite_in, water_threshold_in, slopes_in, slope_threshold_in,
                       water_bodies_in, permanent_water_value_in, crs_in, transform_in, id_in):
    mask_out = np.asarray((satellite_in < (10 ** water_threshold_in)) &
                          (satellite_in > 0) &
                          (slopes_in < slope_threshold_in) &
                          (water_bodies_in != permanent_water_value_in)).astype('float')

    with rio.open('../output/{}_bin_water_mask.tif'.format(id_in), 'w',
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
    with ZipFile('../data/altitude/' + file_in, 'r') as zipObj:
        zipObj.extractall('../data/altitude/' + file_in[:-4])

    return '../data/altitude/' + file_in[:-4] + '/' + file_in[:-4] + '.tif'


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
    z[z == -32768] = 0
    dx = (z[1:-1, 2:] - z[1:-1, :-2]) / (2*cellsize_x)
    dy = (z[2:, 1:-1] - z[:-2, 1:-1]) / (2*cellsize_y)
    slope_deg = np.arctan(np.sqrt(dx*dx + dy*dy)) * (180 / np.pi)

    return slope_deg
