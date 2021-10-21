# syntax=docker/dockerfile:1

FROM docker.pkg.github.com/snap-contrib/docker-snap/snap:latest

COPY requirements.txt requirements.txt
COPY radar-based-flood-mapping.ipynb radar-based-flood-mapping.ipynb

SHELL ["conda", "run", "-n", "env_snap", "/bin/bash", "-c"]
RUN conda install GDAL==3.2.2
RUN pip3 install -r requirements.txt

ENTRYPOINT ["jupyter", "lab","--ip=0.0.0.0","--allow-root"]
