#!/bin/bash

# This script is used to release a new version of the project.
# Release will generate the next tag version based on semver.
# All pushes still go to Main, but this allows ConfigSync Package Manager to
# avoid bumping until a new package is relased.

if ! command -v semver &> /dev/null
then
    echo "semver could not be found. Please install semver by running 'npm install -g semver'"
    exit
fi

# Fetch latest tags and changes and redect all output to dev/null
git fetch origin main > /dev/null 2>&1
git fetch --tags > /dev/null 2>&1

# Get the latest tag (only redirect error)
latest_tag=$(git describe --tags --abbrev=0 2>/dev/null || true)

# Default to v0.0.0 if no tags are found (default to zeroth release)
if [[ "${latest_tag}" == "" ]]; then
  latest_tag="v0.0.0"
fi

# Get the latest tag version
latest_version=$(echo "${latest_tag}" | cut -d'v' -f2)
new_version=$(semver -i ${latest_version})

echo "=========================================="
echo "Current Version: v${latest_version}"
echo "Next Version: v${new_version}"
# check if the user is OK with the new version
echo "=========================================="
echo "Changes:"
echo "=========================================="

# Show the changes since the last tag
git status

# Confirm the release intention
echo "Do you want to release v${new_version}? (y/n)"
read -r response

case "$response" in
    [yY][eE][sS]|[yY]|[yY][aA])
        echo "Proceeding with releasing using v${new_version}..."
        git commit -a -m "Release v${new_version}"
        git tag "v${new_version}"
        git push origin main
        git push origin tag "v${new_version}"
        ;;
    *)
        echo "Operation cancelled."
        exit 1
        ;;
esac
