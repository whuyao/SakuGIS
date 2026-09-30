"""Main SakuGIS window."""

from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path, PurePosixPath
import re
from tempfile import TemporaryDirectory
from typing import Optional

from qgis.PyQt.QtCore import (
    QObject,
    QPoint,
    QThread,
    QTimer,
    Qt,
    QUrl,
    QVariant,
    pyqtSignal,
    pyqtSlot,
)
from qgis.PyQt.QtGui import QColor, QDesktopServices, QKeySequence
from qgis.PyQt.QtWidgets import (
    QAction,
    QActionGroup,
    QApplication,
    QDockWidget,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QToolBar,
)
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsField,
    QgsFillSymbol,
    QgsGeometry,
    QgsLayerTreeGroup,
    QgsLayerTreeLayer,
    QgsMarkerSymbol,
    QgsPointXY,
    QgsProject,
    QgsRasterLayer,
    QgsRectangle,
    QgsVectorLayer,
    QgsWkbTypes,
    QgsSettings,
)
from qgis.gui import (
    QgsLayerTreeMapCanvasBridge,
    QgsMapCanvas,
    QgsMapToolPan,
    QgsMapToolZoom,
)

from sakugis.basemaps import GOOGLE_SATELLITE, OSM, available_google_satellite
from sakugis.agent_models import Candidate, GeoAnalysisResult
from sakugis.agent_panel import AgentPanel
from sakugis.i18n import (
    EN,
    ZH_CN,
    apply_qgis_translation,
    get_language,
    set_language,
    tr,
)
from sakugis.layer_panel import LayerPanel
from sakugis.map_export import MapExportDialog, export_map_layout
from sakugis.map_defaults import choose_startup_city
from sakugis.place_details_panel import PlaceDetailsPanel
from sakugis.project_archive import (
    ArchiveAsset,
    SgdError,
    load_sgd,
    save_sgd,
)
from sakugis.reporting import write_markdown_report
from sakugis.settings_dialog import SettingsDialog
from sakugis.ui_components import MapHud, WelcomeOverlay
from sakugis.ui_theme import (
    DARK,
    LIGHT,
    apply_theme,
    get_theme,
    glyph_icon,
    theme_colors,
)
from sakugis.update_checker import (
    UpdateCheckError,
    UpdateStatus,
    fetch_update_status,
)
from sakugis.vector_tools import AttributeTableDialog, create_layer_style_dialog
from sakugis import __version__


class UpdateCheckWorker(QObject):
    """Run the network check without blocking map interaction."""

    resultReady = pyqtSignal(object)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    @pyqtSlot()
    def run(self) -> None:
        try:
            self.resultReady.emit(fetch_update_status(__version__))
        except UpdateCheckError as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class CandidatePanTool(QgsMapToolPan):
    """Normal pan tool that also recognizes a short click on a candidate."""

    def __init__(self, canvas, click_callback):
        super().__init__(canvas)
        self._click_callback = click_callback
        self._press_position = None

    def canvasPressEvent(self, event) -> None:
        self._press_position = event.pos()
        super().canvasPressEvent(event)

    def canvasReleaseEvent(self, event) -> None:
        press_position = self._press_position
        super().canvasReleaseEvent(event)
        self._press_position = None
        if (
            press_position is not None
            and (event.pos() - press_position).manhattanLength() <= 6
        ):
            self._click_callback(event.mapPoint())


