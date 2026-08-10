"""Unified bilingual settings dialog for SakuGIS."""

from __future__ import annotations

import os
from typing import Dict

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
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
    configured_prompt_char_limit,
    configured_qwen_temperature,
    configured_qwen_timeout,
    has_api_key,
    has_brave_api_key,
    has_postgis_dsn,
    store_api_key,
    store_brave_api_key,
    store_postgis_dsn,
)
from sakugis.i18n import EN, ZH_CN, get_language, tr
from sakugis.ui_theme import DARK, LIGHT, get_theme


class SettingsDialog(QDialog):
    """Central settings UI; secrets are written only to macOS Keychain."""

    settingsApplied = pyqtSignal(object)

    def __init__(self, parent=None, required_section: str = ""):
        super().__init__(parent)
        self._required_section = required_section
        self.setWindowTitle(tr("settings.title"))
        self.setModal(True)
        self.resize(680, 560)
        self.setMinimumSize(620, 500)
        self._build_ui()

    def _build_ui(self) -> None:
        self.tabs = QTabWidget(self)
        self.tabs.addTab(self._build_api_tab(), tr("settings.api_tab"))
        self.tabs.addTab(self._build_model_tab(), tr("settings.model_tab"))
        self.tabs.addTab(self._build_gis_tab(), tr("settings.gis_tab"))
        self.tabs.addTab(
            self._build_interface_tab(), tr("settings.interface_tab")
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

        if self._required_section == "qwen":
            self.tabs.setCurrentIndex(0)
            self.qwen_key_edit.setFocus()

    def _build_api_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setSpacing(12)

        qwen_group = QGroupBox(tr("settings.qwen_group"), tab)
        qwen_layout = QFormLayout(qwen_group)
        self.qwen_status = self._status_label(
            has_api_key(),
            tr("settings.configured"),
            tr("settings.required_missing"),
        )
        self.qwen_key_edit = self._secret_edit(
            (
                tr("settings.keep_existing")
                if has_api_key()
                else tr("settings.enter_required")
            )
        )
        qwen_layout.addRow(tr("settings.status"), self.qwen_status)
        self.base_url_edit = QLineEdit(configured_base_url(), qwen_group)
        self.base_url_edit.setClearButtonEnabled(True)
        qwen_layout.addRow(tr("settings.base_url"), self.base_url_edit)
        qwen_layout.addRow(tr("settings.qwen_key"), self.qwen_key_edit)
        qwen_note = QLabel(tr("settings.qwen_note"), qwen_group)
        qwen_note.setObjectName("MutedLabel")
        qwen_note.setWordWrap(True)
        qwen_layout.addRow("", qwen_note)

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

        layout.addWidget(qwen_group)
        layout.addWidget(brave_group)
        layout.addWidget(security_note)
        layout.addStretch(1)
        return tab

    def _build_model_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 14, 12, 12)

        model_group = QGroupBox(tr("settings.model_group"), tab)
        form = QFormLayout(model_group)
        self.model_combo = QComboBox(model_group)
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

        self.temperature_spin = QDoubleSpinBox(model_group)
        self.temperature_spin.setRange(0.0, 1.0)
        self.temperature_spin.setSingleStep(0.05)
        self.temperature_spin.setDecimals(2)
        self.temperature_spin.setValue(configured_qwen_temperature())

        self.qwen_timeout_spin = QSpinBox(model_group)
        self.qwen_timeout_spin.setRange(30, 300)
        self.qwen_timeout_spin.setSuffix(tr("settings.seconds_suffix"))
        self.qwen_timeout_spin.setValue(configured_qwen_timeout())

        self.prompt_limit_spin = QSpinBox(model_group)
        self.prompt_limit_spin.setRange(8000, 120000)
        self.prompt_limit_spin.setSingleStep(1000)
        self.prompt_limit_spin.setValue(configured_prompt_char_limit())

        self.candidate_limit_spin = QSpinBox(model_group)
        self.candidate_limit_spin.setRange(1, 12)
        self.candidate_limit_spin.setValue(configured_candidate_limit())

        form.addRow(tr("settings.model"), self.model_combo)
        form.addRow(tr("settings.temperature"), self.temperature_spin)
        form.addRow(
            tr("settings.request_timeout"), self.qwen_timeout_spin
        )
        form.addRow(tr("settings.prompt_limit"), self.prompt_limit_spin)
        form.addRow(
            tr("settings.candidate_limit"), self.candidate_limit_spin
        )

        note = QLabel(tr("settings.model_note"), tab)
        note.setObjectName("MutedLabel")
        note.setWordWrap(True)
        layout.addWidget(model_group)
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
        return label

    def _save(self) -> None:
        qwen_key = self.qwen_key_edit.text().strip()
        brave_key = self.brave_key_edit.text().strip()
        postgis_dsn = self.postgis_dsn_edit.text().strip()
        if not has_api_key() and not qwen_key:
            QMessageBox.warning(
                self,
                tr("settings.qwen_required_title"),
                tr("settings.qwen_required_detail"),
            )
            self.tabs.setCurrentIndex(0)
            self.qwen_key_edit.setFocus()
            return

        base_url = self.base_url_edit.text().strip().rstrip("/")
        model = self.model_combo.currentText().strip()
        if not base_url.startswith("https://"):
            QMessageBox.warning(
                self,
                tr("settings.invalid_title"),
                tr("settings.invalid_base_url"),
            )
            self.tabs.setCurrentIndex(0)
            self.base_url_edit.setFocus()
            return
        if not model:
            QMessageBox.warning(
                self,
                tr("settings.invalid_title"),
                tr("settings.invalid_model"),
            )
            self.tabs.setCurrentIndex(1)
            self.model_combo.setFocus()
            return

        try:
            if qwen_key:
                store_api_key(qwen_key)
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
            "base_url": base_url,
            "model": model,
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
        if brave_key:
            os.environ["SAKUGIS_BRAVE_API_KEY"] = brave_key

        self.settingsApplied.emit(values)
        self.accept()
