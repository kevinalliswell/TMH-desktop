from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                           QPushButton, QScrollArea, QFrame, QGroupBox)
from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
import datetime
import threading

from src.services.update_service import UpdateCheckResult, UpdateService
from src.utils.audit import audit, AuditCategory
from src.utils.software_info import load_software_info


class AboutPage(QWidget):
    """关于页面"""

    update_check_finished = Signal(object)

    def __init__(
        self,
        software_info: dict | None = None,
        update_service=None,
        auto_check: bool = True,
    ):
        super().__init__()
        self.software_info = software_info or load_software_info()
        self.update_service = update_service or UpdateService()
        self._update_check_in_progress = False
        self._release_url = None
        self._update_thread = None
        self.update_check_finished.connect(self._apply_update_result)
        self.init_ui()
        if auto_check:
            QTimer.singleShot(0, self.check_for_updates)
        
    def init_ui(self):
        # 设置页面对象名称，用于样式应用
        self.setObjectName("aboutPage")
        
        # 创建主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setObjectName("aboutScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 创建滚动内容容器
        scroll_content = QWidget()
        scroll_content.setObjectName("aboutScrollContent")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(10, 10, 10, 10)
        scroll_layout.setSpacing(20)
        
        # 添加页面标题
        self.create_header(scroll_layout)
        
        # 添加系统信息卡片
        self.create_system_info_card(scroll_layout)

        # 添加软件更新卡片
        self.create_update_card(scroll_layout)
        
        # 添加功能特性卡片
        self.create_features_card(scroll_layout)
        
        # 添加标准规范卡片
        self.create_standards_card(scroll_layout)
        
        # 添加开发团队卡片
        self.create_team_card(scroll_layout)
        
        # 添加版权信息卡片
        self.create_copyright_card(scroll_layout)
        
        # 添加联系方式卡片
        self.create_contact_card(scroll_layout)
        
        # 添加弹性空间
        scroll_layout.addStretch()
        
        # 设置滚动区域内容
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)
        
    def create_header(self, layout):
        """创建页面头部"""
        header_frame = QFrame()
        header_frame.setObjectName("aboutHeader")
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(20, 20, 20, 20)
        header_layout.setSpacing(10)
        
        # 主标题
        title_label = QLabel("TMH-LPF-900")
        title_label.setObjectName("aboutMainTitle")
        title_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(title_label)
        
        # 副标题
        subtitle_label = QLabel("铁矿石冶金性能综合检测与控制系统")
        subtitle_label.setObjectName("aboutSubTitle")
        subtitle_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(subtitle_label)
        
        # 版本信息
        self.version_label = QLabel(f"版本 {self.software_info['version']}")
        self.version_label.setObjectName("aboutVersion")
        self.version_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(self.version_label)

        layout.addWidget(header_frame)

    def create_update_card(self, layout):
        """创建软件更新卡片"""
        card = QGroupBox("软件更新")
        card.setObjectName("aboutInfoCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 30, 20, 20)
        card_layout.setSpacing(10)

        current_version = self.software_info.get("version", "unknown")
        self.update_status_label = QLabel(f"当前版本 {current_version}，尚未检查更新。")
        self.update_status_label.setObjectName("aboutCardContent")
        self.update_status_label.setWordWrap(True)
        card_layout.addWidget(self.update_status_label)

        button_layout = QHBoxLayout()
        self.check_update_button = QPushButton("检查更新")
        self.check_update_button.clicked.connect(self.check_for_updates)
        button_layout.addWidget(self.check_update_button)

        self.download_button = QPushButton("前往下载")
        self.download_button.clicked.connect(self.open_release_page)
        self.download_button.setVisible(False)
        button_layout.addWidget(self.download_button)
        button_layout.addStretch()
        card_layout.addLayout(button_layout)

        layout.addWidget(card)

    def check_for_updates(self):
        """在后台线程检查最新 GitHub Release。"""
        if self._update_check_in_progress:
            return
        self._update_check_in_progress = True
        self.check_update_button.setEnabled(False)
        self.download_button.setVisible(False)
        self.update_status_label.setText("正在检查更新…")
        self._update_thread = threading.Thread(
            target=self._run_update_check,
            name="tmh-update-check",
            daemon=True,
        )
        self._update_thread.start()

    def _run_update_check(self):
        result = self.update_service.check(self.software_info.get("version", "unknown"))
        self.update_check_finished.emit(result)

    def _apply_update_result(self, result: UpdateCheckResult):
        self._update_check_in_progress = False
        self.check_update_button.setEnabled(True)
        self._release_url = result.release_url

        if result.error:
            self.download_button.setVisible(False)
            self.update_status_label.setText("暂时无法检查更新，请稍后重试。")
            return

        if result.update_available:
            self.update_status_label.setText(
                f"发现新版本 {result.latest_version}（当前 {result.current_version}）。"
            )
            self.download_button.setVisible(bool(result.release_url))
            audit(
                AuditCategory.APP,
                "update_available",
                current_version=result.current_version,
                latest_version=result.latest_version,
                release_url=result.release_url,
            )
        else:
            self.download_button.setVisible(False)
            self.update_status_label.setText(
                f"当前版本 {result.current_version} 已是最新版本。"
            )

    def open_release_page(self):
        if self._release_url:
            QDesktopServices.openUrl(QUrl(self._release_url))
        
    def create_system_info_card(self, layout):
        """创建系统信息卡片"""
        card = self.create_info_card("系统简介", [
            "本系统是一套专业的铁矿石冶金性能检测与控制系统，",
            "采用先进的自动化控制技术，实现对实验过程的精确控制",
            "和数据的实时采集与分析。",
            "",
            "系统支持多种标准实验模式，能够满足不同实验需求，",
            "为铁矿石冶金性能研究提供可靠的技术支撑。"
        ])
        layout.addWidget(card)
        
    def create_features_card(self, layout):
        """创建功能特性卡片"""
        features_content = [
            "🌡️ <strong>温度精确控制</strong> - 采用PID控制算法，实现±1°C的控温精度",
            "💨 <strong>气体流量控制</strong> - 支持多种气体流量精确调节",
            "⚖️ <strong>重量实时监测</strong> - 高精度天平数据实时采集",
            "📊 <strong>数据采集存储</strong> - 完整的实验数据记录与管理",
            "📋 <strong>实验报告生成</strong> - 自动化生成标准格式实验报告",
            "🔧 <strong>设备状态监控</strong> - 实时监控设备运行状态",
            "⚙️ <strong>实验模式配置</strong> - 灵活的实验参数配置系统",
            "📈 <strong>数据可视化</strong> - 实时数据图表显示与分析"
        ]
        
        card = self.create_info_card("主要功能", features_content)
        layout.addWidget(card)
        
    def create_standards_card(self, layout):
        """创建标准规范卡片"""
        standards_content = [
            "本系统严格按照以下国家标准执行：",
            "",
            "📖 <strong>GB/T 13240-2018</strong> 铁矿石自由膨胀指数的测定",
            "📖 <strong>GB/T 13241-2017</strong> 铁矿石还原性能的测定", 
            "📖 <strong>GB/T 13242-2017</strong> 铁矿石低温粉化指数的测定",
            "",
            "系统设计完全符合标准要求，确保实验结果的准确性和可靠性。"
        ]
        
        card = self.create_info_card("标准规范", standards_content)
        layout.addWidget(card)
        
    def create_team_card(self, layout):
        """创建开发团队卡片"""
        team_content = [
            "<strong>开发单位：</strong>北京科技大学冶金与生态工程学院",
            "<strong>研发团队：</strong>炼铁新技术科研团队",
            "<strong>技术负责人：</strong>史进朋 Shi Jinpeng",
            "",
            "团队在铁矿石冶金性能检测领域拥有丰富的科研经验，",
            "致力于为冶金行业提供先进的技术解决方案。"
        ]
        
        card = self.create_info_card("开发团队", team_content)
        layout.addWidget(card)
        
    def create_copyright_card(self, layout):
        """创建版权信息卡片"""
        current_year = datetime.datetime.now().year
        copyright_content = [
            f"版权所有 © {current_year} 北京科技大学",
            "保留所有权利",
            "",
            "本软件受版权法保护，未经授权不得复制、分发或修改。",
            "如需商业使用，请联系开发团队获取授权。"
        ]
        
        card = self.create_info_card("版权信息", copyright_content)
        layout.addWidget(card)
        
    def create_contact_card(self, layout):
        """创建联系方式卡片"""
        contact_content = [
            "<strong>地址：</strong>北京市海淀区学院路30号",
            "<strong>电话：</strong>137-2019-7352",
            "<strong>邮箱：</strong>shijinpeng06@126.com",
            "",
            "如有技术问题或合作需求，欢迎随时联系我们。",
            "我们将竭诚为您提供技术支持和服务。"
        ]
        
        card = self.create_info_card("联系方式", contact_content)
        layout.addWidget(card)
        
    def create_info_card(self, title, content_list):
        """创建信息卡片"""
        card = QGroupBox()
        card.setObjectName("aboutInfoCard")
        card.setTitle(title)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 30, 20, 20)
        layout.setSpacing(8)
        
        for content in content_list:
            if content.strip():  # 跳过空行
                label = QLabel(content)
                label.setObjectName("aboutCardContent")
                label.setWordWrap(True)
                layout.addWidget(label)
            else:
                # 添加空行
                layout.addSpacing(8)
        
        return card
