"""Reusable onboarding and map HUD widgets."""

from __future__ import annotations

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from sakugis.i18n import tr


class WelcomeOverlay(QFrame):
    startRequested = pyqtSignal()
    satelliteRequested = pyqtSignal()
    openDataRequested = pyqtSignal()
    dismissed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("WelcomeCard")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumWidth(500)
        self.setMaximumWidth(640)

        self.eyebrow = QLabel(self)
        self.eyebrow.setObjectName("HeroEyebrow")
        self.title = QLabel(self)
        self.title.setObjectName("HeroTitle")
        self.title.setWordWrap(True)
        self.subtitle = QLabel(self)
        self.subtitle.setObjectName("HeroSubtitle")
        self.subtitle.setWordWrap(True)

        self.steps = QLabel(self)
        self.steps.setObjectName("MutedLabel")
        self.steps.setWordWrap(True)

        self.start_button = QPushButton(self)
        self.start_button.setObjectName("PrimaryButton")
        self.start_button.clicked.connect(self.startRequested)
        self.satellite_button = QPushButton(self)
        self.satellite_button.clicked.connect(self.satelliteRequested)
        self.open_button = QPushButton(self)
        self.open_button.setObjectName("GhostButton")
        self.open_button.clicked.connect(self.openDataRequested)
        self.dismiss_button = QPushButton(self)
        self.dismiss_button.setObjectName("GhostButton")
        self.dismiss_button.clicked.connect(self._dismiss)

        primary_row = QHBoxLayout()
        primary_row.addWidget(self.start_button)
        primary_row.addWidget(self.satellite_button)
        secondary_row = QHBoxLayout()
        secondary_row.addWidget(self.open_button)
        secondary_row.addStretch(1)
        secondary_row.addWidget(self.dismiss_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(10)
        layout.addWidget(self.eyebrow)
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addSpacing(5)
        layout.addWidget(self.steps)
        layout.addSpacing(6)
        layout.addLayout(primary_row)
        layout.addLayout(secondary_row)
        self.retranslate_ui()

    def _dismiss(self) -> None:
        self.hide()
        self.dismissed.emit()

    def retranslate_ui(self) -> None:
        self.eyebrow.setText(tr("welcome.eyebrow"))
        self.title.setText(tr("welcome.title"))
        self.subtitle.setText(tr("welcome.subtitle"))
        self.steps.setText(tr("welcome.steps"))
        self.start_button.setText(tr("welcome.start"))
        self.satellite_button.setText(tr("welcome.satellite"))
        self.open_button.setText(tr("welcome.open_data"))
        self.dismiss_button.setText(tr("welcome.dismiss"))
        self.adjustSize()


class MapHud(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("HudCard")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.eyebrow = QLabel(self)
        self.eyebrow.setObjectName("SectionEyebrow")
        self.summary = QLabel(self)
        self.summary.setObjectName("MutedLabel")
        self.hint = QLabel(self)
        self.hint.setObjectName("MutedLabel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(11, 8, 11, 8)
        layout.setSpacing(2)
        layout.addWidget(self.eyebrow)
        layout.addWidget(self.summary)
        layout.addWidget(self.hint)
        self.retranslate_ui()
        self.update_layers(0)

    def retranslate_ui(self) -> None:
        self.eyebrow.setText(tr("hud.live_map"))
        self.hint.setText(tr("hud.hint"))

    def update_layers(self, count: int) -> None:
        self.summary.setText(
            tr("hud.summary", count=count, crs="EPSG:3857")
        )
        self.adjustSize()
