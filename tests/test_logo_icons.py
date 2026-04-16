#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试LOGO转图标效果的脚本
展示从TMH_USTB_LOGO.png生成的各种尺寸图标
"""

import sys
import os
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, 
                              QHBoxLayout, QWidget, QScrollArea, QGroupBox, QGridLayout)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QIcon

class LogoIconTestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TMH Logo 图标测试")
        self.setGeometry(100, 100, 1200, 800)
        
        # 设置窗口图标
        self._set_window_icon()
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # 显示图标信息
        self._create_icon_display(scroll_layout)
        
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)
    
    def _set_window_icon(self):
        """设置窗口图标"""
        icon_paths = [
            "resources/icons/tmh_logo_icon.ico",
            "resources/icons/tmh_logo_icon.png",
            "resources/icons/tmh_enhanced_icon.ico",
            "resources/icons/tmh_enhanced_icon.png"
        ]
        
        for icon_path in icon_paths:
            if os.path.exists(icon_path):
                icon = QPixmap(icon_path)
                if not icon.isNull():
                    self.setWindowIcon(icon)
                    print(f"✓ 窗口图标设置成功: {icon_path}")
                    return
        
        print("⚠ 未找到可用的窗口图标文件")
    
    def _create_icon_display(self, layout):
        """创建图标显示区域"""
        # 标题
        title_label = QLabel("TMH Logo 图标展示")
        title_label.setStyleSheet("font-size: 28px; font-weight: bold; margin: 20px; color: #2C3E50;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 标准图标组
        standard_group = self._create_icon_group("标准图标", "tmh_logo_icon", layout)
        
        # 圆角图标组
        rounded_group = self._create_icon_group("圆角图标", "tmh_logo_rounded", layout)
        
        # 正方形图标组
        square_group = self._create_icon_group("正方形图标", "tmh_logo_square", layout)
        
        # 增强版图标组
        enhanced_group = self._create_icon_group("增强版图标", "tmh_enhanced_icon", layout)
        
        # 预览图
        self._create_preview_section(layout)
    
    def _create_icon_group(self, title, prefix, parent_layout):
        """创建图标组"""
        group = QGroupBox(title)
        group.setStyleSheet("""
            QGroupBox {
                font-size: 16px;
                font-weight: bold;
                margin: 10px;
                padding: 10px;
                border: 2px solid #BDC3C7;
                border-radius: 8px;
                background-color: #F8F9FA;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        group_layout = QGridLayout(group)
        
        # 显示不同尺寸的图标
        sizes = [16, 24, 32, 48, 64, 128, 256]
        row, col = 0, 0
        
        for size in sizes:
            # 创建图标标签
            icon_label = QLabel(f"{size}x{size}")
            icon_label.setStyleSheet("font-size: 12px; margin: 5px;")
            icon_label.setAlignment(Qt.AlignCenter)
            
            # 加载并显示图标
            icon_display = self._load_icon_display(prefix, size)
            
            # 添加到网格布局
            group_layout.addWidget(icon_label, row, col)
            group_layout.addWidget(icon_display, row + 1, col)
            
            col += 1
            if col >= 7:  # 每行最多7个
                col = 0
                row += 2
        
        parent_layout.addWidget(group)
        return group
    
    def _load_icon_display(self, prefix, size):
        """加载并显示图标"""
        icon_display = QLabel()
        icon_display.setFixedSize(80, 80)
        icon_display.setStyleSheet("""
            border: 1px solid #BDC3C7;
            border-radius: 4px;
            background-color: white;
            margin: 2px;
        """)
        icon_display.setAlignment(Qt.AlignCenter)
        
        # 尝试加载图标
        icon_paths = [
            f"resources/icons/{prefix}_{size}x{size}.png",
            f"resources/icons/{prefix}.png"
        ]
        
        for icon_path in icon_paths:
            if os.path.exists(icon_path):
                pixmap = QPixmap(icon_path)
                if not pixmap.isNull():
                    # 缩放到合适大小
                    scaled_pixmap = pixmap.scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    icon_display.setPixmap(scaled_pixmap)
                    break
        
        return icon_display
    
    def _create_preview_section(self, layout):
        """创建预览图部分"""
        preview_group = QGroupBox("预览图")
        preview_group.setStyleSheet("""
            QGroupBox {
                font-size: 16px;
                font-weight: bold;
                margin: 10px;
                padding: 10px;
                border: 2px solid #BDC3C7;
                border-radius: 8px;
                background-color: #F8F9FA;
            }
        """)
        
        preview_layout = QVBoxLayout(preview_group)
        
        # 加载预览图
        preview_path = "resources/icons/tmh_logo_preview.png"
        if os.path.exists(preview_path):
            preview_label = QLabel()
            pixmap = QPixmap(preview_path)
            if not pixmap.isNull():
                # 缩放到合适大小
                scaled_pixmap = pixmap.scaled(800, 600, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                preview_label.setPixmap(scaled_pixmap)
                preview_label.setAlignment(Qt.AlignCenter)
                preview_layout.addWidget(preview_label)
            else:
                error_label = QLabel("无法加载预览图")
                error_label.setStyleSheet("color: red; font-size: 14px;")
                error_label.setAlignment(Qt.AlignCenter)
                preview_layout.addWidget(error_label)
        else:
            error_label = QLabel("预览图文件不存在")
            error_label.setStyleSheet("color: red; font-size: 14px;")
            error_label.setAlignment(Qt.AlignCenter)
            preview_layout.addWidget(error_label)
        
        layout.addWidget(preview_group)

def main():
    app = QApplication(sys.argv)
    
    # 设置应用程序图标
    icon_paths = [
        "resources/icons/tmh_logo_icon.ico",
        "resources/icons/tmh_logo_icon.png",
        "resources/icons/tmh_enhanced_icon.ico"
    ]
    
    for icon_path in icon_paths:
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
            print(f"✓ 应用程序图标设置成功: {icon_path}")
            break
    
    window = LogoIconTestWindow()
    window.show()
    
    print("\n图标测试窗口已打开，请查看:")
    print("1. 窗口标题栏的图标")
    print("2. 任务栏的图标")
    print("3. 窗口内各种尺寸和样式的图标展示")
    print("4. 预览图展示")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
