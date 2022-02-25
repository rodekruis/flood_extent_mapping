import json                                   # JSON encoder and decoder
import glob                                   # data access
from zipfile import ZipFile                   # file management

# Function looks for AOI file, converts to GeoJSON if not given and returns GeoJSON
def readJSONFromAOI(path):
    # check for GeoJSON file in 'AOI' subfolder
    if len(glob.glob('%s/*.geojson' % path)) == 1:
        file = glob.glob('%s/*.geojson' % path)[0]
    elif len(glob.glob('%s/*.json' % path)) == 1:
        file = glob.glob('%s/*.json' % path)[0]

    # convert SHP to GeoJSON if no JSON is given
    elif len(glob.glob('%s/*.shp' % path)) == 1:
        file_name = os.path.splitext(glob.glob('%s/*.shp' % path)[0])[0].split('/')[-1]
        shp_file = geopandas.read_file(glob.glob('%s/*.shp' % path)[0])
        shp_file.to_file('%s/%s.json' % (path, file_name), driver='GeoJSON')
        file = glob.glob('%s/*.json' % path)[0]

    # convert KML to GeoJSON if no JSON or SHP is given
    elif len(glob.glob('%s/*.kml' % path)) == 1:
        file_name = os.path.splitext(glob.glob('%s/*.kml' % path)[0])[0].split('/')[-1]
        kml_file = gdal.OpenEx(glob.glob('%s/*.kml' % path)[0])
        ds = gdal.VectorTranslate('%s/%s.json' % (path, file_name), kml_file, format='GeoJSON')
        del ds
        file = glob.glob('%s/*.json' % path)[0]

    # convert KMZ to JSON if no JSON, SHP, or KML is given
    elif len(glob.glob('%s/*.kmz' % path)) == 1:
        # open KMZ file and extract data
        with ZipFile(glob.glob('%s/*.kmz' % path)[0], 'r') as kmz:
            folder = os.path.splitext(glob.glob('%s/*.kmz' % path)[0])[0]
            kmz.extractall(folder)
        # convert KML to GeoJSON if extracted folder contains one KML file
        if len(glob.glob('%s/*.kml' % folder)) == 1:
            kml_file = gdal.OpenEx(glob.glob('%s/*.kml' % folder)[0])
            ds = gdal.VectorTranslate('%s/%s.json' % (path, folder.split('/')[-1]), kml_file, format='GeoJSON')
            del ds
            file = glob.glob('%s/*.json' % path)[0]
            # remove unzipped KMZ directory and data
            shutil.rmtree(folder)
    # allow to upload AOI file or manually draw AOI if no file was found
    else:
        raise FileNotFoundError

    # open JSON file and store data
    with open(file, 'r') as f:
        data_json = json.load(f)

    return data_json

def get_input_name(input_path):
    # empty string array to store Sentinel-1 files in 'input' subfolder
    files = []
    # add files to list
    for file in glob.glob1(input_path, '*.zip'):
        files.append(file)
    # select input file and start processing if there is only one available Sentinel-1 file
    input_name = files[0]
    return(input_name)

def set_sourcebands(polarisations):
    if polarisations == 'both':
        sourceBands = 'Amplitude_VH,Intensity_VH,Amplitude_VV,Intensity_VV'
    elif polarisations == 'VH':
        sourceBands = 'Amplitude_VH,Intensity_VH'
    elif polarisations == 'VV':
        sourceBands = 'Amplitude_VV,Intensity_VV'
    return(sourceBands) 
    
    
def set_output_extensions(polarisations):
    if polarisations == 'both':
        output_extensions   = 'processed_VHVV'
    elif polarisations == 'VH':
        output_extensions   = 'processed_VH'
    elif polarisations == 'VV':
        output_extensions   = 'processed_VV'
    return(output_extensions) 

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