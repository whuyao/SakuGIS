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
export SAKUGIS_STARTUP_CITY="wuhan"
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

from qgis.PyQt.QtCore import QEventLoop, QTimer
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsProviderRegistry,
    QgsRasterLayer,
    QgsSettings,
)

if os.environ.get("SAKUGIS_SMOKE_AGENT_RESULT") == "1":
    os.environ.setdefault("SAKUGIS_SMOKE_DISABLE_PLACE_SEARCH", "1")
if os.environ.get("SAKUGIS_SMOKE_SETTINGS") == "1":
    os.environ.setdefault(
        "SAKUGIS_QWEN_API_KEY", "smoke-test-key-not-a-real-secret"
    )
    os.environ.setdefault(
        "SAKUGIS_KIMI_API_KEY", "smoke-test-kimi-key-not-a-real-secret"
    )

QgsApplication.setPrefixPath(__import__("os").environ["QGIS_PREFIX_PATH"], True)
app = QgsApplication([], True)
QgsApplication.setPkgDataPath(__import__("os").environ["QGIS_PKG_DATA_PATH"])
QgsApplication.setPluginPath(__import__("os").environ["QGIS_PLUGIN_PATH"])
QgsProviderRegistry.instance(__import__("os").environ["QGIS_PLUGIN_PATH"])
app.initQgis()
QgsApplication.setPkgDataPath(__import__("os").environ["QGIS_PKG_DATA_PATH"])
QgsApplication.setPluginPath(__import__("os").environ["QGIS_PLUGIN_PATH"])

place_setting_keys = (
    "sakugis/ui/place-details-floating",
    "sakugis/ui/place-details-geometry",
)
place_settings = QgsSettings()
place_setting_snapshot = {
    key: (
        place_settings.contains(key),
        place_settings.value(key),
    )
    for key in place_setting_keys
}

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
app.processEvents()

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsPointXY,
)

center_transform = QgsCoordinateTransform(
    window.canvas.mapSettings().destinationCrs(),
    QgsCoordinateReferenceSystem("EPSG:4326"),
    window.project,
)
initial_center = center_transform.transform(window.canvas.center())
if not (
    113.63 <= initial_center.x() <= 114.98
    and 30.04 <= initial_center.y() <= 31.14
):
    raise SystemExit(
        f"Initial map center is not in Wuhan: "
        f"{initial_center.x()}, {initial_center.y()}"
    )
print(
    f"Startup city and initial map center: {window.startup_city.name_en}, "
    f"{initial_center.x():.4f}, {initial_center.y():.4f}"
)

from sakugis.ui_theme import DARK, LIGHT, get_theme

window._set_theme(LIGHT)
if get_theme() != LIGHT or "#F3F6FA" not in app.styleSheet():
    raise SystemExit("Light theme did not apply")
window._set_theme(DARK)
if get_theme() != DARK or "#07101B" not in app.styleSheet():
    raise SystemExit("Dark theme did not restore")
print("Light/dark theme switch: OK")

from pathlib import Path
from tempfile import TemporaryDirectory

from sakugis.project_archive import save_sgd

empty_project_source = TemporaryDirectory(prefix="sakugis-empty-sgd-smoke-")
empty_project_path = Path(empty_project_source.name) / "empty-map.sgd"
save_sgd(
    str(empty_project_path),
    query="尚未运行 Agent 的工程",
    image_paths=[],
    result=None,
    map_state={
        "canvas": {
            "crs": "EPSG:3857",
            "extent_wgs84": [139.55, 35.55, 139.85, 35.85],
        },
        "layers": [],
    },
)
if not window.load_project_path(str(empty_project_path), confirm_discard=False):
    raise SystemExit("Empty SGD project did not load")
window._add_default_basemap_if_empty()
empty_project_wait = QEventLoop()
QTimer.singleShot(220, empty_project_wait.quit)
empty_project_wait.exec_()
empty_center = center_transform.transform(window.canvas.center())
if not (139.55 <= empty_center.x() <= 139.85 and 35.55 <= empty_center.y() <= 35.85):
    raise SystemExit("Default OSM overwrote the saved empty-project extent")
if window._sgd_dirty or window.project.isDirty():
    raise SystemExit("Opening an empty SGD project created false unsaved changes")
