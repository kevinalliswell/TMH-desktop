"""Crashes must leave evidence on disk.

src/app.py installed no faulthandler, no sys.excepthook and no
threading.excepthook. Packaged with PyInstaller --windowed there is no terminal
receiving stderr, so a segfault (the serial-handle race), a worker-thread
exception and a GUI-slot exception all vanished without a line in logs/app.log.
That is why the field reports of 闪退 could never be diagnosed.
"""
import faulthandler
import logging
import sys
import threading

import pytest

from src.utils import crash_diagnostics


@pytest.fixture()
def fresh_diagnostics(monkeypatch):
    """Install into a clean slot and restore the interpreter hooks afterwards."""
    original_sys_hook = sys.excepthook
    original_thread_hook = threading.excepthook
    monkeypatch.setattr(crash_diagnostics, "_installed", False)
    monkeypatch.setattr(crash_diagnostics, "_fault_log", None)
    yield
    sys.excepthook = original_sys_hook
    threading.excepthook = original_thread_hook
    faulthandler.disable()
    crash_diagnostics._installed = False


class _RecordingLogger(logging.Logger):
    def __init__(self):
        super().__init__("recording")
        self.critical_calls = []

    def critical(self, msg, *args, **kwargs):
        self.critical_calls.append((msg, kwargs.get("exc_info")))


def test_install_enables_faulthandler_and_both_excepthooks(fresh_diagnostics):
    assert crash_diagnostics.install(_RecordingLogger()) is True

    assert faulthandler.is_enabled() is True
    assert sys.excepthook is not sys.__excepthook__
    assert threading.excepthook is not threading.__excepthook__
    assert crash_diagnostics.is_installed() is True


def test_install_is_idempotent(fresh_diagnostics):
    logger = _RecordingLogger()
    assert crash_diagnostics.install(logger) is True
    hook_after_first = sys.excepthook

    assert crash_diagnostics.install(logger) is True
    assert sys.excepthook is hook_after_first


def test_main_thread_exception_is_logged(fresh_diagnostics):
    logger = _RecordingLogger()
    crash_diagnostics.install(logger)

    try:
        raise ValueError("boom")
    except ValueError:
        sys.excepthook(*sys.exc_info())

    assert logger.critical_calls, "主线程未捕获异常必须落日志"
    message, exc_info = logger.critical_calls[0]
    assert "主线程未捕获异常" in message
    assert exc_info is not None


def test_worker_thread_exception_is_logged(fresh_diagnostics):
    """threading.excepthook is the only hook that sees worker-thread failures."""
    logger = _RecordingLogger()
    crash_diagnostics.install(logger)

    def _explode():
        raise RuntimeError("worker boom")

    worker = threading.Thread(target=_explode, name="test-worker", daemon=True)
    worker.start()
    worker.join(timeout=5.0)

    assert logger.critical_calls, "工作线程异常不经过 sys.excepthook，必须由 threading.excepthook 记录"
    message, exc_info = logger.critical_calls[0]
    assert "工作线程未捕获异常" in message
    assert "test-worker" in message
    assert exc_info is not None


def test_keyboard_interrupt_is_left_to_the_interpreter(fresh_diagnostics):
    logger = _RecordingLogger()
    crash_diagnostics.install(logger)

    try:
        raise KeyboardInterrupt()
    except KeyboardInterrupt:
        sys.excepthook(*sys.exc_info())

    assert logger.critical_calls == [], "Ctrl+C 不是崩溃，不应记为致命错误"


def test_app_entrypoint_installs_diagnostics_before_building_the_window():
    """Order matters: a crash while constructing devices must be captured too."""
    from pathlib import Path

    source = Path(__file__).resolve().parents[2] / "src" / "app.py"
    text = source.read_text(encoding="utf-8")

    install_at = text.index("install_crash_diagnostics(logger)")
    window_at = text.index("MainWindow()")
    assert install_at < window_at
