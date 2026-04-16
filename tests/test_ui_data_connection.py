#!/usr/bin/env python3
"""
测试UI数据连接
模拟数据流并验证UI组件更新
"""

import sys
import os
import time
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.ui.pages.integrated_control_page import IntegratedControlPage
from src.device_clients.device_manager import DeviceManager
from src.device_clients.data_handler import DataHandler

def create_test_data():
    """创建测试数据"""
    import random
    import time
    
    current_time = time.time()
    
    return {
        "timestamp": current_time,
        "weight": {
            "timestamp": current_time,
            "data": 100.0 + random.uniform(-1, 1)
        },
        "temperatures": {
            f"T{i+1}": 25.0 + random.uniform(-2, 2) 
            for i in range(9)
        },
        "flows": {
            "N2": {"PV": 0.5 + random.uniform(-0.1, 0.1), "SV": 0.5},
            "CO": {"PV": 1.2 + random.uniform(-0.1, 0.1), "SV": 1.2},
            "CO2": {"PV": 1.0 + random.uniform(-0.1, 0.1), "SV": 1.0},
            "H2": {"PV": 0.7 + random.uniform(-0.1, 0.1), "SV": 0.7}
        }
    }

def main():
    app = QApplication(sys.argv)
    
    # 创建模拟的设备和数据处理器
    device_manager = DeviceManager()
    data_handler = DataHandler("data/test.db")
    
    # 创建集成控制页面
    control_page = IntegratedControlPage(device_manager, data_handler)
    control_page.show()
    
    # 创建定时器来模拟数据更新
    def update_data():
        test_data = create_test_data()
        print(f"📡 发送测试数据: {test_data}")
        data_handler.all_data_updated.emit(test_data)
    
    timer = QTimer()
    timer.timeout.connect(update_data)
    timer.start(1000)  # 每秒更新一次
    
    print("UI测试启动，数据将每秒更新一次...")
    print("请查看UI界面中的监控面板和图表是否正常显示数据")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
