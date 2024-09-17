# syntax = docker/dockerfile:1.3
# VULN_SCAN_TIME=2023-12-04_05:13:59


# The build stage
# ---------------
# This stage is building Python wheels for use in later stages by using a base
# image that has more pre-requisites to do so, such as a C++ compiler.
#
# NOTE: If the image version is updated, also update it in ci/refreeze and
#       singleuser-sample's Dockerfile!
#

# Original hub images in jupyterhub/k8s-hub are built with Debian python:3.11-bookworm as base
# Switched to Ubuntu here to reduce vulnerabilities and avoid being quarantine by ECR
ARG BASE_IMAGE_REPO
ARG BASE_IMAGE_NAME
#FROM ubuntu:22.04 as build-stage
FROM ${BASE_IMAGE_REPO}:${BASE_IMAGE_NAME} as build-stage

# Build wheels

# We set pip's cache directory and expose it across build stages via an
# ephemeral docker cache (--mount=type=cache,target=${PIP_CACHE_DIR}). We use
# the same technique for the directory /tmp/wheels.

# Get requirements.txt from https://github.com/jupyterhub/zero-to-jupyterhub-k8s/tree/main/images/hub
# Make sure to get the right tag/version (currently 2.0.0 on 01/25/24)
COPY requirements_jh_4_1_3.txt requirements.txt
RUN apt-get update \
 && apt-get upgrade -y \
 && apt-get install -y --no-install-recommends \
        python3-dev \
        python3-pip \
        libpq-dev \
        libssl-dev \
        libcurl4-openssl-dev \
        build-essential \
        libffi-dev
ARG PIP_CACHE_DIR=/tmp/pip-cache
RUN --mount=type=cache,target=${PIP_CACHE_DIR} \
    pip install build \
 && pip wheel \
        --wheel-dir=/tmp/wheels \
        # pycurl 7.45.3 has wheels, but they aren't portable
        # https://github.com/pycurl/pycurl/issues/834
        --no-binary pycurl \
        -r requirements.txt \
        # Additional wheels for default-stage. Updates below should be repeated
        # in default-stage.
        #
        py-spy


# The final stage - slim version
# ------------------------------
# This stage is originally built and published as quay.io/jupyterhub/k8s-hub-slim. It is meant to
# provide no non-essential packages.
#
#FROM ubuntu:22.04 as slim-stage
FROM ${BASE_IMAGE_REPO}:${BASE_IMAGE_NAME} as slim-stage
ENV DEBIAN_FRONTEND=noninteractive

ARG NB_USER=jovyan \
    NB_UID=1000 \
    HOME=/home/jovyan
RUN adduser \
        --disabled-password \
        --gecos "Default user" \
        --uid ${NB_UID} \
        --home ${HOME} \
        --force-badname \
        ${NB_USER}

RUN apt-get update \
 && apt-get upgrade -y \
 && apt-get install -y --no-install-recommends \
        # requirement for pycurl
        libcurl4 \
        # requirement for using postgres database
        libpq5 \
        # requirement for using a local sqlite database
        sqlite3 \
        tini \
        python3 \
        python3-pip \
 && rm -rf /var/lib/apt/lists/*

RUN echo "alias python=python3" >> ~/.bashrc

# install wheels built in the build stage
# --no-index ensures _only_ wheels from the build stage are installed
COPY requirements_jh_4_1_3.txt /tmp/requirements.txt
ARG PIP_CACHE_DIR=/tmp/pip-cache
RUN --mount=type=cache,target=${PIP_CACHE_DIR} \
    --mount=type=cache,from=build-stage,source=/tmp/wheels,target=/tmp/wheels \
    pip install \
        --no-index \
        --find-links=/tmp/wheels/ \
        -r /tmp/requirements.txt

WORKDIR /srv/jupyterhub
RUN chown ${NB_USER}:${NB_USER} /srv/jupyterhub
USER ${NB_USER}

EXPOSE 8081
ENTRYPOINT ["tini", "--"]
CMD ["jupyterhub", "--config", "/usr/local/etc/jupyterhub/jupyterhub_config.py"]


# The default version
# ---------------------------------
# We add a few non-critical packages on top of the slim version to provide some
# additional utility.
#
FROM slim-stage as default-stage

USER root

ARG PIP_CACHE_DIR=/tmp/pip-cache
RUN --mount=type=cache,target=${PIP_CACHE_DIR} \
    --mount=type=cache,from=build-stage,source=/tmp/wheels,target=/tmp/wheels \
    pip install \
        --no-index \
        --find-links=/tmp/wheels/ \
        # Updates below should be repeated in build-stage.
        #
        # py-spy is useful for profiling performance of running hubs
        py-spy

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        curl \
        dnsutils \
        git \
        less \
        vim \
 && rm -rf /var/lib/apt/lists/*

USER ${NB_USER}

# The final stage - customized version
# ---------------------------------
# Add customization on top of requirements for hub image
FROM default-stage as custom-stage

USER root

# RUN DEBIAN_FRONTEND=noninteractive && apt-get update -y \
# && apt-get dist-upgrade -y \
# && apt-get install python-is-python3 -y \
# && apt-get install build-essential -y \
# && apt-get clean

# Copy announcements server since it is a managed service running in the hub pod
COPY announcements.py  /usr/share/jupyterhub/announcements.py
RUN chown root:root /usr/share/jupyterhub/announcements.py  && chmod 755 /usr/share/jupyterhub/announcements.py

# Copy and install UID/GID package
COPY uidgid /usr/src/uidgid
WORKDIR /usr/src/uidgid
# For now,  leave the full package install so it works as library or image.
# Uncomment below once service is stable to avoid advertising how to attack the service with source code
# RUN find uidgid -name '*.py' | grep -v -E '__init__.py|types.py|client.py' | xargs rm -f
RUN pip install . --no-deps
RUN pip install --no-cache requests kubernetes

RUN chown ${NB_USER}:${NB_USER} /usr/src/uidgid

# Return to correct workdir and user
WORKDIR /srv/jupyterhub

USER ${NB_USER}