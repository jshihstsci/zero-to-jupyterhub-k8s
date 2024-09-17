ARG BASE_IMAGE_REPO
ARG BASE_IMAGE_NAME
#FROM python:3.11-slim
FROM ${BASE_IMAGE_REPO}:${BASE_IMAGE_NAME}

ARG UIDGID_SERVER_URL="localhost:5050"
ARG SVC_UID=1000
ARG SVC_GID=1000

ENV SVC_UID=$SVC_UID
ENV SVC_GID=$SVC_GID
ENV UIDGID_SERVER_URL=$UIDGID_SERVER_URL
ENV BACKGROUND_LOGGING=1
ENV USE_SUDO=1

RUN apt-get update && apt-get install -y sudo

RUN addgroup  --gid $SVC_GID uidgid
RUN adduser -u $SVC_UID --gid $SVC_GID --disabled-password --disabled-login uidgid
RUN echo "uidgid ALL=NOPASSWD:/usr/bin/chown" >> /etc/sudoers


RUN mkdir -p /users && chown $SVC_UID:$SVC_GID /users
RUN mkdir -p /teams && chown $SVC_UID:$SVC_GID /teams
RUN mkdir -p /services/uidgid && chown $SVC_UID:$SVC_GID /services/uidgid
RUN mkdir -p /backups/uidgid && chown $SVC_UID:$SVC_GID /backups/uidgid
RUN mkdir -p /usr/src/app/uidgid && chown $SVC_UID:$SVC_GID /usr/src/app/uidgid

RUN python -m venv /usr/src/app/uidgid/venv

WORKDIR /usr/src/app/uidgid
COPY requirements.txt requirements.txt
RUN /usr/src/app/uidgid/venv/bin/pip install --no-cache --upgrade pip
RUN /usr/src/app/uidgid/venv/bin/pip install --no-cache -r requirements.txt

COPY .  /usr/src/app/uidgid
RUN /usr/src/app/uidgid/venv/bin/pip install --no-cache .

WORKDIR /services/uidgid
USER $SVC_UID:$SVC_GID

CMD /usr/src/app/uidgid/venv/bin/hypercorn --bind ${UIDGID_SERVER_URL} uidgid.service:app
