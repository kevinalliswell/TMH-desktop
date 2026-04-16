#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试新的监控面板设计
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PySide6.QtCore import QTimer
from src.ui.ui_components.monitor_panel import MonitorPanel

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("监控面板测试")
        self.setGeometry(100, 100, 800, 600)
        
        # 设置深色主题
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a1a;
                color: #ffffff;
            }
        """)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建布局
        layout = QVBoxLayout(central_widget)
        
        # 创建监控面板
        self.monitor_panel = MonitorPanel()
        layout.addWidget(self.monitor_panel)
        
        # 创建定时器来模拟数据更新
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(1000)  # 每秒更新一次
        
        # 初始化数据
        self.initial_weight = 100.0
        self.current_time = 0
        
    def update_data(self):
        """模拟数据更新"""
        import random
        import math
        
        # 模拟温度数据
        temperatures = {}
        for i in range(1, 10):
            base_temp = 25.0 + random.uniform(-2, 2)
            temperatures[f"T{i}"] = base_temp
        
        # 模拟流量数据
        flows = {
            "N2": {"PV": 0.5 + random.uniform(-0.1, 0.1)},
            "CO": {"PV": 1.0 + random.uniform(-0.2, 0.2)},
            "CO2": {"PV": 0.8 + random.uniform(-0.15, 0.15)},
            "H2": {"PV": 0.6 + random.uniform(-0.1, 0.1)}
        }
        
        # 模拟重量数据（逐渐减少）
        weight_loss = self.current_time * 0.01  # 每秒减少0.01g
        current_weight = self.initial_weight - weight_loss
        
        # 构建数据字典
        data = {
            "temperatures": temperatures,
            "flows": flows,
            "weight": {"data": current_weight, "timestamp": self.current_time},
            "initial_weight": self.initial_weight
        }
        
        # 更新监控面板
        self.monitor_panel.update_monitor(data)
        
        self.current_time += 1

def main():
    app = QApplication(sys.argv)
    
    # 加载深色主题样式
    style_file = os.path.join(os.path.dirname(__file__), 'src', 'ui', 'styles', 'dark_theme.qss')
    if os.path.exists(style_file):
        with open(style_file, 'r', encoding='utf-8') as f:
            app.setStyleSheet(f.read())
    
    window = TestWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
