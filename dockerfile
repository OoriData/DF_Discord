# SPDX-FileCopyrightText: 2024-present Oori Data <info@oori.dev>
# SPDX-License-Identifier: UNLICENSED

# Took advice from https://pythonspeed.com/articles/base-image-python-docker-images/
# Also, seems to be a known issue with Docker on Apple Silicon Macs.
# Issues finding gcc unless you specify the architecture for the image
FROM python:3.12-slim

# Combine commands in one RUN instruction to minimize # of layers in the file system, saving disk space.
# Also ref: https://github.com/reproducible-containers/buildkit-cache-dance
ENV DEBIAN_FRONTEND=noninteractive
RUN \
  --mount=type=cache,target=/var/cache/apt,sharing=locked \
  --mount=type=cache,target=/var/lib/apt,sharing=locked \
  rm -f /etc/apt/apt.conf.d/docker-clean && \
  echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' >/etc/apt/apt.conf.d/keep-cache && \
  apt update && \
  apt-get upgrade --yes && \
  apt-get install --yes build-essential git python3-dev wget

# In case Docker is running as root, narrow the attack surface to the host
# by doing as much as we can as an unprivileged user
RUN useradd --create-home df-discord
USER df-discord
WORKDIR /home/df-discord/code

# Use a virtualenv to avoid messing with the container's system Python
# No use doing venv activate in a RUN command, because it's just a temporary shell
# Besides, it definitely wouldn't work for Docker containers derived from this image
# Can't use $HOME in the ENV command
ENV VIRTUALENV=/home/df-discord/venv
RUN python3 -m venv $VIRTUALENV
ENV PATH="$VIRTUALENV/bin:$PATH"

# Copy the requirements.txt and constraints.txt files to the container
COPY ./requirements.txt ./requirements.txt
COPY ./constraints.txt ./constraints.txt

RUN python -m pip install --upgrade pip

WORKDIR /home/df-discord/code
RUN --mount=type=cache,target=/home/df-API/.cache/pip,sharing=locked python -m pip install --upgrade -r requirements.txt -c constraints.txt

COPY . /home/df-discord/code/

WORKDIR /home/df-discord/code

CMD python -m discord_app.df_discord
