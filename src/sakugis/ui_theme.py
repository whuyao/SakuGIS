"""SakuGIS visual system with persistent dark and light appearances."""

from __future__ import annotations

import re

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap


DARK = "dark"
LIGHT = "light"
SUPPORTED_THEMES = (DARK, LIGHT)
_theme = DARK

DARK_COLORS = {
    "background": "#07101B",
    "surface": "#0D1928",
    "surface_raised": "#122236",
    "surface_hover": "#182E47",
    "border": "#284158",
    "text": "#E8F1F8",
    "muted": "#91A7B9",
    "cyan": "#42D7F5",
    "cyan_soft": "#193C4A",
    "magenta": "#FF5C93",
    "green": "#61E6A2",
    "amber": "#FFC66D",
    "danger": "#FF7185",
}

LIGHT_COLORS = {
    "background": "#F3F6FA",
    "surface": "#FFFFFF",
    "surface_raised": "#E9EFF5",
    "surface_hover": "#DCE8F2",
    "border": "#B8C7D3",
    "text": "#172534",
    "muted": "#607487",
    "cyan": "#1687A3",
    "cyan_soft": "#D8EEF3",
    "magenta": "#D13F72",
    "green": "#258B5D",
    "amber": "#A76A00",
    "danger": "#C93C52",
}

# Backwards-compatible palette for modules that only need the brand accents.
COLORS = DARK_COLORS


