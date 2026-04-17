"""UI adapter helpers for mapping backend data into view-friendly shapes."""

from src.ui.adapters.snapshot_mapper import (
    ChartTableRowData,
    FrameUiSnapshot,
    build_chart_table_row,
    map_frames_to_ui_snapshot,
)

__all__ = [
    "ChartTableRowData",
    "FrameUiSnapshot",
    "build_chart_table_row",
    "map_frames_to_ui_snapshot",
]

