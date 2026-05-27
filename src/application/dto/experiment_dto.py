from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ExperimentParameters:
    """Inputs required to create and start an experiment."""

    project_name: str = ""
    sample_id: str = ""
    sample_name: str = ""
    sample_weight: float = 0.0
    operator: str = ""
    notes: str = ""
    experiment_type: str = ""
    date: str = ""


@dataclass
class ExperimentCommandResult:
    """Standard command result for application-layer experiment operations."""

    success: bool
    message: str = ""
    experiment_id: str | None = None


@dataclass
class ExperimentStartResult:
    """Result object for experiment startup orchestration."""

    success: bool
    message: str = ""
    experiment_id: str | None = None
    experiment_data: Any | None = None
    experiment_file_path: str | None = None


@dataclass
class ExperimentStageStatus:
    """Runtime stage information safe to expose across layers."""

    phase: str = ""
    stage_name: str = ""
    stage_index: int = 0
    total_stages: int = 0
    elapsed_seconds: float = 0.0
    remaining_seconds: float | None = None


@dataclass
class ExperimentRuntimeStatus:
    """High-level experiment runtime status for presenters and views."""

    is_running: bool = False
    experiment_id: str | None = None
    status_text: str = ""
    system_message: str = ""
    elapsed_text: str = "00:00:00"
    current_stage: ExperimentStageStatus | None = None
