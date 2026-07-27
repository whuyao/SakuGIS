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
  echo "未找到 QGIS.app" >&2
  exit 1
fi

CONTENTS_DIR="$QGIS_BUNDLE/Contents"
export SAKUGIS_RUNTIME_CONTENTS="$CONTENTS_DIR"
export PYTHONDONTWRITEBYTECODE=1
export QT_PLUGIN_PATH="$CONTENTS_DIR/PlugIns"
export QT_QPA_PLATFORM_PLUGIN_PATH="$CONTENTS_DIR/PlugIns/platforms"
export QGIS_PLUGINPATH="$CONTENTS_DIR/PlugIns/qgis"
export QT_QPA_PLATFORM="offscreen"
export QGIS_CUSTOM_CONFIG_PATH="/private/tmp/sakugis-qgis-profile"
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

"$PYTHON_EXECUTABLE" - <<'PY'
import os

from qgis.PyQt.QtCore import QTimer
from qgis.core import Qgis, QgsApplication, QgsProviderRegistry, QgsRasterLayer

QgsApplication.setPrefixPath(__import__("os").environ["QGIS_PREFIX_PATH"], True)
app = QgsApplication([], True)
QgsApplication.setPkgDataPath(__import__("os").environ["QGIS_PKG_DATA_PATH"])
QgsApplication.setPluginPath(__import__("os").environ["QGIS_PLUGIN_PATH"])
QgsProviderRegistry.instance(__import__("os").environ["QGIS_PLUGIN_PATH"])
app.initQgis()
QgsApplication.setPkgDataPath(__import__("os").environ["QGIS_PKG_DATA_PATH"])
QgsApplication.setPluginPath(__import__("os").environ["QGIS_PLUGIN_PATH"])

from sakugis.ui_theme import apply_theme

apply_theme(app)

uri = (
    "type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    "&zmin=0&zmax=19&crs=EPSG3857"
)
layer = QgsRasterLayer(uri, "OpenStreetMap", "wms")
print(f"QGIS version: {Qgis.QGIS_VERSION}")
print(f"OSM layer valid: {layer.isValid()}")
print(f"Provider path: {QgsApplication.pluginPath()}")

if not layer.isValid():
    raise SystemExit(1)

from sakugis.main_window import MainWindow

window = MainWindow()
window.show()

smoke_language = os.environ.get("SAKUGIS_SMOKE_LANGUAGE")
if smoke_language:
    window._set_language(smoke_language)

if os.environ.get("SAKUGIS_SMOKE_GOOGLE") == "1":
    window.add_google_satellite()
    google_layers = [
        layer
        for layer in window.project.mapLayers().values()
        if layer.customProperty("sakugis/basemap-key")
        == "google-satellite-custom-xyz"
    ]
    print(f"Google satellite layer valid: {bool(google_layers)}")
    if not google_layers:
        raise SystemExit(1)

