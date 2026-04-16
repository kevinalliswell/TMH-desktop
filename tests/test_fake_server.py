# test_fake_server.py
import sys
import time
import random
import threading
from PySide6.QtWidgets import QApplication
from src.ui.main_window import MainWindow
from src.device_clients.fake_device_server import FakeSerial
from src.device_clients.balance_client import BalanceClient
from src.device_clients.temp_client import TempClient
from src.device_clients.multi_mfc_client import MultiMFCClient
from src.device_clients.device_manager import DeviceManager
from src.device_clients.data_handler import DataHandler


def install_fake_devices(device_manager: DeviceManager):
    """
    注册 FakeSerial 模拟的设备
    - Balance (1 台)
    - TempClient (9 路温度，合并在一个寄存器模拟)
    - MultiMFCClient (4 台 MFC)
    """
    # 模拟 Balance
    balance = BalanceClient("Balance", {"port": "COM15"})
    balance._ser = FakeSerial("balance")
    device_manager.register_device("Balance", balance)

    # 模拟 Temp（9 路温度数据）
    temp = TempClient("Temp", {"port": "COM10", "slave_address": 1})
    temp._ser = FakeSerial("temp")
    device_manager.register_device("Temp", temp)

    # 模拟 MFC（N2, CO, CO2, H2）
    mfc = MultiMFCClient("MFC", {"port": "COM12", "channels": 4, "device_addr": 1})
    mfc._ser = FakeSerial("mfc")
    device_manager.register_device("MFC", mfc)


def main():
    app = QApplication(sys.argv)

    # 初始化设备管理器和数据处理
    device_manager = DeviceManager()
    data_handler = DataHandler(db_path=":memory:")  # 用内存数据库，避免落盘

    data_handler.set_device_manager(device_manager)

    # 注册 Fake 设备
    install_fake_devices(device_manager)

    # 启动设备和数据处理
    device_manager.start_all()
    data_handler.start()

    # 启动主界面
    window = MainWindow()
    # 替换掉 main_window 里的 device_manager/data_handler
    window.device_manager = device_manager
    window.data_handler = data_handler
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
