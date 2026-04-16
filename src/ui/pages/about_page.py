from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel,
                           QScrollArea, QFrame, QGroupBox)
from PySide6.QtCore import Qt
import datetime

class AboutPage(QWidget):
    """关于页面"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        
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
        version_label = QLabel("版本 1.0.250929")
        version_label.setObjectName("aboutVersion")
        version_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(version_label)
        
        layout.addWidget(header_frame)
        
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