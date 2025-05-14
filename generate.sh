#!/bin/bash

SPECIFIC_OVERLAY=$1
OVERLAYS_BASE="overlays" # Adjust if your base path is different
PACKAGE_FOLDER="package"
PACKAGE_PREFIX="${2:-gdc-cluster-health-pkg-}"
PACKAGE_PREFIX_SHORT="gdc-cluster"


if [[ -z "${SPECIFIC_OVERLAY}" ]]; then
    echo "Building all overlays"
    rm -rf "${PACKAGE_FOLDER}"
    mkdir -p "${PACKAGE_FOLDER}"

    # Find all directories within the overlays base
    for overlay_dir in "$OVERLAYS_BASE"/*/; do
        # Extract the directory name without the trailing slash
        overlay_name="${overlay_dir%/}"
        overlay_name="${overlay_name##*/}"

        if [[ -f "$(pwd)/${OVERLAYS_BASE}/${overlay_name}/kustomization.yaml" ]]; then
            echo "Building overlay: $overlay_name" # Optional for progress updates
            if [[ ! -d "$(pwd)/config/${overlay_name}" ]]; then
                echo "Creating config directory for ${overlay_name}: $(pwd)/config/${overlay_name}"
                mkdir -p "$(pwd)/config/${overlay_name}"
            fi

            # Run the kustomize build command (KGR)
            kustomize build ${OVERLAYS_BASE}/$overlay_name ${HELM_CLI_FLAG} > config/$overlay_name/${PACKAGE_PREFIX_SHORT}$overlay_name-generated.yaml
            kustomize build ${OVERLAYS_BASE}/$overlay_name ${HELM_CLI_FLAG} > package/${PACKAGE_PREFIX}$overlay_name.yaml
        else
            echo "No '${OVERLAYS_BASE}/${overlay_name}/kustomization.yaml' file found in overlay: $overlay_name. Skipping..."
            continue
        fi
    done
else
    echo "Building overlay: $SPECIFIC_OVERLAY"
    kustomize build overlays/$SPECIFIC_OVERLAY > config/$SPECIFIC_OVERLAY/$SPECIFIC_OVERLAY-generated.yaml
fi

echo "Verifying configuration with Nomos"
nomos vet --no-api-server-check --source-format unstructured --path config/