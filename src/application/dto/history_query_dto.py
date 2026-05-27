from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExperimentSummaryDTO:
    """Lightweight metadata shown in the history list."""

    experiment_id: str
    experiment_name: str
    sample_name: str
    sample_weight: float
    start_time: str
    end_time: str | None = None
    operator: str = ""
    experiment_type: str = ""
    description: str = ""


@dataclass
class ExperimentDetailDTO(ExperimentSummaryDTO):
    """Expanded experiment data for charts, exports, and analysis."""

    analysis_results: dict[str, Any] | None = None
    timestamps: list[str] = field(default_factory=list)
    temperatures: list[float] = field(default_factory=list)
    weights: list[float] = field(default_factory=list)
    weight_losses: list[float] = field(default_factory=list)
    gas_flows: dict[str, list[float]] = field(
        default_factory=lambda: {"CO": [], "CO2": [], "N2": [], "H2": []}
    )


@dataclass
class DatabaseIntegrityStatusDTO:
    """Database health status used by the history page."""

    experiment_count: int = 0
    data_count: int = 0
    orphaned_data: int = 0
    experiment_columns: list[str] = field(default_factory=list)
    data_columns: list[str] = field(default_factory=list)
    is_valid: bool = False
    error: str = ""
