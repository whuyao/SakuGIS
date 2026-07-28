"""Bilingual candidate details and Brave web-image discovery panel."""

from __future__ import annotations

import html
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Optional

from qgis.PyQt.QtCore import QObject, QSize, Qt, QUrl, pyqtSignal, pyqtSlot
from qgis.PyQt.QtGui import QDesktopServices, QIcon, QPixmap
from qgis.PyQt.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTextBrowser,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sakugis.agent_models import Candidate
from sakugis.credentials import configured_brave_timeout, has_brave_api_key
from sakugis.i18n import get_language, tr
from sakugis.place_search import (
    BraveSearchClient,
    MemoryPlaceCache,
    PlaceDetails,
    PlaceImageResult,
    PlaceSearchError,
    has_named_gis_identity,
    has_online_place_material,
)


class PlaceDetailsSignals(QObject):
    detailsReady = pyqtSignal(int, object)
    thumbnailReady = pyqtSignal(int, int, object)
    failed = pyqtSignal(int, str)
    finished = pyqtSignal(int)


class PlaceDetailsPanel(QWidget):
    """Shows local GIS evidence immediately, then enriches it asynchronously."""

    contentAvailable = pyqtSignal(object)
    contentUnavailable = pyqtSignal(object, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PlaceDetailsPanel")
        self._candidate: Optional[Candidate] = None
        self._details: Optional[PlaceDetails] = None
        self._request_id = 0
        self._cache = MemoryPlaceCache()
        self._executor = ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="sakugis-place"
        )
        self._signals = PlaceDetailsSignals(self)
        self._signals.detailsReady.connect(self._on_details_ready)
        self._signals.thumbnailReady.connect(self._on_thumbnail_ready)
        self._signals.failed.connect(self._on_failed)
        self._signals.finished.connect(self._on_finished)
        self._jobs: Dict[int, tuple[object, threading.Event]] = {}
        self._shutdown = False
        self._photo_buttons: Dict[int, QToolButton] = {}
        self._build_ui()
        self._show_empty_state()

    def _build_ui(self) -> None:
        self.eyebrow = QLabel(tr("place.eyebrow"), self)
        self.eyebrow.setObjectName("SectionEyebrow")
        self.title_label = QLabel(tr("place.empty_title"), self)
        self.title_label.setObjectName("PlaceDetailsTitle")
        self.title_label.setWordWrap(True)
        self.location_label = QLabel(tr("place.empty_hint"), self)
        self.location_label.setObjectName("MutedLabel")
        self.location_label.setWordWrap(True)

        self.score_chip = QLabel("—", self)
        self.score_chip.setObjectName("PlaceScoreChip")
        self.gis_chip = QLabel("—", self)
        self.gis_chip.setObjectName("PlaceScoreChip")
        chip_row = QHBoxLayout()
        chip_row.setSpacing(6)
        chip_row.addWidget(self.score_chip)
        chip_row.addWidget(self.gis_chip)
        chip_row.addStretch(1)

        self.status_label = QLabel(tr("place.waiting"), self)
        self.status_label.setObjectName("MutedLabel")
        self.status_label.setWordWrap(True)
        self.refresh_button = QPushButton(tr("place.refresh"), self)
        self.refresh_button.setObjectName("GhostButton")
        self.refresh_button.clicked.connect(
            lambda: self.refresh(force_refresh=True)
        )

        header = QVBoxLayout()
        header.setContentsMargins(4, 3, 8, 3)
        header.setSpacing(5)
        header.addWidget(self.eyebrow)
        header.addWidget(self.title_label)
        header.addWidget(self.location_label)
        header.addLayout(chip_row)
        header.addStretch(1)
        header.addWidget(self.status_label)
        header.addWidget(self.refresh_button, 0, Qt.AlignLeft)

        self.overview_browser = QTextBrowser(self)
        self.overview_browser.setOpenExternalLinks(True)
        self.overview_browser.setObjectName("PlaceOverview")

        self.photo_container = QWidget(self)
        self.photo_grid = QGridLayout(self.photo_container)
        self.photo_grid.setContentsMargins(8, 8, 8, 8)
        self.photo_grid.setSpacing(10)
        self.photo_scroll = QScrollArea(self)
        self.photo_scroll.setWidgetResizable(True)
        self.photo_scroll.setFrameShape(QFrame.NoFrame)
        self.photo_scroll.setWidget(self.photo_container)

        self.sources_tree = QTreeWidget(self)
        self.sources_tree.setRootIsDecorated(False)
        self.sources_tree.setAlternatingRowColors(True)
        self.sources_tree.itemActivated.connect(self._open_source_item)

        self.tabs = QTabWidget(self)
        self.tabs.addTab(self.overview_browser, tr("place.overview"))
        self.tabs.addTab(self.photo_scroll, tr("place.photos"))
        self.tabs.addTab(self.sources_tree, tr("place.sources"))

        body = QHBoxLayout(self)
        body.setContentsMargins(12, 9, 12, 10)
        body.setSpacing(12)
        header_widget = QWidget(self)
        header_widget.setMinimumWidth(195)
        header_widget.setMaximumWidth(230)
        header_widget.setLayout(header)
        body.addWidget(header_widget)
        body.addWidget(self.tabs, 1)

    def current_candidate(self) -> Optional[Candidate]:
        return self._candidate

    def settings_changed(self) -> None:
        """Apply credential and timeout changes without restarting the app."""

        self._cache.clear()
        if self._candidate is not None:
            self.set_candidate(self._candidate, force_refresh=True)

    def set_candidate(
        self, candidate: Candidate, force_refresh: bool = False
    ) -> None:
        self._request_id += 1
        self._cancel_jobs()
        self._candidate = candidate
        self._details = None
        self.title_label.setText(candidate.name or tr("place.unnamed"))
        self.location_label.setText(
            " · ".join(
                item
                for item in (
                    candidate.region,
                    candidate.country,
                    f"{candidate.latitude:.5f}, {candidate.longitude:.5f}",
                )
                if item
            )
        )
        self.score_chip.setText(
            tr(
                "place.composite_chip",
                score=f"{candidate.ranking_score * 100:.1f}",
            )
        )
        self.gis_chip.setText(
            tr("place.gis_chip", score=f"{candidate.gis_score * 100:.1f}")
        )
        self.score_chip.setToolTip(
            f"{candidate.ranking_score * 100:.1f}/100"
        )
        self.gis_chip.setToolTip(
            f"{candidate.gis_score * 100:.1f}/100"
        )
        self._render_overview()
        self._clear_photos()
        self._render_sources()
        if not has_named_gis_identity(candidate):
            self.status_label.setText(tr("place.hidden.gis_identity"))
            self.refresh_button.setEnabled(False)
            self.contentUnavailable.emit(candidate, "gis_identity")
            return
        self.refresh(force_refresh=force_refresh)

    def refresh(self, force_refresh: bool = False) -> None:
        if self._candidate is None:
            return
        if os.environ.get("SAKUGIS_SMOKE_DISABLE_PLACE_SEARCH") == "1":
            self.status_label.setText(tr("place.local_only"))
            self.contentUnavailable.emit(self._candidate, "local_only")
            return
        if not has_brave_api_key():
            self.status_label.setText(tr("place.key_missing"))
            self.contentUnavailable.emit(self._candidate, "key_missing")
            return
        self._start_search(force_refresh)

    def _start_search(self, force_refresh: bool) -> None:
        if self._shutdown:
            return
        self._request_id += 1
        request_id = self._request_id
        self._cancel_jobs()
        self.status_label.setText(tr("place.loading"))
        self.refresh_button.setEnabled(False)
        cancellation = threading.Event()
        future = self._executor.submit(
            self._run_search,
            request_id,
            self._candidate,
            get_language(),
            force_refresh,
            cancellation,
        )
        self._jobs[request_id] = (future, cancellation)

    def _run_search(
        self,
        request_id: int,
        candidate: Candidate,
        language: str,
        force_refresh: bool,
        cancellation: threading.Event,
    ) -> None:
        try:
            client = BraveSearchClient(
                cache=self._cache,
                timeout=configured_brave_timeout(),
            )
            details = client.search_place(
                candidate,
                language,
                force_refresh=force_refresh,
            )
            if cancellation.is_set():
                return
            self._signals.detailsReady.emit(request_id, details)
            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = {
                    executor.submit(
                        client.fetch_thumbnail, image.thumbnail_url
                    ): index
                    for index, image in enumerate(details.images)
                }
                for future in as_completed(futures):
                    if cancellation.is_set():
                        break
                    index = futures[future]
                    try:
                        content = future.result()
                    except PlaceSearchError:
                        continue
                    self._signals.thumbnailReady.emit(
                        request_id, index, content
                    )
        except PlaceSearchError as exc:
            if not cancellation.is_set():
                self._signals.failed.emit(request_id, exc.code)
        except Exception:
            if not cancellation.is_set():
                self._signals.failed.emit(request_id, "network")
        finally:
            self._signals.finished.emit(request_id)

    @pyqtSlot(int, object)
    def _on_details_ready(
        self, request_id: int, details: PlaceDetails
    ) -> None:
        if request_id != self._request_id:
            return
        self._details = details
        if not has_online_place_material(details):
            self.status_label.setText(tr("place.hidden.no_material"))
            self._render_overview()
            self._render_photos(details)
            self._render_sources()
            if self._candidate is not None:
                self.contentUnavailable.emit(
                    self._candidate, "no_material"
                )
            return
        self._render_overview()
        self._render_photos(details)
        self._render_sources()
        if details.warnings:
            self.status_label.setText(
                tr(
                    "place.partial",
                    detail=", ".join(
                        tr(f"place.error.{code}")
                        for code in details.warnings
                    ),
                )
            )
        else:
            self.status_label.setText(
                tr(
                    "place.ready",
                    web=len(details.web_results),
                    photos=len(details.images),
                )
            )
        if self._candidate is not None:
            self.contentAvailable.emit(self._candidate)

    @pyqtSlot(int, int, object)
    def _on_thumbnail_ready(
        self, request_id: int, index: int, content: bytes
    ) -> None:
        if request_id != self._request_id:
            return
        button = self._photo_buttons.get(index)
        if button is None:
            return
        pixmap = QPixmap()
        if pixmap.loadFromData(content):
            button.setIcon(QIcon(pixmap))
            button.setIconSize(QSize(114, 72))

    @pyqtSlot(int, str)
    def _on_failed(self, request_id: int, code: str) -> None:
        if request_id != self._request_id:
            return
        self.status_label.setText(tr(f"place.error.{code}"))
        if self._candidate is not None:
            self.contentUnavailable.emit(self._candidate, "search_failed")

    @pyqtSlot(int)
    def _on_finished(self, request_id: int) -> None:
        self._jobs.pop(request_id, None)
        if request_id == self._request_id:
            self.refresh_button.setEnabled(True)

    def _render_overview(self) -> None:
        candidate = self._candidate
        if candidate is None:
            self.overview_browser.setHtml(
                f"<p>{_escape(tr('place.empty_hint'))}</p>"
            )
            return
        parts = [
            f"<h3>{_escape(candidate.name or tr('place.unnamed'))}</h3>",
            (
                f"<p><b>{_escape(tr('place.reverse'))}</b> "
                f"{_escape(candidate.reverse_label or '—')}</p>"
            ),
            (
                f"<p><b>{_escape(tr('place.rationale'))}</b> "
                f"{_escape(candidate.rationale or '—')}</p>"
            ),
            (
                f"<p><b>{_escape(tr('place.coordinate'))}</b> "
                f"{candidate.latitude:.6f}, {candidate.longitude:.6f}"
                f" &nbsp; <b>{_escape(tr('place.radius'))}</b> "
                f"±{candidate.radius_km:,.0f} km"
                f" &nbsp; <b>{_escape(tr('place.coverage'))}</b> "
                f"{candidate.gis_coverage * 100:.0f}%</p>"
            ),
        ]
        details = self._details
        if details and details.web_results:
            parts.append(
                f"<h4>{_escape(tr('place.web_intro'))}</h4>"
            )
            for result in details.web_results:
                description = (
                    f"<br>{_escape(result.description)}"
                    if result.description
                    else ""
                )
                parts.append(
                    "<p>"
                    f'<a href="{_escape(result.url)}">'
                    f"{_escape(result.title)}</a>"
                    f" <span>· {_escape(result.source)}</span>"
                    f"{description}</p>"
                )
        elif details is not None:
            parts.append(f"<p>{_escape(tr('place.no_web'))}</p>")
        parts.append(
            f"<p><i>{_escape(tr('place.source_note'))}</i></p>"
        )
        self.overview_browser.setHtml("".join(parts))

    def _render_photos(self, details: PlaceDetails) -> None:
        self._clear_photos()
        if not details.images:
            label = QLabel(tr("place.no_images"), self.photo_container)
            label.setObjectName("MutedLabel")
            self.photo_grid.addWidget(label, 0, 0)
            return
        for index, image in enumerate(details.images):
            button = QToolButton(self.photo_container)
            button.setObjectName("PlacePhotoCard")
            button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            button.setIconSize(QSize(114, 72))
            button.setFixedSize(132, 112)
            button.setText(
                _short_label(image.title or image.source, 34)
                or tr("place.open_source")
            )
            button.setToolTip(
                f"{image.title}\n{image.source}\n{tr('place.open_source')}"
            )
            button.clicked.connect(
                lambda _checked=False, url=image.page_url: _open_url(url)
            )
            self.photo_grid.addWidget(button, index // 2, index % 2)
            self._photo_buttons[index] = button
        self.photo_grid.setRowStretch((len(details.images) + 1) // 2, 1)

    def _clear_photos(self) -> None:
        while self.photo_grid.count():
            item = self.photo_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._photo_buttons.clear()

    def _render_sources(self) -> None:
        self.sources_tree.clear()
        self.sources_tree.setHeaderLabels(
            [
                tr("place.source_title"),
                tr("place.source_site"),
                tr("place.source_type"),
            ]
        )
        details = self._details
        if details is None:
            return
        for result in details.web_results:
            item = QTreeWidgetItem(
                [result.title, result.source, tr("place.type_web")]
            )
            item.setData(0, Qt.UserRole, result.url)
            item.setToolTip(0, result.description)
            self.sources_tree.addTopLevelItem(item)
        for image in details.images:
            item = QTreeWidgetItem(
                [
                    image.title or image.source,
                    image.source,
                    tr("place.type_image"),
                ]
            )
            item.setData(0, Qt.UserRole, image.page_url)
            self.sources_tree.addTopLevelItem(item)
        self.sources_tree.resizeColumnToContents(1)
        self.sources_tree.resizeColumnToContents(2)

    def _open_source_item(
        self, item: QTreeWidgetItem, _column: int
    ) -> None:
        _open_url(str(item.data(0, Qt.UserRole) or ""))

    def _show_empty_state(self) -> None:
        self.title_label.setText(tr("place.empty_title"))
        self.location_label.setText(tr("place.empty_hint"))
        self.score_chip.setText("—")
        self.gis_chip.setText("—")
        self.status_label.setText(tr("place.waiting"))
        self.refresh_button.setEnabled(False)
        self._render_overview()
        self._clear_photos()
        self._render_sources()

    def _cancel_jobs(self) -> None:
        for _future, cancellation in self._jobs.values():
            cancellation.set()

    def retranslate_ui(self) -> None:
        self.eyebrow.setText(tr("place.eyebrow"))
        self.refresh_button.setText(tr("place.refresh"))
        self.tabs.setTabText(0, tr("place.overview"))
        self.tabs.setTabText(1, tr("place.photos"))
        self.tabs.setTabText(2, tr("place.sources"))
        if self._candidate is None:
            self._show_empty_state()
            return
        self.set_candidate(self._candidate)

    def shutdown(self) -> None:
        if self._shutdown:
            return
        self._shutdown = True
        self._cancel_jobs()
        self._executor.shutdown(wait=True, cancel_futures=True)
        self._jobs.clear()


def _escape(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def _short_label(value: str, maximum: int) -> str:
    normalized = " ".join(str(value or "").split())
    return (
        normalized
        if len(normalized) <= maximum
        else normalized[: maximum - 1].rstrip() + "…"
    )


def _open_url(url: str) -> None:
    parsed = QUrl(url)
    if parsed.scheme() == "https" and parsed.host():
        QDesktopServices.openUrl(parsed)
