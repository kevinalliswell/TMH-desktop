from __future__ import annotations

from types import SimpleNamespace

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
