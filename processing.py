import snappy                                 # SNAP Python interface
import time                                   # time assessment
import numpy as np                            # scientific comupting
import skimage.filters                        # threshold calculation
import jpy                                    # Python-Java bridge
from helperfunctions import plotBand

def make_subset(S1_source, footprint, sourceBands):
    parameters = snappy.HashMap()
    parameters.put('copyMetadata', True)
    geom = snappy.WKTReader().read(footprint)
    parameters.put('geoRegion', geom)
    parameters.put('sourceBands', sourceBands)
    S1_crop = snappy.GPF.createProduct('Subset', parameters, S1_source)
    # status update
    print('\nSubset successfully generated.\n', flush=True)
    return(S1_crop)

def apply_orbit_file(S1_crop):
    print('1. Apply Orbit File:          ', end='', flush=True)
    start_time = time.time()
    parameters = snappy.HashMap()
    # continue with calculation in case no orbit file is available yet
    parameters.put('continueOnFail', True)
    S1_Orb = snappy.GPF.createProduct('Apply-Orbit-File', parameters, S1_crop)
    print('--- %.2f  seconds ---' % (time.time() - start_time), flush=True)
    return(S1_Orb)
    
def thermal_noise_removal(S1_Orb):
    print('2. Thermal Noise Removal:     ', end='', flush=True)
    start_time = time.time()
    parameters = snappy.HashMap()
    parameters.put('removeThermalNoise', True)
    S1_Thm = snappy.GPF.createProduct('ThermalNoiseRemoval', parameters, S1_Orb)
    print('--- %.2f  seconds ---' % (time.time() - start_time), flush=True)
    return(S1_Thm)

def radiometric_calibration(S1_Thm):
    print('3. Radiometric Calibration:   ', end='', flush=True)
    start_time = time.time()
    parameters = snappy.HashMap()
    parameters.put('outputSigmaBand', True)
    S1_Cal = snappy.GPF.createProduct('Calibration', parameters, S1_Thm)
    print('--- %.2f  seconds ---' % (time.time() - start_time), flush=True)
    return(S1_Cal)

def speckle_filtering(S1_Cal):
    print('4. Speckle Filtering:         ', end='', flush=True)
    start_time = time.time()
    parameters = snappy.HashMap()
    parameters.put('filter', 'Lee')
    parameters.put('filterSizeX', 5)
    parameters.put('filterSizeY', 5)
    S1_Spk = snappy.GPF.createProduct('Speckle-Filter', parameters, S1_Cal)
    print('--- %.2f  seconds ---' % (time.time() - start_time), flush=True)
    return(S1_Spk)

def convert_to_db(S1_Spk):
    # Conversion from linear to db operator
    S1_Spk_db = snappy.GPF.createProduct('LinearToFromdB', snappy.HashMap(), S1_Spk)
    return(S1_Spk_db)

def terrain_correction(S1_Spk_db):
    # Terrain-Correction operator
    print('5. Terrain Correction:        ', end='', flush=True)
    start_time = time.time()
    parameters = snappy.HashMap()
    parameters.put('demName', 'SRTM 1Sec HGT')
    parameters.put('demResamplingMethod', 'BILINEAR_INTERPOLATION')
    parameters.put('imgResamplingMethod', 'NEAREST_NEIGHBOUR')
    parameters.put('pixelSpacingInMeter', 10.0)
    parameters.put('nodataValueAtSea', False)
    parameters.put('saveSelectedSourceBand', True)
    S1_TC = snappy.GPF.createProduct('Terrain-Correction', parameters, S1_Spk_db)
    print('--- %.2f  seconds ---' % (time.time() - start_time), flush=True)
    return(S1_TC)

