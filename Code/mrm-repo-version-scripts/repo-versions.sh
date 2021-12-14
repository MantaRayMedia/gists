#!/bin/bash

REPO=$1
TOKEN=`</var/www/.git-key`
DEST=/var/www/mrm-www/www/sites/default/files

curl --location --request GET "https://api.github.com/repos/MantaRayMedia/${REPO}/releases/latest" \
--header "Authorization: token ${TOKEN}" \
--header "Accept: application/vnd.github.v3+json" \
| awk -F '"' '/tag_name/{print $4}' > "$DEST/$REPO.version"
