"""Unified bilingual settings dialog for SakuGIS."""

from __future__ import annotations

import os
from typing import Dict

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFrame,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from qgis.core import QgsSettings

from sakugis.app_settings import save_runtime_settings
from sakugis.credentials import (
    CredentialError,
    configured_base_url,
    configured_brave_timeout,
    configured_candidate_limit,
    configured_model,
    configured_kimi_base_url,
    configured_kimi_model,
    configured_kimi_reasoning_effort,
    configured_kimi_timeout,
    configured_prompt_char_limit,
    configured_qwen_temperature,
    configured_qwen_timeout,
    has_api_key,
    has_brave_api_key,
    has_kimi_api_key,
    has_postgis_dsn,
    store_api_key,
    store_brave_api_key,
    store_kimi_api_key,
    store_postgis_dsn,
)
from sakugis.i18n import EN, ZH_CN, get_language, tr
from sakugis.model_provider import KIMI, QWEN, configured_provider
from sakugis.ui_theme import DARK, LIGHT, get_theme


class SettingsDialog(QDialog):
    """Central settings UI; secrets are written only to macOS Keychain."""

    settingsApplied = pyqtSignal(object)

    def __init__(self, parent=None, required_section: str = ""):
        super().__init__(parent)
        self._required_section = required_section
        self.setWindowTitle(tr("settings.title"))
        self.setModal(True)
        self.resize(820, 760)
        self.setMinimumSize(680, 580)
        self._build_ui()

    def _build_ui(self) -> None:
        self.tabs = QTabWidget(self)
        self.tabs.addTab(
            self._scrollable_tab(self._build_api_tab()),
            tr("settings.api_tab"),
        )
        self.tabs.addTab(
            self._scrollable_tab(self._build_model_tab()),
            tr("settings.model_tab"),
        )
        self.tabs.addTab(
            self._scrollable_tab(self._build_gis_tab()),
            tr("settings.gis_tab"),
        )
        self.tabs.addTab(
            self._scrollable_tab(self._build_interface_tab()),
            tr("settings.interface_tab"),
        )

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel,
            parent=self,
        )
        self.button_box.button(QDialogButtonBox.Save).setText(
            tr("settings.save")
        )
        self.button_box.button(QDialogButtonBox.Cancel).setText(
            tr("settings.cancel")
        )
        self.button_box.button(QDialogButtonBox.Save).setObjectName(
            "PrimaryButton"
        )
        self.button_box.button(QDialogButtonBox.Save).clicked.connect(
            self._save
        )
        self.button_box.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 16)
        layout.setSpacing(12)
        layout.addWidget(self.tabs, 1)
        layout.addWidget(self.button_box)

        # QGIS' macOS theme can otherwise shrink form controls until their text
        # is clipped when a tab contains several groups. Keep every editable
        # field comfortably readable; the tab scroll areas handle small windows.
        for edit in self.findChildren(QLineEdit):
            edit.setMinimumHeight(36)
        for combo in self.findChildren(QComboBox):
            combo.setMinimumHeight(36)
        for spin in self.findChildren(QAbstractSpinBox):
            spin.setMinimumHeight(36)

        if self._required_section in {"qwen", "model"}:
            self.tabs.setCurrentIndex(0)
            if configured_provider() == KIMI:
                self.kimi_key_edit.setFocus()
            else:
                self.qwen_key_edit.setFocus()

    @staticmethod
    def _scrollable_tab(content: QWidget) -> QScrollArea:
        """Keep tab contents at their readable size instead of compressing."""

        content.layout().setSizeConstraint(QLayout.SetMinimumSize)
        content.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setWidget(content)
        return scroll

    def _build_api_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setSpacing(12)

        provider_group = QGroupBox(tr("settings.provider_group"), tab)
        provider_layout = QFormLayout(provider_group)
        self.provider_combo = QComboBox(provider_group)
        self.provider_combo.addItem("通义千问 / Qwen", QWEN)
        self.provider_combo.addItem("Kimi K3", KIMI)
        provider_index = self.provider_combo.findData(configured_provider())
        self.provider_combo.setCurrentIndex(max(0, provider_index))
        provider_layout.addRow(tr("settings.provider"), self.provider_combo)

        qwen_group = QGroupBox(tr("settings.qwen_group"), tab)
        qwen_layout = QFormLayout(qwen_group)
        self.qwen_status = self._status_label(
            has_api_key(),
            tr("settings.configured"),
            tr("settings.provider_missing"),
        )
        self.qwen_key_edit = self._secret_edit(
            (
                tr("settings.keep_existing")
                if has_api_key()
                else tr("settings.enter_required")
            )
        )
        qwen_layout.addRow(tr("settings.status"), self.qwen_status)
        self.qwen_base_url_edit = QLineEdit(configured_base_url(), qwen_group)
        self.qwen_base_url_edit.setClearButtonEnabled(True)
        self.qwen_base_url_edit.setCursorPosition(0)
        qwen_layout.addRow(tr("settings.qwen_base_url"), self.qwen_base_url_edit)
        qwen_layout.addRow(tr("settings.qwen_key"), self.qwen_key_edit)
        qwen_note = QLabel(tr("settings.qwen_note"), qwen_group)
        qwen_note.setObjectName("MutedLabel")
        qwen_note.setWordWrap(True)
        qwen_layout.addRow("", qwen_note)

        kimi_group = QGroupBox(tr("settings.kimi_group"), tab)
        kimi_layout = QFormLayout(kimi_group)
        self.kimi_status = self._status_label(
            has_kimi_api_key(),
            tr("settings.configured"),
            tr("settings.provider_missing"),
        )
        self.kimi_key_edit = self._secret_edit(
            tr("settings.keep_existing")
            if has_kimi_api_key()
            else tr("settings.enter_kimi")
        )
        self.kimi_base_url_edit = QLineEdit(
            configured_kimi_base_url(), kimi_group
        )
        self.kimi_base_url_edit.setClearButtonEnabled(True)
        self.kimi_base_url_edit.setCursorPosition(0)
        kimi_layout.addRow(tr("settings.status"), self.kimi_status)
        kimi_layout.addRow(
            tr("settings.kimi_base_url"), self.kimi_base_url_edit
        )
        kimi_layout.addRow(tr("settings.kimi_key"), self.kimi_key_edit)
        kimi_note = QLabel(tr("settings.kimi_note"), kimi_group)
        kimi_note.setObjectName("MutedLabel")
        kimi_note.setWordWrap(True)
        kimi_layout.addRow("", kimi_note)

        brave_group = QGroupBox(tr("settings.brave_group"), tab)
        brave_layout = QFormLayout(brave_group)
        self.brave_status = self._status_label(
            has_brave_api_key(),
            tr("settings.configured"),
            tr("settings.optional_missing"),
        )
        self.brave_key_edit = self._secret_edit(
            (
                tr("settings.keep_existing")
                if has_brave_api_key()
                else tr("settings.enter_optional")
            )
        )
        self.brave_timeout_spin = QSpinBox(brave_group)
        self.brave_timeout_spin.setRange(3, 30)
        self.brave_timeout_spin.setSuffix(tr("settings.seconds_suffix"))
        self.brave_timeout_spin.setValue(configured_brave_timeout())
        brave_layout.addRow(tr("settings.status"), self.brave_status)
        brave_layout.addRow(tr("settings.brave_key"), self.brave_key_edit)
        brave_layout.addRow(
            tr("settings.request_timeout"), self.brave_timeout_spin
        )
        brave_note = QLabel(tr("settings.brave_note"), brave_group)
        brave_note.setObjectName("MutedLabel")
        brave_note.setWordWrap(True)
        brave_layout.addRow("", brave_note)

        security_note = QLabel(tr("settings.keychain_note"), tab)
        security_note.setObjectName("StatusInfo")
        security_note.setWordWrap(True)

        layout.addWidget(provider_group)
        layout.addWidget(qwen_group)
        layout.addWidget(kimi_group)
        layout.addWidget(brave_group)
        layout.addWidget(security_note)
        layout.addStretch(1)
        return tab

    def _build_model_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 14, 12, 12)

        qwen_group = QGroupBox(tr("settings.qwen_model_group"), tab)
        qwen_form = QFormLayout(qwen_group)
        self.model_combo = QComboBox(qwen_group)
        self.model_combo.setEditable(True)
        self.model_combo.addItems(
            [
                "qwen3.7-plus",
                "qwen3-vl-plus",
                "qwen-vl-max",
            ]
        )
        current_model = configured_model()
        if self.model_combo.findText(current_model) < 0:
            self.model_combo.addItem(current_model)
        self.model_combo.setCurrentText(current_model)

        self.temperature_spin = QDoubleSpinBox(qwen_group)
        self.temperature_spin.setRange(0.0, 1.0)
        self.temperature_spin.setSingleStep(0.05)
        self.temperature_spin.setDecimals(2)
        self.temperature_spin.setValue(configured_qwen_temperature())

        self.qwen_timeout_spin = QSpinBox(qwen_group)
        self.qwen_timeout_spin.setRange(30, 300)
        self.qwen_timeout_spin.setSuffix(tr("settings.seconds_suffix"))
        self.qwen_timeout_spin.setValue(configured_qwen_timeout())

        qwen_form.addRow(tr("settings.model"), self.model_combo)
        qwen_form.addRow(tr("settings.temperature"), self.temperature_spin)
        qwen_form.addRow(
            tr("settings.request_timeout"), self.qwen_timeout_spin
        )

        kimi_group = QGroupBox(tr("settings.kimi_model_group"), tab)
        kimi_form = QFormLayout(kimi_group)
        self.kimi_model_edit = QLineEdit(configured_kimi_model(), kimi_group)
        self.kimi_effort_combo = QComboBox(kimi_group)
        self.kimi_effort_combo.addItem("Low", "low")
        self.kimi_effort_combo.addItem("High", "high")
        self.kimi_effort_combo.addItem("Max", "max")
        effort_index = self.kimi_effort_combo.findData(
            configured_kimi_reasoning_effort()
        )
        self.kimi_effort_combo.setCurrentIndex(max(0, effort_index))
        self.kimi_timeout_spin = QSpinBox(kimi_group)
        self.kimi_timeout_spin.setRange(30, 600)
        self.kimi_timeout_spin.setSuffix(tr("settings.seconds_suffix"))
        self.kimi_timeout_spin.setValue(configured_kimi_timeout())
        kimi_form.addRow(tr("settings.model"), self.kimi_model_edit)
        kimi_form.addRow(
            tr("settings.reasoning_effort"), self.kimi_effort_combo
        )
        kimi_form.addRow(
            tr("settings.request_timeout"), self.kimi_timeout_spin
        )

        agent_group = QGroupBox(tr("settings.agent_parameters"), tab)
        form = QFormLayout(agent_group)
        self.prompt_limit_spin = QSpinBox(agent_group)
        self.prompt_limit_spin.setRange(8000, 120000)
        self.prompt_limit_spin.setSingleStep(1000)
        self.prompt_limit_spin.setValue(configured_prompt_char_limit())

        self.candidate_limit_spin = QSpinBox(agent_group)
        self.candidate_limit_spin.setRange(1, 12)
        self.candidate_limit_spin.setValue(configured_candidate_limit())

        form.addRow(tr("settings.prompt_limit"), self.prompt_limit_spin)
        form.addRow(
            tr("settings.candidate_limit"), self.candidate_limit_spin
        )

        note = QLabel(tr("settings.model_note"), tab)
        note.setObjectName("MutedLabel")
        note.setWordWrap(True)
        layout.addWidget(qwen_group)
        layout.addWidget(kimi_group)
        layout.addWidget(agent_group)
        layout.addWidget(note)
        layout.addStretch(1)
        return tab

    def _build_gis_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setSpacing(12)

        group = QGroupBox(tr("settings.postgis_group"), tab)
        form = QFormLayout(group)
        self.postgis_status = self._status_label(
            has_postgis_dsn(),
            tr("settings.configured"),
            tr("settings.optional_missing"),
        )
        self.postgis_dsn_edit = self._secret_edit(
            (
                tr("settings.keep_existing")
                if has_postgis_dsn()
                else tr("settings.postgis_placeholder")
            )
        )
        form.addRow(tr("settings.status"), self.postgis_status)
        form.addRow(tr("settings.postgis_dsn"), self.postgis_dsn_edit)
        note = QLabel(tr("settings.postgis_note"), group)
        note.setObjectName("MutedLabel")
        note.setWordWrap(True)
        form.addRow("", note)
        layout.addWidget(group)
        layout.addStretch(1)
        return tab

    def _build_interface_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 14, 12, 12)

        group = QGroupBox(tr("settings.interface_group"), tab)
        form = QFormLayout(group)
        self.language_combo = QComboBox(group)
        self.language_combo.addItem(tr("language.chinese"), ZH_CN)
        self.language_combo.addItem(tr("language.english"), EN)
        language_index = self.language_combo.findData(get_language())
        self.language_combo.setCurrentIndex(max(0, language_index))

        self.theme_combo = QComboBox(group)
        self.theme_combo.addItem(tr("theme.light"), LIGHT)
        self.theme_combo.addItem(tr("theme.dark"), DARK)
        theme_index = self.theme_combo.findData(get_theme())
        self.theme_combo.setCurrentIndex(max(0, theme_index))

        form.addRow(tr("settings.language"), self.language_combo)
        form.addRow(tr("settings.theme"), self.theme_combo)
        note = QLabel(tr("settings.interface_note"), group)
        note.setObjectName("MutedLabel")
        note.setWordWrap(True)
        form.addRow("", note)
        layout.addWidget(group)
        layout.addStretch(1)
        return tab

    @staticmethod
    def _secret_edit(placeholder: str) -> QLineEdit:
        edit = QLineEdit()
        edit.setEchoMode(QLineEdit.Password)
        edit.setClearButtonEnabled(True)
        edit.setPlaceholderText(placeholder)
        return edit

    @staticmethod
    def _status_label(
        configured: bool, configured_text: str, missing_text: str
    ) -> QLabel:
        label = QLabel(configured_text if configured else missing_text)
        label.setObjectName("StatusGood" if configured else "StatusWarning")
        label.setMinimumHeight(34)
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        return label

    def _save(self) -> None:
        qwen_key = self.qwen_key_edit.text().strip()
        kimi_key = self.kimi_key_edit.text().strip()
        brave_key = self.brave_key_edit.text().strip()
        postgis_dsn = self.postgis_dsn_edit.text().strip()
        provider = str(self.provider_combo.currentData())
        active_missing = (
            provider == KIMI and not has_kimi_api_key() and not kimi_key
        ) or (provider == QWEN and not has_api_key() and not qwen_key)
        if active_missing:
            QMessageBox.warning(
                self,
                tr("settings.provider_required_title"),
                tr("settings.provider_required_detail"),
            )
            self.tabs.setCurrentIndex(0)
            key_edit = (
                self.kimi_key_edit if provider == KIMI else self.qwen_key_edit
            )
            key_edit.setFocus()
            return

        base_url = self.qwen_base_url_edit.text().strip().rstrip("/")
        kimi_base_url = self.kimi_base_url_edit.text().strip().rstrip("/")
        model = self.model_combo.currentText().strip()
        kimi_model = self.kimi_model_edit.text().strip()
        active_url = kimi_base_url if provider == KIMI else base_url
        active_url_edit = (
            self.kimi_base_url_edit
            if provider == KIMI
            else self.qwen_base_url_edit
        )
        if not active_url.startswith("https://"):
            QMessageBox.warning(
                self,
                tr("settings.invalid_title"),
                tr("settings.invalid_base_url"),
            )
            self.tabs.setCurrentIndex(0)
            active_url_edit.setFocus()
            return
        active_model = kimi_model if provider == KIMI else model
        if not active_model:
            QMessageBox.warning(
                self,
                tr("settings.invalid_title"),
                tr("settings.invalid_model"),
            )
            self.tabs.setCurrentIndex(1)
            model_edit = (
                self.kimi_model_edit
                if provider == KIMI
                else self.model_combo
            )
            model_edit.setFocus()
            return

        try:
            if qwen_key:
                store_api_key(qwen_key)
            if kimi_key:
                store_kimi_api_key(kimi_key)
            if brave_key:
                store_brave_api_key(brave_key)
            if postgis_dsn:
                store_postgis_dsn(postgis_dsn)
        except CredentialError as exc:
            QMessageBox.critical(
                self, tr("settings.save_failed"), str(exc)
            )
            return

        values: Dict[str, object] = {
            "provider": provider,
            "base_url": base_url,
            "model": model,
            "kimi_base_url": kimi_base_url,
            "kimi_model": kimi_model,
            "kimi_reasoning_effort": str(
                self.kimi_effort_combo.currentData()
            ),
            "kimi_timeout": self.kimi_timeout_spin.value(),
            "temperature": self.temperature_spin.value(),
            "qwen_timeout": self.qwen_timeout_spin.value(),
            "max_prompt_chars": self.prompt_limit_spin.value(),
            "candidate_limit": self.candidate_limit_spin.value(),
            "brave_timeout": self.brave_timeout_spin.value(),
            "language": str(self.language_combo.currentData()),
            "theme": str(self.theme_combo.currentData()),
        }
        settings = QgsSettings()
        save_runtime_settings(settings, values)
        settings.setValue("sakugis/ui/language", values["language"])
        settings.setValue("sakugis/ui/theme", values["theme"])

        # A newly entered key must override any launch-time value immediately.
        # The plaintext remains only in this process and the macOS Keychain.
        if qwen_key:
            os.environ["SAKUGIS_QWEN_API_KEY"] = qwen_key
        if kimi_key:
            os.environ["SAKUGIS_KIMI_API_KEY"] = kimi_key
        if brave_key:
            os.environ["SAKUGIS_BRAVE_API_KEY"] = brave_key

        self.settingsApplied.emit(values)
        self.accept()
