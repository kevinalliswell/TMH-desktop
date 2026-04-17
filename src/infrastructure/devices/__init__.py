"""Device-layer adapters bridging legacy device clients to application ports."""

from src.infrastructure.devices.device_hub_adapter import DeviceHubAdapter
from src.infrastructure.devices.snapshot_collector_adapter import SnapshotCollectorAdapter

__all__ = ["DeviceHubAdapter", "SnapshotCollectorAdapter"]

