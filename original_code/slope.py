import os
import zipfile
import rasterio
import numpy as np
import datetime as dt
import geopandas as gpd
from rasterio.merge import merge
from rasterio.transform import array_bounds
from rasterio.warp import calculate_default_transform, reproject, RESAMPLING
from rasterstats import zonal_stats
from fiona.crs import from_epsg
from ftplib import FTP

#Output will be in this CRS, datasets are reprojected if necessary
force_epsg = 4326
def unzip(zip_file, destination):
	os.makedirs(destination, exist_ok=True)

	with zipfile.ZipFile(zip_file) as zf:
		zf.extractall(destination)

	return

def reproject_file(gdf, file_name, epsg):
	t0 = dt.datetime.now()
	print("Reprojecting %s to EPSG %i..." % (file_name, epsg), end="", flush=True)
	gdf = gdf.to_crs(epsg=force_epsg)

	t1 = timestamp(dt.datetime.now(), t0)

	return gdf


def reproject_raster(src_array, src_transform, src_epsg, dst_epsg, src_nodata=-32768, dst_nodata=-32768):
	src_height, src_width = src_array.shape
	dst_affine, dst_width, dst_height = calculate_default_transform(
		from_epsg(src_epsg), 
		from_epsg(dst_epsg), 
		src_width, 
		src_height, 
		*array_bounds(src_height, src_width, src_transform))

	dst_array = np.zeros((dst_width, dst_height))
	dst_array.fill(dst_nodata)

	reproject(
		src_array,
		dst_array,
		src_transform=src_transform,
		src_crs=from_epsg(src_epsg),
		dst_transform=dst_affine,
		dst_crs=from_epsg(dst_epsg),
		src_nodata=src_nodata,
		dst_nodata=dst_nodata,
		resampling=RESAMPLING.nearest)
	
	return dst_array, dst_affine


def slope(array, transform):
	height, width = array.shape
	bounds = array_bounds(height, width, transform)

	cellsize_x = (bounds[2] - bounds[0]) / width
	cellsize_y = (bounds[3] - bounds[1]) / height

	z = np.zeros((height + 2, width + 2))
	z[1:-1,1:-1] = array
	dx = (z[1:-1, 2:] - z[1:-1, :-2]) / (2*cellsize_x)
	dy = (z[2:,1:-1] - z[:-2, 1:-1]) / (2*cellsize_y)

	slope_deg = np.arctan(np.sqrt(dx*dx + dy*dy)) * (180 / np.pi)

	return slope_deg