if os.environ.get("SAKUGIS_SMOKE_AGENT_RESULT") == "1":
    from sakugis.agent_models import Candidate, Evidence, GeoAnalysisResult
    from sakugis.gis_models import GISCheck, SpatialConstraint

    window.add_osm_basemap()
    verified_checks = [
        GISCheck(
            check_id="reverse_country",
            kind="reverse_geocode",
            label="reverse-geocoded country",
            matched=True,
            source="OSM Nominatim",
            detail="Japan (JP)",
        ),
        GISCheck(
            check_id="coastline",
            kind="spatial_constraint",
            label="coastline",
            matched=True,
            source="OSM Overpass",
            count=12,
            nearest_distance_km=3.4,
        ),
        GISCheck(
            check_id="vineyard",
            kind="spatial_constraint",
            label="vineyard",
            matched=None,
            source="OSM Overpass unavailable",
        ),
    ]
    sample_result = GeoAnalysisResult(
        query="左侧通行、临海、附近有活火山和葡萄园",
        image_path="",
        evidence_summary="用于界面冒烟测试的结构化证据。",
        evidence=[
            Evidence(
                evidence_id="E1",
                kind="traffic",
                value="左侧通行",
                reliability=0.85,
                source="smoke-test",
                scale="country",
            ),
            Evidence(
                evidence_id="E2",
                kind="terrain",
                value="临海且附近有火山",
                reliability=0.72,
                source="smoke-test",
                scale="region",
            ),
        ],
        candidates=[
            Candidate(
                candidate_id="C1",
                name="静冈市",
                country="日本",
                region="静冈县",
                latitude=34.977,
                longitude=138.383,
                initial_score=0.9,
                ranking_score=0.94,
                radius_km=60,
                country_code="JP",
                gis_score=0.9,
                gis_coverage=0.8,
                gis_verified=True,
                reverse_label="Shizuoka, Japan",
                gis_backend="OSM Nominatim + Overpass",
                gis_checks=verified_checks,
                supporting_evidence=["E1", "E2"],
                rationale="左侧通行、临海，并能看到富士山地区。",
            ),
            Candidate(
                candidate_id="C2",
                name="内皮尔",
                country="新西兰",
                region="霍克斯湾",
                latitude=-39.488,
                longitude=176.915,
                initial_score=0.55,
                ranking_score=0.57,
                radius_km=70,
                country_code="NZ",
                gis_score=0.75,
                gis_coverage=0.8,
                gis_verified=True,
                reverse_label="Napier, New Zealand",
                gis_backend="OSM Nominatim + Overpass",
                gis_checks=verified_checks,
                supporting_evidence=["E1", "E2"],
                rationale="左侧通行、临海且靠近葡萄酒产区。",
            ),
        ],
        verification_summary="静冈市在当前测试证据下排名第一。",
        caveat="这是界面测试数据，探索评分尚未校准。",
        model="smoke-test",
        gis_backend="OSM Nominatim + Overpass",
        spatial_constraints=[
            SpatialConstraint(
                constraint_id="coastline",
                kind="osm_tag",
                label="coastline",
                radius_km=30,
                tag_key="natural",
                tag_value="coastline",
            ),
            SpatialConstraint(
                constraint_id="vineyard",
                kind="osm_tag",
                label="vineyard",
                radius_km=60,
                tag_key="landuse",
                tag_value="vineyard",
            ),
        ],
    )
    from sakugis.ranking import fuse_candidate_score

    sample_result.candidates[0].model_verification_score = 0.92
    sample_result.candidates[1].model_verification_score = 0.64
    for candidate in sample_result.candidates:
        fuse_candidate_score(candidate, sample_result.evidence)
    sample_result.candidates.sort(
        key=lambda candidate: candidate.ranking_score, reverse=True
    )
    window.agent_panel._show_result(sample_result)
    window.agent_panel.tabs.setCurrentIndex(2)
    window.show_agent_result(sample_result)
    sample_candidate_layers = [
        layer
        for layer in window.project.mapLayers().values()
        if layer.customProperty("sakugis/candidate-layer")
    ]
    if len(sample_candidate_layers) != 2:
        raise SystemExit("Candidate layer group was not created")
    sample_candidate_layers.sort(
        key=lambda layer: float(
            layer.customProperty("sakugis/candidate-score", 0)
        ),
        reverse=True,
    )
    sample_range_layers = [
        layer
        for layer in window.project.mapLayers().values()
        if layer.customProperty("sakugis/agent-result")
        and not layer.customProperty("sakugis/candidate-layer")
    ]
    if sample_range_layers:
        window.layer_panel.view.setCurrentLayer(sample_range_layers[0])
        app.processEvents()
    window.layer_panel.view.setCurrentLayer(sample_candidate_layers[0])
    app.processEvents()
    window._refresh_attribution()
    if (
        os.environ.get("SAKUGIS_SMOKE_GOOGLE") == "1"
        and "Google Maps" not in window.attribution_status.text()
    ):
        raise SystemExit("Google Maps attribution is not visible")
    print(f"Attribution: {window.attribution_status.text()}")
    print("Expandable candidate layers: OK")
    report_path = os.environ.get("SAKUGIS_SMOKE_REPORT")
    if report_path:
        from sakugis.reporting import write_markdown_report

        write_markdown_report(report_path, sample_result)
        print(f"Markdown report: {report_path}")

screenshot_path = os.environ.get("SAKUGIS_SMOKE_SCREENSHOT")
duration_ms = int(os.environ.get("SAKUGIS_SMOKE_DURATION_MS", "750"))
if screenshot_path:
    screenshot_delay = int(
        os.environ.get(
            "SAKUGIS_SMOKE_SCREENSHOT_DELAY_MS",
            str(max(100, min(2500, duration_ms - 100))),
        )
    )
    QTimer.singleShot(screenshot_delay, lambda: window.grab().save(screenshot_path))

QTimer.singleShot(duration_ms, app.quit)
app.exec_()
print("Main window smoke test: OK")

app.exitQgis()
PY
