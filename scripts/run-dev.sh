#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ -n "${QGIS_APP:-}" ]]; then
  QGIS_BUNDLE="$QGIS_APP"
elif [[ -d "/Applications/QGIS.app" ]]; then
  QGIS_BUNDLE="/Applications/QGIS.app"
elif [[ -d "/Applications/QGIS-LTR.app" ]]; then
  QGIS_BUNDLE="/Applications/QGIS-LTR.app"
else
  echo "未找到 QGIS.app。请设置 QGIS_APP=/path/to/QGIS.app" >&2
  exit 1
fi

CONTENTS_DIR="$QGIS_BUNDLE/Contents"

export SAKUGIS_RUNTIME_CONTENTS="$CONTENTS_DIR"
export PYTHONDONTWRITEBYTECODE=1
export QT_PLUGIN_PATH="$CONTENTS_DIR/PlugIns"
export QT_QPA_PLATFORM_PLUGIN_PATH="$CONTENTS_DIR/PlugIns/platforms"
export QGIS_PLUGINPATH="$CONTENTS_DIR/PlugIns/qgis"
export QGIS_CUSTOM_CONFIG_PATH="$PROJECT_DIR/build/profile"
mkdir -p "$QGIS_CUSTOM_CONFIG_PATH"

if [[ -d "$CONTENTS_DIR/Resources/qgis" ]]; then
  export QGIS_PREFIX_PATH="$CONTENTS_DIR/Resources/qgis"
  export QGIS_PKG_DATA_PATH="$CONTENTS_DIR/Resources/qgis"
  export QGIS_PLUGIN_PATH="$CONTENTS_DIR/PlugIns/qgis"
  export GDAL_DATA="$CONTENTS_DIR/Resources/qgis/gdal"
  export PROJ_LIB="$CONTENTS_DIR/Resources/qgis/proj"
  export PYTHONHOME="$CONTENTS_DIR/Frameworks"

  PYTHON_SITE_PACKAGES=""
  for candidate in "$CONTENTS_DIR"/Resources/python*/site-packages; do
    if [[ -d "$candidate" ]]; then
      PYTHON_SITE_PACKAGES="$candidate"
      break
    fi
  done
  export PYTHONPATH="$PROJECT_DIR/src:$PYTHON_SITE_PACKAGES:$CONTENTS_DIR/Resources/qgis/python"

  PYTHON_EXECUTABLE=""
  for candidate in "$CONTENTS_DIR"/MacOS/python3.*; do
    if [[ -x "$candidate" ]]; then
      PYTHON_EXECUTABLE="$candidate"
      break
    fi
  done
else
  export QGIS_PREFIX_PATH="$CONTENTS_DIR/MacOS"
  export QGIS_PKG_DATA_PATH="$CONTENTS_DIR/Resources"
  export QGIS_PLUGIN_PATH="$CONTENTS_DIR/PlugIns/qgis"
  export GDAL_DATA="$CONTENTS_DIR/Resources/gdal"
  export PROJ_LIB="$CONTENTS_DIR/Resources/proj"
  export PYTHONPATH="$PROJECT_DIR/src:$CONTENTS_DIR/Resources/python"
  PYTHON_EXECUTABLE="$CONTENTS_DIR/MacOS/bin/python3"
fi

if [[ -z "$PYTHON_EXECUTABLE" || ! -x "$PYTHON_EXECUTABLE" ]]; then
  echo "QGIS 包中没有可用的 Python 运行时" >&2
  exit 1
fi

exec "$PYTHON_EXECUTABLE" -m sakugis "$@"