# calculate and return threshold of 'Band'-type input
# SNAP API: https://step.esa.int/docs/v6.0/apidoc/engine/
def getThreshold(S1_band):
    # read band
    w = S1_band.getRasterWidth()
    h = S1_band.getRasterHeight()
    band_data = np.zeros(w * h, np.float32)
    S1_band.readPixels(0, 0, w, h, band_data)
    band_data.shape = h * w

    # calculate threshold using Otsu method
    threshold_otsu = skimage.filters.threshold_otsu(band_data)
    # calculate threshold using minimum method
    threshold_minimum = skimage.filters.threshold_minimum(band_data)
    # get number of pixels for both thresholds
    numPixOtsu = len(band_data[abs(band_data - threshold_otsu) < 0.1])
    numPixMinimum = len(band_data[abs(band_data - threshold_minimum) < 0.1])

    # if number of pixels at minimum threshold is less than 1% of number of pixels at Otsu threshold
    if abs(numPixMinimum/numPixOtsu) < 0.001: #this can cause zero division error
        # adjust band data according
        if threshold_otsu < threshold_minimum:
            band_data = band_data[band_data < threshold_minimum]
            threshold_minimum = skimage.filters.threshold_minimum(band_data)
        else:
            band_data = band_data[band_data > threshold_minimum]
            threshold_minimum = skimage.filters.threshold_minimum(band_data)
    
        numPixMinimum = len(band_data[abs(band_data - threshold_minimum) < 0.1])

    # select final threshold
    if abs(numPixMinimum/numPixOtsu) < 0.001:
        threshold = threshold_otsu
    else:
        threshold = threshold_minimum
    return threshold

# calculate binary mask of 'Product'-type intput with respect expression in string array
def binarize(S1_product, expressions):
    BandDescriptor = jpy.get_type('org.esa.snap.core.gpf.common.BandMathsOp$BandDescriptor')
    targetBands = jpy.array('org.esa.snap.core.gpf.common.BandMathsOp$BandDescriptor', len(expressions))

    # loop through bands
    for i in range(len(expressions)):
        targetBand = BandDescriptor()
        targetBand.name = '%s' % S1_product.getBandNames()[i]
        targetBand.type = 'float32'
        targetBand.expression = expressions[i]
        targetBands[i] = targetBand
        
    parameters = snappy.HashMap()
    parameters.put('targetBands', targetBands)    
    mask = snappy.GPF.createProduct('BandMaths', parameters, S1_product)
    return mask

def binarization(S1_TC, S1_Spk_db):
    # Binarization
    print('6. Binarization:              ', end='', flush=True)
    start_time = time.time()
    # add GlobCover band
    parameters = snappy.HashMap()
    parameters.put('landCoverNames', 'GlobCover')
    GlobCover = snappy.GPF.createProduct('AddLandCover', parameters, S1_TC)
    # empty string array for binarization band maths expression(s)
    expressions = ['' for i in range(S1_TC.getNumBands())]
    # empty array for threshold(s)
    thresholds = np.zeros(S1_TC.getNumBands())
    # loop through bands
    for i in range(S1_TC.getNumBands()):
        # calculate threshold of band and store in float array
        # use S1_Spk_db product for performance reasons. S1_TC causes 0-values
        # which distort histogram and thus threshold result
        thresholds[i] = getThreshold(S1_Spk_db.getBandAt(i))
        # formulate expression according to threshold and store in string array
        expressions[i] = 'if (%s < %s && land_cover_GlobCover != 210) then 1 else NaN' % (S1_TC.getBandNames()[i], thresholds[i])
    # do binarization
    S1_floodMask = binarize(GlobCover, expressions)
    print('--- %.2f seconds ---' % (time.time() - start_time), flush=True)
    return(S1_floodMask)

def speckle_filtering(S1_floodMask):
    # Speckle-Filter operator
    print('7. Speckle Filtering:         ', end='', flush=True)
    start_time = time.time()
    parameters = snappy.HashMap()
    parameters.put('filter', 'Median')
    parameters.put('filterSizeX', 5)
    parameters.put('filterSizeY', 5)
    # define flood mask as global for later access
    # global S1_floodMask_Spk
    S1_floodMask_Spk = snappy.GPF.createProduct('Speckle-Filter', parameters, S1_floodMask)
    print('--- %.2f  seconds ---' % (time.time() - start_time), flush=True)
    return(S1_floodMask_Spk)

def plotresults(S1_TC):
    print('8. Plot:                      ', end='', flush=True)
    start_time = time.time()
    for i in range(S1_TC.getNumBands()):
        plotBand(S1_TC.getBandAt(i), thresholds[i])
    print('--- %.2f seconds ---' % (time.time() - start_time), flush=True)