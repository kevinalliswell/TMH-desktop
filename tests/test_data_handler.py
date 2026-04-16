import os
import tempfile
import time
import sqlite3
import pytest
from PySide6.QtCore import QCoreApplication

from src.device_clients.data_handler import DataHandler
from src.device_clients.device_manager import DeviceManager
from src.device_clients.balance_client import BalanceClient
from src.device_clients.temp_client import TempClient
from src.device_clients.multi_mfc_client import MultiMFCClient
from src.device_clients.fake_device_server import FakeSerial


@pytest.fixture(scope="function")
def temp_db():
    """临时数据库文件"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture(scope="function")
def device_manager_with_fake():
    """创建带 FakeSerial 的设备管理器"""
    dm = DeviceManager()

    # 注册一个模拟天平
    balance = BalanceClient("balance", {"port": "FAKE"})
    balance._ser = FakeSerial("balance")
    dm.register_device("balance", balance)

    # 注册一个模拟温控器
    temp = TempClient("temp", {"port": "FAKE", "slave_address": 1})
    temp._ser = FakeSerial("temp")
    dm.register_device("temp", temp)

    # 注册一个模拟 MFC
    mfc = MultiMFCClient("mfc", {"port": "FAKE", "channels": 2, "device_addr": 1})
    mfc._ser = FakeSerial("mfc")
    dm.register_device("mfc", mfc)

    return dm


def test_data_handler_start_stop(temp_db, device_manager_with_fake, qtbot):
    """测试 DataHandler 启停和信号发射"""
    app = QCoreApplication([])

    handler = DataHandler(db_path=temp_db, save_interval=1)
    handler.set_device_manager(device_manager_with_fake)

    received = {"weight": False, "temperature": False, "flow": False, "all": False}

    handler.weight_data_updated.connect(lambda d: received.__setitem__("weight", True))
    handler.temperature_data_updated.connect(lambda d: received.__setitem__("temperature", True))
    handler.flow_data_updated.connect(lambda d: received.__setitem__("flow", True))
    handler.all_data_updated.connect(lambda d: received.__setitem__("all", True))

    device_manager_with_fake.start_all_devices()
    handler.start()

    qtbot.wait(2000)  # 等待 2 秒采集数据

    handler.stop()
    device_manager_with_fake.stop_all_devices()

    assert all(received.values())

    # 验证数据库是否写入
    conn = sqlite3.connect(temp_db)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM weight_data")
    weight_count = cur.fetchone()[0]
    conn.close()
    assert weight_count > 0
