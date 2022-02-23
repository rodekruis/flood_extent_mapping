import json                                   # JSON encoder and decoder
import glob                                   # data access

# Function looks for AOI file, converts to GeoJSON if not given and returns GeoJSON
def readJSONFromAOI(path):
    # check for GeoJSON file in 'AOI' subfolder
    if len(glob.glob('%s/*.geojson' % path)) == 1:
        file = glob.glob('%s/*.geojson' % path)[0]
    # open JSON file and store data
    with open(file, 'r') as f:
        data_json = json.load(f)
    return data_json