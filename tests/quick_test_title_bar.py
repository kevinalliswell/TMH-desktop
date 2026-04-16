#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TitleBar 快速测试脚本
简单验证标题栏组件的基本功能
"""

import sys
import os
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.ui.ui_components.title_bar import TitleBar


def quick_test():
    """快速测试函数"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # 创建主窗口
    window = QMainWindow()
    window.setWindowTitle("TitleBar 快速测试")
    window.setGeometry(100, 100, 1000, 600)
    
    # 软件信息
    software_info = {
        'description': 'TMH-LPF-900 铁矿石全性能综合检测与控制系统',
        'version': '1.0.0'
    }
    
    # 创建标题栏
    title_bar = TitleBar(software_info, window)
    
    # 设置主窗口布局
    central_widget = QWidget()
    window.setCentralWidget(central_widget)
    layout = QVBoxLayout(central_widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(title_bar)
    
    # 添加内容区域
    content = QLabel("TitleBar 测试成功！\n\n观察以下功能：\n• Logo脉冲动画\n• 时间显示更新\n• 通信状态显示\n• 现代化UI样式")
    content.setStyleSheet("""
        QLabel {
            background: #2d2d2d;
            color: white;
            font-size: 16px;
            padding: 20px;
            text-align: center;
        }
    """)
    layout.addWidget(content)
    
    # 测试通信状态
    title_bar.update_communication_status(True, "测试设备")
    
    window.show()
    
    print("✅ TitleBar 快速测试启动成功")
    print("📋 测试项目:")
    print("   • Logo脉冲动画效果")
    print("   • 时间显示自动更新")
    print("   • 通信状态显示 (已连接)")
    print("   • 现代化渐变背景")
    print("   • 圆角状态标签")
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(quick_test())
