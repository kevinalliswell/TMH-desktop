#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单测试监控面板样式
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel
from PySide6.QtCore import Qt

def main():
    app = QApplication(sys.argv)
    
    # 加载深色主题样式
    style_file = os.path.join(os.path.dirname(__file__), 'src', 'ui', 'styles', 'dark_theme.qss')
    if os.path.exists(style_file):
        with open(style_file, 'r', encoding='utf-8') as f:
            app.setStyleSheet(f.read())
    
    # 创建主窗口
    window = QMainWindow()
    window.setWindowTitle("监控面板样式测试")
    window.setGeometry(100, 100, 600, 400)
    
    # 创建中央部件
    central_widget = QWidget()
    window.setCentralWidget(central_widget)
    
    # 创建布局
    layout = QVBoxLayout(central_widget)
    
    # 测试样式是否正确应用
    test_label = QLabel("测试标签")
    test_label.setObjectName("mainLabel")
    test_label.setText("主要标签测试")
    layout.addWidget(test_label)
    
    test_temp = QLabel("25.5")
    test_temp.setObjectName("tempValue")
    test_temp.setText("25.5")
    layout.addWidget(test_temp)
    
    test_weight = QLabel("100.123")
    test_weight.setObjectName("weightValue")
    test_weight.setText("100.123")
    layout.addWidget(test_weight)
    
    test_flow = QLabel("1.25")
    test_flow.setObjectName("flowValue")
    test_flow.setText("1.25")
    layout.addWidget(test_flow)
    
    test_minor = QLabel("24.1")
    test_minor.setObjectName("minorTempValue")
    test_minor.setText("24.1")
    layout.addWidget(test_minor)
    
    window.show()
    
    print("样式测试窗口已打开，请检查样式是否正确应用")
    print("如果样式正确，应该看到：")
    print("- 主要标签：白色文字")
    print("- 温度值：红色大字体，黑色背景")
    print("- 重量值：青色大字体，黑色背景")
    print("- 流量值：蓝色大字体，黑色背景")
    print("- 次要温度：小字体，深色背景")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
