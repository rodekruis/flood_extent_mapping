import os                                     # data access
import time                                   # time assessment
import snappy                                 # SNAP Python interface
from osgeo import ogr, gdal, osr              # data conversion
import geopandas                              # data analysis and manipulation

def writingoutput(floodmask, directory, inputname, output_extensions, polarisations):

    print('Exporting...\n', flush=True)
    # check if output folders exists, if not create folders
    output_path = os.path.join(directory, 'output')
    if not os.path.isdir(output_path):
        os.mkdir(output_path)
    GeoTIFF_path = os.path.join(output_path, 'GeoTIFF')
    if not os.path.isdir(GeoTIFF_path):
        os.mkdir(GeoTIFF_path)
    SHP_path = os.path.join(output_path, 'SHP')
    if not os.path.isdir(SHP_path):
        os.mkdir(SHP_path)
    KML_path = os.path.join(output_path, 'KML')
    if not os.path.isdir(KML_path):
        os.mkdir(KML_path)
    GeoJSON_path = os.path.join(output_path, 'GeoJSON')
    if not os.path.isdir(GeoJSON_path):
        os.mkdir(GeoJSON_path)

    # write output file as GeoTIFF
    print('1. GeoTIFF:                   ', end='', flush=True)
    start_time = time.time()
    snappy.ProductIO.writeProduct(floodmask, '%s/%s_%s' % (GeoTIFF_path, os.path.splitext(inputname)[0], output_extensions), 'GeoTIFF')
    print('--- %.2f seconds ---' % (time.time() - start_time), flush=True)
    # convert GeoTIFF to SHP
    print('2. SHP:                       ', end='', flush=True)
    start_time = time.time()
    # allow GDAL to throw Python exceptions
    gdal.UseExceptions()
    open_image = gdal.Open('%s/%s_%s.tif' % (GeoTIFF_path, os.path.splitext(inputname)[0], output_extensions))
    srs = osr.SpatialReference()
    srs.ImportFromWkt(open_image.GetProjectionRef())
    shp_driver = ogr.GetDriverByName('ESRI Shapefile')
    # empty string array for bands in GeoTIFF
    output_shp = ['' for i in range(open_image.RasterCount)]
    if open_image.RasterCount == 1:
        output_shp[0] = '%s/%s_processed_%s' % (SHP_path, os.path.splitext(inputname)[0], polarisations)
    else:
        VH_SHP_path = os.path.join(SHP_path, 'VH')
        if not os.path.isdir(VH_SHP_path):
            os.mkdir(VH_SHP_path)
        VV_SHP_path = os.path.join(SHP_path, 'VV')
        if not os.path.isdir(VV_SHP_path):
            os.mkdir(VV_SHP_path)
        output_shp[0] = '%s/%s_processed_VH' % (VH_SHP_path, os.path.splitext(inputname)[0])
        output_shp[1] = '%s/%s_processed_VV' % (VV_SHP_path, os.path.splitext(inputname)[0])
    # loops through bands in GeoTIFF
    for i in range(open_image.RasterCount):
        input_band = open_image.GetRasterBand(i+1)
        output_shapefile = shp_driver.CreateDataSource(output_shp[i] + '.shp')
        new_shapefile = output_shapefile.CreateLayer(output_shp[i], srs=srs)
        new_shapefile.CreateField(ogr.FieldDefn('DN', ogr.OFTInteger))
        gdal.Polygonize(input_band, input_band.GetMaskBand(), new_shapefile, 0, [], callback=None)
        # filters attributes with values other than 1 (sould be NaN or respective value)
        new_shapefile.SetAttributeFilter('DN != 1')
        for feat in new_shapefile:
            new_shapefile.DeleteFeature(feat.GetFID())
        new_shapefile.SyncToDisk()
    print('--- %.2f seconds ---' % (time.time() - start_time), flush=True)

    # convert SHP to KML
    print('3. KML:                       ', end='', flush=True)
    start_time = time.time()
    if open_image.RasterCount == 1:
        shp_file = gdal.OpenEx('%s/%s_processed_%s.shp' % (SHP_path, os.path.splitext(inputname)[0], polarisations))
        ds = gdal.VectorTranslate('%s/%s_processed_%s.kml' % (KML_path, os.path.splitext(inputname)[0], polarisations), shp_file, format='KML')
        del ds
    else:
        shp_file_VH = gdal.OpenEx('%s/%s_processed_VH.shp' % (VH_SHP_path, os.path.splitext(inputname)[0]))
        ds_VH = gdal.VectorTranslate('%s/%s_processed_VH.kml' % (KML_path, os.path.splitext(inputname)[0]), shp_file_VH, format='KML')
        del ds_VH
        shp_file_VV = gdal.OpenEx('%s/%s_processed_VV.shp' % (VV_SHP_path, os.path.splitext(inputname)[0]))
        ds_VV = gdal.VectorTranslate('%s/%s_processed_VV.kml' % (KML_path, os.path.splitext(inputname)[0]), shp_file_VV, format='KML')
        del ds_VV
    print('--- %.2f seconds ---' % (time.time() - start_time), flush=True)

    # convert SHP to GeoJSON
    print('4. GeoJSON:                   ', end='', flush=True)
    start_time = time.time()
    if open_image.RasterCount == 1:
        shp_file = geopandas.read_file('%s/%s_processed_%s.shp' % (SHP_path, os.path.splitext(inputname)[0], polarisations))
        shp_file.to_file('%s/%s_processed_%s.json' % (GeoJSON_path, os.path.splitext(inputname)[0], polarisations), driver='GeoJSON')
    else:
        shp_file_VH = geopandas.read_file('%s/%s_processed_VH.shp' % (VH_SHP_path, os.path.splitext(inputname)[0]))
        shp_file_VH.to_file('%s/%s_processed_VH.json' % (GeoJSON_path, os.path.splitext(inputname)[0]), driver='GeoJSON')    
        shp_file_VV = geopandas.read_file('%s/%s_processed_VV.shp' % (VV_SHP_path, os.path.splitext(inputname)[0]))
        shp_file_VV.to_file('%s/%s_processed_VV.json' % (GeoJSON_path, os.path.splitext(inputname)[0]), driver='GeoJSON')
    print('--- %.2f seconds ---\n' % (time.time() - start_time), flush=True)
    print('Files successfuly stored under %s.\n' % output_path, flush=True)
    print('Data export done.')