from __future__ import annotations

from types import SimpleNamespace

from src.ui.adapters.snapshot_mapper import map_frames_to_ui_snapshot
from src.ui.ui_components.control_panel import ControlPanel
from src.ui.ui_components.monitor_panel import MonitorPanel


class LabelStub:
    def __init__(self):
        self.text = ""

    def setText(self, value: str):
        self.text = value


def test_monitor_panel_maps_temperature_channels_to_pv_sv_labels():
    label_names = [
        "PV1", "SV1", "PV2", "SV2", "PV3", "SV3",
        "T7", "T8", "T9",
        "N2", "CO", "CO2", "H2", "TotalFlow",
        "Balance", "WeightLoss", "WeightLossRate",
    ]
    fake_panel = SimpleNamespace(
        labels={name: LabelStub() for name in label_names},
        TEMP_DISPLAY_LABELS=MonitorPanel.TEMP_DISPLAY_LABELS,
    )
    frames = {
        "temperature": SimpleNamespace(
            payload={
                "temperatures": {
                    "T1": 101.1,
                    "T2": 201.2,
                    "T3": 102.3,
                    "T4": 202.4,
                    "T5": 103.5,
                    "T6": 203.6,
                    "T7": 31.7,
                    "T8": 32.8,
                    "T9": 33.9,
                }
            }
        )
    }

    MonitorPanel.update_monitor(fake_panel, frames)

    assert fake_panel.labels["PV1"].text == "101.1"
    assert fake_panel.labels["SV1"].text == "201.2"
    assert fake_panel.labels["PV2"].text == "102.3"
    assert fake_panel.labels["SV2"].text == "202.4"
    assert fake_panel.labels["PV3"].text == "103.5"
    assert fake_panel.labels["SV3"].text == "203.6"
    assert fake_panel.labels["T7"].text == "31.7"
    assert fake_panel.labels["T8"].text == "32.8"
    assert fake_panel.labels["T9"].text == "33.9"


def test_flow_monitor_uses_pv_when_pv_and_sv_differ():
    frames = {
        "flows": {
            "N2": SimpleNamespace(payload={"pv": 1.25, "sv": 8.75}),
            "CO": SimpleNamespace(payload={"pv": 0.50, "sv": 4.00}),
        }
    }

    snapshot = map_frames_to_ui_snapshot(frames)

    assert snapshot.flows == {"N2": 1.25, "CO": 0.50}
    assert snapshot.total_flow == 1.75

    fake_panel = SimpleNamespace(
        labels={
            name: LabelStub()
            for name in (
                "N2", "CO", "CO2", "H2", "TotalFlow",
                "Balance", "WeightLoss", "WeightLossRate",
            )
        },
        TEMP_DISPLAY_LABELS=MonitorPanel.TEMP_DISPLAY_LABELS,
    )
    MonitorPanel.update_monitor(fake_panel, frames)

    assert fake_panel.labels["N2"].text == "1.25"
    assert fake_panel.labels["CO"].text == "0.50"
    assert fake_panel.labels["TotalFlow"].text == "1.75"


def test_flow_labels_explicitly_distinguish_actual_pv_from_setpoint_sv():
    monitor_labels = [label for label, _, _ in MonitorPanel.FLOW_DISPLAY_ITEMS]

    assert all("PV" in label for label in monitor_labels)
    assert "SV" in ControlPanel.FLOW_SETPOINT_TITLE
