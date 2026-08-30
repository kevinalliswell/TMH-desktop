# src/ui/main_window.py
import os
import json
import logging
from dataclasses import dataclass

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QFrame,
    QHBoxLayout, QStackedWidget, QMessageBox
)
from PySide6.QtGui import QAction, QKeySequence, QPixmap

# 导入页面
from src.ui.pages.integrated_control_page import IntegratedControlPage
from src.ui.pages.experiment_mode_settings_page import ExperimentModeSettingsPage
from src.ui.pages.history_query_page import HistoryQuery
from src.ui.pages.help_page import HelpPage
from src.ui.pages.about_page import AboutPage
from src.ui.pages.communication_settings_page import CommunicationSettings
from src.ui.pages.home_page import HomePage

# 导入 UI 组件
from src.ui.ui_components.title_bar import TitleBar
from src.ui.ui_components.sidebar import Sidebar
from src.ui.ui_components.status_bar import StatusBar

# 导入运行时服务
from src.application.services import (
    CommunicationService,
    HistoryQueryService,
    ReportExportService,
)
from src.services.app_runtime import AppRuntime
from src.services.database import ExperimentDatabase
from src.services.experiment_facade import ExperimentFacade
from src.services.experiment_modes import ExperimentModeManager
from src.services.experiment_type_manager import ExperimentTypeManager
from src.utils.password_manager import PasswordManager


