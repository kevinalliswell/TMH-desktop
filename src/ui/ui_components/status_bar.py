# src/ui/ui_components/status_bar.py
from PySide6.QtWidgets import QStatusBar, QLabel


class StatusBar(QStatusBar):
    """
    系统状态栏
    显示数据库状态 / 实验运行状态 / 消息提示
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("StatusBar")


        # 左侧消息提示
        self.message_label = QLabel("就绪")
        self.addPermanentWidget(self.message_label)

        # # 数据库状态
        # self.db_status = QLabel("数据库: 未连接")
        # self.addPermanentWidget(self.db_status)

        # 实验状态
        # self.exp_status = QLabel("实验: 未运行")
        # self.addPermanentWidget(self.exp_status)

    def set_message(self, msg: str, level: str = "info"):
        self.message_label.setText(msg)
        if level == "ok":
            self.message_label.setStyleSheet("color: #4CAF50; font-weight: bold;")  # 绿色
        elif level == "error":
            self.message_label.setStyleSheet("color: #F44336; font-weight: bold;")  # 红色
        else:
            self.message_label.setStyleSheet("color: #9E9E9E;")  # 灰色/普通