def download_srtm(bounding_box, download_path):
	base_url = "srtm.csi.cgiar.org"
	data_dir = "SRTM_V41/SRTM_Data_GeoTiff"

	tile_x0 = int((bounding_box[0] + 180) // 5) + 1
	tile_x1 = int((bounding_box[2] + 180) // 5) + 1
	tile_y0 = int((60 - bounding_box[3]) // 5) + 1
	tile_y1 = int((60 - bounding_box[1]) // 5) + 1

	tif_list = []
	zip_list = []
	ignore_list =[]

	t1 = dt.datetime.now()

	print("Checking local cache for SRTM tiles...", end="", flush=True)

	ignore_file = os.path.join(download_path, "ignore_tiles.txt")
	if os.path.isfile(ignore_file):
		with open(ignore_file, 'r') as file:
			for line in file.readlines():
				ignore_list.append(line.strip())

	for x_int in range(tile_x0, tile_x1 + 1):
		for y_int in range(tile_y0, tile_y1 + 1):
			if x_int > 9: x = str(x_int)
			else: x = "0" + str(x_int)
			if y_int > 9: y = str(y_int)
			else: y = "0" + str(y_int)

			tile_folder = os.path.join(download_path, "%s_%s" % (x, y))
			tile_path = os.path.join(tile_folder, "srtm_%s_%s.tif" % (x, y))
			zip_path = os.path.join(download_path, "srtm_%s_%s.zip" % (x, y))

			if os.path.isfile(tile_path): tif_list.append(tile_path)
			else: 
				if "%s_%s" % (x, y) not in ignore_list: 
					zip_list.append((tile_folder, tile_path, zip_path, x, y))

	total_tiles = len(tif_list) + len(zip_list)
	print("found %i of %i tiles..." % (len(tif_list), total_tiles), end="", flush=True)
	t1 = timestamp(dt.datetime.now(), t1)

	if zip_list:
		print("Connecting to %s..." % base_url, end="", flush=True)
		with FTP(base_url) as ftp:
			ftp.login()
			print("OK!")
			ftp.cwd(data_dir)
	
			os.makedirs(download_path, exist_ok=True)

			for tile_folder, tile_path, zip_path, x, y in list(zip_list):
				t1 = dt.datetime.now()

				zip_name = os.path.basename(zip_path)
				print("Retrieving %s..." % zip_name, end="", flush=True)

				if not os.path.isfile(zip_path):
					with open(zip_path, 'wb') as write_file: 
						try: 
							ftp.retrbinary('RETR ' + zip_name, write_file.write)
						except: 
							print("skipped...", end="", flush=True)
							os.remove(zip_path)
							zip_list.remove((tile_folder, tile_path, zip_path, x, y))
							ignore_list.append("%s_%s" % (x,y))
				
				else: print("found locally...", end="", flush=True)

				t1 = timestamp(dt.datetime.now(), t1)

		if ignore_list:
			with open(ignore_file, 'w') as file:
				for tile in ignore_list:
					file.write(tile + '\n')

	if zip_list:
		print("Unzipping downloaded tiles...", end="", flush=True)
		for tile_folder, tile_path, zip_path, x, y in zip_list: 
			unzip(zip_path, tile_folder)
			tif_list.append(tile_path)

		t1 = timestamp(dt.datetime.now(), t1)

	return tif_list
def srtm_features(admin_geometry, bounding_box, download_path):
	file_list = download_srtm(bounding_box, download_path)	

	t1 = dt.datetime.now()	
	print("Reading SRTM data...", end="", flush=True)

	raster_list = []

	for input_raster in file_list: 
		raster_list.append(rasterio.open(input_raster))

	if len(raster_list) > 1: 
		srtm_dem, srtm_transform = merge(raster_list, nodata=-32768)
		srtm_dem = srtm_dem[0]
	else: 
		srtm_dem = raster_list[0].read(1)
		srtm_transform = raster_list[0].affine

	for input_raster in raster_list:
		input_raster.close()
	del(raster_list)

	# Add no data mask!!

	t1 = timestamp(dt.datetime.now(), t1)

	print("Reprojecting DEM to EPSG %i..." % force_epsg, end="", flush=True)
	srtm_utm, transform_utm = reproject_raster(srtm_dem, srtm_transform, 4326, force_epsg, -32768, 0)
	t1 = timestamp(dt.datetime.now(), t1)

	print("Calculating mean elevation...", end="", flush=True)
	avg_elevation = zonal_stats(admin_geometry, srtm_utm, stats='mean', nodata=-32768, all_touched=True, affine=transform_utm)
	avg_elevation = [i['mean'] for i in avg_elevation]
	t1 = timestamp(dt.datetime.now(), t1)

	print("Calculating mean slope...", end="", flush=True)
	avg_slope = zonal_stats(admin_geometry, slope(srtm_utm, transform_utm), stats='mean', nodata=0, all_touched=True, affine=transform_utm)
	avg_slope = [i['mean'] for i in avg_slope]
	t1 = timestamp(dt.datetime.now(), t1)

	# print("Calculating mean ruggedness...", end="", flush=True)
	# avg_rugged = zonal_stats(admin_geometry, ruggedness(srtm_utm, transform_utm), stats='mean', nodata=0, all_touched=True, affine=transform_utm)
	# avg_rugged = [i['mean'] for i in avg_rugged]
	# t1 = timestamp(dt.datetime.now(), t1)

	return avg_elevation, avg_slope