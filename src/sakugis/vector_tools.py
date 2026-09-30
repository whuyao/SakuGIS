"""Basic vector styling and attribute-table tools for SakuGIS."""

from __future__ import annotations

from typing import Any

from qgis.PyQt.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
)
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
)
from qgis.core import (
    QgsFeatureRequest,
    QgsStyle,
    QgsVectorLayer,
)
from qgis.gui import QgsRendererPropertiesDialog

from sakugis.i18n import ZH_CN, get_language, tr


MAX_TABLE_ROWS = 10_000


def _display_value(value: Any) -> str:
    if value is None:
        return tr("attribute.null")
    return str(value)


class FeatureTableModel(QAbstractTableModel):
    """Small, sortable snapshot of a vector layer's attribute rows."""

    def __init__(self, layer: QgsVectorLayer, parent=None):
        super().__init__(parent)
        self._headers = [tr("attribute.fid")]
        self._headers.extend(
            layer.attributeDisplayName(index)
            for index in range(len(layer.fields()))
        )
        request = QgsFeatureRequest().setLimit(MAX_TABLE_ROWS)
        self._rows = [
            (feature.id(), list(feature.attributes()))
            for feature in layer.getFeatures(request)
        ]

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._headers)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        feature_id, attributes = self._rows[index.row()]
        value = feature_id if index.column() == 0 else attributes[index.column() - 1]
        if role in {Qt.DisplayRole, Qt.ToolTipRole}:
            return _display_value(value)
        if role == Qt.UserRole:
            return feature_id
        return None

    def headerData(self, section: int, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal and 0 <= section < len(self._headers):
            return self._headers[section]
        if orientation == Qt.Vertical:
            return section + 1
        return None

    def feature_id(self, row: int) -> int:
        return int(self._rows[row][0])


class AttributeTableDialog(QDialog):
    """Browse, filter, select, and zoom to vector-layer attributes."""

    def __init__(self, layer: QgsVectorLayer, canvas, parent=None):
        super().__init__(parent)
        self.layer = layer
        self.canvas = canvas
        self.setWindowTitle(tr("attribute.title", name=layer.name()))
        self.resize(980, 620)
        self.setMinimumSize(700, 420)

        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText(tr("attribute.search_hint"))
        self.model = FeatureTableModel(layer, self)
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.proxy.setFilterKeyColumn(-1)
        self.proxy.setDynamicSortFilter(True)
        self.search_edit.textChanged.connect(self.proxy.setFilterFixedString)

        self.table = QTableView(self)
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.ExtendedSelection)
        self.table.setWordWrap(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.selectionModel().selectionChanged.connect(
            self._select_features
        )
        self.table.doubleClicked.connect(lambda _index: self._zoom_selected())

        total = max(0, int(layer.featureCount()))
        shown = self.model.rowCount()
        count_key = (
            "attribute.count_limited" if shown < total else "attribute.count"
        )
        self.count_label = QLabel(
            tr(count_key, shown=shown, total=total), self
        )
        self.count_label.setObjectName("MutedLabel")

        self.zoom_button = QPushButton(tr("attribute.zoom_selected"), self)
        self.zoom_button.clicked.connect(self._zoom_selected)
        close_button = QPushButton(tr("attribute.close"), self)
        close_button.clicked.connect(self.accept)
        actions = QHBoxLayout()
        actions.addWidget(self.count_label, 1)
        actions.addWidget(self.zoom_button)
        actions.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(10)
        layout.addWidget(self.search_edit)
        layout.addWidget(self.table, 1)
        layout.addLayout(actions)

    def _selected_feature_ids(self) -> list[int]:
        ids = []
        for proxy_index in self.table.selectionModel().selectedRows(0):
            source_index = self.proxy.mapToSource(proxy_index)
            ids.append(self.model.feature_id(source_index.row()))
        return ids

    def _select_features(self, *_args) -> None:
        self.layer.selectByIds(self._selected_feature_ids())
        self.layer.triggerRepaint()
        self.canvas.refresh()

    def _zoom_selected(self) -> None:
        if not self._selected_feature_ids():
            QMessageBox.information(
                self,
                tr("attribute.no_selection_title"),
                tr("attribute.no_selection"),
            )
            return
        self.canvas.zoomToSelected(self.layer)
        self.canvas.refresh()


def create_layer_style_dialog(
    layer: QgsVectorLayer,
    canvas,
    parent=None,
) -> QgsRendererPropertiesDialog:
    """Create QGIS' complete native vector symbology dialog."""

    dialog = QgsRendererPropertiesDialog(
        layer,
        QgsStyle.defaultStyle(),
        False,
        parent,
    )
    dialog.setMapCanvas(canvas)
    dialog.setWindowTitle(tr("style.title", name=layer.name()))
    dialog.resize(1040, 720)
    dialog.setMinimumSize(820, 580)
    button_box = dialog.findChild(QDialogButtonBox)
    if button_box is not None:
        ok_button = button_box.button(QDialogButtonBox.Ok)
        cancel_button = button_box.button(QDialogButtonBox.Cancel)
        if ok_button is not None:
            ok_button.setText(tr("style.native_ok"))
        if cancel_button is not None:
            cancel_button.setText(tr("style.cancel"))
    if get_language() == ZH_CN:
        renderer_names = {
            "Single Symbol": tr("style.renderer.single"),
            "Categorized": tr("style.renderer.categorized"),
            "Graduated": tr("style.renderer.graduated"),
            "Rule-based": tr("style.renderer.rule_based"),
            "Point Displacement": tr("style.renderer.point_displacement"),
            "Point Cluster": tr("style.renderer.point_cluster"),
            "Heatmap": tr("style.renderer.heatmap"),
            "Inverted Polygons": tr("style.renderer.inverted"),
            "Merged Features": tr("style.renderer.merged"),
            "Embedded Symbols": tr("style.renderer.embedded"),
            "No Symbols": tr("style.renderer.none"),
        }
        for combo in dialog.findChildren(QComboBox):
            for index in range(combo.count()):
                translated = renderer_names.get(combo.itemText(index))
                if translated:
                    combo.setItemText(index, translated)
    return dialog
