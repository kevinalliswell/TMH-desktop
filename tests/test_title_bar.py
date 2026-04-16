#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TitleBar 组件测试文件
测试优化后的标题栏组件的各种功能
"""

import sys
import os
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QPushButton, QHBoxLayout
from PySide6.QtCore import QTimer

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.ui.ui_components.title_bar import TitleBar


class TestMainWindow(QMainWindow):
    """测试主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TitleBar 测试窗口")
        self.setGeometry(100, 100, 1200, 800)
        
        # 软件信息
        self.software_info = {
            'description': 'TMH-LPF-900 铁矿石全性能综合检测与控制系统',
            'version': '1.0.0',
            'author': '北京科技大学炼铁新技术科研团队'
        }
        
        self.init_ui()
        self.setup_test_timer()
        
    def init_ui(self):
        """初始化UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 创建标题栏
        self.title_bar = TitleBar(self.software_info, self)
        main_layout.addWidget(self.title_bar)
        
        # 创建测试控制区域
        test_widget = QWidget()
        test_widget.setStyleSheet("""
            QWidget {
                background: #2d2d2d;
                color: white;
            }
        """)
        test_layout = QVBoxLayout(test_widget)
        test_layout.setContentsMargins(20, 20, 20, 20)
        test_layout.setSpacing(15)
        
        # 测试按钮区域
        button_layout = QHBoxLayout()
        
        # 连接状态测试按钮
        self.connect_btn = QPushButton("模拟连接")
        self.connect_btn.clicked.connect(self.test_connected)
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background: #4CAF50;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #45a049;
            }
        """)
        button_layout.addWidget(self.connect_btn)
        
        # 断开连接测试按钮
        self.disconnect_btn = QPushButton("模拟断开")
        self.disconnect_btn.clicked.connect(self.test_disconnected)
        self.disconnect_btn.setStyleSheet("""
            QPushButton {
                background: #f44336;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #da190b;
            }
        """)
        button_layout.addWidget(self.disconnect_btn)
        
        # 错误状态测试按钮
        self.error_btn = QPushButton("模拟错误")
        self.error_btn.clicked.connect(self.test_error)
        self.error_btn.setStyleSheet("""
            QPushButton {
                background: #FF5722;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #e64a19;
            }
        """)
        button_layout.addWidget(self.error_btn)
        
        # 主题切换测试按钮
        self.theme_btn = QPushButton("切换主题")
        self.theme_btn.clicked.connect(self.test_theme_toggle)
        self.theme_btn.setStyleSheet("""
            QPushButton {
                background: #2196F3;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #1976D2;
            }
        """)
        button_layout.addWidget(self.theme_btn)
        
        test_layout.addLayout(button_layout)
        
        # 信息显示区域
        self.info_label = QLabel("点击按钮测试标题栏功能")
        self.info_label.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-size: 14px;
                padding: 10px;
                background: rgba(255,255,255,0.1);
                border-radius: 5px;
            }
        """)
        test_layout.addWidget(self.info_label)
        
        # 添加弹性空间
        test_layout.addStretch()
        
        main_layout.addWidget(test_widget)
        
    def setup_test_timer(self):
        """设置测试定时器"""
        self.test_timer = QTimer()
        self.test_timer.timeout.connect(self.update_test_info)
        self.test_timer.start(2000)  # 每2秒更新一次
        
    def update_test_info(self):
        """更新测试信息"""
        current_time = self.title_bar.time_display.text()
        comm_status = self.title_bar.comm_status.text()
        
        info_text = f"""
        当前时间: {current_time}
        通信状态: {comm_status}
        主题模式: {'暗色' if self.title_bar.is_dark_theme else '亮色'}
        
        测试说明:
        - 点击"模拟连接"测试连接状态显示
        - 点击"模拟断开"测试断开状态显示  
        - 点击"模拟错误"测试错误状态显示
        - 点击"切换主题"测试主题切换功能
        - 观察Logo的脉冲动画效果
        - 观察时间显示是否正常更新
        """
        self.info_label.setText(info_text)
        
    def test_connected(self):
        """测试连接状态"""
        self.title_bar.update_communication_status(True, "测试设备")
        self.info_label.setText("✅ 已测试连接状态 - 应显示绿色'已连接 测试设备'")
        
    def test_disconnected(self):
        """测试断开状态"""
        self.title_bar.update_communication_status(False)
        self.info_label.setText("❌ 已测试断开状态 - 应显示红色'未连接'")
        
    def test_error(self):
        """测试错误状态"""
        self.title_bar.update_communication_status(False, "", "设备通信超时")
        self.info_label.setText("⚠️ 已测试错误状态 - 应显示橙色'连接错误: 设备通信超时'")
        
    def test_theme_toggle(self):
        """测试主题切换"""
        self.title_bar.is_dark_theme = not self.title_bar.is_dark_theme
        self.title_bar.update_theme_style()
        
        # 更新整个窗口的主题
        if self.title_bar.is_dark_theme:
            self.setStyleSheet("""
                QMainWindow {
                    background: #1a1a1a;
                }
            """)
        else:
            self.setStyleSheet("""
                QMainWindow {
                    background: #f0f0f0;
                }
            """)
            
        self.info_label.setText(f"🎨 已切换主题 - 当前为{'暗色' if self.title_bar.is_dark_theme else '亮色'}主题")


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用样式
    app.setStyle('Fusion')
    
    # 创建测试窗口
    window = TestMainWindow()
    window.show()
    
    print("TitleBar 测试程序启动")
    print("=" * 50)
    print("测试功能:")
    print("1. Logo脉冲动画效果")
    print("2. 时间显示更新")
    print("3. 通信状态显示 (连接/断开/错误)")
    print("4. 主题切换功能")
    print("5. 现代化UI样式")
    print("=" * 50)
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
