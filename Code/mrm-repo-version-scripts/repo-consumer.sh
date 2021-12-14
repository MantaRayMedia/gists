#!/bin/bash

while read LINE; do
   /bin/bash repo-versions.sh $LINE
done <.git-repo-list
