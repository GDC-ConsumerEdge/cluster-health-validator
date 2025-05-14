#!/bin/bash
VERSION="$1"
APP="${2}"  # usually ${CONTAINER_NAME}
DOCKERFILE="${3:-Dockerfile}"

function setup_project() {
  # Create a .envrc file
  # check if file .envrc exists
  if [[ -f ".envrc" ]]; then
    echo "Environment file .envrc already exists, skipping setting up .envrc"
  fi
}

function display_common() {
  echo "Typical Containers:"
  echo "  * ${CONTAINER_NAME}"
}

function build_container() {
  if [[ -f ".npmrc" ]]; then
    docker build -f "${DOCKERFILE}" -t "${APP}:${VERSION}" . --secret id=npmrc,src=./.npmrc
  else
    docker build -f "${DOCKERFILE}" -t "${APP}:${VERSION}" . --secret id=npmrc,src=./.npmrc
  fi

  if [[ $? -ne 0 ]]; then
      echo "Cannot build docker"
      exit 1
  fi
}

function release_container() {
  docker tag "${APP}:${VERSION}" "${IMAGE_URL}:${VERSION}"
  # shellcheck disable=SC2181
  if [[ $? -ne 0 ]]; then
      echo "Cannot Tag Docker Build with version"
      exit 1
  fi
  docker tag "${APP}:${VERSION}" "${IMAGE_URL}:latest"
  # shellcheck disable=SC2181
  if [[ $? -ne 0 ]]; then
      echo "Cannot Tag Docker Build with latest"
      exit 1
  fi
  docker push "${IMAGE_URL}:${VERSION}"
  # shellcheck disable=SC2181
  if [[ $? -ne 0 ]]; then
      echo "Cannot Push Version Tagged"
      exit 1
  fi
  docker push "${IMAGE_URL}:latest"
  # shellcheck disable=SC2181
  if [[ $? -ne 0 ]]; then
      echo "Cannot Push Latest Tagged"
      exit 1
  fi
}

function create_registry_url() {
  if [[ -z "${IMAGE_URL}" ]]; then
    export IMAGE_URL="registry.gitlab.com/${SCM_PROJECT}/${APP}"
  fi
}

function validate_main() {
  if [[ -z "${APP}" ]]; then
    echo "Usage: ./build.sh <VERSION> <container> <APP-optional>"
    exit 1
  fi

  REQUIRED_VARIABLES=( "APP" "VERSION" "SCM_PROJECT" )
  # shellcheck disable=SC2043
  HAS_ERROR=0
  for REQ in "${REQUIRED_VARIABLES[@]}"
  do
    if [[ -z "${REQ}" ]]; then
      echo "Variable ${REQ} is required and does not have a value"
      HAS_ERROR=1
    fi
  done

  if [[ ${HAS_ERROR} -gt 0 ]]; then
    echo "One or more required variables are not set. Please set and re-run."
    exit 1
  fi
}


validate_main
setup_project
display_common
create_registry_url

echo "Building ${IMAGE_URL}:${VERSION}..."

build_container

# Confirm the release intention
echo "Do you want to release/push ${IMAGE_URL}:v${new_version}? (y/n)"
read -r response

case "$response" in
    [yY][eE][sS]|[yY]|[yY][aA])
        echo "Releasing ${IMAGE_URL}:v${new_version}..."
        release_container
        ;;
    *)
        echo "Operation cancelled."
        exit 1
        ;;
esac
