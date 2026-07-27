"""Layer tree panel and layer-oriented controls."""

from __future__ import annotations

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsLayerTreeModel, QgsProject
from qgis.gui import QgsLayerTreeView
from sakugis.i18n import tr


class LayerPanel(QWidget):
    removeRequested = pyqtSignal()
    zoomRequested = pyqtSignal()
    candidateLayerActivated = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LayerWorkspace")
        self.eyebrow_label = QLabel(tr("layer.eyebrow"), self)
        self.eyebrow_label.setObjectName("SectionEyebrow")
        self.title_label = QLabel(tr("layer.workspace"), self)
        self.title_label.setObjectName("SectionTitle")
        self.summary_label = QLabel(self)
        self.summary_label.setObjectName("MutedLabel")
        self.hint_label = QLabel(tr("layer.hint"), self)
        self.hint_label.setObjectName("MutedLabel")
        self.hint_label.setWordWrap(True)

        self.view = QgsLayerTreeView(self)
        self.view.setObjectName("LayerTree")
        self.model = QgsLayerTreeModel(QgsProject.instance().layerTreeRoot(), self)
        self.model.setFlag(QgsLayerTreeModel.AllowNodeReorder)
        self.model.setFlag(QgsLayerTreeModel.AllowNodeRename)
        self.model.setFlag(QgsLayerTreeModel.AllowNodeChangeVisibility)
        self.model.setFlag(QgsLayerTreeModel.ShowLegend)
        self.view.setModel(self.model)
        self.view.setHeaderHidden(True)
        self.view.setTextElideMode(Qt.ElideRight)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._show_context_menu)

        self.opacity_label = QLabel(tr("layer.opacity", value=100), self)
        self.opacity_slider = QSlider(Qt.Horizontal, self)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.setEnabled(False)
        self.opacity_slider.valueChanged.connect(self._set_current_layer_opacity)
        self.view.currentLayerChanged.connect(self._current_layer_changed)

        self.remove_button = QPushButton(tr("layer.remove"), self)
        self.remove_button.setObjectName("DangerButton")
        self.remove_button.clicked.connect(self.removeRequested)
        self.zoom_button = QPushButton(tr("layer.zoom"), self)
        self.zoom_button.setObjectName("PrimaryButton")
        self.zoom_button.clicked.connect(self.zoomRequested)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.zoom_button)
        button_layout.addWidget(self.remove_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(self.eyebrow_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.view, 1)
        layout.addWidget(self.hint_label)
        layout.addWidget(self.opacity_label)
        layout.addWidget(self.opacity_slider)
        layout.addLayout(button_layout)
        self.refresh_summary(len(QgsProject.instance().mapLayers()))

    def retranslate_ui(self) -> None:
        self.remove_button.setText(tr("layer.remove"))
        self.zoom_button.setText(tr("layer.zoom"))
        self.eyebrow_label.setText(tr("layer.eyebrow"))
        self.title_label.setText(tr("layer.workspace"))
        self.hint_label.setText(tr("layer.hint"))
        self.refresh_summary(len(QgsProject.instance().mapLayers()))
        self.opacity_label.setText(
            tr("layer.opacity", value=self.opacity_slider.value())
        )

    def refresh_summary(self, count: int) -> None:
        self.summary_label.setText(tr("layer.summary", count=count))

    def current_layer(self):
        return self.view.currentLayer()

    def selected_layers(self):
        return self.view.selectedLayers()

    def _layer_opacity(self, layer) -> float:
        if hasattr(layer, "opacity"):
            return float(layer.opacity())
        renderer = getattr(layer, "renderer", lambda: None)()
        if renderer and hasattr(renderer, "opacity"):
            return float(renderer.opacity())
        return 1.0

    def _current_layer_changed(self, layer) -> None:
        self.opacity_slider.blockSignals(True)
        if layer is None:
            self.opacity_slider.setValue(100)
            self.opacity_slider.setEnabled(False)
            self.opacity_label.setText(tr("layer.opacity", value=100))
        else:
            opacity = round(self._layer_opacity(layer) * 100)
            self.opacity_slider.setValue(opacity)
            self.opacity_slider.setEnabled(True)
            self.opacity_label.setText(tr("layer.opacity", value=opacity))
            if layer.customProperty("sakugis/candidate-layer"):
                self.candidateLayerActivated.emit(layer)
        self.opacity_slider.blockSignals(False)

    def _set_current_layer_opacity(self, value: int) -> None:
        layer = self.current_layer()
        if layer is None:
            return

        opacity = value / 100.0
        if hasattr(layer, "setOpacity"):
            layer.setOpacity(opacity)
        else:
            renderer = getattr(layer, "renderer", lambda: None)()
            if renderer and hasattr(renderer, "setOpacity"):
                renderer.setOpacity(opacity)
        layer.triggerRepaint()
        self.opacity_label.setText(tr("layer.opacity", value=value))

    def _show_context_menu(self, position) -> None:
        index = self.view.indexAt(position)
        if not index.isValid():
            return
        self.view.setCurrentIndex(index)

        menu = QMenu(self)
        menu.addAction(tr("layer.zoom"), self.zoomRequested.emit)
        menu.addSeparator()
        menu.addAction(tr("layer.rename"), lambda: self.view.edit(index))
        menu.addAction(tr("layer.remove_menu"), self.removeRequested.emit)
        menu.exec_(self.view.viewport().mapToGlobal(position))
