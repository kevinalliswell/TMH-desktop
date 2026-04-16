# test_fake_integration.py
import sys
import time
import random
from PySide6.QtWidgets import QApplication

from src.ui.main_window import MainWindow
from src.device_clients.device_manager import DeviceManager
from src.device_clients.data_handler import DataHandler
from src.device_clients.base_device import BaseDevice


# ========== Fake 设备实现 ==========
class FakeBalance(BaseDevice):
    def __init__(self, name="Balance", config=None):
        super().__init__(name, config or {})
        self._last_weight = None

    def start(self): self._running = True
    def stop(self): self._running = False
    def send_command(self, cmd, payload=None): pass

    def read(self):
        self._last_weight = round(100 + random.uniform(-1, 1), 3)
        self.mark_data_updated()

    def get_status(self):
        self.read()
        status = super().get_status()
        status.update({"last_weight": self._last_weight})
        return status


class FakeTemp(BaseDevice):
    def __init__(self, name="Temp", config=None):
        super().__init__(name, config or {})
        self._last_temps = {}

    def start(self): self._running = True
    def stop(self): self._running = False
    def send_command(self, cmd, payload=None): pass

    def read(self):
        self._last_temps = {f"T{i+1}": round(25 + random.uniform(-2, 2), 1) for i in range(9)}
        self.mark_data_updated()

    def get_status(self):
        self.read()
        status = super().get_status()
        status.update({"last_temperatures_C": self._last_temps})
        return status


class FakeMFC(BaseDevice):
    def __init__(self, name="MFC", config=None):
        super().__init__(name, config or {})
        self._last_values = {}

    def start(self): self._running = True
    def stop(self): self._running = False
    def send_command(self, cmd, payload=None): pass

    def read(self):
        self._last_values = {
            "N2": {"PV": round(random.uniform(0.3, 0.5), 2), "SV": 0.5},
            "CO": {"PV": round(random.uniform(1.0, 1.2), 2), "SV": 1.2},
            "CO2": {"PV": round(random.uniform(0.8, 1.0), 2), "SV": 1.0},
            "H2": {"PV": round(random.uniform(0.5, 0.7), 2), "SV": 0.7},
        }
        self.mark_data_updated()

    def get_status(self):
        self.read()
        status = super().get_status()
        status.update({"last_values": self._last_values})
        return status


# ========== 主程序入口 ==========
def main():
    app = QApplication(sys.argv)

    # 设备管理器和数据处理
    dm = DeviceManager()
    dh = DataHandler(db_path=":memory:")  # 内存数据库，避免生成文件
    dh.set_device_manager(dm)

    # 注册 Fake 设备
    dm.register_device("Balance", FakeBalance())
    dm.register_device("Temp", FakeTemp())
    dm.register_device("MFC", FakeMFC())

    # 启动设备与采集
    dm.start_all()
    dh.start()

    # 启动主窗口
    window = MainWindow()
    window.device_manager = dm
    window.data_handler = dh
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