def _setting_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value or "").strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SakuGIS")
        self.resize(1440, 900)
        self.setMinimumSize(1040, 680)
        self.setCorner(
            Qt.BottomLeftCorner, Qt.LeftDockWidgetArea
        )
        self.setCorner(
            Qt.BottomRightCorner, Qt.RightDockWidgetArea
        )
        self._last_analysis_result = None
        self._coordinate_display = None
        self._current_scale = None
        self._candidates_by_id = {}
        self._place_details_available = False
        self._update_thread = None
        self._update_worker = None
        self._sgd_path = ""
        self._sgd_dirty = False
        self._restoring_sgd = False
        self._sgd_extraction = None
        self.startup_city = choose_startup_city(
            os.environ.get("SAKUGIS_STARTUP_CITY", "")
        )

        self.project = QgsProject.instance()
        self._shutting_down = False
        self._visibility_slot = lambda _: self._refresh_attribution()
        self.project.layerTreeRoot().visibilityChanged.connect(
            self._visibility_slot
        )
        self.canvas = QgsMapCanvas(self)
        self.canvas.setObjectName("MapCanvas")
        self.canvas.setCanvasColor(QColor(theme_colors()["background"]))
        self.canvas.enableAntiAliasing(True)
        self.canvas.setParallelRenderingEnabled(True)
        self.canvas.setDestinationCrs(QgsCoordinateReferenceSystem("EPSG:3857"))
        self.setCentralWidget(self.canvas)

        self.layer_panel = LayerPanel(self)
        self.layer_panel.removeRequested.connect(self.remove_selected_layers)
        self.layer_panel.zoomRequested.connect(self.zoom_to_current_layer)
        self.layer_panel.styleRequested.connect(self.open_layer_style)
        self.layer_panel.attributeTableRequested.connect(
            self.open_attribute_table
        )
        self.layer_panel.candidateLayerActivated.connect(
            self._zoom_to_candidate_layer
        )
        self.layer_panel.view.currentLayerChanged.connect(
            self._update_vector_actions
        )

        self.layer_dock = QDockWidget(tr("dock.layers"), self)
        self.layer_dock.setObjectName("layersDock")
        self.layer_dock.setAllowedAreas(
            Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea
        )
        self.layer_dock.setWidget(self.layer_panel)
        self.layer_dock.setMinimumWidth(360)
        self.layer_dock.setMaximumWidth(410)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.layer_dock)

        self.agent_panel = AgentPanel(self)
        self.agent_panel.analysisCompleted.connect(self.show_agent_result)
        self.agent_panel.candidateSelected.connect(
            self.show_candidate_details
        )
        self.agent_panel.candidateActivated.connect(
            self._activate_candidate
        )
        self.agent_panel.reportExportRequested.connect(self.export_report)
        self.agent_panel.settingsRequested.connect(self.open_settings)
        self.agent_panel.sessionChanged.connect(self._mark_sgd_dirty)
        self.agent_dock = QDockWidget(tr("dock.agents"), self)
        self.agent_dock.setObjectName("geoAgentsDock")
        self.agent_dock.setAllowedAreas(
            Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea
        )
        self.agent_dock.setWidget(self.agent_panel)
        self.agent_dock.setMinimumWidth(430)
        self.agent_dock.setMaximumWidth(520)
        self.addDockWidget(Qt.RightDockWidgetArea, self.agent_dock)

        self.place_details_panel = PlaceDetailsPanel(self)
        self.place_details_panel.archiveChanged.connect(self._mark_sgd_dirty)
        self.agent_panel.analysisStarted.connect(
            self.place_details_panel.clear_case
        )
        self.place_details_panel.contentAvailable.connect(
            self._on_place_details_available
        )
        self.place_details_panel.contentUnavailable.connect(
            self._on_place_details_unavailable
        )
        self.place_details_dock = QDockWidget(
            tr("dock.place_details"), self
        )
        self.place_details_dock.setObjectName("placeDetailsDock")
        self.place_details_dock.setAllowedAreas(
            Qt.LeftDockWidgetArea
            | Qt.RightDockWidgetArea
            | Qt.BottomDockWidgetArea
            | Qt.TopDockWidgetArea
        )
        self.place_details_dock.setFeatures(
            QDockWidget.DockWidgetClosable
            | QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
        )
        self.place_details_dock.setWidget(self.place_details_panel)
        self.place_details_dock.setMinimumSize(440, 260)
        self.addDockWidget(
            Qt.BottomDockWidgetArea, self.place_details_dock
        )
        self.place_details_dock.hide()
        self.place_details_dock.toggleViewAction().setEnabled(False)
        self.place_details_dock.topLevelChanged.connect(
            self._place_details_top_level_changed
        )
        self.place_details_dock.visibilityChanged.connect(
            self._place_details_visibility_changed
        )

        self.bridge = QgsLayerTreeMapCanvasBridge(
            self.project.layerTreeRoot(), self.canvas, self
        )
        self.bridge.setCanvasLayers()

        self.pan_tool = CandidatePanTool(
            self.canvas, self._select_candidate_at_map_point
        )
        self.zoom_in_tool = QgsMapToolZoom(self.canvas, False)
        self.zoom_out_tool = QgsMapToolZoom(self.canvas, True)

        self._create_actions()
        self._create_menus()
        self._create_toolbar()
        self._create_status_bar()
        self._connect_canvas_signals()
        self._create_overlays()

        self.project.layersAdded.connect(self._project_layers_changed)
        self.project.layersRemoved.connect(self._project_layers_changed)

        self.activate_pan()
        self._set_initial_extent()
        QTimer.singleShot(0, self._add_default_basemap_if_empty)
        QTimer.singleShot(80, self._show_welcome_if_needed)

    def _create_actions(self) -> None:
        self.open_data_action = QAction(
            glyph_icon("↗"),
            tr("action.open_data"),
            self,
        )
        self.open_data_action.setShortcut(QKeySequence.Open)
        self.open_data_action.triggered.connect(self.open_data)

        self.open_project_action = QAction(tr("action.open_project"), self)
        self.open_project_action.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self.open_project_action.triggered.connect(self.open_project)

        self.save_project_action = QAction(
            glyph_icon("↓"),
            tr("action.save_project"),
            self,
        )
        self.save_project_action.setShortcut(QKeySequence.Save)
        self.save_project_action.triggered.connect(self.save_project)

        self.save_project_as_action = QAction(tr("action.save_as"), self)
        self.save_project_as_action.setShortcut(QKeySequence.SaveAs)
        self.save_project_as_action.triggered.connect(
            lambda: self.save_project(save_as=True)
        )
        self.export_report_action = QAction(
            glyph_icon("⇩"), tr("action.export_report"), self
        )
        self.export_report_action.setShortcut(QKeySequence("Ctrl+Shift+E"))
        self.export_report_action.setEnabled(False)
        self.export_report_action.triggered.connect(self.export_report)
        self.export_map_action = QAction(
            glyph_icon("▣"), tr("action.export_map"), self
        )
        self.export_map_action.setShortcut(QKeySequence("Ctrl+Shift+P"))
        self.export_map_action.triggered.connect(self.export_map)

        self.add_osm_action = QAction(tr("action.add_osm"), self)
        self.add_osm_action.triggered.connect(self.add_osm_basemap)
        self.add_google_satellite_action = QAction(
            glyph_icon("◉"),
            tr("action.add_google_satellite"), self
        )
        self.add_google_satellite_action.triggered.connect(
            self.add_google_satellite
        )

        self.pan_action = QAction(glyph_icon("✥"), tr("action.pan"), self)
        self.pan_action.setCheckable(True)
        self.pan_action.triggered.connect(self.activate_pan)

        self.zoom_in_action = QAction(glyph_icon("+"), tr("action.zoom_in"), self)
        self.zoom_in_action.setCheckable(True)
        self.zoom_in_action.triggered.connect(self.activate_zoom_in)

        self.zoom_out_action = QAction(glyph_icon("−"), tr("action.zoom_out"), self)
        self.zoom_out_action.setCheckable(True)
        self.zoom_out_action.triggered.connect(self.activate_zoom_out)

        self.full_extent_action = QAction(tr("action.full_extent"), self)
        self.full_extent_action.triggered.connect(self.canvas.zoomToFullExtent)

        self.initial_extent_action = QAction(tr("action.initial_extent"), self)
        self.initial_extent_action.triggered.connect(self._set_initial_extent)

        self.remove_layer_action = QAction(tr("action.remove_layers"), self)
        self.remove_layer_action.triggered.connect(self.remove_selected_layers)
        self.layer_style_action = QAction(tr("action.layer_style"), self)
        self.layer_style_action.setEnabled(False)
        self.layer_style_action.triggered.connect(self.open_layer_style)
        self.attribute_table_action = QAction(
            tr("action.attribute_table"), self
        )
        self.attribute_table_action.setEnabled(False)
        self.attribute_table_action.triggered.connect(self.open_attribute_table)

        self.about_action = QAction(tr("action.about"), self)
        self.about_action.triggered.connect(self.show_about)
        self.show_welcome_action = QAction(
            glyph_icon("?"), tr("action.show_welcome"), self
        )
        self.show_welcome_action.triggered.connect(self.show_welcome)

        self.exit_action = QAction(tr("action.exit"), self)
        self.exit_action.setShortcut(QKeySequence.Quit)
        self.exit_action.triggered.connect(self.close)

        self.settings_action = QAction(tr("action.settings"), self)
        self.settings_action.setShortcut(QKeySequence("Ctrl+,"))
        self.settings_action.triggered.connect(
            lambda _checked=False: self.open_settings()
        )

        self.language_action_group = QActionGroup(self)
        self.language_action_group.setExclusive(True)
        self.chinese_action = QAction(tr("language.chinese"), self)
        self.chinese_action.setCheckable(True)
        self.chinese_action.setData(ZH_CN)
        self.english_action = QAction(tr("language.english"), self)
        self.english_action.setCheckable(True)
        self.english_action.setData(EN)
        for action in (self.chinese_action, self.english_action):
            self.language_action_group.addAction(action)
            action.triggered.connect(
                lambda checked, selected=action: (
                    self._set_language(str(selected.data())) if checked else None
                )
            )
        self.chinese_action.setChecked(get_language() == ZH_CN)
        self.english_action.setChecked(get_language() == EN)

        self.theme_action_group = QActionGroup(self)
        self.theme_action_group.setExclusive(True)
        self.light_theme_action = QAction(tr("theme.light"), self)
        self.light_theme_action.setCheckable(True)
        self.light_theme_action.setData(LIGHT)
        self.dark_theme_action = QAction(tr("theme.dark"), self)
        self.dark_theme_action.setCheckable(True)
        self.dark_theme_action.setData(DARK)
        for action in (self.light_theme_action, self.dark_theme_action):
            self.theme_action_group.addAction(action)
            action.triggered.connect(
                lambda checked, selected=action: (
                    self._set_theme(str(selected.data())) if checked else None
                )
            )
        self.light_theme_action.setChecked(get_theme() == LIGHT)
        self.dark_theme_action.setChecked(get_theme() == DARK)

        self.map_tool_actions = [
            self.pan_action,
            self.zoom_in_action,
            self.zoom_out_action,
        ]

    def _create_menus(self) -> None:
        self.file_menu = self.menuBar().addMenu(tr("menu.file"))
        self.file_menu.addAction(self.open_data_action)
        self.file_menu.addAction(self.open_project_action)
        self.file_menu.addAction(self.save_project_action)
        self.file_menu.addAction(self.save_project_as_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.export_map_action)
        self.file_menu.addAction(self.export_report_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.exit_action)

        self.map_menu = self.menuBar().addMenu(tr("menu.map"))
        self.map_menu.addAction(self.pan_action)
        self.map_menu.addAction(self.zoom_in_action)
        self.map_menu.addAction(self.zoom_out_action)
        self.map_menu.addSeparator()
        self.map_menu.addAction(self.full_extent_action)
        self.map_menu.addAction(self.initial_extent_action)

        self.layer_menu = self.menuBar().addMenu(tr("menu.layer"))
        self.layer_menu.addAction(self.add_osm_action)
        self.layer_menu.addAction(self.add_google_satellite_action)
        self.layer_menu.addSeparator()
        self.layer_menu.addAction(self.layer_style_action)
        self.layer_menu.addAction(self.attribute_table_action)
        self.layer_menu.addSeparator()
        self.layer_menu.addAction(self.remove_layer_action)

        self.agent_menu = self.menuBar().addMenu(tr("menu.agent"))
        self.agent_menu.addAction(self.agent_dock.toggleViewAction())
        self.agent_menu.addAction(
            self.place_details_dock.toggleViewAction()
        )

        self.settings_menu = self.menuBar().addMenu(tr("menu.settings"))
        self.settings_menu.addAction(self.settings_action)

        self.help_menu = self.menuBar().addMenu(tr("menu.help"))
        self.help_menu.addAction(self.show_welcome_action)
        self.help_menu.addSeparator()
        self.help_menu.addAction(self.about_action)

    def _create_toolbar(self) -> None:
        self.main_toolbar = QToolBar(tr("toolbar.main"), self)
        self.main_toolbar.setObjectName("mainToolbar")
        self.main_toolbar.setMovable(False)
        self.main_toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.main_toolbar.addAction(self.open_data_action)
        self.main_toolbar.addAction(self.save_project_action)
        self.main_toolbar.addSeparator()
        self.main_toolbar.addAction(self.pan_action)
        self.main_toolbar.addAction(self.zoom_in_action)
        self.main_toolbar.addAction(self.zoom_out_action)
        self.main_toolbar.addAction(self.full_extent_action)
        self.main_toolbar.addAction(self.initial_extent_action)
        self.main_toolbar.addSeparator()
        self.main_toolbar.addAction(self.add_osm_action)
        self.main_toolbar.addAction(self.add_google_satellite_action)
        self.main_toolbar.addSeparator()
        self.main_toolbar.addAction(self.export_map_action)
        self.main_toolbar.addAction(self.export_report_action)
        self.addToolBar(self.main_toolbar)

    def _create_status_bar(self) -> None:
        self.render_status = QLabel(tr("status.ready"), self)
        self.coordinate_status = QLabel(tr("status.coordinate_empty"), self)
        self.scale_status = QLabel(tr("status.scale_empty"), self)
        self.attribution_status = QLabel("", self)
        self.attribution_status.setTextFormat(Qt.RichText)
        self.attribution_status.setOpenExternalLinks(True)

        self.statusBar().addWidget(self.render_status)
        self.statusBar().addPermanentWidget(self.coordinate_status)
        self.statusBar().addPermanentWidget(self.scale_status)
        self.statusBar().addPermanentWidget(self.attribution_status)

    def _set_language(self, language: str) -> None:
        set_language(language)
        apply_qgis_translation(QApplication.instance())
        QgsSettings().setValue("sakugis/ui/language", get_language())
        self.retranslate_ui()

    def _set_theme(self, theme: str) -> None:
        apply_theme(QApplication.instance(), theme)
        QgsSettings().setValue("sakugis/ui/theme", get_theme())
        self.canvas.setCanvasColor(
            QColor(theme_colors()["background"])
        )
        self._refresh_action_icons()
        self.canvas.refresh()

    def open_settings(self, required_section: str = "") -> None:
        dialog = SettingsDialog(self, required_section=required_section)
        dialog.settingsApplied.connect(self._apply_settings)
        dialog.exec_()

    def _apply_settings(self, values) -> None:
        language = str(values.get("language", get_language()))
        theme = str(values.get("theme", get_theme()))
        if language != get_language():
            self._set_language(language)
        if theme != get_theme():
            self._set_theme(theme)
        self.chinese_action.setChecked(get_language() == ZH_CN)
        self.english_action.setChecked(get_language() == EN)
        self.light_theme_action.setChecked(get_theme() == LIGHT)
        self.dark_theme_action.setChecked(get_theme() == DARK)
        self.agent_panel.refresh_runtime_status()
        self.place_details_panel.settings_changed()
        self.statusBar().showMessage(tr("settings.saved"), 4000)

    def _refresh_action_icons(self) -> None:
        self.open_data_action.setIcon(glyph_icon("↗"))
        self.save_project_action.setIcon(glyph_icon("↓"))
        self.export_report_action.setIcon(glyph_icon("⇩"))
        self.export_map_action.setIcon(glyph_icon("▣"))
        self.add_google_satellite_action.setIcon(glyph_icon("◉"))
        self.pan_action.setIcon(glyph_icon("✥"))
        self.zoom_in_action.setIcon(glyph_icon("+"))
        self.zoom_out_action.setIcon(glyph_icon("−"))
        self.show_welcome_action.setIcon(glyph_icon("?"))

    def retranslate_ui(self) -> None:
        self.open_data_action.setText(tr("action.open_data"))
        self.open_project_action.setText(tr("action.open_project"))
        self.save_project_action.setText(tr("action.save_project"))
        self.save_project_as_action.setText(tr("action.save_as"))
        self.export_report_action.setText(tr("action.export_report"))
        self.export_map_action.setText(tr("action.export_map"))
        self.add_osm_action.setText(tr("action.add_osm"))
        self.add_google_satellite_action.setText(
            tr("action.add_google_satellite")
        )
        self.pan_action.setText(tr("action.pan"))
        self.zoom_in_action.setText(tr("action.zoom_in"))
        self.zoom_out_action.setText(tr("action.zoom_out"))
        self.full_extent_action.setText(tr("action.full_extent"))
        self.initial_extent_action.setText(tr("action.initial_extent"))
        self.remove_layer_action.setText(tr("action.remove_layers"))
        self.layer_style_action.setText(tr("action.layer_style"))
        self.attribute_table_action.setText(tr("action.attribute_table"))
        self.about_action.setText(tr("action.about"))
        self.show_welcome_action.setText(tr("action.show_welcome"))
        self.exit_action.setText(tr("action.exit"))
        self.settings_action.setText(tr("action.settings"))
        self.file_menu.setTitle(tr("menu.file"))
        self.map_menu.setTitle(tr("menu.map"))
        self.layer_menu.setTitle(tr("menu.layer"))
        self.agent_menu.setTitle(tr("menu.agent"))
        self.settings_menu.setTitle(tr("menu.settings"))
        self.help_menu.setTitle(tr("menu.help"))
        self.chinese_action.setText(tr("language.chinese"))
        self.english_action.setText(tr("language.english"))
        self.light_theme_action.setText(tr("theme.light"))
        self.dark_theme_action.setText(tr("theme.dark"))
        self.layer_dock.setWindowTitle(tr("dock.layers"))
        self.agent_dock.setWindowTitle(tr("dock.agents"))
        self.place_details_dock.setWindowTitle(tr("dock.place_details"))
        self.place_details_dock.toggleViewAction().setText(
            tr("action.place_details")
        )
        self.main_toolbar.setWindowTitle(tr("toolbar.main"))
        self.render_status.setText(tr("status.ready"))
        if self._coordinate_display is None:
            self.coordinate_status.setText(tr("status.coordinate_empty"))
        else:
            key, values = self._coordinate_display
            self.coordinate_status.setText(tr(key, **values))
        if self._current_scale is None:
            self.scale_status.setText(tr("status.scale_empty"))
        else:
            self.scale_status.setText(
                tr("status.scale", scale=f"{self._current_scale:,.0f}")
            )
        self.layer_panel.retranslate_ui()
        self.agent_panel.retranslate_ui()
        self.place_details_panel.retranslate_ui()
        self.welcome_overlay.retranslate_ui()
        self.map_hud.retranslate_ui()
        self._update_workspace_state()

    def _create_overlays(self) -> None:
        self.welcome_overlay = WelcomeOverlay(self.canvas)
        self.welcome_overlay.startRequested.connect(self._welcome_start)
        self.welcome_overlay.satelliteRequested.connect(
            self._welcome_add_satellite
        )
        self.welcome_overlay.openDataRequested.connect(self._welcome_open_data)
        self.welcome_overlay.dismissed.connect(self._remember_welcome_dismissed)
        self.welcome_overlay.hide()

        self.map_hud = MapHud(self.canvas)
        self.map_hud.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.map_hud.show()
        self._position_overlays()

    def _position_overlays(self) -> None:
        if not hasattr(self, "welcome_overlay"):
            return
        canvas_width = self.canvas.width()
        welcome_width = min(640, max(500, canvas_width - 64))
        self.welcome_overlay.setFixedWidth(welcome_width)
        self.welcome_overlay.adjustSize()
        self.welcome_overlay.move(
            max(24, (canvas_width - self.welcome_overlay.width()) // 2),
            48,
        )
        self.map_hud.move(16, 16)
        self.map_hud.raise_()
        self.welcome_overlay.raise_()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_overlays()

    def _show_welcome_if_needed(self) -> None:
        if self._last_analysis_result is not None:
            return
        dismissed = bool(
            QgsSettings().value(
                "sakugis/ui/welcomeDismissed", False, type=bool
            )
        )
        if not dismissed:
            self.show_welcome()

    def show_welcome(self) -> None:
        self.map_hud.hide()
        self.welcome_overlay.show()
        self._position_overlays()
        self.welcome_overlay.raise_()

    def _hide_welcome(self) -> None:
        self.welcome_overlay.hide()
        self.map_hud.show()
        self.map_hud.raise_()

    def _remember_welcome_dismissed(self) -> None:
        QgsSettings().setValue("sakugis/ui/welcomeDismissed", True)

    def _welcome_start(self) -> None:
        self._hide_welcome()
        self.agent_dock.show()
        self.agent_dock.raise_()
        self.agent_panel.focus_query()

    def _welcome_add_satellite(self) -> None:
        self._hide_welcome()
        self.add_google_satellite()

    def _welcome_open_data(self) -> None:
        self._hide_welcome()
        self.open_data()

    def _update_workspace_state(self) -> None:
        count = len(self.project.mapLayers())
        self.map_hud.update_layers(count)
        self.layer_panel.refresh_summary(count)

    def _connect_canvas_signals(self) -> None:
        self.canvas.xyCoordinates.connect(self._update_coordinates)
        self.canvas.scaleChanged.connect(self._update_scale)
        self.canvas.extentsChanged.connect(self._mark_saved_extent_dirty)
        self.canvas.renderStarting.connect(
            lambda: self.render_status.setText(tr("status.rendering"))
        )
        self.canvas.renderComplete.connect(
            lambda _: self.render_status.setText(tr("status.ready"))
        )

    def _mark_saved_extent_dirty(self) -> None:
        if self._sgd_path:
            self._mark_sgd_dirty()

    def _set_active_map_action(self, active) -> None:
        for action in self.map_tool_actions:
            action.setChecked(action is active)

    def activate_pan(self) -> None:
        self.canvas.setMapTool(self.pan_tool)
        self._set_active_map_action(self.pan_action)

    def activate_zoom_in(self) -> None:
        self.canvas.setMapTool(self.zoom_in_tool)
        self._set_active_map_action(self.zoom_in_action)

    def activate_zoom_out(self) -> None:
        self.canvas.setMapTool(self.zoom_out_tool)
        self._set_active_map_action(self.zoom_out_action)

    def _set_initial_extent(self) -> None:
        source_crs = QgsCoordinateReferenceSystem("EPSG:4326")
        destination_crs = self.canvas.mapSettings().destinationCrs()
        transform = QgsCoordinateTransform(
            source_crs, destination_crs, self.project
        )
        startup_extent = QgsRectangle(*self.startup_city.extent_wgs84)
        self.canvas.setExtent(transform.transformBoundingBox(startup_extent))
        self.canvas.refresh()

    def _update_coordinates(self, point) -> None:
        try:
            transform = QgsCoordinateTransform(
                self.canvas.mapSettings().destinationCrs(),
                QgsCoordinateReferenceSystem("EPSG:4326"),
                self.project,
            )
            geographic = transform.transform(point)
            values = {
                "x": f"{geographic.x():.5f}",
                "y": f"{geographic.y():.5f}",
            }
            self._coordinate_display = ("status.latlon", values)
            self.coordinate_status.setText(
                tr("status.latlon", **values)
            )
        except Exception:
            values = {
                "x": f"{point.x():.2f}",
                "y": f"{point.y():.2f}",
            }
            self._coordinate_display = ("status.coordinate", values)
            self.coordinate_status.setText(
                tr("status.coordinate", **values)
            )

    def _update_scale(self, scale: float) -> None:
        self._current_scale = scale
        self.scale_status.setText(tr("status.scale", scale=f"{scale:,.0f}"))

    def add_osm_basemap(self) -> None:
        for layer in self.project.mapLayers().values():
            if layer.customProperty("sakugis/basemap-key") == OSM.key:
                self._refresh_attribution()
                return

        project_was_empty = not self.project.mapLayers()
        layer = QgsRasterLayer(OSM.uri, OSM.name, OSM.provider)
        if not layer.isValid():
            QMessageBox.warning(
                self,
                tr("dialog.basemap_failed"),
                tr("dialog.basemap_failed_detail"),
            )
            return

        layer.setCustomProperty("sakugis/basemap-key", OSM.key)
        layer.setCustomProperty("sakugis/attribution", OSM.attribution_html)
        self.project.addMapLayer(layer, False)
        self.project.layerTreeRoot().addLayer(layer)
        self._refresh_attribution()
        if project_was_empty:
            self._set_initial_extent()
        self.canvas.refresh()

    def add_google_satellite(self) -> None:
        self._hide_welcome()
        for layer in self.project.mapLayers().values():
            if (
                layer.customProperty("sakugis/basemap-key")
                == GOOGLE_SATELLITE.key
            ):
                self._refresh_attribution()
                return

        definition = available_google_satellite()
        project_was_empty = not self.project.mapLayers()
        layer = QgsRasterLayer(
            definition.uri,
            tr("basemap.google_satellite"),
            definition.provider,
        )
        if not layer.isValid():
            QMessageBox.warning(
                self,
                tr("dialog.google_failed"),
                tr("dialog.google_failed_detail"),
            )
            return

        layer.setCustomProperty(
            "sakugis/basemap-key", definition.key
        )
        layer.setCustomProperty(
            "sakugis/attribution", definition.attribution_html
        )
        layer.setCustomProperty("sakugis/visualization-only", True)
        self.project.addMapLayer(layer, False)
        self.project.layerTreeRoot().addLayer(layer)
        self._refresh_attribution()
        self.statusBar().showMessage(tr("dialog.google_policy"), 7000)
        if project_was_empty:
            self._set_initial_extent()
        self.canvas.refresh()

    def _add_default_basemap_if_empty(self) -> None:
        if not self.project.mapLayers():
            if self._sgd_path:
                saved_extent = QgsRectangle(self.canvas.extent())
                previous_restoring = self._restoring_sgd
                self._restoring_sgd = True
                self.add_osm_basemap()
                QTimer.singleShot(
                    150,
                    lambda: self._finish_empty_sgd_basemap(
                        saved_extent, previous_restoring
                    ),
                )
                return
            self.add_osm_basemap()
            # The layer-tree bridge may apply the global XYZ extent on the
            # next event-loop turn, so restore this launch's city afterwards.
            QTimer.singleShot(150, self._set_initial_extent)
            if not self.project.fileName():
                self.project.setDirty(False)

    def _finish_empty_sgd_basemap(
        self, saved_extent: QgsRectangle, previous_restoring: bool
    ) -> None:
        if self._shutting_down:
            return
        try:
            self.canvas.setExtent(saved_extent)
            self.canvas.refresh()
            self.project.setDirty(False)
            self._sgd_dirty = False
        finally:
            self._restoring_sgd = previous_restoring

    def _project_layers_changed(self, *_args) -> None:
        if not self._shutting_down:
            self._update_workspace_state()

    def open_data(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            tr("dialog.open_gis"),
            str(Path.home()),
            tr("dialog.gis_filter"),
        )
        if not paths:
            return

        added_layers = []
        for path in paths:
            suffix = Path(path).suffix.lower()
            if suffix in {".tif", ".tiff", ".vrt", ".img"}:
                layer = QgsRasterLayer(path, Path(path).stem)
            else:
                layer = QgsVectorLayer(path, Path(path).stem, "ogr")

            if layer.isValid():
                self.project.addMapLayer(layer)
                added_layers.append(layer)
            else:
                QMessageBox.warning(
                    self,
                    tr("dialog.load_failed"),
                    tr("dialog.load_failed_detail", path=path),
                )

        if added_layers:
            self._hide_welcome()
            self.zoom_to_layer(added_layers[-1])

    def open_project(self) -> None:
        if not self._confirm_discard_changes():
            return

        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("dialog.open_project"),
            str(Path.home()),
            tr("dialog.project_filter"),
        )
        if not path:
            return

        self.load_project_path(path, confirm_discard=False)

    def load_project_path(self, path: str, confirm_discard: bool = True) -> bool:
        if confirm_discard and not self._confirm_discard_changes():
            return False

        if Path(path).suffix.lower() == ".sgd":
            return self._load_sgd_path(path)

        self.project.clear()
        if not self.project.read(path):
            QMessageBox.critical(
                self,
                tr("dialog.project_open_failed"),
                tr("dialog.project_open_failed_detail", path=path),
            )
            return False
        self._release_sgd_extraction()
        self._sgd_path = ""
        self._sgd_dirty = False
        self._last_analysis_result = None
        self._candidates_by_id = {}
        self.agent_panel.restore_session("", [], None)
        self.place_details_panel.clear_case()
        self.export_report_action.setEnabled(False)
        self.setWindowTitle(f"SakuGIS — {Path(path).name}")
        self._hide_welcome()
        self._refresh_attribution()
        self.canvas.refresh()
        return True

    def save_project(self, checked: bool = False, save_as: bool = False) -> bool:
        current = self._sgd_path or self.project.fileName()
        if current and not save_as:
            if Path(current).suffix.lower() == ".sgd":
                return self._save_sgd_path(current)
            if self.project.write():
                self.statusBar().showMessage(tr("status.project_saved"), 3000)
                return True
            QMessageBox.critical(
                self,
                tr("dialog.save_failed"),
                tr("dialog.save_failed_detail", path=current),
            )
            return False

        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            tr("dialog.save_project"),
            current or str(Path.home() / tr("dialog.untitled")),
            tr("dialog.save_project_filter"),
        )
        if not path:
            return False

        if not Path(path).suffix:
            path += ".qgz" if "QGIS" in selected_filter else ".sgd"
        if Path(path).suffix.lower() == ".sgd":
            return self._save_sgd_path(path)
        if not self.project.write(path):
            QMessageBox.critical(
                self,
                tr("dialog.save_failed"),
                tr("dialog.save_failed_detail", path=path),
            )
            return False
        self._sgd_path = ""
        self._sgd_dirty = False
        self.setWindowTitle(f"SakuGIS — {Path(path).name}")
        self.statusBar().showMessage(tr("status.project_saved"), 3000)
        return True

    def _mark_sgd_dirty(self, *_args) -> None:
        if not self._restoring_sgd and not self._shutting_down:
            self._sgd_dirty = True

    def _save_sgd_path(self, path: str) -> bool:
        try:
            with TemporaryDirectory(prefix="sakugis-save-") as staging:
                staging_root = Path(staging)
                map_state, assets = self._capture_sgd_map_state(staging_root)
                place_details, place_blobs = (
                    self.place_details_panel.archive_snapshot()
                )
                for archive_path, content in place_blobs.items():
                    staged_path = staging_root.joinpath(*Path(archive_path).parts)
                    staged_path.parent.mkdir(parents=True, exist_ok=True)
                    staged_path.write_bytes(content)
                    assets.append(ArchiveAsset(str(staged_path), archive_path))
                destination = save_sgd(
                    path,
                    query=self.agent_panel.query_text(),
                    image_paths=self.agent_panel.image_paths(),
                    result=self._last_analysis_result,
                    map_state=map_state,
                    place_details=place_details,
                    assets=assets,
                    application_version=__version__,
                )
        except (OSError, SgdError, ValueError) as exc:
            QMessageBox.critical(
                self,
                tr("dialog.save_failed"),
                tr("dialog.sgd_save_failed_detail", error=str(exc)),
            )
            return False
        self._sgd_path = str(destination)
        self._sgd_dirty = False
        self.project.setDirty(False)
        self.setWindowTitle(f"SakuGIS — {destination.name}")
        self.statusBar().showMessage(tr("status.project_saved"), 3000)
        return True

    @staticmethod
    def _safe_layer_id(value: str, index: int) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-")
        return cleaned[:48] or f"layer-{index}"

    @staticmethod
    def _portable_source_suffix(source: str) -> str:
        parts = source.split("|")[1:]
        allowed = []
        for part in parts:
            key = part.partition("=")[0].strip().casefold()
            if key in {"layername", "geometrytype"}:
                allowed.append(part)
        return "".join(f"|{part}" for part in allowed)

    def _capture_sgd_map_state(
        self, staging_root: Path
    ) -> tuple[dict, list[ArchiveAsset]]:
        root = self.project.layerTreeRoot()
        layer_records = []
        assets = []
        warnings = []
        packaged_sources = {}
        supported = {
            ".geojson",
            ".json",
            ".gpkg",
            ".shp",
            ".kml",
            ".gpx",
            ".tif",
            ".tiff",
            ".img",
        }
        for index, layer in enumerate(root.layerOrder(), 1):
            if layer.customProperty("sakugis/agent-result"):
                continue
            node = root.findLayer(layer.id())
            record = {
                "name": layer.name(),
                "visible": bool(node and node.isVisible()),
            }
            basemap_key = str(layer.customProperty("sakugis/basemap-key", ""))
            if basemap_key:
                record.update({"kind": "basemap", "basemap_key": basemap_key})
                layer_records.append(record)
                continue

            source = str(layer.source() or "")
            primary_source = Path(source.split("|", 1)[0]).expanduser()
            suffix = primary_source.suffix.lower()
            if not primary_source.is_file() or suffix not in supported:
                warnings.append(tr("sgd.warning_layer_skipped", name=layer.name()))
                continue
            layer_id = self._safe_layer_id(layer.id(), index)
            source_key = str(primary_source.resolve())
            archive_primary = packaged_sources.get(source_key)
            if archive_primary is None:
                archive_dir = f"layers/{index:03d}-{layer_id}"
                archive_primary = f"{archive_dir}/{primary_source.name}"
                packaged_sources[source_key] = archive_primary
                companion_files = [primary_source]
                if suffix == ".shp":
                    companion_files = sorted(
                        primary_source.parent.glob(f"{primary_source.stem}.*")
                    )
                else:
                    for extra in (
                        Path(f"{primary_source}.aux.xml"),
                        Path(f"{primary_source}.ovr"),
                    ):
                        if extra.is_file():
                            companion_files.append(extra)
                for companion in companion_files:
                    assets.append(
                        ArchiveAsset(
                            str(companion), f"{archive_dir}/{companion.name}"
                        )
                    )
            kind = "vector" if isinstance(layer, QgsVectorLayer) else "raster"
            record.update(
                {
                    "kind": kind,
                    "provider": str(layer.providerType()),
                    "archive_primary": archive_primary,
                    "source_suffix": self._portable_source_suffix(source),
                }
            )
            try:
                opacity = (
                    layer.opacity()
                    if isinstance(layer, QgsVectorLayer)
                    else layer.renderer().opacity()
                )
                record["opacity"] = float(opacity)
            except (AttributeError, TypeError):
                pass
            style_path = staging_root / f"{index:03d}-{layer_id}.qml"
            try:
                layer.saveNamedStyle(str(style_path))
                if style_path.is_file():
                    style_archive = f"styles/{index:03d}-{layer_id}.qml"
                    assets.append(ArchiveAsset(str(style_path), style_archive))
                    record["style_path"] = style_archive
            except (AttributeError, RuntimeError):
                pass
            layer_records.append(record)

        try:
            destination_crs = self.canvas.mapSettings().destinationCrs()
            transform = QgsCoordinateTransform(
                destination_crs,
                QgsCoordinateReferenceSystem("EPSG:4326"),
                self.project,
            )
            geographic_extent = transform.transformBoundingBox(self.canvas.extent())
            extent = [
                geographic_extent.xMinimum(),
                geographic_extent.yMinimum(),
                geographic_extent.xMaximum(),
                geographic_extent.yMaximum(),
            ]
            crs = destination_crs.authid()
        except Exception:
            extent = []
            crs = "EPSG:3857"
        return (
            {
                "canvas": {"crs": crs, "extent_wgs84": extent},
                "layers": layer_records,
                "warnings": warnings,
            },
            assets,
        )

    def _load_sgd_path(self, path: str) -> bool:
        extraction = TemporaryDirectory(prefix="sakugis-open-")
        try:
            loaded = load_sgd(path, extraction.name)
        except (OSError, SgdError, ValueError) as exc:
            extraction.cleanup()
            QMessageBox.critical(
                self,
                tr("dialog.project_open_failed"),
                tr("dialog.sgd_open_failed_detail", error=str(exc)),
            )
            return False

        self._restoring_sgd = True
        try:
            self.project.clear()
            self._release_sgd_extraction()
            self._sgd_extraction = extraction
            self._last_analysis_result = loaded.result
            self._candidates_by_id = {}
            self.place_details_panel.clear_case()
            self._restore_sgd_map_state(loaded.map_state, loaded.extraction_root)
            self.place_details_panel.restore_archive(
                loaded.place_details, loaded.extraction_root
            )
            self.agent_panel.restore_session(
                loaded.query, loaded.image_paths, loaded.result
            )
            if loaded.result is not None:
                self.show_agent_result(loaded.result)
            else:
                self.export_report_action.setEnabled(False)
            self._restore_sgd_canvas(loaded.map_state)
            self._sgd_path = str(Path(path).resolve())
            self._sgd_dirty = False
            self.project.setDirty(False)
        except Exception as exc:
            self.project.clear()
            self._release_sgd_extraction()
            QMessageBox.critical(
                self,
                tr("dialog.project_open_failed"),
                tr("dialog.sgd_open_failed_detail", error=str(exc)),
            )
            return False
        finally:
            self._restoring_sgd = False
        self.setWindowTitle(f"SakuGIS — {Path(path).name}")
        self._hide_welcome()
        self._refresh_attribution()
        self.canvas.refresh()
        warning_count = len(loaded.warnings)
        if warning_count:
            QMessageBox.information(
                self,
                tr("sgd.warning_title"),
                "\n".join(loaded.warnings),
            )
        self.statusBar().showMessage(tr("status.project_loaded"), 4000)
        return True

    def _restore_sgd_map_state(self, map_state: dict, root_path: Path) -> None:
        root = self.project.layerTreeRoot()
        for record in map_state.get("layers") or []:
            if not isinstance(record, dict):
                continue
            layer = None
            kind = str(record.get("kind") or "")
            if kind == "basemap":
                key = str(record.get("basemap_key") or "")
                if key == OSM.key:
                    self.add_osm_basemap()
                elif key == GOOGLE_SATELLITE.key:
                    self.add_google_satellite()
                layer = next(
                    (
                        item
                        for item in self.project.mapLayers().values()
                        if item.customProperty("sakugis/basemap-key") == key
                    ),
                    None,
                )
            else:
                if kind not in {"vector", "raster"}:
                    continue
                archive_primary = str(record.get("archive_primary") or "")
                if not archive_primary:
                    continue
                source_path = self._sgd_member_path(root_path, archive_primary)
                source = str(source_path) + self._portable_source_suffix(
                    str(record.get("source_suffix") or "")
                )
                name = str(record.get("name") or source_path.stem)
                if kind == "vector":
                    layer = QgsVectorLayer(source, name, "ogr")
                else:
                    layer = QgsRasterLayer(source, name, "gdal")
                if not layer.isValid():
                    continue
                self.project.addMapLayer(layer, False)
                root.addLayer(layer)
                style_path = str(record.get("style_path") or "")
                if style_path:
                    layer.loadNamedStyle(
                        str(self._sgd_member_path(root_path, style_path))
                    )
                try:
                    opacity = float(record.get("opacity", 1.0))
                    if isinstance(layer, QgsVectorLayer):
                        layer.setOpacity(opacity)
                    else:
                        layer.renderer().setOpacity(opacity)
                except (AttributeError, TypeError, ValueError):
                    pass
            if layer is not None:
                node = root.findLayer(layer.id())
                if node is not None:
                    node.setItemVisibilityChecked(bool(record.get("visible", True)))

    @staticmethod
    def _sgd_member_path(root_path: Path, archive_path: str) -> Path:
        member = PurePosixPath(archive_path)
        if (
            not archive_path
            or "\\" in archive_path
            or member.is_absolute()
            or any(part in {"", ".", ".."} for part in member.parts)
        ):
            raise ValueError("Invalid path in SGD map state.")
        return root_path.joinpath(*member.parts)

    def _restore_sgd_canvas(self, map_state: dict) -> None:
        canvas_state = map_state.get("canvas") or {}
        extent = canvas_state.get("extent_wgs84") or []
        crs = QgsCoordinateReferenceSystem(str(canvas_state.get("crs") or "EPSG:3857"))
        if crs.isValid():
            self.canvas.setDestinationCrs(crs)
        if len(extent) != 4:
            return
        transform = QgsCoordinateTransform(
            QgsCoordinateReferenceSystem("EPSG:4326"),
            self.canvas.mapSettings().destinationCrs(),
            self.project,
        )
        self.canvas.setExtent(
            transform.transformBoundingBox(QgsRectangle(*[float(item) for item in extent]))
        )

    def _release_sgd_extraction(self) -> None:
        extraction = self._sgd_extraction
        self._sgd_extraction = None
        if extraction is not None:
            extraction.cleanup()

    def export_report(self, checked: bool = False) -> bool:
        result = self._last_analysis_result
        if result is None:
            QMessageBox.information(
                self,
                tr("dialog.export_report"),
                tr("dialog.no_report"),
            )
            return False
        top_name = result.candidates[0].name if result.candidates else "result"
        safe_name = re.sub(r"[^\w\u3400-\u9fff.-]+", "-", top_name).strip("-")
        timestamp = datetime.now().strftime("%Y%m%d-%H%M")
        suggested = Path.home() / f"SakuGIS-{safe_name or 'result'}-{timestamp}.md"
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("dialog.export_report"),
            str(suggested),
            tr("dialog.report_filter"),
        )
        if not path:
            return False
        if Path(path).suffix.lower() != ".md":
            path += ".md"
        try:
            destination = write_markdown_report(path, result)
        except OSError as exc:
            QMessageBox.critical(
                self,
                tr("dialog.report_failed"),
                tr("dialog.report_failed_detail", error=str(exc)),
            )
            return False
        self.statusBar().showMessage(
            tr("status.report_saved", path=str(destination)),
            6000,
        )
        return True

    def remove_selected_layers(self) -> None:
        layers = self.layer_panel.selected_layers()
        if not layers:
            layer = self.layer_panel.current_layer()
            layers = [layer] if layer else []
        for layer in layers:
            self.project.removeMapLayer(layer.id())
        self._refresh_attribution()

    def _update_vector_actions(self, layer=None) -> None:
        if not hasattr(self, "layer_style_action"):
            return
        is_vector = isinstance(layer, QgsVectorLayer)
        styleable = is_vector and layer.geometryType() in {
            QgsWkbTypes.PointGeometry,
            QgsWkbTypes.LineGeometry,
            QgsWkbTypes.PolygonGeometry,
        }
        self.layer_style_action.setEnabled(styleable)
        self.attribute_table_action.setEnabled(is_vector)

    def open_layer_style(self, layer=None) -> None:
        if not isinstance(layer, QgsVectorLayer):
            layer = self.layer_panel.current_layer()
        if not isinstance(layer, QgsVectorLayer):
            QMessageBox.information(
                self,
                tr("style.vector_required_title"),
                tr("style.vector_required"),
            )
            return
        if layer.geometryType() not in {
            QgsWkbTypes.PointGeometry,
            QgsWkbTypes.LineGeometry,
            QgsWkbTypes.PolygonGeometry,
        }:
            QMessageBox.information(
                self,
                tr("style.vector_required_title"),
                tr("style.geometry_required"),
            )
            return
        renderer = layer.renderer()
        renderer_before = renderer.dump() if renderer is not None else ""
        dialog = create_layer_style_dialog(layer, self.canvas, self)
        accepted = bool(dialog.exec_())
        renderer = layer.renderer()
        renderer_after = renderer.dump() if renderer is not None else ""
        if not accepted and renderer_before == renderer_after:
            return

        node = self.project.layerTreeRoot().findLayer(layer.id())
        if node is not None:
            self.layer_panel.model.refreshLayerLegend(node)
        self.project.setDirty(True)
        self._mark_sgd_dirty()
        layer.triggerRepaint()
        self.canvas.refresh()
        self.statusBar().showMessage(
            tr("status.layer_style_applied", name=layer.name()), 4000
        )

    def open_attribute_table(self, layer=None) -> None:
        if not isinstance(layer, QgsVectorLayer):
            layer = self.layer_panel.current_layer()
        if not isinstance(layer, QgsVectorLayer):
            QMessageBox.information(
                self,
                tr("attribute.vector_required_title"),
                tr("attribute.vector_required"),
            )
            return
        AttributeTableDialog(layer, self.canvas, self).exec_()

    def export_map(self, checked: bool = False) -> bool:
        if not self.canvas.layers():
            QMessageBox.information(
                self,
                tr("map_export.empty_title"),
                tr("map_export.empty"),
            )
            return False
        project_title = Path(
            self._sgd_path or self.project.fileName() or ""
        ).stem
        dialog = MapExportDialog(project_title or tr("map_export.default_title"), self)
        if not dialog.exec_():
            return False
        options = dialog.options()
        if options.file_format == "pdf":
            file_filter = tr("map_export.pdf_filter")
            suffix = ".pdf"
        else:
            file_filter = tr("map_export.png_filter")
            suffix = ".png"
        safe_title = re.sub(r"[^\w.-]+", "-", options.title).strip("-.")
        suggested = Path.home() / f"{safe_title or 'SakuGIS-map'}{suffix}"
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("map_export.save_title"),
            str(suggested),
            file_filter,
        )
        if not path:
            return False
        try:
            destination, google_excluded = export_map_layout(
                self.project, self.canvas, path, options
            )
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.critical(
                self,
                tr("map_export.failed_title"),
                tr("map_export.failed", error=str(exc)),
            )
            return False
        detail = tr("status.map_exported", path=str(destination))
        if google_excluded:
            detail += " · " + tr("map_export.google_excluded")
        self.statusBar().showMessage(detail, 8000)
        return True

    def zoom_to_current_layer(self) -> None:
        layer = self.layer_panel.current_layer()
        if layer:
            self.zoom_to_layer(layer)

    def zoom_to_layer(self, layer) -> None:
        extent = layer.extent()
        if extent.isEmpty():
            return
        try:
            transform = QgsCoordinateTransform(
                layer.crs(), self.canvas.mapSettings().destinationCrs(), self.project
            )
            extent = transform.transformBoundingBox(extent)
        except Exception:
            pass
        self.canvas.setExtent(extent)
        self.canvas.refresh()

    def show_agent_result(self, result: GeoAnalysisResult) -> None:
        self._mark_sgd_dirty()
        self._last_analysis_result = result
        self._candidates_by_id = {
            candidate.candidate_id: candidate
            for candidate in result.candidates
        }
        self.export_report_action.setEnabled(True)
        self._hide_welcome()
        root = self.project.layerTreeRoot()
        for layer in list(self.project.mapLayers().values()):
            if layer.customProperty("sakugis/agent-result"):
                self.project.removeMapLayer(layer.id())
        for child in list(root.children()):
            if (
                isinstance(child, QgsLayerTreeGroup)
                and child.customProperty("sakugis/agent-result-group")
            ):
                root.removeChildNode(child)

        range_layer = QgsVectorLayer(
            "Polygon?crs=EPSG:3857", tr("agent.layer_ranges"), "memory"
        )
        range_provider = range_layer.dataProvider()
        range_provider.addAttributes(
            [
                QgsField("rank", QVariant.Int),
                QgsField("name", QVariant.String),
                QgsField("score", QVariant.Double),
                QgsField("radius_km", QVariant.Double),
            ]
        )
        range_layer.updateFields()

        to_web_mercator = QgsCoordinateTransform(
            QgsCoordinateReferenceSystem("EPSG:4326"),
            QgsCoordinateReferenceSystem("EPSG:3857"),
            self.project,
        )
        candidate_layers = []
        range_features = []
        for rank, candidate in enumerate(result.candidates, 1):
            score = round(candidate.ranking_score * 100, 1)
            gis_score = round(candidate.gis_score * 100, 1)
            coverage = round(candidate.gis_coverage * 100, 1)
            layer_name = tr(
                "agent.layer_item",
                rank=rank,
                name=candidate.name,
                score=f"{score:g}",
                gis=f"{gis_score:g}",
                coverage=f"{coverage:g}",
            )
            candidate_layer = QgsVectorLayer(
                "Point?crs=EPSG:4326", layer_name, "memory"
            )
            candidate_provider = candidate_layer.dataProvider()
            candidate_provider.addAttributes(
                [
                    QgsField("rank", QVariant.Int),
                    QgsField("name", QVariant.String),
                    QgsField("country", QVariant.String),
                    QgsField("country_code", QVariant.String),
                    QgsField("score", QVariant.Double),
                    QgsField("gis_score", QVariant.Double),
                    QgsField("gis_coverage", QVariant.Double),
                    QgsField("radius_km", QVariant.Double),
                    QgsField("reverse_label", QVariant.String),
                    QgsField("rationale", QVariant.String),
                ]
            )
            candidate_layer.updateFields()
            point_feature = QgsFeature(candidate_layer.fields())
            point_feature.setGeometry(
                QgsGeometry.fromPointXY(
                    QgsPointXY(candidate.longitude, candidate.latitude)
                )
            )
            point_feature.setAttributes(
                [
                    rank,
                    candidate.name,
                    candidate.country,
                    candidate.country_code,
                    score,
                    gis_score,
                    coverage,
                    candidate.radius_km,
                    candidate.reverse_label,
                    candidate.rationale,
                ]
            )
            candidate_provider.addFeature(point_feature)
            candidate_layer.updateExtents()
            candidate_layer.renderer().setSymbol(
                QgsMarkerSymbol.createSimple(
                    {
                        "name": "circle",
                        "color": "#ff4f81",
                        "outline_color": "#ffffff",
                        "outline_width": "0.8",
                        "size": "5.5",
                    }
                )
            )
            candidate_layer.setCustomProperty(
                "sakugis/agent-result", True
            )
            candidate_layer.setCustomProperty(
                "sakugis/candidate-layer", True
            )
            candidate_layer.setCustomProperty(
                "sakugis/candidate-id", candidate.candidate_id
            )
            candidate_layer.setCustomProperty(
                "sakugis/candidate-name", candidate.name
            )
            candidate_layer.setCustomProperty(
                "sakugis/candidate-latitude", candidate.latitude
            )
            candidate_layer.setCustomProperty(
                "sakugis/candidate-longitude", candidate.longitude
            )
            candidate_layer.setCustomProperty(
                "sakugis/candidate-radius-km", candidate.radius_km
            )
            candidate_layer.setCustomProperty(
                "sakugis/candidate-score", score
            )
            candidate_layer.setCustomProperty(
                "sakugis/candidate-gis-score", gis_score
            )
            candidate_layer.setCustomProperty(
                "sakugis/candidate-coverage", coverage
            )
            candidate_layer.setCustomProperty(
                "sakugis/confidence-status", result.confidence_status
            )
            candidate_layer.setCustomProperty(
                "sakugis/attribution", OSM.attribution_html
            )
            candidate_layers.append(candidate_layer)

            projected = to_web_mercator.transform(
                QgsPointXY(candidate.longitude, candidate.latitude)
            )
            range_feature = QgsFeature(range_layer.fields())
            range_feature.setGeometry(
                QgsGeometry.fromPointXY(projected).buffer(
                    candidate.radius_km * 1000.0, 48
                )
            )
            range_feature.setAttributes(
                [
                    rank,
                    candidate.name,
                    round(candidate.ranking_score * 100, 1),
                    candidate.radius_km,
                ]
            )
            range_features.append(range_feature)

        range_provider.addFeatures(range_features)
        range_layer.updateExtents()

        range_symbol = QgsFillSymbol.createSimple(
            {
                "color": "255,79,129,28",
                "outline_color": "255,79,129,145",
                "outline_width": "0.7",
            }
        )
        range_layer.renderer().setSymbol(range_symbol)

        range_layer.setCustomProperty("sakugis/agent-result", True)
        range_layer.setCustomProperty(
            "sakugis/confidence-status", result.confidence_status
        )
        range_layer.setCustomProperty(
            "sakugis/attribution", OSM.attribution_html
        )

        candidate_group = root.insertGroup(
            0, tr("agent.layer_group", count=len(candidate_layers))
        )
        candidate_group.setCustomProperty(
            "sakugis/agent-result-group", True
        )
        candidate_group.setExpanded(True)
        for candidate_layer in candidate_layers:
            self.project.addMapLayer(candidate_layer, False)
            candidate_group.addLayer(candidate_layer)
        self.project.addMapLayer(range_layer, False)
        root.insertLayer(1, range_layer)
        if result.candidates:
            self._zoom_to_candidate_set(result.candidates)
        self.statusBar().showMessage(
            tr("status.agent_layers", count=len(result.candidates)),
            6000,
        )
        self._refresh_attribution()

    def _zoom_to_candidate_layer(self, layer) -> None:
        candidate_id = str(
            layer.customProperty("sakugis/candidate-id", "")
        )
        candidate = self._candidates_by_id.get(candidate_id)
        if candidate is not None:
            self.agent_panel.select_candidate(candidate)
        try:
            latitude = float(
                layer.customProperty("sakugis/candidate-latitude")
            )
            longitude = float(
                layer.customProperty("sakugis/candidate-longitude")
            )
            radius_km = float(
                layer.customProperty("sakugis/candidate-radius-km", 10.0)
            )
        except (TypeError, ValueError):
            return
        destination = self.canvas.mapSettings().destinationCrs()
        transform = QgsCoordinateTransform(
            QgsCoordinateReferenceSystem("EPSG:4326"),
            destination,
            self.project,
        )
        point = transform.transform(QgsPointXY(longitude, latitude))
        radius = max(radius_km * 1000.0, 5000.0)
        self.canvas.setExtent(
            QgsRectangle(
                point.x() - radius,
                point.y() - radius,
                point.x() + radius,
                point.y() + radius,
            )
        )
        self.canvas.refresh()
        self.statusBar().showMessage(
            tr(
                "status.candidate_selected",
                name=layer.customProperty("sakugis/candidate-name"),
                score=f"{float(layer.customProperty('sakugis/candidate-score', 0)):g}",
                gis=f"{float(layer.customProperty('sakugis/candidate-gis-score', 0)):g}",
                coverage=f"{float(layer.customProperty('sakugis/candidate-coverage', 0)):g}",
            ),
            5000,
        )

    def _zoom_to_candidate_set(self, candidates) -> None:
        destination = self.canvas.mapSettings().destinationCrs()
        transform = QgsCoordinateTransform(
            QgsCoordinateReferenceSystem("EPSG:4326"),
            destination,
            self.project,
        )
        points = [
            transform.transform(QgsPointXY(item.longitude, item.latitude))
            for item in candidates
        ]
        if not points:
            return
        extent = QgsRectangle(
            min(point.x() for point in points),
            min(point.y() for point in points),
            max(point.x() for point in points),
            max(point.y() for point in points),
        )
        if len(points) == 1 or extent.isEmpty():
            radius = max(candidates[0].radius_km * 1000.0, 20000.0)
            point = points[0]
            extent = QgsRectangle(
                point.x() - radius,
                point.y() - radius,
                point.x() + radius,
                point.y() + radius,
            )
        else:
            extent.grow(max(extent.width(), extent.height()) * 0.12)
        self.canvas.setExtent(extent)
        self.canvas.refresh()

    def zoom_to_candidate(self, candidate: Candidate) -> None:
        destination = self.canvas.mapSettings().destinationCrs()
        transform = QgsCoordinateTransform(
            QgsCoordinateReferenceSystem("EPSG:4326"),
            destination,
            self.project,
        )
        point = transform.transform(
            QgsPointXY(candidate.longitude, candidate.latitude)
        )
        radius = max(candidate.radius_km * 1000.0, 5000.0)
        self.canvas.setExtent(
            QgsRectangle(
                point.x() - radius,
                point.y() - radius,
                point.x() + radius,
                point.y() + radius,
            )
        )
        self.canvas.refresh()

    def _activate_candidate(self, candidate: Candidate) -> None:
        self.zoom_to_candidate(candidate)

    def show_candidate_details(self, candidate: Candidate) -> None:
        if not isinstance(candidate, Candidate):
            return
        if self.place_details_dock.isVisible():
            self._save_place_details_geometry()
        self._place_details_available = False
        self.place_details_dock.toggleViewAction().setEnabled(False)
        self.place_details_dock.hide()
        self.statusBar().showMessage(tr("place.checking"), 5000)
        self.place_details_panel.set_candidate(candidate)

    def _on_place_details_available(self, candidate: Candidate) -> None:
        current = self.place_details_panel.current_candidate()
        if (
            current is None
            or current.candidate_id != candidate.candidate_id
        ):
            return
        self._place_details_available = True
        action = self.place_details_dock.toggleViewAction()
        action.setEnabled(True)
        settings = QgsSettings()
        floating = _setting_bool(
            settings.value(
                "sakugis/ui/place-details-floating",
                True,
            ),
            True,
        )
        self.place_details_dock.setFloating(floating)
        if floating:
            geometry = settings.value(
                "sakugis/ui/place-details-geometry"
            )
            restored = False
            if geometry:
                try:
                    restored = bool(
                        self.place_details_dock.restoreGeometry(geometry)
                    )
                except (TypeError, ValueError):
                    restored = False
            if not restored:
                width, height = 760, 500
                self.place_details_dock.resize(width, height)
                self.place_details_dock.move(
                    self.mapToGlobal(
                        QPoint(
                            max(24, (self.width() - width) // 2),
                            max(64, (self.height() - height) // 2),
                        )
                    )
                )
        else:
            self.resizeDocks(
                [self.place_details_dock],
                [320],
                Qt.Vertical,
            )
        self.place_details_dock.show()
        self.place_details_dock.raise_()
        self.statusBar().showMessage(tr("place.available"), 3500)

    def _on_place_details_unavailable(
        self, candidate: Candidate, reason: str
    ) -> None:
        current = self.place_details_panel.current_candidate()
        if (
            current is None
            or current.candidate_id != candidate.candidate_id
        ):
            return
        self._place_details_available = False
        self.place_details_dock.toggleViewAction().setEnabled(False)
        self.place_details_dock.hide()
        key = {
            "gis_identity": "place.hidden.gis_identity",
            "no_material": "place.hidden.no_material",
            "key_missing": "place.hidden.key_missing",
            "local_only": "place.hidden.local_only",
        }.get(reason, "place.hidden.search_failed")
        self.statusBar().showMessage(tr(key), 6000)

    def _place_details_top_level_changed(self, floating: bool) -> None:
        if floating:
            self.place_details_dock.setMinimumSize(620, 400)
        else:
            self.place_details_dock.setMinimumSize(440, 260)
        QgsSettings().setValue(
            "sakugis/ui/place-details-floating",
            bool(floating),
        )

    def _place_details_visibility_changed(self, visible: bool) -> None:
        if not visible:
            self._save_place_details_geometry()

    def _save_place_details_geometry(self) -> None:
        if self.place_details_dock.isFloating():
            QgsSettings().setValue(
                "sakugis/ui/place-details-geometry",
                self.place_details_dock.saveGeometry(),
            )

    def _select_candidate_at_map_point(self, point) -> None:
        candidate = self._nearest_candidate(point)
        if candidate is None:
            return
        self.agent_panel.select_candidate(candidate)

    def _nearest_candidate(self, point) -> Optional[Candidate]:
        if not self._candidates_by_id:
            return None
        transform = QgsCoordinateTransform(
            QgsCoordinateReferenceSystem("EPSG:4326"),
            self.canvas.mapSettings().destinationCrs(),
            self.project,
        )
        tolerance = max(self.canvas.mapUnitsPerPixel() * 14.0, 1.0)
        nearest = None
        nearest_distance = tolerance
        for candidate in self._candidates_by_id.values():
            projected = transform.transform(
                QgsPointXY(candidate.longitude, candidate.latitude)
            )
            dx = projected.x() - point.x()
            dy = projected.y() - point.y()
            distance = (dx * dx + dy * dy) ** 0.5
            if distance <= nearest_distance:
                nearest = candidate
                nearest_distance = distance
        return nearest

    def _refresh_attribution(self) -> None:
        attributions = []
        root = self.project.layerTreeRoot()
        for layer in self.project.mapLayers().values():
            node = root.findLayer(layer.id())
            if isinstance(node, QgsLayerTreeLayer) and node.isVisible():
                attribution = layer.customProperty("sakugis/attribution")
                if attribution:
                    attributions.append(attribution)
        self.attribution_status.setText(" · ".join(dict.fromkeys(attributions)))

    def show_about(self) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle(tr("about.title"))
        box.setTextFormat(Qt.RichText)
        box.setText(tr("about.body"))
        check_button = box.addButton(
            tr("update.check_button"), QMessageBox.ActionRole
        )
        close_button = box.addButton(
            tr("update.close_button"), QMessageBox.RejectRole
        )
        box.setDefaultButton(close_button)
        box.exec_()
        if box.clickedButton() is check_button:
            self.check_for_updates()

    def check_for_updates(self) -> None:
        if self._update_thread and self._update_thread.isRunning():
            self.statusBar().showMessage(tr("update.checking"), 3000)
            return

        self.statusBar().showMessage(tr("update.checking"), 0)
        thread = QThread(self)
        worker = UpdateCheckWorker()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.resultReady.connect(self._show_update_result)
        worker.failed.connect(self._show_update_error)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._update_check_finished)
        self._update_thread = thread
        self._update_worker = worker
        thread.start()

    def _update_check_finished(self) -> None:
        self._update_thread = None
        self._update_worker = None

    def _show_update_result(self, status: UpdateStatus) -> None:
        if self._shutting_down:
            return
        self.statusBar().clearMessage()
        if not status.update_available:
            QMessageBox.information(
                self,
                tr("update.current_title"),
                tr("update.current_detail", version=__version__),
            )
            return

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle(tr("update.available_title"))
        box.setText(
            tr(
                "update.available_detail",
                current=__version__,
                latest=status.latest_version,
            )
        )
        download_button = None
        if status.download_url:
            download_button = box.addButton(
                tr("update.download_button"), QMessageBox.AcceptRole
            )
        notes_button = box.addButton(
            tr("update.notes_button"), QMessageBox.ActionRole
        )
        later_button = box.addButton(
            tr("update.later_button"), QMessageBox.RejectRole
        )
        box.setDefaultButton(download_button or notes_button)
        box.exec_()
        clicked = box.clickedButton()
        if download_button is not None and clicked is download_button:
            QDesktopServices.openUrl(QUrl(status.download_url))
        elif clicked is notes_button and status.release_url:
            QDesktopServices.openUrl(QUrl(status.release_url))
        elif clicked is later_button:
            return

    def _show_update_error(self, _detail: str) -> None:
        if self._shutting_down:
            return
        self.statusBar().clearMessage()
        QMessageBox.warning(
            self,
            tr("update.error_title"),
            tr("update.error_detail"),
        )

    def _confirm_discard_changes(self) -> bool:
        if not self._sgd_dirty and not self.project.isDirty():
            return True
        layers = list(self.project.mapLayers().values())
        only_automatic_osm = (
            not self._sgd_dirty
            and not self.project.fileName()
            and bool(layers)
            and all(
                layer.customProperty("sakugis/basemap-key") == OSM.key
                for layer in layers
            )
        )
        if only_automatic_osm:
            return True

        choice = QMessageBox.warning(
            self,
            tr("dialog.unsaved"),
            tr("dialog.unsaved_question"),
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )
        if choice == QMessageBox.Save:
            return self.save_project()
        if choice == QMessageBox.Discard:
            return True
        return False

    def closeEvent(self, event) -> None:
        if self.agent_panel.is_busy():
            QMessageBox.information(
                self,
                tr("dialog.agent_busy"),
                tr("dialog.agent_busy_detail"),
            )
            event.ignore()
            return
        if self._confirm_discard_changes():
            self.prepare_for_shutdown()
            event.accept()
        else:
            event.ignore()

    def prepare_for_shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        update_thread = self._update_thread
        if update_thread and update_thread.isRunning():
            update_thread.quit()
            update_thread.wait(9000)
        self._save_place_details_geometry()
        self.place_details_panel.shutdown()
        self._release_sgd_extraction()
        try:
            self.project.layerTreeRoot().visibilityChanged.disconnect(
                self._visibility_slot
            )
        except (TypeError, RuntimeError):
            pass
        for signal, slot in (
            (self.project.layersAdded, self._project_layers_changed),
            (self.project.layersRemoved, self._project_layers_changed),
        ):
            try:
                signal.disconnect(slot)
            except (TypeError, RuntimeError):
                pass
        try:
            self.canvas.stopRendering()
            self.canvas.freeze(True)
            self.canvas.setLayers([])
        except RuntimeError:
            pass
