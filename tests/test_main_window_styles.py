#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试主窗体中的样式应用
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from PySide6.QtWidgets import QApplication
from src.ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    
    # 创建主窗体
    window = MainWindow()
    window.show()
    
    print("主窗体已打开，请检查监控面板样式是否正确应用")
    print("如果样式正确，应该看到：")
    print("- 监控面板有深色主题背景")
    print("- 主要温度值：红色大字体，黑色背景")
    print("- 重量值：青色大字体，黑色背景")
    print("- 流量值：蓝色大字体，黑色背景")
    print("- 次要温度：小字体，深色背景")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
