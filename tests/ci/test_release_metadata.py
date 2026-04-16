import json
from pathlib import Path

from build_release import TMHBuilder
from scripts.release_manager import (
    get_release_section,
    prepare_release,
    verify_release_metadata,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOFTWARE_INFO_PATH = PROJECT_ROOT / "configs" / "software.info"
CHANGELOG_PATH = PROJECT_ROOT / "CHANGELOG.md"


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


def test_version_metadata_is_consistent():
    info = json.loads(SOFTWARE_INFO_PATH.read_text(encoding="utf-8"))
    result = verify_release_metadata()

    assert result["version"] == info["version"]
    assert result["tag"] == f"v{info['version']}"


def test_prepare_release_moves_unreleased_section(tmp_path):
    software_info_path = tmp_path / "software.info"
    changelog_path = tmp_path / "CHANGELOG.md"

    software_info_path.write_text(
        json.dumps(
            {
                "version": "1.1.251121",
                "release_date": "2025-11-21",
                "build_date": "2025-11-21",
                "description": "TMH",
            },
            indent=4,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )
    changelog_path.write_text(
        "# Changelog\n\n"
        "## [Unreleased]\n\n"
        "### Added\n\n"
        "- Add new release command.\n\n"
        "## [1.1.251121] - 2025-11-21\n\n"
        "### Changed\n\n"
        "- Previous release.\n",
        encoding="utf-8",
    )

    info, changelog = prepare_release(
        "1.1.251122",
        "2025-11-22",
        software_info_path=software_info_path,
        changelog_path=changelog_path,
    )

    assert info["version"] == "1.1.251122"
    assert info["release_date"] == "2025-11-22"
    assert "## [1.1.251122] - 2025-11-22" in changelog
    assert "- Add new release command." in changelog
    assert changelog.index("## [Unreleased]") < changelog.index("## [1.1.251122] - 2025-11-22")


def test_can_extract_release_section_for_notes():
    changelog = CHANGELOG_PATH.read_text(encoding="utf-8")
    section = get_release_section(changelog, "1.1.251121")

    assert section is not None
    assert section.version == "1.1.251121"
    assert section.release_date == "2025-11-21"
    assert "统一使用 `tmh_comm` 协议包" in section.body