window.project.clear()
window._release_sgd_extraction()
window._sgd_path = ""
window._sgd_dirty = False
window._set_initial_extent()
window.add_osm_basemap()
empty_project_source.cleanup()
print("Empty SGD extent and clean-state replay: OK")

smoke_theme = os.environ.get("SAKUGIS_SMOKE_THEME")
if smoke_theme:
    window._set_theme(smoke_theme)

smoke_language = os.environ.get("SAKUGIS_SMOKE_LANGUAGE")
if smoke_language:
    window._set_language(smoke_language)

if os.environ.get("SAKUGIS_SMOKE_SETTINGS") == "1":
    from sakugis.candidate_retrieval import HybridCandidateRetriever
    from sakugis.kimi_client import KimiClient
    from sakugis.model_provider import KIMI, QWEN, configured_provider
    from sakugis.qwen_client import QwenClient
    from sakugis.settings_dialog import SettingsDialog

    if window.settings_menu.title() not in {"设置", "Settings"}:
        raise SystemExit("Settings menu is missing")
    if not window.settings_action.isEnabled():
        raise SystemExit("Settings action is disabled")

    applied = []
    dialog = SettingsDialog(window)
    dialog.settingsApplied.connect(applied.append)
    dialog.settingsApplied.connect(window._apply_settings)
    dialog.show()
    app.processEvents()
    readable_controls = (
        dialog.qwen_base_url_edit,
        dialog.qwen_key_edit,
        dialog.kimi_base_url_edit,
        dialog.kimi_key_edit,
        dialog.brave_key_edit,
    )
    if any(control.height() < 36 for control in readable_controls):
        raise SystemExit("Settings input fields are vertically compressed")
    if any(
        status.height() < 34
        for status in (
            dialog.qwen_status,
            dialog.kimi_status,
            dialog.brave_status,
        )
    ):
        raise SystemExit("Settings status fields are vertically compressed")
    settings_screenshot = os.environ.get(
        "SAKUGIS_SMOKE_SETTINGS_SCREENSHOT"
    )
    if settings_screenshot and not dialog.grab().save(settings_screenshot):
        raise SystemExit("Settings screenshot could not be saved")
    dialog.model_combo.setCurrentText("qwen-settings-smoke")
    dialog.temperature_spin.setValue(0.20)
    dialog.qwen_timeout_spin.setValue(91)
    dialog.prompt_limit_spin.setValue(33000)
    dialog.candidate_limit_spin.setValue(6)
    dialog.brave_timeout_spin.setValue(8)
    dialog._save()
    app.processEvents()

    client = QwenClient(api_key="smoke-test-key-not-a-real-secret")
    retriever = HybridCandidateRetriever()
    if not applied:
        raise SystemExit("Settings did not emit an applied event")
    if client.model != "qwen-settings-smoke":
        raise SystemExit("Model setting did not apply immediately")
    if client.temperature != 0.20 or client.timeout != 91:
        raise SystemExit("Qwen runtime settings did not apply immediately")
    if client.max_prompt_chars != 33000:
        raise SystemExit("Prompt limit did not apply immediately")
    if retriever.maximum_queries != 6:
        raise SystemExit("Candidate limit did not apply immediately")
    if "6" not in str(
        QgsSettings().value("sakugis/agents/candidate_limit", "")
    ):
        raise SystemExit("Candidate limit was not persisted")

    kimi_dialog = SettingsDialog(window)
    kimi_dialog.settingsApplied.connect(window._apply_settings)
    kimi_dialog.provider_combo.setCurrentIndex(
        kimi_dialog.provider_combo.findData(KIMI)
    )
    kimi_dialog.kimi_model_edit.setText("kimi-k3")
    kimi_dialog.kimi_effort_combo.setCurrentIndex(
        kimi_dialog.kimi_effort_combo.findData("max")
    )
    kimi_dialog.kimi_timeout_spin.setValue(241)
    kimi_dialog._save()
    app.processEvents()
    kimi_client = KimiClient(api_key="smoke-test-kimi-key-not-a-real-secret")
    if configured_provider() != KIMI:
        raise SystemExit("Kimi provider setting did not apply immediately")
    if kimi_client.model != "kimi-k3":
        raise SystemExit("Kimi model setting did not apply immediately")
    if kimi_client.reasoning_effort != "max" or kimi_client.timeout != 241:
        raise SystemExit("Kimi reasoning settings did not apply immediately")

    restore_dialog = SettingsDialog(window)
    restore_dialog.settingsApplied.connect(window._apply_settings)
    restore_dialog.provider_combo.setCurrentIndex(
        restore_dialog.provider_combo.findData(QWEN)
    )
    restore_dialog._save()
    app.processEvents()
    if configured_provider() != QWEN:
        raise SystemExit("Qwen default provider did not restore")
    print("Unified Qwen/Kimi settings and immediate apply: OK")

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

