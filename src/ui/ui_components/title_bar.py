# src/ui/ui_components/title_bar.py
import os
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, 
                               QLabel, QGraphicsOpacityEffect)
from PySide6.QtCore import Qt, QTimer, QDateTime, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPixmap
from src.utils.logger import get_logger


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
        logo_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "resources", "icons", "ustb_logo.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            # 缩放图片到合适大小，使用高质量缩放
            scaled_pixmap = pixmap.scaled(50, 50, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
        else:
            # 如果图片不存在，显示文字作为后备
            logo_label.setText("TMH")
        
        logo_layout.addWidget(logo_label)
        
        left_layout.addWidget(logo_container)
        
        # 标题信息区域
        title_container = QWidget()
        title_layout = QVBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(3)
        
        # 主标题
        self.main_title = QLabel(self.software_info.get('description', 'TMH-LPF-900 铁矿石全性能综合检测与控制系统'))
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

    def create_right_section(self):
        """创建右侧状态信息区域"""
        right_widget = QWidget()
        right_widget.setStyleSheet("background: transparent;")
        right_layout = QHBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(15)
        
        # 通信状态
        self.comm_status = QLabel("未连接")
        self.comm_status.setObjectName("commStatus")
        self.comm_status.setAlignment(Qt.AlignCenter)
        self.comm_status.setFixedHeight(40)
        right_layout.addWidget(self.comm_status)
        
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
    _MAX_STATUS_LEN = 36  # label 显示文本的最大字符数

    def update_communication_status(self, is_connected: bool, device_name: str = "", error_message: str = ""):
        """更新通信状态

        状态语义：
        - is_connected=True  + error_message=""    -> connected  (全部连接，绿色)
        - is_connected=True  + error_message 非空  -> partial    (部分连接，橙色)
        - is_connected=False + error_message 非空  -> error      (错误，红色)
        - is_connected=False + error_message=""    -> disconnected (未连接，灰色)
        """
        if is_connected and not error_message:
            status_text = f"已连接 {device_name}" if device_name else "已连接"
            status_key = "connected"
        elif is_connected and error_message:
            status_text = f"部分连接 {device_name}" if device_name else "部分连接"
            status_key = "partial"
        elif error_message:
            status_text = f"连接错误: {error_message}"
            status_key = "error"
        else:
            status_text = "未连接"
            status_key = "disconnected"

        # 长文本保护：label 截断 + tooltip 显示完整内容
        if len(status_text) > self._MAX_STATUS_LEN:
            self.comm_status.setToolTip(status_text)
            status_text = status_text[:self._MAX_STATUS_LEN - 1] + "…"
        else:
            self.comm_status.setToolTip("")

        self.comm_status.setText(status_text)
        self.comm_status.setProperty("status", status_key)

        # 刷新样式
        self.comm_status.style().unpolish(self.comm_status)
        self.comm_status.style().polish(self.comm_status)

    def update_theme_style(self):
        """根据当前主题更新标题栏样式"""
        # 主题样式现在由主窗口的样式表控制
        # 这里只需要刷新样式
        self.style().unpolish(self)
        self.style().polish(self)
