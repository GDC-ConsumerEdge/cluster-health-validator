
###################################################################
##
## Build Variables
##
###################################################################

## Container Name (if applicable)
export CONTAINER_NAME="%%CONTAINER_NAME%%"
## Project GitLab org
export SCM_ORG="%%SCM_ORG%%"
## Project Name
export SCM_PROJECT="${SCM_ORG}/%%SCM_PROJECT%%"
## Used to publish container to (if applicable)
export IMAGE_URL="registry.SCM-HOST.com/${SCM_PROJECT}/${CONTAINER_NAME}"
## Used in automation to move 'latest' to the container
export IMAGE_LATEST_FULL="${IMAGE_URL}:latest"

## package version number (default start of 0.0.1)
export VERSION="v0.0.1" # This can be updated automatically with `./release.sh` if desired