DARK_STYLESHEET = """
QMainWindow, QDialog, QMessageBox, QWidget {
    color: #E8F1F8;
    background-color: #07101B;
    selection-background-color: #1C6E86;
    selection-color: #FFFFFF;
}
QLabel {
    background: transparent;
}
QMenuBar {
    background: #091421;
    color: #C9D8E5;
    border-bottom: 1px solid #20374B;
    padding: 3px 6px;
}
QMenuBar::item {
    background: transparent;
    padding: 6px 10px;
    border-radius: 5px;
}
QMenuBar::item:selected {
    background: #182E47;
    color: #FFFFFF;
}
QMenu {
    background: #102033;
    color: #E8F1F8;
    border: 1px solid #31516D;
    padding: 6px;
}
QMenu::item {
    padding: 7px 26px 7px 10px;
    border-radius: 5px;
}
QMenu::item:selected {
    background: #1C6E86;
}
QToolBar {
    background: #0A1624;
    border: none;
    border-bottom: 1px solid #284158;
    spacing: 5px;
    padding: 7px 9px;
}
QToolButton {
    background: transparent;
    color: #C9D8E5;
    border: 1px solid transparent;
    border-radius: 7px;
    padding: 6px 8px;
}
QToolButton:hover {
    background: #182E47;
    border-color: #31516D;
    color: #FFFFFF;
}
QToolButton:checked {
    background: #193C4A;
    border-color: #42D7F5;
    color: #73E7FF;
}
QDockWidget {
    color: #C9D8E5;
    font-weight: 600;
}
QDockWidget::title {
    background: #0B1725;
    border-bottom: 1px solid #284158;
    padding: 8px 10px;
    text-align: left;
}
QGroupBox {
    background: #0D1928;
    border: 1px solid #284158;
    border-radius: 9px;
    margin-top: 13px;
    padding: 11px 10px 9px 10px;
    font-weight: 600;
    color: #DDEAF4;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 11px;
    padding: 0 5px;
    color: #AFC2D1;
}
QLineEdit, QTextEdit, QTextBrowser, QListView, QListWidget, QTreeView, QTreeWidget {
    background: #091522;
    alternate-background-color: #0D1B2A;
    color: #E8F1F8;
    border: 1px solid #284158;
    border-radius: 7px;
    padding: 6px;
}
QLineEdit:focus, QTextEdit:focus, QListView:focus, QListWidget:focus,
QTreeView:focus, QTreeWidget:focus {
    border: 1px solid #42D7F5;
}
QLineEdit[readOnly="true"] {
    color: #91A7B9;
    background: #0A1420;
}
QHeaderView::section {
    background: #122236;
    color: #AFC2D1;
    padding: 6px;
    border: none;
    border-right: 1px solid #284158;
    border-bottom: 1px solid #284158;
    font-weight: 600;
}
QTreeView::item, QTreeWidget::item {
    padding: 4px 2px;
    border-radius: 4px;
}
QTreeView::item:hover, QTreeWidget::item:hover {
    background: #152A40;
}
QTreeView::item:selected, QTreeWidget::item:selected {
    background: #1A6379;
    color: #FFFFFF;
}
QPushButton {
    background: #162A40;
    color: #DCE9F3;
    border: 1px solid #31516D;
    border-radius: 7px;
    padding: 7px 12px;
    min-height: 18px;
    font-weight: 600;
}
QPushButton:hover {
    background: #1D3855;
    border-color: #4B789A;
}
QPushButton:pressed {
    background: #10243A;
}
QPushButton:disabled {
    color: #617486;
    background: #101B27;
    border-color: #203041;
}
QPushButton#PrimaryButton {
    background: #137D98;
    border: 1px solid #42D7F5;
    color: #FFFFFF;
    padding: 8px 15px;
}
QPushButton#PrimaryButton:hover {
    background: #1995B5;
}
QPushButton#GhostButton {
    background: transparent;
    border-color: #284158;
    color: #AFC2D1;
}
QPushButton#DangerButton {
    background: #432333;
    border-color: #8E3E58;
    color: #FFB2C8;
}
QProgressBar {
    background: #0A1420;
    border: 1px solid #284158;
    border-radius: 6px;
    color: #E8F1F8;
    text-align: center;
    min-height: 18px;
}
QProgressBar::chunk {
    border-radius: 5px;
    background: #24BCD9;
}
QTabWidget::pane {
    border: 1px solid #284158;
    border-radius: 7px;
    background: #091522;
}
QTabBar::tab {
    background: #0D1928;
    color: #91A7B9;
    border: 1px solid #20374B;
    padding: 7px 12px;
}
QTabBar::tab:selected {
    background: #193C4A;
    color: #73E7FF;
    border-color: #42D7F5;
}
QSlider::groove:horizontal {
    height: 4px;
    background: #20374B;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 14px;
    margin: -5px 0;
    background: #42D7F5;
    border: 2px solid #0D1928;
    border-radius: 7px;
}
QScrollBar:vertical {
    background: #091522;
    width: 11px;
}
QScrollBar::handle:vertical {
    background: #31516D;
    min-height: 28px;
    border-radius: 5px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QStatusBar {
    background: #08131F;
    color: #9EB2C2;
    border-top: 1px solid #20374B;
}
QStatusBar QLabel {
    background: transparent;
    padding: 2px 5px;
}
QLabel#HeroEyebrow {
    color: #42D7F5;
    font-size: 11px;
    font-weight: 700;
}
QLabel#HeroTitle {
    color: #F2F8FC;
    font-size: 22px;
    font-weight: 700;
}
QLabel#HeroSubtitle, QLabel#MutedLabel {
    color: #91A7B9;
}
QLabel#SectionEyebrow {
    color: #6FDFF6;
    font-size: 10px;
    font-weight: 700;
}
QLabel#SectionTitle {
    color: #EDF6FC;
    font-size: 16px;
    font-weight: 700;
}
QLabel#PlaceDetailsTitle {
    color: #F2F8FC;
    font-size: 19px;
    font-weight: 700;
}
QLabel#PlaceScoreChip {
    color: #82EAFF;
    background: #143846;
    border: 1px solid #2C6E81;
    border-radius: 8px;
    padding: 5px 8px;
    font-weight: 700;
    font-size: 11px;
}
QToolButton#PlacePhotoCard {
    background: #0D1928;
    color: #DDEAF4;
    border: 1px solid #284158;
    border-radius: 10px;
    padding: 6px;
    font-weight: 600;
}
QToolButton#PlacePhotoCard:hover {
    background: #182E47;
    border-color: #42D7F5;
    color: #FFFFFF;
}
QTextBrowser#PlaceOverview {
    padding: 10px 12px;
}
QLabel#StatusGood {
    color: #61E6A2;
    background: #15372D;
    border: 1px solid #2F765A;
    border-radius: 7px;
    padding: 5px 8px;
}
QLabel#StatusInfo {
    color: #73E7FF;
    background: #143846;
    border: 1px solid #2C6E81;
    border-radius: 7px;
    padding: 5px 8px;
}
QLabel#StatusWarning {
    color: #FFD89A;
    background: #3B301D;
    border: 1px solid #765C2B;
    border-radius: 7px;
    padding: 5px 8px;
}
QLabel#StepIdle {
    color: #72899B;
    background: #0D1928;
    border: 1px solid #284158;
    border-radius: 8px;
    padding: 6px 8px;
}
QLabel#StepActive {
    color: #82EAFF;
    background: #143846;
    border: 1px solid #42D7F5;
    border-radius: 8px;
    padding: 6px 8px;
}
QLabel#StepDone {
    color: #8BF0BA;
    background: #15372D;
    border: 1px solid #3B8A69;
    border-radius: 8px;
    padding: 6px 8px;
}
QLabel#PhotoPreview {
    background: #091522;
    border: 1px dashed #31516D;
    border-radius: 8px;
    color: #7F98AB;
}
QFrame#WelcomeCard {
    background: rgba(9, 21, 34, 242);
    border: 1px solid #3B6D89;
    border-radius: 16px;
}
QFrame#HudCard {
    background: rgba(8, 20, 33, 220);
    border: 1px solid #31516D;
    border-radius: 9px;
}
QFrame#Divider {
    background: #284158;
    min-height: 1px;
    max-height: 1px;
}
QToolTip {
    background: #122236;
    color: #E8F1F8;
    border: 1px solid #42D7F5;
    padding: 5px;
}
"""

