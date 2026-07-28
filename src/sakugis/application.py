"""Application bootstrap for the embedded QGIS runtime."""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path
from typing import Optional, Tuple


_SHUTTING_DOWN = False


def _runtime_contents() -> Optional[Path]:
    configured = os.environ.get("SAKUGIS_RUNTIME_CONTENTS")
    if configured:
        return Path(configured).resolve()

    executable = Path(sys.executable).resolve()
    for parent in executable.parents:
        if parent.name == "Contents":
            return parent
    return None


def _configure_runtime_environment() -> Tuple[Path, Path, Path]:
    contents = _runtime_contents()
    configured_prefix = os.environ.get("QGIS_PREFIX_PATH")

    if configured_prefix:
        prefix = Path(configured_prefix)
    elif contents and (contents / "Resources" / "qgis").is_dir():
        prefix = contents / "Resources" / "qgis"
    elif contents:
        prefix = contents / "MacOS"
    else:
        raise RuntimeError(
            "找不到 QGIS 运行时。请通过 scripts/run-dev.sh 启动，"
            "或设置 QGIS_PREFIX_PATH。"
        )

    if contents:
        modern_layout = (contents / "Resources" / "qgis").is_dir()
        resource_root = (
            contents / "Resources" / "qgis"
            if modern_layout
            else contents / "Resources"
        )
        defaults = {
            "QGIS_PKG_DATA_PATH": resource_root,
            "QGIS_PLUGIN_PATH": contents / "PlugIns" / "qgis",
            "GDAL_DATA": resource_root / "gdal",
            "PROJ_LIB": resource_root / "proj",
            "QT_PLUGIN_PATH": contents / "PlugIns",
            "QT_QPA_PLATFORM_PLUGIN_PATH": contents / "PlugIns" / "platforms",
            "QGIS_PLUGINPATH": contents / "PlugIns" / "qgis",
        }
        for name, path in defaults.items():
            os.environ.setdefault(name, str(path))

    package_data = Path(os.environ.get("QGIS_PKG_DATA_PATH", str(prefix)))
    plugin_path = Path(os.environ.get("QGIS_PLUGIN_PATH", str(prefix)))
    return prefix, package_data, plugin_path


def _install_exception_hook() -> None:
    from qgis.PyQt.QtCore import QCoreApplication
    from qgis.PyQt.QtWidgets import QApplication, QMessageBox
    from sakugis.i18n import tr

    def show_exception(exc_type, exc_value, exc_traceback):
        details = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        print(details, file=sys.stderr)
        if (
            _SHUTTING_DOWN
            or QApplication.instance() is None
            or QCoreApplication.closingDown()
        ):
            return
        box = QMessageBox()
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle(tr("app.error_title"))
        box.setText(str(exc_value))
        box.setDetailedText(details)
        box.exec_()

    sys.excepthook = show_exception


def run() -> int:
    global _SHUTTING_DOWN
    _SHUTTING_DOWN = False
    prefix, package_data, plugin_path = _configure_runtime_environment()
    launch_arguments = list(sys.argv[1:])

    from qgis.core import (
        QgsApplication,
        QgsProviderRegistry,
        QgsSettings,
    )

    QgsApplication.setPrefixPath(str(prefix), True)
    # Some bundled PyQGIS/SIP builds reject Python str values in argv. QGIS
    # does not need our launcher arguments; SakuGIS handles project paths below.
    app = QgsApplication([], True)
    QgsApplication.setPkgDataPath(str(package_data))
    QgsApplication.setPluginPath(str(plugin_path))
    QgsProviderRegistry.instance(str(plugin_path))
    app.setApplicationName("SakuGIS")
    app.setApplicationDisplayName("SakuGIS")
    app.setOrganizationName("UrbanComp")
    app.setOrganizationDomain("urbancomp.net")
    app.initQgis()
    QgsApplication.setPkgDataPath(str(package_data))
    QgsApplication.setPluginPath(str(plugin_path))

    settings = QgsSettings()
    from sakugis.app_settings import load_runtime_settings
    from sakugis.i18n import set_language

    load_runtime_settings(settings)
    set_language(str(settings.value("sakugis/ui/language", "zh_CN")))
    from sakugis.ui_theme import apply_theme, normalize_theme

    apply_theme(
        app,
        normalize_theme(str(settings.value("sakugis/ui/theme", "dark"))),
    )
    settings.setValue(
        "qgis/networkAndProxy/userAgent",
        "SakuGIS/0.3.0 (+https://urbancomp.net)",
    )

    _install_exception_hook()

    from sakugis.main_window import MainWindow

    window = MainWindow()
    for argument in launch_arguments:
        candidate = Path(argument)
        if candidate.suffix.lower() in {".qgz", ".qgs"} and candidate.is_file():
            window.load_project_path(str(candidate), confirm_discard=False)
            break
    window.show()
    try:
        autoclose_ms = int(os.environ.get("SAKUGIS_AUTOCLOSE_MS", "0"))
    except ValueError:
        autoclose_ms = 0
    if autoclose_ms > 0:
        from qgis.PyQt.QtCore import QTimer

        def close_for_test() -> None:
            window.close()

        QTimer.singleShot(autoclose_ms, close_for_test)

    exit_code = app.exec_()
    _SHUTTING_DOWN = True
    sys.excepthook = sys.__excepthook__
    try:
        window.prepare_for_shutdown()
        window.hide()
        window.deleteLater()
        app.processEvents()
    except RuntimeError:
        pass
    app.exitQgis()
    return int(exit_code)
