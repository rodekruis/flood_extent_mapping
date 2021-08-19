# flood extent mapping from Sentinel-1 images 


More descriptions will follow when app is completed 

### Setup Docker-SNAP container 

We start from an existing docker container, that can be found [here](https://github.com/snap-contrib/docker-snap). 
This will contain a working Python version + ESA's SNAP interface for analysing Sentinel-1 satelite images (the Python API called snappy). 
The following instructions are mainly following the instructions shown 
in their README


As this solution requires one to have accounts at Docker, GitHub and still perform quite some steps, we will attempt to simplify the process when setting up the final application. 


##### step 1: Installing Docker: 
Easiest way to get Docker (including the command line interface), is to install [Docker desktop](https://www.docker.com/?utm_source=google&utm_medium=cpc&utm_campaign=dockerhomepage&utm_content=nemea&utm_term=dockerhomepage&utm_budget=growth&gclid=CjwKCAjwgviIBhBkEiwA10D2jzQw0B0_kGBpkPksSWDBnzpF7qEJCCWggWGvt5fMmdyqwfQ4FWd81RoCtrgQAvD_BwE)

Once done, this should provide you with a 'normal app with GUI to run Docker', as well as the 'command line interface', which is what we will use in the instructions that follow. 

##### step 1: Login to GitHub 
Docker can obtain the image stored in the GitHub repository once we have done the following trick 

1. [Go to this GitHub page](https://github.com/settings/tokens/new) and login with your GitHub credentials. 
2. Tick the checkbox that says "read:packages"
3. Enter a name on top and generate a token 
4. Go to your command line ('Terminal App' on a Mac):
```{bash}
docker login docker.pkg.github.com --username <your_GitHub_username> --password <generated_token>
```
*note: you enter the generated token, not your GitHub password*


##### step 2: Prepare DockerFile for our App
This step is already done for end-user obviously. 
For completeness sake, the following has been done: 
1. Created file with exactly the name "Dockerfile" , no extension 
2. contents for now is just saying it should build on top of the SNAP image: 
```
FROM docker.pkg.github.com/snap-contrib/docker-snap/snap:latest
```

**note: This docker file will contain more instructions later. That will partially simplify the entire process** 

##### step 3: Build the Docker container 

In your terminal: 
```
docker build  <directory_that_has_the_Dockerfile>  -t <enter_name_of_image_you_want>
```

If you'd look in Docker Desktop (under the 'images' tab) you should now see two images: The 'pulled' copy of the docker-snap image and the one created from our Dockerfile (representing our 'flood-extend-mapping app'). 



**for macOS users** 
If experiencing an error saying something like '... authentication failed', the following solution from stackoverflow did the trick for me. 
Replace the above by doing: 
```
export DOCKER_BUILDKIT=0

export COMPOSE_DOCKER_CLI_BUILD=0

docker build  <directory_that_has_the_Dockerfile>  -t <enter_name_of_image_you_want>
```


##### step 4: Run the docker container 

In your terminal, execute:
```
docker run \
--rm \
-it \
-v <DIRECTORY ON COMPUTER>:/home/jovyan/flood_extent_mapping \
-p 8888:8888 \
--name <CHOOSE NAME OF CONTAINER> \
<NAME OF IMAGE THAT YOU SET IN STEP 3>
```


To explain what is goin on, we basically used "docker run our created image", with some additional options that are mainly needed during development. Some of the following may not be needed in the final product. 


* Give the resulting container a name we can reference if you want to exit and re-enter some other day (```--name``` option)
* Open a terminal on the 'vitual linux container that is build by Docker' (```-it``` option)
* Have a folder on your computer that maps to a 'virtual folder inside the container'. This way, you can edit code that can be then run inside the container as well as store output of the container's code on your computer (such that it exists after stopping the Docker container). (```-v``` option)

* Map a port that we will use for Jupyter lab (```-p``` option)
* Automatically remove the container when it exits (```--rm``` flag)



At this point, you should have entered a terminal inside the container and you are in principle 'good to go'. 

Let's just setup Jupyter and install some additional packages needed. 
These steps can eventually easily be includen in the Dockerfile, such that end users are done after this step. 

##### step 5: Setting up Jupyter lab inside the conda environment that has SNAP 

1. The Docker container has two conda environents, 'base' and 'env_snap', the later is the one containing the working version of SNAP. 
To switch into this environment, we must first setup/initialise conda (this container is in essence a new computer and this is the first time you use conda on it)
```
conda init
```

2. It will ask you to restart the terminal. The only way of doing this without exiting the Docker container (which also reverts the previous command apparently), is to use: 
```
exec bash 
```

3. Now we have things setup, we can enter the correct conda enviroment,  
```
conda activate env_snap
```
4. , install jupyterlab, 

```
conda install -c conda-forge jupyterlab
```

5. and tart Jupyterlab  (the ip option used here is needed to access it in our browser that exists outside of the container. We mapped port 8888 to the ip 0.0.0.0)

```
jupyter-lab --ip=0.0.0.0
```

6. In your browser go to <http://localhost:8888/lab/>
The first time it will ask you to enter the 'token', which is that long sequence of numbers/letters seen in the URL shown when starting Jupyter-lab. 
Typically, you'll only have to do this once. 


7. Happy coding in Jupyter :-)

#### step 6: Additional package requirements 
This part will go into the Dockerfile 

```
conda install -c conda-forge scipy, numpy, matplotlib, pandas   #(altijd goed om te hebben, maar misschien niet expliciet nodig dit keer) 
pip install sentinelsat. 
conda install geopandas
pip install rasterio
conda install scikit-image           
conda install -c anaconda ipyleaflet        # NIET NODIG VOOR UITEINDELIJKE APP 
conda install -c anaconda ipywidgets     # NIET NODIG VOOR UITEINDELIJKE APP 
```



## Stuff to add to Dockerfile 
```
# installing packages 
conda init 
exec bash 
conda activate env_snap 
conda install -c conda-forge scipy, numpy, matplotlib, pandas   #(altijd goed om te hebben, maar misschien niet expliciet nodig dit keer) 
pip install sentinelsat. 
conda install geopandas
pip install rasterio
conda install scikit-image           
conda install -c anaconda ipyleaflet        # NIET NODIG VOOR UITEINDELIJKE APP 
conda install -c anaconda ipywidgets     # NIET NODIG VOOR UITEINDELIJKE APP 
```
















