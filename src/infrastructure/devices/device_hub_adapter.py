from __future__ import annotations

import time
from typing import Any

from src.application.dto import DeviceSnapshot, HealthStatus, SnapshotBundle


class DeviceHubAdapter:
    """Application-facing adapter over the legacy DeviceManager."""

    def __init__(self, device_manager):
        self.device_manager = device_manager

    def start_all(self) -> None:
        self.device_manager.start_all()

    def stop_all(self) -> None:
        self.device_manager.stop_all()

    def get_status(self, name: str = None):
        return self.device_manager.get_status(name)

    def get_status_legacy(self) -> dict[str, Any]:
        return self.device_manager.get_status_legacy()

    def get_snapshots(self) -> SnapshotBundle:
        status = self.get_status_legacy()
        frames = status.get("frames") or {}
        devices: dict[str, DeviceSnapshot] = {}

        temp_frame = frames.get("temperature")
        if temp_frame:
            devices["Temp"] = DeviceSnapshot(
                device_name="Temp",
                device_type="temperature",
                timestamp=getattr(temp_frame, "timestamp", None),
                payload=getattr(temp_frame, "payload", {}) or {},
                is_connected=True,
                is_running=True,
            )

        weight_frame = frames.get("weight")
        if weight_frame:
            devices["Balance"] = DeviceSnapshot(
                device_name="Balance",
                device_type="weight",
                timestamp=getattr(weight_frame, "timestamp", None),
                payload=getattr(weight_frame, "payload", {}) or {},
                is_connected=True,
                is_running=True,
            )

        flow_frames = frames.get("flows") or {}
        if flow_frames:
            channels = {}
            latest_ts = None
            for gas_type, frame in flow_frames.items():
                payload = getattr(frame, "payload", {}) or {}
                channels[gas_type] = {
                    "pv": payload.get("pv"),
                    "sv": payload.get("sv"),
                    "meta": getattr(frame, "meta", {}) or {},
                }
                frame_ts = getattr(frame, "timestamp", None)
                if frame_ts is not None:
                    latest_ts = frame_ts if latest_ts is None else max(latest_ts, frame_ts)

            devices["MFC"] = DeviceSnapshot(
                device_name="MFC",
                device_type="flow",
                timestamp=latest_ts,
                payload={"channels": channels},
                is_connected=True,
                is_running=True,
            )

        return SnapshotBundle(
            devices=devices,
            timestamp=status.get("timestamp"),
        )

    def latest_snapshot_bundle(self) -> SnapshotBundle:
        return self.get_snapshots()

    def get_all_status(self) -> dict[str, dict[str, Any]]:
        devices = self._devices_snapshot()
        status = {}
        for name, device in devices.items():
            latest_data = self._get_latest_data(device)
            last_update_ts = self._extract_timestamp(latest_data)
            status[name] = {
                "data": latest_data,
                "running": getattr(device, "is_alive", lambda: False)(),
                "connected": bool(getattr(device, "serial_port_available", False)),
                "last_update_ts": last_update_ts,
                "error_message": "" if last_update_ts is not None else "无最新数据",
            }
        return status

    def get_comm_status(self) -> HealthStatus:
        is_connected, device_names, error_msg = self.device_manager.get_connection_status()
        return HealthStatus(
            is_connected=is_connected,
            is_running=bool(self.device_manager.running),
            last_update_ts=time.time(),
            error_message=error_msg or "",
        )

    def get_connection_status(self):
        return self.device_manager.get_connection_status()

    def set_flow(self, gas_name: str, flow_lpm: float) -> bool:
        return self.device_manager.set_flow(gas_name, flow_lpm)

    def tare_balance(self) -> bool:
        return self.device_manager.tare_balance()

    def _devices_snapshot(self) -> dict[str, Any]:
        lock = getattr(self.device_manager, "_devices_lock", None)
        if lock is None:
            return dict(getattr(self.device_manager, "devices", {}))
        with lock:
            return dict(getattr(self.device_manager, "devices", {}))

    def _get_latest_data(self, device):
        if hasattr(device, "get_latest_data"):
            return device.get_latest_data()
        if hasattr(device, "_last_valid_data"):
            return getattr(device, "_last_valid_data")
        if hasattr(device, "get_data"):
            return device.get_data()
        return None

    def _extract_timestamp(self, data) -> float | None:
        if isinstance(data, dict):
            if isinstance(data.get("timestamp"), (int, float)):
                return float(data["timestamp"])

            timestamps = []
            for value in data.values():
                if isinstance(value, dict) and isinstance(value.get("timestamp"), (int, float)):
                    timestamps.append(float(value["timestamp"]))
            if timestamps:
                return max(timestamps)
        return None
