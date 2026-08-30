from __future__ import annotations

import inspect
import json
from pathlib import Path

from PySide6.QtWidgets import QApplication

from src.ui.dialogs.experiment_dialog import ExperimentDialog
from src.ui.pages.about_page import AboutPage
from src.ui.ui_components.title_bar import TitleBar
from src.utils.logger import LoggerManager
from src.utils.path_manager import PathManager
from src.utils.software_info import DEFAULT_SOFTWARE_INFO, load_software_info


def test_software_info_loader_uses_config_and_shared_fallback(tmp_path):
    info_path = tmp_path / "software.info"
    info_path.write_text(
        json.dumps({"version": "9.8.7", "description": "Test Product"}),
        encoding="utf-8",
    )

    configured = load_software_info(info_path)
    fallback = load_software_info(tmp_path / "missing.info")

    assert configured["version"] == "9.8.7"
    assert configured["description"] == "Test Product"
    assert configured["author"] == DEFAULT_SOFTWARE_INFO["author"]
    assert fallback == DEFAULT_SOFTWARE_INFO
    assert fallback["description"] == "TMH-LPF-900 铁矿石冶金性能综合检测与控制系统"


def test_about_page_displays_supplied_release_version():
    app = QApplication.instance() or QApplication([])
    page = AboutPage({"version": "9.8.7"})

    assert page.version_label.text() == "版本 9.8.7"
    assert app is not None


def test_runtime_paths_are_resolved_by_path_manager():
    assert LoggerManager().log_dir == Path(PathManager.get_logs_path())
    assert TitleBar.logo_path() == PathManager.get_resources_path("icons/ustb_logo.png")


def test_experiment_dialog_does_not_create_cwd_relative_config_directory():
    source = inspect.getsource(ExperimentDialog.save_settings)

    assert 'os.makedirs("configs"' not in source
