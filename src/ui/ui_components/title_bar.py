# src/ui/ui_components/title_bar.py
from pathlib import Path

from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout,
                               QLabel, QGraphicsOpacityEffect)
from PySide6.QtCore import Qt, QTimer, QDateTime, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPixmap
from src.utils.logger import get_logger
from src.utils.path_manager import PathManager
from src.utils.software_info import DEFAULT_SOFTWARE_INFO


class TitleBar(QWidget):
    """
    现代化自定义标题栏
    - 左侧：Logo + 系统信息
    - 右侧：通信状态 + 系统时间
    """

    def __init__(self, software_info=None, parent=None):
        super().__init__(parent)
        self.setObjectName("TitleBar")

        self.software_info = software_info or {}
        self.is_dark_theme = True

        self.logger = get_logger(__name__)
        self.init_ui()
        self.setup_timer()

    # ==============================
    # UI 初始化
    # ==============================
    def init_ui(self):
        """初始化现代化UI"""
        self.setFixedHeight(90)
        self.update_theme_style()  # 使用动态主题样式
        
        # 主布局
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(30, 15, 30, 15)
        main_layout.setSpacing(30)

        # 左侧：Logo和标题信息
        left_section = self.create_left_section()
        main_layout.addWidget(left_section)
        
        # 添加弹性空间
        main_layout.addStretch()
        
        # 右侧：状态信息
        right_section = self.create_right_section()
        main_layout.addWidget(right_section)

    def create_left_section(self):
        """创建左侧Logo和标题区域"""
        left_widget = QWidget()
        left_widget.setStyleSheet("background: transparent;")
        left_layout = QHBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(20)
        
        # Logo区域 - 添加现代化渐变背景和脉冲动画效果
        logo_container = QWidget()
        logo_container.setObjectName("logoContainer")
        logo_container.setFixedSize(60, 60)
        
        # 添加脉冲动画
        self.logo_opacity_effect = QGraphicsOpacityEffect()
        logo_container.setGraphicsEffect(self.logo_opacity_effect)
        
        self.logo_animation = QPropertyAnimation(self.logo_opacity_effect, b"opacity")
        self.logo_animation.setDuration(3000)
        self.logo_animation.setStartValue(1.0)
        self.logo_animation.setEndValue(0.7)
        self.logo_animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.logo_animation.setLoopCount(-1)
        self.logo_animation.start()
        
        logo_layout = QVBoxLayout(logo_container)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建Logo标签 - 优先使用图片，后备文字
        logo_label = QLabel()
        logo_label.setObjectName("logoLabel")
        logo_label.setAlignment(Qt.AlignCenter)
        
        # 加载PNG图片
        logo_path = self.logo_path()
        if Path(logo_path).exists():
            pixmap = QPixmap(logo_path)
            # 缩放图片到合适大小，使用高质量缩放
            scaled_pixmap = pixmap.scaled(50, 50, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
        else:
            # 如果图片不存在，显示文字作为后备
            self.logger.warning(f"标题栏Logo不存在: {logo_path}")
            logo_label.setText("TMH")
        
        logo_layout.addWidget(logo_label)
        
        left_layout.addWidget(logo_container)
        
        # 标题信息区域
        title_container = QWidget()
        title_layout = QVBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(3)
        
        # 主标题
        self.main_title = QLabel(self.software_info.get('description', DEFAULT_SOFTWARE_INFO['description']))
        self.main_title.setObjectName("mainTitle")
        title_layout.addWidget(self.main_title)
        
        # 副标题
        self.sub_title = QLabel("Iron Ore Comprehensive Performance Detection and Control System")
        self.sub_title.setObjectName("subTitle")
        title_layout.addWidget(self.sub_title)
        
        # 系统主题
        self.system_theme = QLabel("北京科技大学 · 炼铁新技术科研团队实验室")
        self.system_theme.setObjectName("systemTheme")
        title_layout.addWidget(self.system_theme)
        
        left_layout.addWidget(title_container)
        
        return left_widget

    @staticmethod
    def logo_path() -> str:
        return PathManager.get_resources_path("icons/ustb_logo.png")

    def create_right_section(self):
        """创建右侧状态信息区域"""
        right_widget = QWidget()
        right_widget.setStyleSheet("background: transparent;")
        right_layout = QHBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(15)

        # 通信状态改为仅在状态栏显示，标题栏不再重复展示
        # 系统时间
        self.time_display = QLabel()
        self.time_display.setObjectName("timeDisplay")
        self.time_display.setAlignment(Qt.AlignCenter)
        self.time_display.setFixedHeight(40)
        right_layout.addWidget(self.time_display)
        
        return right_widget

    # ==============================
    # 时间更新
    # ==============================
    def setup_timer(self):
        """设置时间更新定时器"""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)  # 每秒更新一次
        self.update_time()  # 立即更新一次

    def update_time(self):
        """更新时间显示"""
        current_time = QDateTime.currentDateTime()
        time_str = current_time.toString("yyyy-MM-dd hh:mm:ss")
        if hasattr(self, 'time_display'):
            self.time_display.setText(time_str)

    # ==============================
    # 功能函数
    # ==============================
    def update_theme_style(self):
        """根据当前主题更新标题栏样式"""
        # 主题样式现在由主窗口的样式表控制
        # 这里只需要刷新样式
        self.style().unpolish(self)
        self.style().polish(self)