if os.environ.get("SAKUGIS_SMOKE_GIS_TOOLS") == "1":
    from pathlib import Path
    import shutil
    from tempfile import TemporaryDirectory

    from qgis.PyQt.QtCore import QVariant
    from qgis.PyQt.QtGui import QColor
    from qgis.core import (
        QgsCategorizedSymbolRenderer,
        QgsFeature,
        QgsField,
        QgsGradientColorRamp,
        QgsGeometry,
        QgsGraduatedSymbolRenderer,
        QgsRectangle,
        QgsRendererCategory,
        QgsSingleSymbolRenderer,
        QgsSymbol,
        QgsVectorLayer,
    )
    from qgis.gui import QgsRendererPropertiesDialog
    from sakugis.map_export import MapExportOptions, export_map_layout
    from sakugis.vector_tools import (
        AttributeTableDialog,
        FeatureTableModel,
        create_layer_style_dialog,
    )
    from sakugis.i18n import apply_qgis_translation

    window.project.clear()
    geometry_cases = (
        ("Point", ("POINT (0 0)", "POINT (1 1)")),
        ("LineString", ("LINESTRING (0 0, 1 1)", "LINESTRING (0 1, 1 2)")),
        ("Polygon", (
            "POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))",
            "POLYGON ((1 1, 2 1, 2 2, 1 2, 1 1))",
        )),
    )
    smoke_layers = []
    for geometry_name, wkts in geometry_cases:
        layer = QgsVectorLayer(
            f"{geometry_name}?crs=EPSG:4326",
            f"Smoke {geometry_name}",
            "memory",
        )
        provider = layer.dataProvider()
        provider.addAttributes(
            [QgsField("class", QVariant.String), QgsField("value", QVariant.Int)]
        )
        layer.updateFields()
        features = []
        for index, wkt in enumerate(wkts):
            feature = QgsFeature(layer.fields())
            feature.setAttributes(["A" if index == 0 else "B", index + 1])
            feature.setGeometry(QgsGeometry.fromWkt(wkt))
            features.append(feature)
        if not provider.addFeatures(features):
            raise SystemExit(f"Could not create {geometry_name} smoke layer")
        layer.updateExtents()
        window.project.addMapLayer(layer)
        smoke_layers.append(layer)

        base_symbol = QgsSymbol.defaultSymbol(layer.geometryType())
        base_symbol.setColor(QColor("#42ADD4"))
        layer.setRenderer(QgsSingleSymbolRenderer(base_symbol.clone()))
        if layer.renderer().type() != "singleSymbol":
            raise SystemExit(f"Single style failed for {geometry_name}")
        second_symbol = base_symbol.clone()
        second_symbol.setColor(QColor("#DD3F72"))
        layer.setRenderer(
            QgsCategorizedSymbolRenderer(
                "class",
                [
                    QgsRendererCategory("A", base_symbol, "A"),
                    QgsRendererCategory("B", second_symbol, "B"),
                ],
            )
        )
        renderer = layer.renderer()
        if renderer.type() != "categorizedSymbol" or len(renderer.categories()) != 2:
            raise SystemExit(f"Categorized renderer is invalid for {geometry_name}")

    point_layer = smoke_layers[0]
    graduated = QgsGraduatedSymbolRenderer.createRenderer(
        point_layer,
        "value",
        5,
        QgsGraduatedSymbolRenderer.EqualInterval,
        QgsSymbol.defaultSymbol(point_layer.geometryType()),
        QgsGradientColorRamp(QColor("#440154"), QColor("#FDE725")),
    )
    point_layer.setRenderer(graduated)
    if point_layer.renderer().type() != "graduatedSymbol":
        raise SystemExit("Continuous numeric graduated renderer was not applied")
    if len(point_layer.renderer().ranges()) != 5:
        raise SystemExit("Continuous numeric renderer did not create five classes")

    apply_qgis_translation(app)
    style_dialog = create_layer_style_dialog(point_layer, window.canvas, window)
    if not isinstance(style_dialog, QgsRendererPropertiesDialog):
        raise SystemExit("Layer styling did not use QGIS' native dialog")
    if style_dialog.minimumWidth() < 820 or style_dialog.minimumHeight() < 580:
        raise SystemExit("Native QGIS styling dialog is too compressed")
    style_screenshot = os.environ.get("SAKUGIS_SMOKE_GIS_STYLE_SCREENSHOT")
    if style_screenshot:
        style_dialog.show()
        app.processEvents()
        if not style_dialog.grab().save(style_screenshot):
            raise SystemExit("Layer style screenshot could not be saved")
    style_dialog.reject()
    app.processEvents()

    window.layer_panel.view.setCurrentLayer(point_layer)
    app.processEvents()
    if not window.layer_panel.style_button.isEnabled():
        raise SystemExit("Layer Style button is disabled for a point layer")
    if not window.layer_panel.attribute_button.isEnabled():
        raise SystemExit("Attribute Table button is disabled for a point layer")
    if not window.layer_style_action.isEnabled():
        raise SystemExit("Layer Style menu action is disabled for a point layer")
    if not window.attribute_table_action.isEnabled():
        raise SystemExit("Attribute Table menu action is disabled for a point layer")
    table_model = FeatureTableModel(point_layer)
    if table_model.rowCount() != 2 or table_model.columnCount() != 3:
        raise SystemExit("Attribute table did not expose fields and rows")
    attribute_dialog = AttributeTableDialog(point_layer, window.canvas, window)
    attribute_screenshot = os.environ.get(
        "SAKUGIS_SMOKE_GIS_ATTRIBUTE_SCREENSHOT"
    )
    if attribute_screenshot:
        attribute_dialog.show()
        app.processEvents()
        if not attribute_dialog.grab().save(attribute_screenshot):
            raise SystemExit("Attribute table screenshot could not be saved")
    attribute_dialog.table.selectRow(0)
    app.processEvents()
    if len(point_layer.selectedFeatureIds()) != 1:
        raise SystemExit("Attribute table selection did not reach the layer")
    attribute_dialog.hide()

    window.canvas.setDestinationCrs(point_layer.crs())
    window.canvas.setExtent(QgsRectangle(-0.25, -0.25, 2.25, 2.25))
    window.canvas.refresh()
    app.processEvents()
    with TemporaryDirectory(prefix="sakugis-map-export-") as export_root:
        export_root = Path(export_root)
        retained_export_root = os.environ.get("SAKUGIS_SMOKE_GIS_EXPORT_DIR")
        for file_format in ("png", "pdf"):
            destination, google_excluded = export_map_layout(
                window.project,
                window.canvas,
                str(export_root / f"smoke-map.{file_format}"),
                MapExportOptions(
                    title="SakuGIS GIS Tools Smoke",
                    subtitle="Point / line / polygon",
                    creator="SakuGIS Smoke",
                    file_format=file_format,
                    dpi=96,
                ),
            )
            if google_excluded or not destination.is_file():
                raise SystemExit(f"{file_format.upper()} map export failed")
            if destination.stat().st_size < 1000:
                raise SystemExit(f"{file_format.upper()} map export is empty")
            if retained_export_root:
                retained_path = Path(retained_export_root)
                retained_path.mkdir(parents=True, exist_ok=True)
                shutil.copy2(destination, retained_path / destination.name)
    print("QGIS native single/categorized/graduated styling: OK")
    print("Attribute table display and map selection: OK")
    print("A4 PNG/PDF map composition export: OK")

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
                retrieval_score=0.95,
                retrieval_source="PostGIS OSM index",
                retrieval_label="静岡市, 静岡県, 日本",
                retrieval_source_id="relation/223148",
                retrieval_verified=True,
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
                retrieval_score=0.88,
                retrieval_source="PostGIS OSM index",
                retrieval_label="Napier City, Hawke's Bay, New Zealand",
                retrieval_source_id="relation/2094140",
                retrieval_verified=True,
            ),
        ],
        verification_summary="静冈市在当前测试证据下排名第一。",
        caveat="这是界面测试数据，探索评分尚未校准。",
        model="smoke-test",
        gis_backend="OSM Nominatim + Overpass",
        retrieval_backend="PostGIS OSM index",
        retrieval_resolved_count=2,
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
    preserved_result = window.agent_panel.last_result()
    window.agent_panel._prepare_new_search()
    app.processEvents()
    if window.agent_panel.view_result_button.isHidden():
        raise SystemExit("View Result action is missing after editing input")
    if not window.agent_panel.result_splitter.isHidden():
        raise SystemExit("Result workspace did not yield space to input editor")
    window.agent_panel._return_to_result()
    app.processEvents()
    if not window.agent_panel.view_result_button.isHidden():
        raise SystemExit("View Result action remained visible on result page")
    if window.agent_panel.result_splitter.isHidden():
        raise SystemExit("Preserved result could not be shown again")
    if window.agent_panel.last_result() is not preserved_result:
        raise SystemExit("Editing input discarded the previous result")
    print("Edit Input / View Result round trip: OK")
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
    selected_candidate = sample_result.candidates[0]
    if window.place_details_dock.isVisible():
        raise SystemExit("Candidate details opened without online material")
    if (
        window.place_details_panel.current_candidate().candidate_id
        != selected_candidate.candidate_id
    ):
        raise SystemExit("Candidate details did not follow layer selection")
    QgsSettings().setValue("sakugis/ui/place-details-floating", True)
    window._on_place_details_available(selected_candidate)
    app.processEvents()
    if not window.place_details_dock.isVisible():
        raise SystemExit("Qualified candidate details did not open")
    if not window.place_details_dock.isFloating():
        raise SystemExit("Candidate details did not open as a floating window")
    destination_point = QgsCoordinateTransform(
        QgsCoordinateReferenceSystem("EPSG:4326"),
        window.canvas.mapSettings().destinationCrs(),
        window.project,
    ).transform(
        QgsPointXY(
            selected_candidate.longitude,
            selected_candidate.latitude,
        )
    )
    if (
        window._nearest_candidate(destination_point).candidate_id
        != selected_candidate.candidate_id
    ):
        raise SystemExit("Map marker hit testing did not find candidate")
    window._set_language("en")
    if window.place_details_panel.tabs.tabText(1) != "Web Photos":
        raise SystemExit("English place details translation did not apply")
    window._set_language("zh_CN")
    if window.place_details_panel.tabs.tabText(1) != "网络照片":
        raise SystemExit("Chinese place details translation did not apply")
    print("Candidate details availability gate: OK")
    print("Candidate details floating window: OK")
    print("Candidate details list/layer/map linkage: OK")
    print("Candidate details Chinese/English switch: OK")
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
    if os.environ.get("SAKUGIS_SMOKE_SGD") == "1":
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from qgis.PyQt.QtGui import QColor, QImage

        source_case = TemporaryDirectory(prefix="sakugis-sgd-smoke-source-")
        source_root = Path(source_case.name)
        photo_path = source_root / "multimodal-input.png"
        image = QImage(32, 24, QImage.Format_RGB32)
        image.fill(QColor("#33aacc"))
        if not image.save(str(photo_path)):
            raise SystemExit("Could not create SGD smoke-test photo")
        local_data_path = source_root / "review-area.geojson"
        local_data_path.write_text(
            '{"type":"FeatureCollection","features":['
            '{"type":"Feature","properties":{"name":"review"},'
            '"geometry":{"type":"Point","coordinates":[138.383,34.977]}}]}',
            encoding="utf-8",
        )
        from qgis.core import QgsVectorLayer

        local_layer = QgsVectorLayer(
            str(local_data_path), "SGD local review layer", "ogr"
        )
        if not local_layer.isValid():
            raise SystemExit("Could not create SGD local layer")
        local_layer.setOpacity(0.42)
        window.project.addMapLayer(local_layer)
        sample_result.image_path = str(photo_path)
        sample_result.image_paths = [str(photo_path)]
        window.agent_panel.restore_session(
            sample_result.query, [str(photo_path)], sample_result
        )
        archived_thumbnail = source_root / "places/C1/thumbnail-1.img"
        archived_thumbnail.parent.mkdir(parents=True, exist_ok=True)
        archived_thumbnail.write_bytes(photo_path.read_bytes())
        window.place_details_panel.restore_archive(
            {
                "candidates": {
                    "C1": {
                        "candidate_id": "C1",
                        "query": "静冈市 地点介绍",
                        "web_results": [
                            {
                                "title": "静冈市测试介绍",
                                "url": "https://example.com/shizuoka",
                                "description": "SGD 离线复盘测试资料",
                                "source": "example.com",
                            }
                        ],
                        "images": [
                            {
                                "title": "静冈市测试照片",
                                "page_url": "https://example.com/shizuoka/photo",
                                "thumbnail_url": "https://imgs.search.brave.com/example",
                                "original_url": "https://example.com/shizuoka.jpg",
                                "source": "example.com",
                                "width": 32,
                                "height": 24,
                            }
                        ],
                        "warnings": [],
                        "thumbnails": [
                            {
                                "index": 0,
                                "archive_path": "places/C1/thumbnail-1.img",
                            }
                        ],
                    }
                }
            },
            source_root,
        )
        window.place_details_panel.set_candidate(sample_result.candidates[0])
        project_path = source_root / "round-trip.sgd"
        if not window._save_sgd_path(str(project_path)):
            raise SystemExit("SGD project save failed")
        if not project_path.is_file():
            raise SystemExit("SGD project file was not created")
        if not window.load_project_path(str(project_path), confirm_discard=False):
            raise SystemExit("SGD project load failed")
        replay_layers = [
            layer
            for layer in window.project.mapLayers().values()
            if layer.customProperty("sakugis/candidate-layer")
        ]
        if len(replay_layers) != len(sample_result.candidates):
            raise SystemExit("SGD replay did not rebuild candidate map layers")
        if window.agent_panel.query_text() != sample_result.query:
            raise SystemExit("SGD replay did not restore query text")
        if len(window.agent_panel.image_paths()) != 1:
            raise SystemExit("SGD replay did not restore packaged photos")
        if not Path(window.agent_panel.image_paths()[0]).is_file():
            raise SystemExit("SGD replay photo is not available")
        if window.agent_panel.last_result() is None:
            raise SystemExit("SGD replay did not restore Agent results")
        replay_place_details, replay_place_blobs = (
            window.place_details_panel.archive_snapshot()
        )
        if (
            replay_place_details["candidates"]["C1"]["web_results"][0]["title"]
            != "静冈市测试介绍"
        ):
            raise SystemExit("SGD replay did not restore web descriptions")
        if len(replay_place_blobs) != 1:
            raise SystemExit("SGD replay did not restore web photo thumbnails")
        restored_local_layers = [
            layer
            for layer in window.project.mapLayers().values()
            if layer.name() == "SGD local review layer"
        ]
        if len(restored_local_layers) != 1:
            raise SystemExit("SGD replay did not restore packaged local GIS data")
        if restored_local_layers[0].featureCount() != 1:
            raise SystemExit("SGD replay local GIS data is incomplete")
        if abs(restored_local_layers[0].opacity() - 0.42) > 0.01:
            raise SystemExit("SGD replay did not restore layer opacity")
        if not window.save_project():
            raise SystemExit("SGD replay project could not be saved again")
        source_case.cleanup()
        print("SGD save/load and map replay: OK")

screenshot_path = os.environ.get("SAKUGIS_SMOKE_SCREENSHOT")
duration_ms = int(os.environ.get("SAKUGIS_SMOKE_DURATION_MS", "750"))
place_tab = os.environ.get("SAKUGIS_SMOKE_PLACE_TAB")
if place_tab is not None:
    QTimer.singleShot(
        max(100, duration_ms - 1800),
        lambda: window.place_details_panel.tabs.setCurrentIndex(
            int(place_tab)
        ),
    )
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

window.prepare_for_shutdown()
for key, (existed, value) in place_setting_snapshot.items():
    if existed:
        place_settings.setValue(key, value)
    else:
        place_settings.remove(key)
app.exitQgis()
PY
