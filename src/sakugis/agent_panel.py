"""Dockable UI for the three-stage geolocation workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from qgis.PyQt.QtCore import QObject, QThread, Qt, pyqtSignal, pyqtSlot
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
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

from sakugis.agent_models import Candidate, GeoAnalysisResult
from sakugis.credentials import (
    CredentialError,
    configured_model,
    has_api_key,
    import_profile_csv,
    store_postgis_dsn,
)
from sakugis.geo_agents import GeoAgentPipeline
from sakugis.i18n import tr
from sakugis.postgis_provider import PostGISConfig


class AnalysisWorker(QObject):
    progress = pyqtSignal(int, str)
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, image_path: str, query: str):
        super().__init__()
        self.image_path = image_path
        self.query = query

    @pyqtSlot()
    def run(self) -> None:
        try:
            result = GeoAgentPipeline().run(
                image_path=self.image_path,
                query=self.query,
                progress=self.progress.emit,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.completed.emit(result)


class AgentPanel(QWidget):
    analysisCompleted = pyqtSignal(object)
    candidateActivated = pyqtSignal(object)
    reportExportRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: Optional[QThread] = None
        self._worker: Optional[AnalysisWorker] = None
        self._image_path = ""
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
        self.image_path_edit = QLineEdit(self)
        self.image_path_edit.setReadOnly(True)
        self.image_path_edit.setPlaceholderText(tr("agent.photo_optional"))
        self.choose_photo_button = QPushButton(tr("agent.choose"), self)
        self.choose_photo_button.clicked.connect(self._choose_photo)
        self.clear_photo_button = QPushButton(tr("agent.clear"), self)
        self.clear_photo_button.clicked.connect(self._clear_photo)
        photo_row = QHBoxLayout()
        photo_row.addWidget(self.image_path_edit, 1)
        photo_row.addWidget(self.choose_photo_button)
        photo_row.addWidget(self.clear_photo_button)
        self.preview = QLabel(tr("agent.no_photo"), self)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumHeight(110)
        self.preview.setMaximumHeight(180)
        self.preview.setStyleSheet(
            "QLabel { background: #091522; border: 1px dashed #31516D; "
            "border-radius: 8px; color: #7F98AB; }"
        )
        photo_layout = QVBoxLayout(self.photo_group)
        photo_layout.addLayout(photo_row)
        photo_layout.addWidget(self.preview)

        self.query_group = QGroupBox(tr("agent.query"), self)
        self.query_edit = QTextEdit(self)
        self.query_edit.setPlaceholderText(tr("agent.query_hint"))
        self.query_edit.setMaximumHeight(110)
        query_layout = QVBoxLayout(self.query_group)
        query_layout.addWidget(self.query_edit)

        api_row = QHBoxLayout()
        self.api_status = QLabel(self)
        self.import_key_button = QPushButton(tr("agent.import_key"), self)
        self.import_key_button.clicked.connect(self._import_api_key)
        api_row.addWidget(self.api_status, 1)
        api_row.addWidget(self.import_key_button)
        self.gis_status = QLabel(self)
        self.configure_postgis_button = QPushButton(
            tr("agent.configure_postgis"), self
        )
        self.configure_postgis_button.clicked.connect(self._configure_postgis)
        gis_row = QHBoxLayout()
        gis_row.addWidget(self.gis_status, 1)
        gis_row.addWidget(self.configure_postgis_button)

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
                tr("agent.score"),
                tr("agent.coverage"),
                tr("agent.range"),
            ]
        )
        self.candidate_tree.setRootIsDecorated(False)
        self.candidate_tree.setAlternatingRowColors(True)
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
        layout.addLayout(api_row)
        layout.addLayout(gis_row)
        layout.addLayout(run_row)
        layout.addWidget(self.progress_label)
        layout.addWidget(self.result_splitter, 1)
        layout.addLayout(result_actions)

        self._refresh_gis_status()
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
        self.image_path_edit.setPlaceholderText(tr("agent.photo_optional"))
        self.choose_photo_button.setText(tr("agent.choose"))
        self.clear_photo_button.setText(tr("agent.clear"))
        if not self._image_path:
            self.preview.setText(tr("agent.no_photo"))
        self.query_group.setTitle(tr("agent.query"))
        self.query_edit.setPlaceholderText(tr("agent.query_hint"))
        self.import_key_button.setText(tr("agent.import_key"))
        self.configure_postgis_button.setText(tr("agent.configure_postgis"))
        self.run_button.setText(tr("agent.run"))
        self.export_button.setText(tr("agent.export"))
        self.new_search_button.setText(tr("agent.new_search"))
        self.evidence_tree.setHeaderLabels(
            [
                tr("agent.evidence"),
                tr("agent.content"),
                tr("agent.reliability"),
                tr("agent.source"),
            ]
        )
        self.candidate_tree.setHeaderLabels(
            [
                tr("agent.rank"),
                tr("agent.candidate"),
                tr("agent.score"),
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
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("agent.choose_photo_title"),
            str(Path.home()),
            tr("agent.image_filter"),
        )
        if not path:
            return
        self._image_path = path
        self.image_path_edit.setText(path)
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

    def _clear_photo(self) -> None:
        self._image_path = ""
        self.image_path_edit.clear()
        self.preview.setPixmap(QPixmap())
        self.preview.setText(tr("agent.no_photo"))

    def _import_api_key(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("agent.import_title"),
            str(Path.home()),
            tr("agent.csv_filter"),
        )
        if not path:
            return
        try:
            import_profile_csv(path)
        except CredentialError as exc:
            QMessageBox.critical(self, tr("agent.key_import_failed"), str(exc))
            return
        self._refresh_key_status()
        QMessageBox.information(
            self,
            tr("agent.key_imported"),
            tr("agent.key_imported_detail"),
        )

    def _refresh_key_status(self) -> None:
        if has_api_key():
            self.api_status.setText(
                tr("agent.key_ready", model=configured_model())
            )
            self.api_status.setObjectName("StatusGood")
        else:
            self.api_status.setText(tr("agent.key_missing"))
            self.api_status.setObjectName("StatusWarning")
        self.api_status.style().unpolish(self.api_status)
        self.api_status.style().polish(self.api_status)

    def _refresh_gis_status(self) -> None:
        if PostGISConfig.from_environment().enabled:
            self.gis_status.setText(tr("agent.gis_postgis"))
        else:
            self.gis_status.setText(tr("agent.gis_online"))
        self.gis_status.setObjectName("StatusInfo")
        self.gis_status.style().unpolish(self.gis_status)
        self.gis_status.style().polish(self.gis_status)

    def _configure_postgis(self) -> None:
        dsn, accepted = QInputDialog.getText(
            self,
            tr("agent.postgis_title"),
            tr("agent.postgis_prompt"),
            QLineEdit.Password,
        )
        if not accepted or not dsn.strip():
            return
        try:
            store_postgis_dsn(dsn)
        except CredentialError as exc:
            QMessageBox.critical(self, tr("agent.postgis_failed"), str(exc))
            return
        self._refresh_gis_status()
        QMessageBox.information(
            self,
            tr("agent.postgis_title"),
            tr("agent.postgis_saved"),
        )

    def _start_analysis(self) -> None:
        if self.is_busy():
            return
        query = self.query_edit.toPlainText().strip()
        if not self._image_path and not query:
            QMessageBox.information(
                self, tr("agent.input_needed"), tr("agent.input_needed_detail")
            )
            return
        if not has_api_key():
            QMessageBox.warning(
                self,
                tr("agent.key_required"),
                tr("agent.key_required_detail"),
            )
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
        self._worker = AnalysisWorker(self._image_path, query)
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
                    f"{evidence.reliability * 100:.0f}%",
                    evidence.source,
                ]
            )
            item.setToolTip(1, evidence.value)
            self.evidence_tree.addTopLevelItem(item)
        self.evidence_tree.resizeColumnToContents(0)
        self.evidence_tree.resizeColumnToContents(2)

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
                    f"{candidate.ranking_score * 100:.0f}/100",
                    f"{candidate.gis_coverage * 100:.0f}%",
                    f"±{candidate.radius_km:,.0f} km",
                ]
            )
            item.setData(0, Qt.UserRole, candidate)
            components = candidate.ranking_components
            score_detail = ""
            if components:
                score_detail = "\n" + tr(
                    "report.score_formula",
                    retrieval=f"{components.get('retrieval', 0.0) * 100:.1f}",
                    model=f"{components.get('model', 0.0) * 100:.1f}",
                    effective_model=f"{components.get('effective_model', 0.0) * 100:.1f}",
                    confidence=f"{components.get('evidence_confidence', 0.0) * 100:.0f}",
                    gis=f"{components.get('gis', 0.0) * 100:.1f}",
                    effective_gis=f"{components.get('effective_gis', 0.0) * 100:.1f}",
                    coverage=f"{components.get('gis_coverage', 0.0) * 100:.0f}",
                    penalty=f"{components.get('contradiction_penalty', 0.0) * 100:.1f}",
                )
            item.setToolTip(
                1,
                (
                    f"{candidate.latitude:.6f}, {candidate.longitude:.6f}\n"
                    f"{candidate.rationale}\n{candidate.reverse_label}"
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
        self.gis_tree.resizeColumnToContents(1)
        self.gis_tree.resizeColumnToContents(2)
        self.gis_tree.resizeColumnToContents(3)

        self.summary_browser.setHtml(
            f"<h4>{self._escape(tr('agent.verification_summary'))}</h4>"
            f"<p>{self._escape(result.verification_summary)}</p>"
            f"<p><b>{self._escape(tr('agent.important'))}</b>"
            f"{self._escape(result.caveat)}</p>"
            "<p>"
            + self._escape(
                tr(
                    "agent.model_note",
                    model=result.model,
                    backend=result.gis_backend,
                )
            )
            + "</p>"
        )

    def _activate_candidate(self, item: QTreeWidgetItem, _column: int) -> None:
        candidate = item.data(0, Qt.UserRole)
        if isinstance(candidate, Candidate):
            self.candidateActivated.emit(candidate)

    @staticmethod
    def _escape(value: str) -> str:
        return (
            str(value)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
