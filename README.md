# flood-extent-mapping
*Currently in development*

Docker container that runs the UN-SPIDER jupyter notebook. 

**Scope**: rough map of flood extent based on satellite imagery

**Input**: Area of Interest. Currently supported:

* GeoJSON
* KML
* KMZ
* SHP

**Output**: Flooded area, in:

* GeoTIFF
* SHP
* KML 
* GeoJSON

## Credits

* This [UN-SPIDER Radar-based Flood Mapping Jupyter notebook](https://github.com/UN-SPIDER/radar-based-flood-mapping)
* This Docker image: [docker-snap](github.com/snap-contrib/docker-snap)

Development: Wouter Oosterheert, Misha Klein, Rosanna van Hespen, Jacopo Margutti

Contact: [Jacopo Margutti](mailto:jmargutti@redcross.nl)

## File structure
Place the following files in a dedicated folder `directory_with_files`:

* `Dockerfile` used to build image
* `requirements.txt` required python packages
* `radar-based-flood-mapping.ipynb` jupyter notebook


## Requirements:

Only Docker is needed. 

## Getting started

### TLDR
1. Install Docker
2. Get a Personal Access Token that has `read:packages` for the GitHub Container repository
3. Log on to the repository: `docker login docker.pkg.github.com --username <your_user_name> --password <generated_token_not_password>
`
4. Build the image `docker build  <directory_with_files> -t <choose_image_name>`
5. Run the image `docker run -it -v <directory_with_files>:/home/jovyan/flood_extent_mapping -p 8888:8888 --name <container-name> <image_name>`
6. Go to [localhost:8888](localhost:8888)
7. Create a folder named 'AOI' and place 1 file in it with the area of interest (GeoJSON, SHP, KML, KMZ).
8. Run notebook. Set `tile_id` to select which satellite image to download in codeblock 4. 
9. Run the rest of the notebook. 

### Detailed instructions
 
#### 1. Install Docker

Docker Desktop installation guides are available for [Windows](https://docs.docker.com/desktop/windows/install/) and [Mac](https://docs.docker.com/desktop/mac/install/) (Windows requires WSL2).

#### 2. Login to the GitHub Container registry

1. Login on github and [go to this  page](https://github.com/settings/tokens/new) and create a personal access token with the scope *read:packages*. Copy the token somewhere. 
2. Go to your command line ('Terminal App' on a Mac, 'Powershell' on Windows) and login to the GitHub Container registry:
```{bash}
docker login docker.pkg.github.com --username <GitHub_username> --password <personal_access_token>
```

#### 3. Create the container
Build the image:
```{bash}
docker build  <directory>  -t <choose_image_name>
```

*If  experiencing an error saying something like '... authentication failed', use this for macOS users:*
```{bash}
export DOCKER_BUILDKIT=0
export COMPOSE_DOCKER_CLI_BUILD=0
```
*or this for Windows users:*
```{bash}
set DOCKER_BUILDKIT=0
set COMPOSE_DOCKER_CLI_BUILD=0
```

Run the container:
```{bash}
docker run -it -v <directory>:/home/jovyan/flood_extent_mapping -p 8888:8888 --name <container-name> <image_name>
```

* `-it` = interactive
* `-v` = links to the volume on the local host
* `-p` port
* `--name` choose name for the container
* name of the image

The container has an entrypoint that immediately runs the jupyter notebook that has the ip address 0.0.0.0. Port 8888 is mapped to this address, so the notebook can now be accessed through [localhost:8888](localhost:8888). 

## 4. Running the notebook
Create a folder named 'AOI' and place 1 file in it with the area of interest (GeoJSON, SHP, KML, KMZ).
1. *User Input*: Choose a start and end date in which to search through the Copernicus Hub, and set username and password to access the Hub. 
2. *Initialization*: run
3. *Download Image*: Running this will show a map and table with available satellite images and their productID's. ProductID's are ordered as Tile1, Tile2, etc.
4. Set the `tile_id` for the image you want to download. Run the codeblock and the download (usually ~1GB) will start. The image is stored in the folder 'input'. 
5. *Processing*: the satellite image is processed. Steps 6 and 8 can cause the notebook kernel to crash if the image is too large. 
6. *Data export*: Stores the flood map as GeoTIFF, GeoJSON, KML and SHP files in a folder called 'output', and shows a geojson map of the flood extent. 

## Software required to run the jupyter-notebook
The required software is automatically installed with the Docker image, that we  based on Docker image 'docker-snap' version ?? (18-06-2021). For completeness, the following software is needed to run the jupyter-notebook (listed with known working version numbers):

* Python (version 3.9.5)
* GDAL (version 3.2.2)
* SNAP (version 8.0.0)

All python packages are installed in the conda environment 'env-snap'. GDAl is already  installed with the *docker-snap* image but not recognised as a python package, therefore it is explicitely listed in the Dockerfile.
*So far GDAL version 3.2.2 is the only version that installs without causing errors.*
