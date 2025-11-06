#!/bin/bash
# Usage: ./build_macos_dmg.sh <dist-dir> <output-dmg>

set -euo pipefail

DIST_DIR=${1:-dist}
OUT_DMG=${2:-pySPEC.dmg}
APP_BASENAME="pySPEC"

echo "Looking for file in ${DIST_DIR}..."

APP_PATH="pySPEC"

if [ -z "$APP_PATH" ]; then
  echo "No ${APP_PATH} found in ${DIST_DIR}. Listing contents:" >&2
  ls -la "${DIST_DIR}" || true
  exit 1
fi

echo "Found app bundle: ${APP_PATH}"

# If the app bundle name isn't the desired name, rename it inside dist
APP_FILENAME=$(basename "$APP_PATH")
if [ "$APP_FILENAME" != "${APP_BASENAME}.app" ]; then
  echo "Renaming ${APP_FILENAME} -> ${APP_BASENAME}.app"
  mv "$APP_PATH" "${DIST_DIR}/${APP_BASENAME}.app"
  APP_PATH="${DIST_DIR}/${APP_BASENAME}.app"
fi

# Create a temporary staging folder for the .dmg contents
STAGING_DIR=".dmg_staging"
rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"

# Copy the .app into the staging folder
cp -R "$APP_PATH" "$STAGING_DIR/"

VOLNAME="${APP_BASENAME}"

echo "Creating compressed DMG ${OUT_DMG}..."
hdiutil create -volname "$VOLNAME" -srcfolder "$STAGING_DIR" -ov -format UDZO "$OUT_DMG"

echo "DMG created: $(pwd)/${OUT_DMG}"

# Cleanup
rm -rf "$STAGING_DIR"

exit 0
