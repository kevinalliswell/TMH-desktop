from __future__ import annotations

import json

from PySide6.QtWidgets import QApplication

from src.services.update_service import (
    UpdateCheckResult,
    UpdateService,
    is_newer_version,
    parse_version,
)
from src.ui.pages.about_page import AboutPage


class _Response:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, limit: int) -> bytes:
        return self._body[:limit]


def test_release_version_comparison_handles_prefixes_and_component_lengths():
    assert parse_version("v1.6.260702") == (1, 6, 260702)
    assert is_newer_version("v1.7.0", "1.6.260702") is True
    assert is_newer_version("1.6.260702", "v1.6.260702.0") is False


def test_update_service_reports_new_release_and_safe_download_url():
    def opener(request, timeout):
        assert request.full_url.endswith("/releases/latest")
        assert timeout == 5.0
        return _Response(
            {
                "tag_name": "v1.7.0",
                "html_url": "https://github.com/kevinalliswell/TMH-desktop/releases/tag/v1.7.0",
            }
        )

    result = UpdateService(opener=opener).check("1.6.260702")

    assert result.update_available is True
    assert result.latest_version == "1.7.0"
    assert result.release_url.endswith("/releases/tag/v1.7.0")
    assert result.error is None


def test_update_service_falls_back_to_repository_releases_for_untrusted_url():
    service = UpdateService(
        opener=lambda request, timeout: _Response(
            {"tag_name": "v2.0.0", "html_url": "https://example.com/fake-installer"}
        )
    )

    result = service.check("1.0.0")

    assert result.release_url == "https://github.com/kevinalliswell/TMH-desktop/releases"


def test_update_service_contains_network_failures():
    def unavailable(request, timeout):
        raise OSError("offline")

    result = UpdateService(opener=unavailable).check("1.6.260702")

    assert result.update_available is False
    assert result.error


def test_about_page_renders_available_update_without_network_thread():
    app = QApplication.instance() or QApplication([])
    page = AboutPage(
        {"version": "1.6.260702"},
        update_service=object(),
        auto_check=False,
    )

    page._apply_update_result(
        UpdateCheckResult(
            current_version="1.6.260702",
            latest_version="1.7.0",
            update_available=True,
            release_url="https://github.com/kevinalliswell/TMH-desktop/releases/tag/v1.7.0",
        )
    )

    assert "1.7.0" in page.update_status_label.text()
    assert page.download_button.isVisibleTo(page)
    assert app is not None


def test_about_page_runs_update_check_on_background_thread():
    app = QApplication.instance() or QApplication([])

    class CurrentVersionService:
        def check(self, current_version):
            return UpdateCheckResult(
                current_version=current_version,
                latest_version=current_version,
            )

    page = AboutPage(
        {"version": "1.6.260702"},
        update_service=CurrentVersionService(),
        auto_check=False,
    )

    page.check_for_updates()
    page._update_thread.join(timeout=1)
    app.processEvents()

    assert not page._update_thread.is_alive()
    assert page.check_update_button.isEnabled()
    assert "已是最新版本" in page.update_status_label.text()
