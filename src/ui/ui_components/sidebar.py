# src/ui/ui_components/sidebar.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QFrame, QHBoxLayout
from PySide6.QtCore import Signal, Qt


class Sidebar(QFrame):
    """
    左侧菜单栏
    - 提供菜单按钮
    - 支持折叠/展开
    - 对外发射 page_selected 信号
    """

    page_selected = Signal(int)  # 发射页面索引

    def __init__(self, parent=None):
        super().__init__(parent)
        self.buttons = []
        self.is_expanded = True
        self.toggle_button = None
        self._init_ui()

    def _init_ui(self):
        self.setFixedWidth(150)  # 默认展开宽度
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)

        self.menu_items = [
            ("首页", "🏠"),
            ("实验管理", "🧪"),
            ("实验配置", "⚙️"),
            ("历史查询", "📊"),
            ("通信设置", "🔌"),
            ("使用帮助", "❓"),
            ("关于系统", "ℹ️"),
        ]

        for i, (text, icon) in enumerate(self.menu_items):
            btn = QPushButton(f"{icon} {text}")
            btn.setFixedHeight(60)
            # 设置字体大小
            btn.setStyleSheet("font-size: 16px;")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, index=i: self._on_button_clicked(index))
            btn.original_text = text
            btn.icon_text = icon
            self.buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        # 折叠/展开按钮
        self.toggle_button = QPushButton("◀")
        self.toggle_button.setFixedSize(40, 40)  # 增大按钮尺寸
        self.toggle_button.clicked.connect(self.toggle_sidebar)

        toggle_layout = QHBoxLayout()
        toggle_layout.addStretch()
        toggle_layout.addWidget(self.toggle_button)
        layout.addLayout(toggle_layout)

        # 默认选中首页
        if self.buttons:
            self.buttons[0].setChecked(True)

    def _on_button_clicked(self, index: int):
        """按钮点击时切换选中状态并发射信号"""
        for i, btn in enumerate(self.buttons):
            btn.setChecked(i == index)
        self.page_selected.emit(index)

    def toggle_sidebar(self):
        """切换侧边栏展开/折叠状态"""
        if self.is_expanded:
            # 折叠：只显示图标
            self.setFixedWidth(60)
            self.toggle_button.setText("▶")
            for btn in self.buttons:
                btn.setText(btn.icon_text)
                btn.setToolTip(btn.original_text)  # 折叠时用 tooltip 显示文字
        else:
            # 展开：显示图标 + 文字
            self.setFixedWidth(150)  # 更新展开宽度
            self.toggle_button.setText("◀")
            for btn in self.buttons:
                btn.setText(f"{btn.icon_text} {btn.original_text}")
                btn.setToolTip("")
        self.is_expanded = not self.is_expanded