@dataclass
class UiDependencies:
    """UI composition root dependencies assembled by MainWindow."""

    experiment_api: ExperimentFacade
    communication_service: CommunicationService
    experiment_mode_manager: ExperimentModeManager
    experiment_type_manager: ExperimentTypeManager
    history_query_service: HistoryQueryService
    report_export_service: ReportExportService
    password_manager: PasswordManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.logger = logging.getLogger(__name__)
        self.runtime = None
        self.runtime_services = None
        self.ui_dependencies = None
        self.integrated_control_page = None

        # 软件信息
        self.software_info = self._load_software_info()
        self.setWindowTitle(f"{self.software_info['description']} V{self.software_info['version']}")
        self.setMinimumSize(1200, 800)
        
        # 窗体状态管理
        self.is_window_maximized = False
        
        # 设置窗口图标
        self._set_window_icon()

        # 初始化运行时服务
        self.runtime = AppRuntime(self)
        self.runtime.start()
        self.runtime_services = self.runtime.services
        self.ui_dependencies = self._build_ui_dependencies()
        self.runtime.comm_status_updated.connect(self._on_comm_status_updated)

        # 应用暗色主题
        self._apply_stylesheet("dark")

        # 初始化 UI
        self._init_ui()

        # 设置全屏快捷键
        self._create_fullscreen_action()

        self.logger.debug("主窗口初始化完成===")

    def _set_window_icon(self):
        """设置窗口图标"""
        try:
            # 尝试使用增强版图标
            icon_paths = [
                "resources/icons/tmh2_icon_128x128.ico",
                "resources/icons/tmh_logo_icon.ico", 
                "resources/icons/logo.ico",
                "resources/icons/tmh_icon.ico"
            ]
            
            for icon_path in icon_paths:
                if os.path.exists(icon_path):
                    icon = QPixmap(icon_path)
                    if not icon.isNull():
                        self.setWindowIcon(icon)
                        self.logger.info(f"窗口图标设置成功: {icon_path}")
                        return
            
            self.logger.warning("未找到可用的窗口图标文件")
        except Exception as e:
            self.logger.error(f"设置窗口图标失败: {e}")

    # ==============================
    # UI 初始化
    # ==============================
    def _init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(3)

        # 标题栏
        self.title_bar = TitleBar(self.software_info)
        title_frame = QFrame()
        title_layout = QVBoxLayout(title_frame)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.addWidget(self.title_bar)
        main_layout.addWidget(title_frame)

        # 内容区（侧边栏 + 页面区）
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(10)

        # 左侧 Sidebar
        self.sidebar = Sidebar()
        self.sidebar.setObjectName("Sidebar")  # 设置对象名称以应用样式
        self.sidebar.page_selected.connect(self._on_sidebar_clicked)
        content_layout.addWidget(self.sidebar)

        # 页面区
        self.stacked_widget = QStackedWidget()
        content_layout.addWidget(self.stacked_widget, 1)

        content_widget = QWidget()
        content_widget.setLayout(content_layout)
        main_layout.addWidget(content_widget)

        # 底部状态栏
        self.status_bar = StatusBar(self)
        self.setStatusBar(self.status_bar)

        # 创建并添加所有页面
        self._create_pages()

    # ==============================
    # 页面管理
    # ==============================
    def _build_ui_dependencies(self) -> UiDependencies:
        """Assemble UI-facing services in one place."""
        experiment_database = ExperimentDatabase()
        history_query_service = HistoryQueryService(repository=experiment_database)
        return UiDependencies(
            experiment_api=ExperimentFacade(self.runtime_services.experiment_runtime),
            communication_service=CommunicationService(),
            experiment_mode_manager=self.runtime_services.experiment_mode_manager,
            experiment_type_manager=self.runtime_services.experiment_type_manager,
            history_query_service=history_query_service,
            report_export_service=ReportExportService(
                history_query_service=history_query_service
            ),
            password_manager=PasswordManager(),
        )

    def _create_pages(self):
        self.integrated_control_page = IntegratedControlPage(
            self.runtime_services.device_manager,
            self.runtime_services.data_handler,
            self,
            experiment_api=self.ui_dependencies.experiment_api,
            device_hub=self.runtime_services.device_hub,
            gas_safety_limits=self.runtime_services.communication_config.mfc.gas_safety_limits,
            experiment_type_manager=self.ui_dependencies.experiment_type_manager,
        )

        self.comm_settings_page = CommunicationSettings(
            runtime=self.runtime,
            parent=self,
            communication_service=self.ui_dependencies.communication_service,
            apply_callback=self._apply_comm_settings,
            password_manager=self.ui_dependencies.password_manager,
        )

        self.experiment_mode_settings_page = ExperimentModeSettingsPage(
            parent=self,
            mode_manager=self.ui_dependencies.experiment_mode_manager,
            gas_safety_limits=self.runtime_services.communication_config.mfc.gas_safety_limits,
        )
        self.experiment_mode_settings_page.mode_created.connect(
            self._on_experiment_modes_changed
        )
        self.experiment_mode_settings_page.mode_updated.connect(
            self._on_experiment_modes_changed
        )
        self.experiment_mode_settings_page.mode_deleted.connect(
            self._on_experiment_modes_changed
        )

        self.history_query_page = HistoryQuery(
            parent=self,
            history_query_service=self.ui_dependencies.history_query_service,
            report_export_service=self.ui_dependencies.report_export_service,
            password_manager=self.ui_dependencies.password_manager,
        )

        pages = [
            HomePage(self.software_info),
            self.integrated_control_page,
            self.experiment_mode_settings_page,
            self.history_query_page,
            self.comm_settings_page,
            HelpPage(),
            AboutPage(),
        ]

        for page in pages:
            self.stacked_widget.addWidget(page)

    def _apply_comm_settings(self):
        """Apply settings and refresh pages that hold runtime-backed references."""
        self.runtime.apply_comm_settings()
        self.runtime_services = self.runtime.services
        self.ui_dependencies = self._build_ui_dependencies()
        if self.integrated_control_page:
            self.integrated_control_page.rebind_runtime(
                self.runtime_services.device_manager,
                self.runtime_services.data_handler,
                self.ui_dependencies.experiment_api,
                device_hub=self.runtime_services.device_hub,
                gas_safety_limits=self.runtime_services.communication_config.mfc.gas_safety_limits,
                experiment_type_manager=self.ui_dependencies.experiment_type_manager,
            )

    def _on_experiment_modes_changed(self, *_args) -> None:
        """Synchronously refresh every view of experiment_modes.json."""
        self.ui_dependencies.experiment_api.reload_experiment_modes()

    # ==============================
    # 通信状态
    # ==============================
    def _on_comm_status_updated(self, is_connected: bool, device_names: str, error_msg: str):
        # 通信状态仅在状态栏显示（标题栏不再重复展示）
        if is_connected and not error_msg:
            self.status_bar.set_message(f"已连接设备: {device_names}", "ok")
        elif is_connected and error_msg:
            self.status_bar.set_message(f"已连接: {device_names} | 异常: {error_msg}", "error")
        else:
            self.status_bar.set_message(
                f"设备状态: {error_msg}" if error_msg else "没有设备连接", "error"
            )

    # ==============================
    # 工具
    # ==============================
    def _on_sidebar_clicked(self, index):
        # 切换页面前检查通信设置是否有未保存修改
        current_widget = self.stacked_widget.currentWidget()
        if isinstance(current_widget, CommunicationSettings):
            if not current_widget.check_unsaved_changes():
                return
        self.stacked_widget.setCurrentIndex(index)

    def _create_fullscreen_action(self):
        action = QAction("全屏模式", self)
        action.setShortcut(QKeySequence("F11"))
        action.triggered.connect(self._toggle_fullscreen)
        self.addAction(action)
        self.is_fullscreen = False

    def _toggle_fullscreen(self):
        if self.is_fullscreen:
            self.showNormal()
        else:
            self.showFullScreen()
        self.is_fullscreen = not self.is_fullscreen

    def _apply_stylesheet(self, theme="dark"):
        from src.utils.path_manager import PathManager
        qss_file = "dark_theme.qss" if theme == "dark" else "light_theme.qss"
        # 样式文件在 resources/styles/ 目录中
        qss_path = PathManager.get_styles_path(qss_file)
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        else:
            self.logger.warning(f"样式文件不存在: {qss_path}")

    def _load_software_info(self):
        from src.utils.path_manager import PathManager
        info_path = PathManager.get_config_path("software.info")
        if not os.path.exists(info_path):
            return {
                "version": "1.0.0",
                "author": "北京科技大学",
                "description": "TMH-LPF-900 铁矿石全性能综合检测与控制系统",
                "release_date": "2024-01-20",
                "copyright": "© 2024 北京科技大学",
            }
        with open(info_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def changeEvent(self, event):
        """窗体状态变化事件处理"""
        super().changeEvent(event)
        
        if event.type() == event.Type.WindowStateChange:
            # 检测窗体最大化状态变化
            current_maximized = self.isMaximized()
            
            if current_maximized != self.is_window_maximized:
                self.is_window_maximized = current_maximized
                self._notify_window_state_changed(current_maximized)
    
    def _notify_window_state_changed(self, is_maximized):
        """通知窗体状态变化"""
        try:
            # 通知监控面板调整字体大小
            if hasattr(self, 'integrated_control_page') and self.integrated_control_page:
                if hasattr(self.integrated_control_page, 'monitor_panel'):
                    self.integrated_control_page.monitor_panel.set_window_maximized_state(is_maximized)
                    self.logger.debug(f"窗体状态变化通知发送: {'最大化' if is_maximized else '正常'}")
        except Exception as e:
            self.logger.error(f"通知窗体状态变化失败: {e}")

    def closeEvent(self, event):
        # 检查通信设置是否有未保存修改
        if hasattr(self, 'comm_settings_page') and self.comm_settings_page:
            if self.comm_settings_page.has_unsaved_changes:
                if not self.comm_settings_page.check_unsaved_changes():
                    event.ignore()
                    return

        # 增加关闭提示
        reply = QMessageBox.question(
            self,
            "退出确认",
            "确定要退出系统吗？\n\n退出后将结束实验、保存实验数据并关闭所有设备。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.No:
            event.ignore()
            return

        try:
            # 结束实验（如有实验在进行，可在此处添加相关逻辑）
            if hasattr(self, "integrated_control_page") and self.integrated_control_page:
                try:
                    if hasattr(self.integrated_control_page, "end_experiment"):
                        self.integrated_control_page.end_experiment()
                except Exception as e:
                    self.logger.error(f"结束实验出错: {e}")

            # 停止运行时服务
            if self.runtime:
                self.runtime.stop()

            # 如有其它需要保存的数据，可在此处添加保存逻辑

        except Exception as e:
            self.logger.error(f"处理关闭事件出错: {e}")

        super().closeEvent(event)
