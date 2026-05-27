from __future__ import annotations

from src.application.dto import SnapshotBundle


class SnapshotCollectorAdapter:
    """Application-facing snapshot collector over the legacy DataHandler."""

    def __init__(self, data_handler):
        self.data_handler = data_handler

    def start(self) -> None:
        self.data_handler.start()

    def stop(self) -> None:
        self.data_handler.stop()

    def latest_snapshot_bundle(self) -> SnapshotBundle:
        bundle = self.data_handler.latest_snapshot_bundle()
        return bundle or SnapshotBundle()
