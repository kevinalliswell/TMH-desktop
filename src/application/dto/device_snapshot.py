from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class HealthStatus:
    """Standard health view for runtime-managed components."""

    is_connected: bool = False
    is_running: bool = False
    last_update_ts: float | None = None
    error_message: str = ""


@dataclass
class DeviceSnapshot:
    """Normalized device snapshot shared across UI, services, and storage."""

    device_name: str
    device_type: str
    timestamp: float | None
    payload: dict[str, Any] = field(default_factory=dict)
    is_connected: bool = False
    is_running: bool = False
    error_message: str = ""


@dataclass
class SnapshotBundle:
    """Collection of normalized snapshots captured around the same instant."""

    devices: dict[str, DeviceSnapshot] = field(default_factory=dict)
    timestamp: float | None = None
