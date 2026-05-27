from PySide6.QtWidgets import QWidget, QVBoxLayout, QFrame
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl
from src.utils.path_manager import PathManager
from src.utils.logger import get_logger

class HelpPage(QWidget):
    """帮助页面"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        # 设置帮助页面对象名称，用于样式应用
        self.setObjectName("helpPage")
        
        # 创建主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 创建容器框架
        container_frame = QFrame()
        container_frame.setObjectName("helpContainer")
        container_layout = QVBoxLayout(container_frame)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        # 创建Web引擎视图
        self.web_view = QWebEngineView()
        self.web_view.setObjectName("helpWebView")
        
        # 获取help.html的绝对路径
        help_file = PathManager.get_resources_path("help.html")

        get_logger(__name__).debug(f"help_file: {help_file}")
        
        # 加载本地HTML文件
        self.web_view.setUrl(QUrl.fromLocalFile(help_file))
        
        # 将Web视图添加到容器
        container_layout.addWidget(self.web_view)
        
        # 将容器添加到主布局
        layout.addWidget(container_frame) 