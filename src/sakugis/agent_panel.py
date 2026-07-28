"""Dockable UI for the three-stage geolocation workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from qgis.PyQt.QtCore import QObject, QThread, Qt, pyqtSignal, pyqtSlot
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sakugis.agent_models import MAX_CASE_PHOTOS, Candidate, GeoAnalysisResult
from sakugis.credentials import (
    configured_model,
    has_api_key,
    has_brave_api_key,
)
from sakugis.geo_agents import GeoAgentPipeline
from sakugis.i18n import tr
from sakugis.postgis_provider import PostGISConfig


class AnalysisWorker(QObject):
    progress = pyqtSignal(int, str)
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, image_paths: list[str], query: str):
        super().__init__()
        self.image_paths = image_paths
        self.query = query

    @pyqtSlot()
    def run(self) -> None:
        try:
            result = GeoAgentPipeline().run(
                image_paths=self.image_paths,
                query=self.query,
                progress=self.progress.emit,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.completed.emit(result)


class AgentPanel(QWidget):
    analysisCompleted = pyqtSignal(object)
    candidateSelected = pyqtSignal(object)
    candidateActivated = pyqtSignal(object)
    reportExportRequested = pyqtSignal()
    settingsRequested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: Optional[QThread] = None
        self._worker: Optional[AnalysisWorker] = None
        self._image_paths: list[str] = []
        self._last_result: Optional[GeoAnalysisResult] = None
        self._build_ui()
        self._refresh_key_status()

    def _build_ui(self) -> None:
        self.setObjectName("AgentWorkspace")
        self.eyebrow_label = QLabel(tr("agent.eyebrow"), self)
        self.eyebrow_label.setObjectName("SectionEyebrow")
        self.workspace_title = QLabel(tr("agent.workspace_title"), self)
        self.workspace_title.setObjectName("SectionTitle")
        self.workspace_subtitle = QLabel(
            tr("agent.workspace_subtitle"), self
        )
        self.workspace_subtitle.setObjectName("MutedLabel")
        self.workspace_subtitle.setWordWrap(True)

        self.step_labels = [
            QLabel(tr("agent.step_evidence"), self),
            QLabel(tr("agent.step_candidates"), self),
            QLabel(tr("agent.step_verify"), self),
        ]
        step_row = QHBoxLayout()
        step_row.setSpacing(5)
        for label in self.step_labels:
            label.setAlignment(Qt.AlignCenter)
            label.setObjectName("StepIdle")
            step_row.addWidget(label, 1)

        self.photo_group = QGroupBox(tr("agent.photo"), self)
        self.photo_count_label = QLabel(self)
        self.photo_count_label.setObjectName("MutedLabel")
        self.choose_photo_button = QPushButton(tr("agent.add_photos"), self)
        self.choose_photo_button.clicked.connect(self._choose_photo)
        self.remove_photo_button = QPushButton(
            tr("agent.remove_selected"), self
        )
        self.remove_photo_button.clicked.connect(self._remove_selected_photos)
        self.clear_photo_button = QPushButton(tr("agent.clear_all"), self)
        self.clear_photo_button.clicked.connect(self._clear_photos)
        photo_row = QHBoxLayout()
        photo_row.addWidget(self.photo_count_label, 1)
        photo_row.addWidget(self.choose_photo_button)
        photo_row.addWidget(self.remove_photo_button)
        photo_row.addWidget(self.clear_photo_button)
        self.photo_list = QListWidget(self)
        self.photo_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.photo_list.setMaximumHeight(105)
        self.photo_list.currentItemChanged.connect(
            lambda current, _previous: self._show_photo_item(current)
        )
        self.preview = QLabel(tr("agent.no_photo"), self)
        self.preview.setObjectName("PhotoPreview")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumHeight(110)
        self.preview.setMaximumHeight(180)
        photo_layout = QVBoxLayout(self.photo_group)
        photo_layout.addLayout(photo_row)
        photo_layout.addWidget(self.photo_list)
        photo_layout.addWidget(self.preview)

        self.query_group = QGroupBox(tr("agent.query"), self)
        self.query_edit = QTextEdit(self)
        self.query_edit.setPlaceholderText(tr("agent.query_hint"))
        self.query_edit.setMaximumHeight(110)
        query_layout = QVBoxLayout(self.query_group)
        query_layout.addWidget(self.query_edit)

        self.service_group = QGroupBox(tr("agent.services"), self)
        service_layout = QVBoxLayout(self.service_group)
        service_layout.setContentsMargins(9, 8, 9, 8)
        service_layout.setSpacing(4)
        self.api_status = QLabel(self)
        self.brave_status = QLabel(self)
        self.gis_status = QLabel(self)
        self.settings_hint = QLabel(tr("agent.settings_hint"), self)
        self.settings_hint.setObjectName("MutedLabel")
        self.settings_hint.setWordWrap(True)
        service_layout.addWidget(self.api_status)
        service_layout.addWidget(self.brave_status)
        service_layout.addWidget(self.gis_status)
        service_layout.addWidget(self.settings_hint)

        run_row = QHBoxLayout()
        self.run_button = QPushButton(tr("agent.run"), self)
        self.run_button.setObjectName("PrimaryButton")
        self.run_button.setDefault(True)
        self.run_button.clicked.connect(self._start_analysis)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_label = QLabel(tr("agent.waiting"), self)
        self.progress_label.setObjectName("MutedLabel")
        run_row.addWidget(self.run_button)
        run_row.addWidget(self.progress_bar, 1)

        self.evidence_tree = QTreeWidget(self)
        self.evidence_tree.setHeaderLabels(
            [
                tr("agent.evidence"),
                tr("agent.content"),
                tr("agent.photos"),
                tr("agent.reliability"),
                tr("agent.source"),
            ]
        )
        self.evidence_tree.setRootIsDecorated(False)
        self.evidence_tree.setAlternatingRowColors(True)

        self.candidate_tree = QTreeWidget(self)
        self.candidate_tree.setHeaderLabels(
            [
                tr("agent.rank"),
                tr("agent.candidate"),
                tr("agent.place_lookup"),
                tr("agent.score"),
                tr("agent.evidence_score"),
                tr("agent.photo_match"),
                tr("agent.gis_score"),
                tr("agent.coverage"),
                tr("agent.range"),
            ]
        )
        self.candidate_tree.setRootIsDecorated(False)
        self.candidate_tree.setAlternatingRowColors(True)
        self.candidate_tree.itemSelectionChanged.connect(
            self._show_candidate_comparison
        )
        self.candidate_tree.itemDoubleClicked.connect(self._activate_candidate)

        self.gis_tree = QTreeWidget(self)
        self.gis_tree.setHeaderLabels(
            [
                tr("agent.candidate"),
                tr("agent.check"),
                tr("agent.result"),
                tr("agent.distance"),
                tr("agent.source"),
            ]
        )
        self.gis_tree.setRootIsDecorated(False)
        self.gis_tree.setAlternatingRowColors(True)

        self.tabs = QTabWidget(self)
        self.tabs.addTab(self.evidence_tree, tr("agent.evidence"))
        self.tabs.addTab(self.candidate_tree, tr("agent.candidates_tab"))
        self.tabs.addTab(self.gis_tree, tr("agent.gis_checks"))

        self.summary_browser = QTextBrowser(self)
        self.summary_browser.setOpenExternalLinks(True)
        self.summary_browser.setPlaceholderText(tr("agent.summary_hint"))
        self.result_splitter = QSplitter(Qt.Vertical, self)
        self.result_splitter.addWidget(self.tabs)
        self.result_splitter.addWidget(self.summary_browser)
        self.result_splitter.setStretchFactor(0, 3)
        self.result_splitter.setStretchFactor(1, 1)
        self.tabs.setMinimumHeight(170)

        self.export_button = QPushButton(tr("agent.export"), self)
        self.export_button.setObjectName("GhostButton")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(lambda: self.reportExportRequested.emit())
        self.new_search_button = QPushButton(tr("agent.new_search"), self)
        self.new_search_button.setObjectName("GhostButton")
        self.new_search_button.setVisible(False)
        self.new_search_button.clicked.connect(self._prepare_new_search)
        result_actions = QHBoxLayout()
        result_actions.addWidget(self.new_search_button)
        result_actions.addStretch(1)
        result_actions.addWidget(self.export_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addWidget(self.eyebrow_label)
        layout.addWidget(self.workspace_title)
        layout.addWidget(self.workspace_subtitle)
        layout.addLayout(step_row)
        layout.addWidget(self.photo_group)
        layout.addWidget(self.query_group)
        layout.addWidget(self.service_group)
        layout.addLayout(run_row)
        layout.addWidget(self.progress_label)
        layout.addWidget(self.result_splitter, 1)
        layout.addLayout(result_actions)

        self._refresh_gis_status()
        self._refresh_photo_list()
        self._set_step_state(0)

    def retranslate_ui(self) -> None:
        self.eyebrow_label.setText(tr("agent.eyebrow"))
        self.workspace_title.setText(tr("agent.workspace_title"))
        self.workspace_subtitle.setText(tr("agent.workspace_subtitle"))
        for label, key in zip(
            self.step_labels,
            (
                "agent.step_evidence",
                "agent.step_candidates",
                "agent.step_verify",
            ),
        ):
            label.setText(tr(key))
        self.photo_group.setTitle(tr("agent.photo"))
        self.choose_photo_button.setText(tr("agent.add_photos"))
        self.remove_photo_button.setText(tr("agent.remove_selected"))
        self.clear_photo_button.setText(tr("agent.clear_all"))
        self._refresh_photo_list()
        if not self._image_paths:
            self.preview.setText(tr("agent.no_photo"))
        self.query_group.setTitle(tr("agent.query"))
        self.query_edit.setPlaceholderText(tr("agent.query_hint"))
        self.service_group.setTitle(tr("agent.services"))
        self.settings_hint.setText(tr("agent.settings_hint"))
        self.run_button.setText(tr("agent.run"))
        self.export_button.setText(tr("agent.export"))
        self.new_search_button.setText(tr("agent.new_search"))
        self.evidence_tree.setHeaderLabels(
            [
                tr("agent.evidence"),
                tr("agent.content"),
                tr("agent.photos"),
                tr("agent.reliability"),
                tr("agent.source"),
            ]
        )
        self.candidate_tree.setHeaderLabels(
            [
                tr("agent.rank"),
                tr("agent.candidate"),
                tr("agent.place_lookup"),
                tr("agent.score"),
                tr("agent.evidence_score"),
                tr("agent.photo_match"),
                tr("agent.gis_score"),
                tr("agent.coverage"),
                tr("agent.range"),
            ]
        )
        self.gis_tree.setHeaderLabels(
            [
                tr("agent.candidate"),
                tr("agent.check"),
                tr("agent.result"),
                tr("agent.distance"),
                tr("agent.source"),
            ]
        )
        self.tabs.setTabText(0, tr("agent.evidence"))
        self.tabs.setTabText(1, tr("agent.candidates_tab"))
        self.tabs.setTabText(2, tr("agent.gis_checks"))
        self.summary_browser.setPlaceholderText(tr("agent.summary_hint"))
        if self._last_result is not None:
            self._show_result(self._last_result)
            if not self.is_busy():
                self.progress_label.setText(tr("agent.complete"))
        elif not self.is_busy():
            self.progress_label.setText(tr("agent.waiting"))
        self._refresh_key_status()
        self._refresh_gis_status()

    def focus_query(self) -> None:
        self.query_edit.setFocus(Qt.OtherFocusReason)

    def _prepare_new_search(self) -> None:
        self.photo_group.show()
        self.query_group.show()
        self.new_search_button.hide()
        self.focus_query()

    def _set_step_state(self, percent: int) -> None:
        if percent >= 100:
            active_index = 3
        elif percent >= 70:
            active_index = 2
        elif percent >= 35:
            active_index = 1
        elif percent > 0:
            active_index = 0
        else:
            active_index = -1
        for index, label in enumerate(self.step_labels):
            if index < active_index or active_index == 3:
                object_name = "StepDone"
            elif index == active_index:
                object_name = "StepActive"
            else:
                object_name = "StepIdle"
            if label.objectName() != object_name:
                label.setObjectName(object_name)
                label.style().unpolish(label)
                label.style().polish(label)

    def is_busy(self) -> bool:
        return bool(self._thread and self._thread.isRunning())

    def _choose_photo(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            tr("agent.choose_photo_title"),
            str(Path.home()),
            tr("agent.image_filter"),
        )
        if not paths:
            return
        previous_count = len(self._image_paths)
        for path in paths:
            if path not in self._image_paths:
                self._image_paths.append(path)
            if len(self._image_paths) >= MAX_CASE_PHOTOS:
                break
        selected = (
            self._image_paths[previous_count]
            if len(self._image_paths) > previous_count
            else self._image_paths[-1]
        )
        self._refresh_photo_list(selected)

    def _refresh_photo_list(self, selected_path: str = "") -> None:
        if not selected_path and self.photo_list.currentItem() is not None:
            selected_path = str(
                self.photo_list.currentItem().data(Qt.UserRole) or ""
            )
        self.photo_list.blockSignals(True)
        self.photo_list.clear()
        selected_row = -1
        for index, path in enumerate(self._image_paths, 1):
            photo_item = QListWidgetItem(f"P{index} · {Path(path).name}")
            photo_item.setData(Qt.UserRole, path)
            photo_item.setToolTip(path)
            self.photo_list.addItem(photo_item)
            if path == selected_path:
                selected_row = index - 1
        self.photo_list.blockSignals(False)
        self.photo_count_label.setText(
            tr(
                "agent.photo_count",
                count=len(self._image_paths),
                maximum=MAX_CASE_PHOTOS,
            )
        )
        has_photos = bool(self._image_paths)
        self.remove_photo_button.setEnabled(has_photos)
        self.clear_photo_button.setEnabled(has_photos)
        self.choose_photo_button.setEnabled(
            len(self._image_paths) < MAX_CASE_PHOTOS
        )
        if has_photos:
            self.photo_list.setCurrentRow(
                selected_row if selected_row >= 0 else 0
            )
        else:
            self.preview.setPixmap(QPixmap())
            self.preview.setText(tr("agent.no_photo"))

    def _show_photo_item(self, item) -> None:
        if item is None:
            return
        path = str(item.data(Qt.UserRole) or "")
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self.preview.setText(tr("agent.preview_failed"))
            self.preview.setPixmap(QPixmap())
        else:
            self.preview.setPixmap(
                pixmap.scaled(
                    self.preview.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )

    def _remove_selected_photos(self) -> None:
        selected = {
            str(item.data(Qt.UserRole) or "")
            for item in self.photo_list.selectedItems()
        }
        if not selected and self.photo_list.currentItem() is not None:
            selected.add(
                str(self.photo_list.currentItem().data(Qt.UserRole) or "")
            )
        self._image_paths = [
            path for path in self._image_paths if path not in selected
        ]
        self._refresh_photo_list()

    def _clear_photos(self) -> None:
        self._image_paths = []
        self._refresh_photo_list()

    def _refresh_key_status(self) -> None:
        if has_api_key():
            self.api_status.setText(
                tr("agent.key_ready", model=configured_model())
            )
            self.api_status.setObjectName("StatusGood")
        else:
            self.api_status.setText(tr("agent.key_missing"))
            self.api_status.setObjectName("StatusWarning")
        if has_brave_api_key():
            self.brave_status.setText(tr("agent.brave_ready"))
            self.brave_status.setObjectName("StatusGood")
        else:
            self.brave_status.setText(tr("agent.brave_optional"))
            self.brave_status.setObjectName("StatusInfo")
        for label in (self.api_status, self.brave_status):
            label.style().unpolish(label)
            label.style().polish(label)

    def _refresh_gis_status(self) -> None:
        if PostGISConfig.from_environment().enabled:
            self.gis_status.setText(tr("agent.gis_postgis"))
        else:
            self.gis_status.setText(tr("agent.gis_online"))
        self.gis_status.setObjectName("StatusInfo")
        self.gis_status.style().unpolish(self.gis_status)
        self.gis_status.style().polish(self.gis_status)

    def refresh_runtime_status(self) -> None:
        self._refresh_key_status()
        self._refresh_gis_status()

    def _start_analysis(self) -> None:
        if self.is_busy():
            return
        query = self.query_edit.toPlainText().strip()
        if not self._image_paths and not query:
            QMessageBox.information(
                self, tr("agent.input_needed"), tr("agent.input_needed_detail")
            )
            return
        if not has_api_key():
            self.settingsRequested.emit("qwen")
            return

        self.evidence_tree.clear()
        self.candidate_tree.clear()
        self.gis_tree.clear()
        self.summary_browser.clear()
        self._last_result = None
        self.photo_group.show()
        self.query_group.show()
        self.new_search_button.hide()
        self.export_button.setEnabled(False)
        self.progress_bar.setValue(1)
        self.progress_label.setText(tr("agent.starting"))
        self._set_step_state(1)
        self.run_button.setEnabled(False)

        self._thread = QThread(self)
        self._worker = AnalysisWorker(list(self._image_paths), query)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.completed.connect(self._on_completed)
        self._worker.failed.connect(self._on_failed)
        self._worker.completed.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._worker.completed.connect(self._worker.deleteLater)
        self._worker.failed.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._thread_finished)
        self._thread.start()

    @pyqtSlot(int, str)
    def _on_progress(self, percent: int, message: str) -> None:
        self.progress_bar.setValue(percent)
        self.progress_label.setText(message)
        self._set_step_state(percent)

    @pyqtSlot(object)
    def _on_completed(self, result: GeoAnalysisResult) -> None:
        self.progress_bar.setValue(100)
        self.progress_label.setText(tr("agent.complete"))
        self._set_step_state(100)
        self._last_result = result
        self.export_button.setEnabled(True)
        self.photo_group.hide()
        self.query_group.hide()
        self.new_search_button.show()
        self._show_result(result)
        self.analysisCompleted.emit(result)

    @pyqtSlot(str)
    def _on_failed(self, message: str) -> None:
        self.progress_label.setText(tr("agent.analysis_failed"))
        self._set_step_state(0)
        QMessageBox.critical(
            self,
            tr("agent.analysis_failed_title"),
            message or tr("agent.unknown_error"),
        )

    @pyqtSlot()
    def _thread_finished(self) -> None:
        self.run_button.setEnabled(True)
        self._worker = None
        self._thread = None

    def _show_result(self, result: GeoAnalysisResult) -> None:
        self._last_result = result
        self.evidence_tree.clear()
        self.candidate_tree.clear()
        self.gis_tree.clear()
        self.summary_browser.clear()
        self.export_button.setEnabled(True)
        self.photo_group.hide()
        self.query_group.hide()
        self.new_search_button.show()
        self.result_splitter.setSizes([250, 125])
        for evidence in result.evidence:
            item = QTreeWidgetItem(
                [
                    evidence.kind,
                    evidence.value,
                    ", ".join(evidence.photo_ids) or "—",
                    f"{evidence.reliability * 100:.0f}%",
                    evidence.source,
                ]
            )
            item.setToolTip(1, evidence.value)
            item.setToolTip(
                0,
                "\n".join(
                    part
                    for part in (
                        f"ID: {evidence.evidence_id}",
                        (
                            f"Group: {evidence.correlation_group}"
                            if evidence.correlation_group
                            else ""
                        ),
                        (
                            "Supports: " + ", ".join(evidence.supports)
                            if evidence.supports
                            else ""
                        ),
                        (
                            "Contradicts: "
                            + ", ".join(evidence.contradicts)
                            if evidence.contradicts
                            else ""
                        ),
                    )
                    if part
                ),
            )
            self.evidence_tree.addTopLevelItem(item)
        self.evidence_tree.resizeColumnToContents(0)
        self.evidence_tree.resizeColumnToContents(2)
        self.evidence_tree.resizeColumnToContents(3)

        for index, candidate in enumerate(result.candidates, 1):
            location = " · ".join(
                part
                for part in [candidate.name, candidate.region, candidate.country]
                if part
            )
            item = QTreeWidgetItem(
                [
                    str(index),
                    location,
                    (
                        f"{candidate.retrieval_score * 100:.0f}/100 ✓"
                        if candidate.retrieval_verified
                        else tr("agent.lookup_fallback")
                    ),
                    f"{candidate.ranking_score * 100:.0f}/100",
                    f"{candidate.model_verification_score * 100:.0f}/100",
                    (
                        f"{candidate.photo_support_count}/"
                        f"{candidate.photo_total_count}"
                        if candidate.photo_total_count > 1
                        else "—"
                    ),
                    f"{candidate.gis_score * 100:.0f}/100",
                    f"{candidate.gis_coverage * 100:.0f}%",
                    f"±{candidate.radius_km:,.0f} km",
                ]
            )
            item.setData(0, Qt.UserRole, candidate)
            components = candidate.ranking_components
            score_detail = ""
            if components:
                score_detail = "\n" + self._score_formula(candidate)
            item.setToolTip(
                1,
                (
                    f"{candidate.latitude:.6f}, {candidate.longitude:.6f}\n"
                    f"{candidate.rationale}\n{candidate.reverse_label}"
                    f"\n{candidate.retrieval_source}: "
                    f"{candidate.retrieval_label or '—'}"
                    f"{score_detail}"
                ),
            )
            self.candidate_tree.addTopLevelItem(item)
            for check in candidate.gis_checks:
                if check.matched is True:
                    check_result = tr("agent.passed")
                elif check.matched is False:
                    check_result = tr("agent.failed")
                else:
                    check_result = tr("agent.unavailable")
                distance = (
                    f"{check.nearest_distance_km:,.1f} km"
                    if check.nearest_distance_km is not None
                    else "—"
                )
                check_item = QTreeWidgetItem(
                    [
                        candidate.name,
                        tr(f"gis.{check.check_id}"),
                        check_result,
                        distance,
                        check.source,
                    ]
                )
                check_item.setToolTip(1, check.detail)
                self.gis_tree.addTopLevelItem(check_item)
        self.candidate_tree.resizeColumnToContents(0)
        self.candidate_tree.resizeColumnToContents(2)
        self.candidate_tree.resizeColumnToContents(3)
        self.candidate_tree.resizeColumnToContents(4)
        self.candidate_tree.resizeColumnToContents(5)
        self.candidate_tree.resizeColumnToContents(6)
        self.candidate_tree.resizeColumnToContents(7)
        self.candidate_tree.resizeColumnToContents(8)
        self.gis_tree.resizeColumnToContents(1)
        self.gis_tree.resizeColumnToContents(2)
        self.gis_tree.resizeColumnToContents(3)

        self.summary_browser.setHtml(self._overall_summary_html(result))
        if self.candidate_tree.topLevelItemCount():
            self.candidate_tree.setCurrentItem(
                self.candidate_tree.topLevelItem(0)
            )

    def _overall_summary_html(self, result: GeoAnalysisResult) -> str:
        return (
            f"<h4>{self._escape(tr('agent.verification_summary'))}</h4>"
            f"<p>{self._escape(result.verification_summary)}</p>"
            f"<p><b>{self._escape(tr('agent.important'))}</b>"
            f"{self._escape(result.caveat)}</p>"
            "<p>"
            + self._escape(
                tr(
                    "agent.model_note",
                    model=result.model,
                    retrieval=result.retrieval_backend,
                    backend=result.gis_backend,
                )
            )
            + "</p>"
        )

    def _show_candidate_comparison(self) -> None:
        if self._last_result is None:
            return
        items = self.candidate_tree.selectedItems()
        if not items:
            self.summary_browser.setHtml(
                self._overall_summary_html(self._last_result)
            )
            return
        candidate = items[0].data(0, Qt.UserRole)
        if not isinstance(candidate, Candidate):
            return
        self.candidateSelected.emit(candidate)
        support = self._supporting_evidence_text(candidate)
        contradictions = "; ".join(candidate.contradictions) or "—"
        photo_match = (
            f"{candidate.photo_support_count}/{candidate.photo_total_count}"
            if candidate.photo_total_count > 1
            else "—"
        )
        self.summary_browser.setHtml(
            f"<h4>{self._escape(candidate.name)}</h4>"
            f"<p><b>{self._escape(tr('agent.score'))}:</b> "
            f"{candidate.ranking_score * 100:.1f}/100 &nbsp; "
            f"<b>{self._escape(tr('agent.evidence_score'))}:</b> "
            f"{candidate.model_verification_score * 100:.1f}/100 &nbsp; "
            f"<b>{self._escape(tr('agent.photo_match'))}:</b> "
            f"{self._escape(photo_match)} &nbsp; "
            f"<b>{self._escape(tr('agent.gis_score'))}:</b> "
            f"{candidate.gis_score * 100:.1f}/100</p>"
            f"<p><b>{self._escape(tr('report.reverse'))}:</b> "
            f"{self._escape(candidate.reverse_label or '—')}</p>"
            f"<p><b>{self._escape(tr('report.place_lookup'))}:</b> "
            f"{self._escape(candidate.retrieval_source or '—')} · "
            f"{self._escape(candidate.retrieval_label or '—')} "
            f"({candidate.retrieval_score * 100:.1f}/100)<br>"
            f"<b>{self._escape(tr('report.lookup_query'))}:</b> "
            f"{self._escape(candidate.retrieval_query or '—')}</p>"
            f"<p><b>{self._escape(tr('report.rationale'))}:</b> "
            f"{self._escape(candidate.rationale or '—')}</p>"
            f"<p><b>{self._escape(tr('report.support'))}:</b> "
            f"{self._escape(support)}<br>"
            f"<b>{self._escape(tr('report.contradictions'))}:</b> "
            f"{self._escape(contradictions)}</p>"
            f"<p>{self._escape(self._score_formula(candidate))}</p>"
            f"<p><i>{self._escape(tr('agent.double_click_hint'))}</i></p>"
        )

    def _supporting_evidence_text(self, candidate: Candidate) -> str:
        if self._last_result is None:
            return ", ".join(candidate.supporting_evidence) or "—"
        by_id = {
            item.evidence_id: item for item in self._last_result.evidence
        }
        details = []
        for evidence_id in candidate.supporting_evidence:
            evidence = by_id.get(evidence_id)
            if evidence is None:
                details.append(evidence_id)
                continue
            photos = "/".join(evidence.photo_ids)
            provenance = f" [{photos}]" if photos else ""
            details.append(
                f"{evidence_id}{provenance}: {evidence.value}"
            )
        return "; ".join(details) or "—"

    @staticmethod
    def _score_formula(candidate: Candidate) -> str:
        components = candidate.ranking_components
        key = (
            "report.score_formula_multi"
            if candidate.photo_total_count > 1
            else "report.score_formula"
        )
        return tr(
            key,
            retrieval=f"{components.get('retrieval', 0.0) * 100:.1f}",
            model_candidate=(
                f"{components.get('model_candidate', 0.0) * 100:.1f}"
            ),
            place_lookup=(
                f"{components.get('place_lookup', 0.0) * 100:.1f}"
            ),
            model=f"{components.get('model', 0.0) * 100:.1f}",
            effective_model=f"{components.get('effective_model', 0.0) * 100:.1f}",
            confidence=f"{components.get('evidence_confidence', 0.0) * 100:.0f}",
            photo=(
                f"{components.get('effective_photo_consistency', 0.0) * 100:.0f}"
            ),
            gis=f"{components.get('gis', 0.0) * 100:.1f}",
            effective_gis=f"{components.get('effective_gis', 0.0) * 100:.1f}",
            coverage=f"{components.get('gis_coverage', 0.0) * 100:.0f}",
            penalty=f"{components.get('contradiction_penalty', 0.0) * 100:.1f}",
        )

    def _activate_candidate(self, item: QTreeWidgetItem, _column: int) -> None:
        candidate = item.data(0, Qt.UserRole)
        if isinstance(candidate, Candidate):
            self.candidateActivated.emit(candidate)

    def select_candidate(self, candidate: Candidate) -> bool:
        for index in range(self.candidate_tree.topLevelItemCount()):
            item = self.candidate_tree.topLevelItem(index)
            stored = item.data(0, Qt.UserRole)
            if (
                isinstance(stored, Candidate)
                and stored.candidate_id == candidate.candidate_id
            ):
                self.tabs.setCurrentWidget(self.candidate_tree)
                if self.candidate_tree.currentItem() is item:
                    self.candidateSelected.emit(stored)
                else:
                    self.candidate_tree.setCurrentItem(item)
                self.candidate_tree.scrollToItem(item)
                return True
        return False

    @staticmethod
    def _escape(value: str) -> str:
        return (
            str(value)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
