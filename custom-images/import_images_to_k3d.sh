#! /bin/bash

# List the local docker images and import all to k3d cluster

set -eu

CLUSTER_NAME=${1:-"mycluster"}

image_arr=($(docker images | tail -n +2 | awk '{print $1":"$2}'))
echo ${image_arr}

for image in "${image_arr[@]}"
do
    echo "Importing image ${image}"
    k3d image import ${image} -c ${CLUSTER_NAME}
done