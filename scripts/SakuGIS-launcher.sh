#!/bin/bash

set -euo pipefail

CONTENTS_DIR="$(cd "$(dirname "$0")/.." && pwd)"

export SAKUGIS_RUNTIME_CONTENTS="$CONTENTS_DIR"
export PYTHONDONTWRITEBYTECODE=1
export QGIS_PREFIX_PATH="$CONTENTS_DIR/MacOS"
export GDAL_DATA="$CONTENTS_DIR/Resources/gdal"
export PROJ_LIB="$CONTENTS_DIR/Resources/proj"
export QT_PLUGIN_PATH="$CONTENTS_DIR/PlugIns"
export QT_QPA_PLATFORM_PLUGIN_PATH="$CONTENTS_DIR/PlugIns/platforms"
export QGIS_PLUGINPATH="$CONTENTS_DIR/PlugIns/qgis"
export PYTHONPATH="$CONTENTS_DIR/Resources/sakugis:$CONTENTS_DIR/Resources/python"
export QGIS_CUSTOM_CONFIG_PATH="$HOME/Library/Application Support/SakuGIS"

exec "$CONTENTS_DIR/MacOS/bin/python3" -m sakugis "$@"
