"""Main SakuGIS window."""

from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import re
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
from sakugis.i18n import EN, ZH_CN, get_language, set_language, tr
from sakugis.layer_panel import LayerPanel
from sakugis.map_defaults import choose_startup_city
from sakugis.place_details_panel import PlaceDetailsPanel
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
        self.layer_panel.candidateLayerActivated.connect(
            self._zoom_to_candidate_layer
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
        self.canvas.renderStarting.connect(
            lambda: self.render_status.setText(tr("status.rendering"))
        )
        self.canvas.renderComplete.connect(
            lambda _: self.render_status.setText(tr("status.ready"))
        )

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
            self.add_osm_basemap()
            # The layer-tree bridge may apply the global XYZ extent on the
            # next event-loop turn, so restore this launch's city afterwards.
            QTimer.singleShot(150, self._set_initial_extent)
            if not self.project.fileName():
                self.project.setDirty(False)

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

        self.project.clear()
        if not self.project.read(path):
            QMessageBox.critical(
                self,
                tr("dialog.project_open_failed"),
                tr("dialog.project_open_failed_detail", path=path),
            )
            return False
        self.setWindowTitle(f"SakuGIS — {Path(path).name}")
        self._hide_welcome()
        self._refresh_attribution()
        self.canvas.refresh()
        return True

    def save_project(self, checked: bool = False, save_as: bool = False) -> bool:
        current = self.project.fileName()
        if current and not save_as:
            if self.project.write():
                self.statusBar().showMessage(tr("status.project_saved"), 3000)
                return True
            QMessageBox.critical(
                self,
                tr("dialog.save_failed"),
                tr("dialog.save_failed_detail", path=current),
            )
            return False

        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("dialog.save_project"),
            current or str(Path.home() / tr("dialog.untitled")),
            tr("dialog.project_filter"),
        )
        if not path:
            return False

        if not Path(path).suffix:
            path += ".qgz"
        if not self.project.write(path):
            QMessageBox.critical(
                self,
                tr("dialog.save_failed"),
                tr("dialog.save_failed_detail", path=path),
            )
            return False
        self.setWindowTitle(f"SakuGIS — {Path(path).name}")
        self.statusBar().showMessage(tr("status.project_saved"), 3000)
        return True

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
        if not self.project.isDirty():
            return True
        layers = list(self.project.mapLayers().values())
        only_automatic_osm = (
            not self.project.fileName()
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