_LIGHT_REPLACEMENTS = {
    "#07101b": "#F3F6FA",
    "#0d1928": "#FFFFFF",
    "#122236": "#E9EFF5",
    "#182e47": "#DCE8F2",
    "#284158": "#B8C7D3",
    "#e8f1f8": "#172534",
    "#91a7b9": "#607487",
    "#42d7f5": "#1687A3",
    "#193c4a": "#D8EEF3",
    "#ff5c93": "#D13F72",
    "#61e6a2": "#258B5D",
    "#ffc66d": "#A76A00",
    "#ff7185": "#C93C52",
    "#1c6e86": "#1687A3",
    "#091421": "#F7F9FC",
    "#c9d8e5": "#34495E",
    "#20374b": "#C8D3DC",
    "#102033": "#FFFFFF",
    "#31516d": "#A9BCCB",
    "#0a1624": "#F7F9FC",
    "#73e7ff": "#0A6F88",
    "#0b1725": "#F0F4F8",
    "#ddeaf4": "#243647",
    "#afc2d1": "#52687A",
    "#091522": "#FFFFFF",
    "#0d1b2a": "#F4F7FA",
    "#0a1420": "#F0F3F6",
    "#152a40": "#E7F0F5",
    "#1a6379": "#1687A3",
    "#162a40": "#E8F1F7",
    "#dce9f3": "#253848",
    "#1d3855": "#D9E8F1",
    "#4b789a": "#7A9DB5",
    "#10243a": "#CFE0EA",
    "#617486": "#8A99A6",
    "#101b27": "#EBEFF2",
    "#203041": "#D1DAE1",
    "#137d98": "#147E99",
    "#1995b5": "#0E6D84",
    "#432333": "#FCE8EE",
    "#8e3e58": "#D68A9E",
    "#ffb2c8": "#8E2444",
    "#24bcd9": "#1687A3",
    "#72899b": "#708393",
    "#82eaff": "#096B83",
    "#8bf0ba": "#1B774C",
    "#15372d": "#E4F4EC",
    "#2f765a": "#8BC2A7",
    "#143846": "#DCEFF3",
    "#2c6e81": "#83B7C4",
    "#ffd89a": "#8A5800",
    "#3b301d": "#FFF4D8",
    "#765c2b": "#D6B66C",
    "#3b8a69": "#79B797",
    "#3b6d89": "#8CB4C7",
    "#08131f": "#F4F7FA",
    "#9eb2c2": "#52687A",
    "#f2f8fc": "#142433",
    "#6fdff6": "#0B718A",
    "#edf6fc": "#172534",
    "#7f98ab": "#718392",
    "rgba(9, 21, 34, 242)": "rgba(255, 255, 255, 245)",
    "rgba(8, 20, 33, 220)": "rgba(255, 255, 255, 225)",
}
_LIGHT_PATTERN = re.compile(
    "|".join(
        sorted(
            (re.escape(value) for value in _LIGHT_REPLACEMENTS),
            key=len,
            reverse=True,
        )
    ),
    re.IGNORECASE,
)
LIGHT_STYLESHEET = _LIGHT_PATTERN.sub(
    lambda match: _LIGHT_REPLACEMENTS[match.group(0).lower()],
    DARK_STYLESHEET,
)
STYLESHEET = DARK_STYLESHEET


def normalize_theme(theme: str) -> str:
    return theme if theme in SUPPORTED_THEMES else DARK


def get_theme() -> str:
    return _theme


def theme_colors(theme: str = "") -> dict:
    selected = normalize_theme(theme or _theme)
    return LIGHT_COLORS if selected == LIGHT else DARK_COLORS


def apply_theme(application, theme: str = DARK) -> None:
    global _theme
    _theme = normalize_theme(theme)
    application.setStyle("Fusion")
    application.setFont(QFont("Avenir Next", 13))
    application.setStyleSheet(
        LIGHT_STYLESHEET if _theme == LIGHT else DARK_STYLESHEET
    )


def glyph_icon(glyph: str, color: str = "") -> QIcon:
    color = color or theme_colors()["cyan"]
    pixmap = QPixmap(28, 28)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor(color), 1.6))
    font = QFont("Avenir Next", 15)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, glyph)
    painter.end()
    return QIcon(pixmap)
