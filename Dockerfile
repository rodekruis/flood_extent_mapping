# syntax=docker/dockerfile:1

FROM docker.pkg.github.com/snap-contrib/docker-snap/snap:latest

WORKDIR /app

COPY requirements.txt requirements.txt
COPY floodmapping.ipynb floodmapping.ipynb

SHELL ["conda", "run", "-n", "env_snap", "/bin/bash", "-c"]
RUN pip3 install -r requirements.txt

COPY . .

ENTRYPOINT ["jupyter", "lab","--ip=0.0.0.0","--allow-root"]