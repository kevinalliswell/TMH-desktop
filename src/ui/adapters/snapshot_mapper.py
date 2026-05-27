from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


def _safe_number(value) -> Optional[float]:
    if value is None:
        return None
    if not isinstance(value, (int, float)):
        return None
    if value != value:
        return None
    return float(value)


@dataclass
class FrameUiSnapshot:
    """UI-friendly snapshot mapped from backend standard frames."""

    temperatures: dict[str, Optional[float]] = field(default_factory=dict)
    flows: dict[str, Optional[float]] = field(default_factory=dict)
    weight: Optional[float] = None
    sample_temperature: Optional[float] = None
    total_flow: float = 0.0


@dataclass
class ChartTableRowData:
    """Formatted row data for the experiment chart table."""

    timestamp_text: str
    duration_text: str
    sample_temperature_text: str
    flow_texts: dict[str, str]
    weight_text: str
    weight_loss_text: str
    weight_loss_rate_text: str
    experiment_status: str
    system_prompt: str


def map_frames_to_ui_snapshot(frames: dict) -> FrameUiSnapshot:
    """Normalize backend frames into a single UI snapshot."""
    if not isinstance(frames, dict):
        frames = {}

    temperatures = {}
    temp_frame = frames.get("temperature")
    if temp_frame and hasattr(temp_frame, "payload"):
        payload = temp_frame.payload if isinstance(temp_frame.payload, dict) else {}
        raw_temps = payload.get("temperatures", {}) or {}
        if isinstance(raw_temps, dict):
            temperatures = {
                name: _safe_number(value)
                for name, value in raw_temps.items()
            }

    flows = {}
    total_flow = 0.0
    flow_frames = frames.get("flows")
    if isinstance(flow_frames, dict):
        for gas_type, flow_frame in flow_frames.items():
            if not flow_frame or not hasattr(flow_frame, "payload"):
                continue
            payload = flow_frame.payload if isinstance(flow_frame.payload, dict) else {}
            pv = _safe_number(payload.get("pv"))
            flows[gas_type] = pv
            if pv is not None:
                total_flow += pv

    weight = None
    weight_frame = frames.get("weight")
    if weight_frame and hasattr(weight_frame, "payload"):
        payload = weight_frame.payload if isinstance(weight_frame.payload, dict) else {}
        weight = _safe_number(payload.get("weight"))

    return FrameUiSnapshot(
        temperatures=temperatures,
        flows=flows,
        weight=weight,
        sample_temperature=temperatures.get("T8"),
        total_flow=total_flow,
    )


def build_chart_table_row(
    timestamp: float,
    snapshot: FrameUiSnapshot,
    experiment_start_time: Optional[float],
    experiment_status: str = "",
    system_prompt: str = "",
    initial_weight: float = 0.0,
) -> ChartTableRowData:
    """Build a formatted table row DTO for ChartTabs."""
    dt = datetime.fromtimestamp(timestamp)
    timestamp_text = dt.strftime("%Y-%m-%d %H:%M:%S")

    if experiment_start_time is None:
        experiment_start_time = timestamp
    duration_seconds = int(timestamp - experiment_start_time)
    hours = duration_seconds // 3600
    minutes = (duration_seconds % 3600) // 60
    seconds = duration_seconds % 60
    duration_text = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    sample_temp = snapshot.sample_temperature
    sample_temperature_text = (
        f"{sample_temp:.1f}" if sample_temp is not None and sample_temp != 0 else "--"
    )

    flow_texts = {}
    for gas in ("N2", "CO", "CO2", "H2"):
        value = snapshot.flows.get(gas)
        flow_texts[gas] = f"{value:.2f}" if value is not None else "--"

    weight_text = f"{snapshot.weight:.3f}" if snapshot.weight is not None else "--"
    weight_loss_text = "--"
    weight_loss_rate_text = "--"
    if initial_weight > 0 and snapshot.weight is not None:
        weight_loss = initial_weight - snapshot.weight
        weight_loss_rate = (weight_loss / initial_weight) * 100
        weight_loss_text = f"{weight_loss:.3f}"
        weight_loss_rate_text = f"{weight_loss_rate:.2f}"

    return ChartTableRowData(
        timestamp_text=timestamp_text,
        duration_text=duration_text,
        sample_temperature_text=sample_temperature_text,
        flow_texts=flow_texts,
        weight_text=weight_text,
        weight_loss_text=weight_loss_text,
        weight_loss_rate_text=weight_loss_rate_text,
        experiment_status=experiment_status,
        system_prompt=system_prompt,
    )
