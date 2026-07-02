"""Single-instance guard (issue #26).

Only one TMH instance may run at a time, because the serial ports / device buses
are exclusive resources held by the first instance. A second launch must be
refused with a prompt instead of silently failing to talk to the hardware.

Uses ``QLockFile``: it stores the owner PID/host and automatically reclaims a
stale lock left behind by a crashed previous instance, so a crash does not
permanently block future launches.
"""
from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import QDir, QLockFile

from src.utils.logger import get_logger

logger = get_logger(__name__)

_DEFAULT_APP_ID = "TMH-LPF-900"
# Reclaim a lock whose owner process is gone after this many ms (crash recovery).
_STALE_LOCK_MS = 30_000


def lock_file_path(app_id: str = _DEFAULT_APP_ID) -> str:
    """Absolute path of the single-instance lock file (in the system temp dir)."""
    return os.path.join(QDir.tempPath(), f"{app_id}.lock")


def acquire_single_instance_lock(app_id: str = _DEFAULT_APP_ID) -> Optional[QLockFile]:
    """Try to acquire the single-instance lock.

    Returns the held ``QLockFile`` on success — the caller MUST keep it alive for
    the whole application lifetime (let it go out of scope and the lock releases).
    Returns ``None`` if another live instance already holds the lock.
    """
    lock = QLockFile(lock_file_path(app_id))
    lock.setStaleLockTime(_STALE_LOCK_MS)

    if lock.tryLock(100):
        return lock

    # 已被占用：记录持有者信息用于诊断（getLockInfo 返回形态随平台/版本而异，容错处理）。
    try:
        info = lock.getLockInfo()
    except Exception:
        info = None
    logger.warning(f"单实例锁已被占用，拒绝启动第二个实例。持有者信息: {info}")
    return None
