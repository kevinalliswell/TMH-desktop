"""Virtual table model for large experiment histories."""

from __future__ import annotations

import math
from datetime import datetime

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


HEADERS = (
    "时间",
    "实验时长(min)",
    "温度(℃)",
    "重量(g)",
    "失重(%)",
    "CO(L/min)",
    "CO₂(L/min)",
    "N₂(L/min)",
    "H₂(L/min)",
)


def select_plot_indices(
    indices: list[int],
    max_points: int = 5_000,
    series: list[list[float]] | None = None,
) -> list[int]:
    """Return a bounded sample, preserving endpoints and optional local extrema."""
    if max_points < 2:
        raise ValueError("max_points must be at least 2")
    if len(indices) <= max_points:
        return list(indices)

    usable_series = [values for values in (series or []) if values]
    if usable_series:
        bucket_count = max(1, (max_points - 2) // (2 * len(usable_series)))
        selected = {indices[0], indices[-1]}
        for bucket in range(bucket_count):
            start = bucket * len(indices) // bucket_count
            end = (bucket + 1) * len(indices) // bucket_count
            bucket_indices = indices[start:end]
            for values in usable_series:
                candidates = [
                    index
                    for index in bucket_indices
                    if index < len(values)
                    and isinstance(values[index], (int, float))
                    and math.isfinite(values[index])
                ]
                if candidates:
                    selected.add(min(candidates, key=values.__getitem__))
                    selected.add(max(candidates, key=values.__getitem__))
        return sorted(selected)

    stride = math.ceil((len(indices) - 1) / (max_points - 1))
    sampled = list(indices[::stride])
    if sampled[-1] != indices[-1]:
        sampled.append(indices[-1])
    return sampled


class HistoryDataTableModel(QAbstractTableModel):
    """Expose history rows lazily so Qt creates widgets only for visible cells."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._experiment: dict = {}
        self._elapsed_minutes: list[float | None] = []
        self._row_count = 0
        self._timestamp_cache: dict[int, str] = {}

    def clear(self) -> None:
        self.set_experiment({}, [])

    def set_experiment(
        self,
        experiment: dict,
        elapsed_minutes: list[float | None],
    ) -> None:
        self.beginResetModel()
        self._experiment = experiment
        self._elapsed_minutes = elapsed_minutes
        self._timestamp_cache = {}
        gas_flows = experiment.get("gas_flows", {})
        series = [
            experiment.get("timestamps", []),
            elapsed_minutes,
            experiment.get("temperatures", []),
            experiment.get("weights", []),
            experiment.get("weight_losses", []),
            gas_flows.get("CO", []),
            gas_flows.get("CO2", []),
            gas_flows.get("N2", []),
            gas_flows.get("H2", []),
        ]
        self._row_count = max((len(values) for values in series), default=0)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802 - Qt API
        return 0 if parent.isValid() else self._row_count

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: N802 - Qt API
        return 0 if parent.isValid() else len(HEADERS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):  # noqa: N802 - Qt API
        if role == Qt.DisplayRole and orientation == Qt.Horizontal and 0 <= section < len(HEADERS):
            return HEADERS[section]
        return super().headerData(section, orientation, role)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.TextAlignmentRole:
            return Qt.AlignCenter
        if role != Qt.DisplayRole:
            return None

        row = index.row()
        column = index.column()
        if column == 0:
            return self._formatted_timestamp(row)
        if column == 1:
            return self._formatted_number(self._elapsed_minutes, row, 2)

        gas_flows = self._experiment.get("gas_flows", {})
        columns = (
            self._experiment.get("temperatures", []),
            self._experiment.get("weights", []),
            self._experiment.get("weight_losses", []),
            gas_flows.get("CO", []),
            gas_flows.get("CO2", []),
            gas_flows.get("N2", []),
            gas_flows.get("H2", []),
        )
        precision = 4 if column == 3 else 2
        return self._formatted_number(columns[column - 2], row, precision)

    def _formatted_timestamp(self, row: int) -> str:
        if row in self._timestamp_cache:
            return self._timestamp_cache[row]
        timestamps = self._experiment.get("timestamps", [])
        if row >= len(timestamps):
            return ""
        raw = timestamps[row]
        try:
            formatted = datetime.fromisoformat(str(raw)).strftime("%Y-%m-%d %H:%M:%S")
        except (TypeError, ValueError):
            formatted = str(raw)
        self._timestamp_cache[row] = formatted
        return formatted

    @staticmethod
    def _formatted_number(values, row: int, precision: int) -> str:
        if row >= len(values) or values[row] is None:
            return ""
        try:
            return f"{float(values[row]):.{precision}f}"
        except (TypeError, ValueError):
            return str(values[row])
