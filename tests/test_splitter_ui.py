#!/usr/bin/env python3
"""
测试历史查询页面的分割器功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication, QMainWindow
from src.ui.pages.history_query_page import HistoryQuery

def main():
    app = QApplication(sys.argv)
    
    # 创建主窗口
    window = QMainWindow()
    window.setWindowTitle("测试历史查询页面分割器")
    window.setGeometry(100, 100, 1200, 800)
    
    # 创建历史查询页面
    history_page = HistoryQuery()
    window.setCentralWidget(history_page)
    
    # 显示窗口
    window.show()
    
    print("历史查询页面已创建，包含可调节的分割器")
    print("您可以通过拖拽分割器来调整表格和曲线区域的占比")
    print("默认占比为1:1")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
