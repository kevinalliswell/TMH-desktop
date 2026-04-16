# src/ui/pages/home_page.py
import json
import os

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap


class HomePage(QWidget):
    """首页 - 欢迎页面，展示软件基本信息"""

    def __init__(self, software_info: dict = None, parent=None):
        super().__init__(parent)
        self.software_info = software_info or self._load_software_info()
        self._init_ui()

    # ==============================
    # UI 初始化
    # ==============================
    def _init_ui(self):
        self.setObjectName("homePage")
        layout = QVBoxLayout(self)

        # Logo
        logo_label = QLabel()
        pixmap = QPixmap("resources/icons/USTB_logo_horizontal.png")
        if not pixmap.isNull():
            logo_label.setPixmap(
                pixmap.scaled(600, 600, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        logo_label.setAlignment(Qt.AlignCenter)

        # 欢迎文字
        welcome_text = QLabel("欢迎使用")
        welcome_text.setAlignment(Qt.AlignCenter)
        welcome_text.setStyleSheet("font-size: 36px; font-weight: bold;")

        # 软件名称
        title_text = QLabel(self.software_info.get("description", ""))
        title_text.setAlignment(Qt.AlignCenter)
        title_text.setStyleSheet("font-size: 28px; font-weight: bold;")

        # 软件信息区域
        info_widget = self._create_info_widget()

        # 布局组装
        layout.addStretch()
        layout.addWidget(logo_label)
        layout.addWidget(welcome_text)
        layout.addWidget(title_text)
        layout.addSpacing(20)
        layout.addWidget(info_widget)
        layout.addStretch()

    def _create_info_widget(self) -> QWidget:
        """创建软件信息展示区域"""
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setSpacing(8)

        info_style = "font-size: 14px; color: #888888;"
        small_style = "font-size: 12px; color: #888888;"

        info_items = [
            (f"版本: {self.software_info.get('version', '')}", info_style),
            (f"作者: {self.software_info.get('author', '')}", info_style),
            (f"发布日期: {self.software_info.get('release_date', '')}", info_style),
            ("版权所有 © 2025 北京科技大学@炼铁新技术科研团队", small_style),
            (f"联系方式: {self.software_info.get('contact', '')}", small_style),
            (f"官网: {self.software_info.get('website', '')}", small_style),
        ]

        for text, style in info_items:
            label = QLabel(text)
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet(style)
            info_layout.addWidget(label)

        return info_widget

    # ==============================
    # 工具方法
    # ==============================
    @staticmethod
    def _load_software_info() -> dict:
        """当未传入 software_info 时，从配置文件加载"""
        from src.utils.path_manager import PathManager
        info_path = PathManager.get_config_path("software.info")
        if os.path.exists(info_path):
            with open(info_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "version": "1.0.0",
            "author": "北京科技大学",
            "description": "TMH-LPF-900 铁矿石全性能综合检测与控制系统",
            "release_date": "2024-01-20",
            "copyright": "© 2024 北京科技大学",
        }
