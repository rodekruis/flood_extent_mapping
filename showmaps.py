import ipyleaflet                             # visualization
import os                                     # data access
from IPython.display import display           # visualization
from osgeo import ogr, gdal, osr              # data conversion
import json                                   # JSON encoder and decoder

def plotdownloadmap(data_json, product_json):
    print('DOWNLOADMAP')
    download_map = ipyleaflet.Map(zoom = 6)
    download_map.add_control(ipyleaflet.SearchControl(
        position = 'topleft',
        url = 'https://nominatim.openstreetmap.org/search?format=json&q={s}',
        zoom = 5))
    download_map.add_control(ipyleaflet.ScaleControl(position='bottomleft'))
    display(download_map)

    # show AOI on map according to JSON data
    aoi = ipyleaflet.GeoJSON(data = data_json, style = {'color' : 'green'})
    try:
        # GeoJSON format if KMZ is given
        download_map.center = (aoi.data['features'][0]['geometry']['coordinates'][0][0][0][1],
                               aoi.data['features'][0]['geometry']['coordinates'][0][0][0][0])
    except:
        # GeoJSON format if JSON or SHP is given
        download_map.center = (aoi.data['features'][0]['geometry']['coordinates'][0][0][1],
                               aoi.data['features'][0]['geometry']['coordinates'][0][0][0])
    download_map.add_layer(aoi)
    geo_json = ipyleaflet.GeoJSON(data = product_json,
                          name = 'S1 tiles',
                          style = {'color' : 'royalblue'},
                          hover_style = {'fillOpacity' : 0.4})
    download_map.add_layer(geo_json)
    
    
def plotbasicmap(S1_source, data_json):
    print('BASICMAP')
    # read geographic coordinates from Sentinel-1 image meta data
    meta_data = S1_source.getMetadataRoot().getElement('Abstracted_Metadata')
    # refines center of map according to Sentinel-1 image
    center = (meta_data.getAttributeDouble('centre_lat'), meta_data.getAttributeDouble('centre_lon'))
    locations = [[{'lat' : meta_data.getAttributeDouble('first_near_lat'), 'lng' : meta_data.getAttributeDouble('first_near_long')},
                  {'lat' : meta_data.getAttributeDouble('last_near_lat'),  'lng' : meta_data.getAttributeDouble('last_near_long')},
                  {'lat' : meta_data.getAttributeDouble('last_far_lat'),   'lng' : meta_data.getAttributeDouble('last_far_long')},
                  {'lat' : meta_data.getAttributeDouble('first_far_lat'),  'lng' : meta_data.getAttributeDouble('first_far_long')}]]

    # creates interactive map
    basic_map = ipyleaflet.Map(center = center, zoom = 7.5)
    # defines fixed polygon illustrating Sentinel-1 image
    polygon_fix = ipyleaflet.Polygon(locations = locations, color='royalblue')
    basic_map.add_layer(polygon_fix)
    # displays map
    basic_map.add_control(ipyleaflet.ScaleControl(position='bottomleft'))
    display(basic_map)
    
    # show AOI on map according to JSON data
    basic_map.add_layer(ipyleaflet.GeoJSON(data = data_json, style = {'color' : 'green'}))        


def plotfloodmap(input_name, polarisations, directory, output_extensions):  
    print('FLOODMAP')
    # plot results
    results_map = ipyleaflet.Map(zoom=9, basemap=ipyleaflet.basemaps.OpenStreetMap.Mapnik)    
    display(results_map)
    
    output_path = os.path.join(directory, 'output')
    GeoTIFF_path = os.path.join(output_path, 'GeoTIFF')
    open_image = gdal.Open('%s/%s_%s.tif' % (GeoTIFF_path, os.path.splitext(input_name)[0], output_extensions))
    GeoJSON_path = os.path.join(output_path, 'GeoJSON')
    
    if open_image.RasterCount == 1:

        file = '%s/%s_processed_%s.json' % (GeoJSON_path, os.path.splitext(input_name)[0], polarisations)
        with open(file, 'r') as f:
            data_json = json.load(f) 
        mask = ipyleaflet.GeoJSON(data = data_json, name = 'Flood Mask', style = {'color':'blue', 'opacity':'1', 'fillColor':'blue', 'fillOpacity':'1', 'weight':'0.8'})
        results_map.add_layer(mask)
        results_map.center = (mask.data['features'][0]['geometry']['coordinates'][0][0][1],
                              mask.data['features'][0]['geometry']['coordinates'][0][0][0])
    else:
        file_VV = '%s/%s_processed_VV.json' % (GeoJSON_path, os.path.splitext(input_name)[0])
        with open(file_VV, 'r') as f_VV:
            data_json_VV = json.load(f_VV)
        mask_VV = ipyleaflet.GeoJSON(data = data_json_VV, name = 'Flood Mask: VV', style = {'color':'red', 'opacity':'1', 'fillColor':'red', 'fillOpacity':'1', 'weight':'0.8'})
        results_map.add_layer(mask_VV)
        results_map.center = (mask_VV.data['features'][0]['geometry']['coordinates'][0][0][1],
                              mask_VV.data['features'][0]['geometry']['coordinates'][0][0][0])  
        file_VH = '%s/%s_processed_VH.json' % (GeoJSON_path, os.path.splitext(input_name)[0])
        with open(file_VH, 'r') as f_VH:
            data_json_VH = json.load(f_VH)
        mask_VH = ipyleaflet.GeoJSON(data = data_json_VH, name = 'Flood Mask: VH', style = {'color':'blue', 'opacity':'1', 'fillColor':'blue', 'fillOpacity':'1', 'weight':'0.8'})
        results_map.add_layer(mask_VH)
    results_map.add_control(ipyleaflet.FullScreenControl())
    results_map.add_control(ipyleaflet.LayersControl(position='topright'))
    results_map.add_control(ipyleaflet.ScaleControl(position='bottomleft'))