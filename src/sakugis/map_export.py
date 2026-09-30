"""Simple A4 map composition and export for SakuGIS."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import getpass
from pathlib import Path

from qgis.PyQt.QtGui import QColor, QFont
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)
from qgis.core import (
    QgsApplication,
    QgsLayoutExporter,
    QgsLayoutItemLabel,
    QgsLayoutItemLegend,
    QgsLayoutItemMap,
    QgsLayoutItemPicture,
    QgsLayoutItemScaleBar,
    QgsLayoutPoint,
    QgsLayoutSize,
    QgsPrintLayout,
    QgsProject,
    QgsUnitTypes,
)

from sakugis.i18n import tr
from sakugis import __version__


GOOGLE_BASEMAP_KEY = "google-satellite-custom-xyz"


@dataclass(frozen=True)
class MapExportOptions:
    title: str
    subtitle: str
    creator: str
    file_format: str
    dpi: int


class MapExportDialog(QDialog):
    def __init__(self, default_title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("map_export.title"))
        self.resize(520, 300)

        self.title_edit = QLineEdit(default_title, self)
        self.subtitle_edit = QLineEdit(tr("map_export.default_subtitle"), self)
        self.creator_edit = QLineEdit(getpass.getuser(), self)
        self.format_combo = QComboBox(self)
        self.format_combo.addItem("PDF", "pdf")
        self.format_combo.addItem("PNG", "png")
        self.dpi_spin = QSpinBox(self)
        self.dpi_spin.setRange(96, 600)
        self.dpi_spin.setValue(300)
        self.dpi_spin.setSuffix(" dpi")

        form = QFormLayout()
        form.setVerticalSpacing(12)
        form.addRow(tr("map_export.map_title"), self.title_edit)
        form.addRow(tr("map_export.subtitle"), self.subtitle_edit)
        form.addRow(tr("map_export.creator"), self.creator_edit)
        form.addRow(tr("map_export.format"), self.format_combo)
        form.addRow(tr("map_export.resolution"), self.dpi_spin)

        note = QLabel(tr("map_export.note"), self)
        note.setObjectName("MutedLabel")
        note.setWordWrap(True)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self
        )
        buttons.button(QDialogButtonBox.Ok).setText(tr("map_export.continue"))
        buttons.button(QDialogButtonBox.Cancel).setText(tr("map_export.cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(14)
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addStretch(1)
        layout.addWidget(buttons)

    def options(self) -> MapExportOptions:
        return MapExportOptions(
            title=self.title_edit.text().strip() or "SakuGIS Map",
            subtitle=self.subtitle_edit.text().strip(),
            creator=self.creator_edit.text().strip() or getpass.getuser(),
            file_format=str(self.format_combo.currentData()),
            dpi=self.dpi_spin.value(),
        )


def _add_label(
    layout,
    text: str,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    point_size: int = 8,
    bold: bool = False,
    frame: bool = False,
):
    label = QgsLayoutItemLabel(layout)
    label.setText(text)
    label.setFont(
        QFont("Avenir Next", point_size, QFont.Bold if bold else QFont.Normal)
    )
    label.setFrameEnabled(frame)
    label.setMarginX(1.2 if frame else 0)
    label.setMarginY(0.7 if frame else 0)
    layout.addLayoutItem(label)
    label.attemptResize(
        QgsLayoutSize(width, height, QgsUnitTypes.LayoutMillimeters)
    )
    label.attemptMove(
        QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters)
    )
    return label


def _north_arrow_path() -> str:
    relative = Path("arrows") / "NorthArrow_02.svg"
    candidates = [Path(QgsApplication.pkgDataPath()) / "svg" / relative]
    candidates.extend(Path(root) / relative for root in QgsApplication.svgPaths())
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return ""


def export_map_layout(
    project: QgsProject,
    canvas,
    destination: str,
    options: MapExportOptions,
) -> tuple[Path, bool]:
    """Export the current canvas extent as an A4 landscape PDF or PNG."""

    output = Path(destination).expanduser()
    suffix = ".pdf" if options.file_format == "pdf" else ".png"
    if output.suffix.lower() != suffix:
        output = output.with_suffix(suffix)
    output.parent.mkdir(parents=True, exist_ok=True)

    visible_layers = list(canvas.layers())
    google_excluded = any(
        layer.customProperty("sakugis/basemap-key") == GOOGLE_BASEMAP_KEY
        for layer in visible_layers
    )
    export_layers = [
        layer
        for layer in visible_layers
        if layer.customProperty("sakugis/basemap-key") != GOOGLE_BASEMAP_KEY
    ]
    if not export_layers:
        raise ValueError(tr("map_export.no_exportable_layers"))

    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    layout.setName("SakuGIS Export")
    page = layout.pageCollection().page(0)
    page.setPageSize(
        QgsLayoutSize(297, 210, QgsUnitTypes.LayoutMillimeters)
    )

    map_item = QgsLayoutItemMap(layout)
    layout.addLayoutItem(map_item)
    map_item.attemptMove(
        QgsLayoutPoint(10, 10, QgsUnitTypes.LayoutMillimeters)
    )
    map_item.attemptResize(
        QgsLayoutSize(217, 158, QgsUnitTypes.LayoutMillimeters)
    )
    map_item.setCrs(canvas.mapSettings().destinationCrs())
    map_item.setExtent(canvas.extent())
    map_item.setLayers(export_layers)
    map_item.setKeepLayerSet(True)
    map_item.setFrameEnabled(True)
    map_item.invalidateCache()
    layout.setReferenceMap(map_item)

    legend = QgsLayoutItemLegend(layout)
    legend.setTitle(tr("map_export.legend"))
    legend.setLinkedMap(map_item)
    legend.setResizeToContents(False)
    legend.setFrameEnabled(True)
    layout.addLayoutItem(legend)
    legend.attemptMove(
        QgsLayoutPoint(232, 10, QgsUnitTypes.LayoutMillimeters)
    )
    legend.attemptResize(
        QgsLayoutSize(55, 158, QgsUnitTypes.LayoutMillimeters)
    )

    # Keep the title area opaque even when a provider paints outside the map
    # item's nominal bounds during a headless QGIS export.
    lower_band = _add_label(
        layout,
        "",
        x=0,
        y=168,
        width=297,
        height=42,
    )
    lower_band.setBackgroundEnabled(True)
    lower_band.setBackgroundColor(QColor("#FFFFFF"))
    # Redraw the map frame above the opaque band so its bottom edge remains
    # crisp in both PDF and raster output.
    _add_label(
        layout,
        "",
        x=10,
        y=10,
        width=217,
        height=158,
        frame=True,
    )

    title_block = _add_label(
        layout,
        "",
        x=10,
        y=174,
        width=277,
        height=26,
        frame=True,
    )
    title_block.setBackgroundEnabled(True)
    title_block.setBackgroundColor(QColor("#FFFFFF"))

    _add_label(
        layout,
        options.title,
        x=13,
        y=176,
        width=106,
        height=7,
        point_size=14,
        bold=True,
    )
    _add_label(
        layout,
        options.subtitle,
        x=13,
        y=183,
        width=106,
        height=5,
        point_size=8,
    )

    north_path = _north_arrow_path()
    if north_path:
        north = QgsLayoutItemPicture(layout)
        north.setPicturePath(north_path)
        north.setLinkedMap(map_item)
        north.setResizeMode(QgsLayoutItemPicture.Zoom)
        layout.addLayoutItem(north)
        north.attemptResize(
            QgsLayoutSize(13, 13, QgsUnitTypes.LayoutMillimeters)
        )
        north.attemptMove(
            QgsLayoutPoint(271, 175.5, QgsUnitTypes.LayoutMillimeters)
        )
    else:
        _add_label(
            layout,
            "N ↑",
            x=271,
            y=177,
            width=13,
            height=9,
            point_size=14,
            bold=True,
        )

    _add_label(
        layout,
        "SAKUGIS / URBANCOMP",
        x=208,
        y=177,
        width=58,
        height=5,
        point_size=9,
        bold=True,
    )
    source_names = []
    if any(
        layer.customProperty("sakugis/basemap-key") == "osm-standard"
        for layer in export_layers
    ):
        source_names.append("© OpenStreetMap contributors")
    source_names.append(tr("map_export.layer_count", count=len(export_layers)))
    source_text = " · ".join(source_names)
    _add_label(
        layout,
        source_text,
        x=208,
        y=183,
        width=58,
        height=5,
        point_size=7,
    )

    scale = QgsLayoutItemScaleBar(layout)
    scale.setStyle("Single Box")
    scale.setLinkedMap(map_item)
    scale.setNumberOfSegments(4)
    scale.setNumberOfSegmentsLeft(0)
    scale.setHeight(3)
    layout.addLayoutItem(scale)
    scale.applyDefaultSize()
    scale.attemptMove(
        QgsLayoutPoint(126, 179, QgsUnitTypes.LayoutMillimeters)
    )

    map_scale = max(1, round(map_item.scale()))
    printed_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    metadata = (
        (tr("map_export.created_by"), options.creator, 10, 50),
        (tr("map_export.printed_at"), printed_at, 60, 54),
        (tr("map_export.scale"), f"1:{map_scale:,}", 114, 43),
        (tr("map_export.version"), f"SakuGIS {__version__}", 157, 43),
        (tr("map_export.sheet"), "1 / 1", 200, 30),
        (tr("map_export.layers"), str(len(export_layers)), 230, 57),
    )
    for heading, value, x, width in metadata:
        _add_label(
            layout,
            f"{heading}\n{value}",
            x=x,
            y=190,
            width=width,
            height=10,
            point_size=6,
            frame=True,
        )

    exporter = QgsLayoutExporter(layout)
    if options.file_format == "pdf":
        settings = QgsLayoutExporter.PdfExportSettings()
        settings.dpi = options.dpi
        result = exporter.exportToPdf(str(output), settings)
    else:
        settings = QgsLayoutExporter.ImageExportSettings()
        settings.dpi = options.dpi
        settings.exportMetadata = False
        settings.generateWorldFile = False
        result = exporter.exportToImage(str(output), settings)
    if result != QgsLayoutExporter.Success:
        raise RuntimeError(tr("map_export.export_failed_code", code=int(result)))
    return output, google_excluded
