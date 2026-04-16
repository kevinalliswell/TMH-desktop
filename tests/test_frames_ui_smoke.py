import os
import sys
import time

from PySide6.QtWidgets import QApplication

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.ui.ui_components.monitor_panel import MonitorPanel
from src.ui.ui_components.chart_tabs import ChartTabs
from tmh_comm.standard import build_balance_frame, build_mfc_frame, build_temp_frame


def _make_frames():
    temp = build_temp_frame(
        model="TEMP-CTRL",
        temperatures={"T1": 100.0, "T8": 888.8, "T9": 900.0},
        meta={"port": "COM10", "baudrate": 9600, "slave_address": 0},
    )
    weight = build_balance_frame(
        model="BALANCE-1200",
        weight=123.456,
        meta={"port": "COM15", "baudrate": 1200},
    )
    flows = {
        "N2": build_mfc_frame(model="MQV0020BS", gas_type="N2", pv=1.23, sv=1.50, meta={}),
        "CO": build_mfc_frame(model="MQV0020BS", gas_type="CO", pv=0.45, sv=0.50, meta={}),
    }
    return {"temperature": temp, "weight": weight, "flows": flows}


def _make_bad_frames():
    # payload 类型错误、pv NaN、weight 非数
    class Dummy:
        def __init__(self, payload):
            self.payload = payload

    return {
        "temperature": Dummy(payload="not-a-dict"),
        "weight": Dummy(payload={"weight": "oops"}),
        "flows": {
            "N2": Dummy(payload={"pv": float("nan")}),
            "CO2": None,
        },
    }


def main():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication(sys.argv)

    monitor = MonitorPanel()
    charts = ChartTabs()

    frames = _make_frames()
    bad_frames = _make_bad_frames()

    # 正常帧
    monitor.update_monitor(frames, initial_weight=200.0)
    charts.update_from_frames(time.time(), frames, experiment_status="运行中", system_prompt="OK", initial_weight=200.0)

    # 异常帧与空帧
    monitor.update_monitor(bad_frames, initial_weight=0.0)
    charts.update_from_frames(time.time(), bad_frames, experiment_status="运行中", system_prompt="BAD", initial_weight=0.0)
    monitor.update_monitor({}, initial_weight=0.0)
    charts.update_from_frames(time.time(), {}, experiment_status="运行中", system_prompt="EMPTY", initial_weight=0.0)

    print("frames UI smoke test: PASS")


if __name__ == "__main__":
    main()
