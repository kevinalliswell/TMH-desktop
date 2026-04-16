import json
from pathlib import Path

from build_release import TMHBuilder


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOFTWARE_INFO_PATH = PROJECT_ROOT / "configs" / "software.info"


def test_software_info_has_required_release_fields():
    info = json.loads(SOFTWARE_INFO_PATH.read_text(encoding="utf-8"))

    assert info["version"]
    assert info["release_date"]
    assert info["description"]
    assert info["python_version"] == "3.10+"


def test_builder_uses_current_configured_version():
    info = json.loads(SOFTWARE_INFO_PATH.read_text(encoding="utf-8"))
    builder = TMHBuilder()

    assert builder.project_root == PROJECT_ROOT
    assert builder.app_version == info["version"]
    assert builder.main_script.exists()

