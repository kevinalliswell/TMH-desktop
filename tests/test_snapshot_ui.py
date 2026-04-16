# test_snapshot_ui.py
"""
测试快照UI - 用于验证数据流从设备到UI的完整路径
"""
import sys
import json
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QTextEdit, QLabel

from src.device_clients.device_manager import DeviceManager
from src.device_clients.data_handler import DataHandler
from src.device_clients.fake_device_server import FakeBalance, FakeTemp, FakeMFC


# ========== 测试 UI ==========
class SnapshotWindow(QWidget):
    def __init__(self, data_handler):
        super().__init__()
        self.setWindowTitle("Snapshot 数据监控 - 测试虚拟设备数据流")
        self.resize(1000, 700)

        layout = QVBoxLayout(self)
        
        # 添加标题
        title_label = QLabel("虚拟设备数据流测试")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)
        
        # 数据展示区域
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet("font-family: 'Consolas', 'Monaco', monospace; font-size: 12px;")
        layout.addWidget(self.text_edit)

        # 订阅信号
        data_handler.all_data_updated.connect(self.show_snapshot)
        
        # 添加状态标签
        self.status_label = QLabel("等待数据...")
        self.status_label.setStyleSheet("color: orange; margin: 5px;")
        layout.addWidget(self.status_label)

    def show_snapshot(self, snapshot: dict):
        """显示快照数据"""
        self.status_label.setText("✅ 数据接收正常")
        self.status_label.setStyleSheet("color: green; margin: 5px;")
        
        # 格式化显示数据
        formatted_data = json.dumps(snapshot, indent=2, ensure_ascii=False)
        self.text_edit.setPlainText(formatted_data)


def main():
    """主函数 - 启动测试应用"""
    app = QApplication(sys.argv)
    
    try:
        print("🚀 启动虚拟设备数据流测试...")
        
        # 初始化设备管理器 & 数据处理器
        dm = DeviceManager()
        dh = DataHandler(db_path=":memory:")
        dh.set_device_manager(dm)

        # 注册 Fake 设备
        print("📡 注册虚拟设备...")
        dm.register_device("Balance", FakeBalance("Balance", {}))
        dm.register_device("Temp", FakeTemp("Temp", {}))
        dm.register_device("MFC", FakeMFC("MFC", {}))

        # 启动设备和服务
        print("▶️ 启动设备和服务...")
        dm.start_all()
        dh.start()

        # 显示测试窗口
        print("🖥️ 显示测试窗口...")
        window = SnapshotWindow(dh)
        window.show()
        
        print("✅ 测试应用启动完成！")
        print("💡 提示：观察窗口中的数据更新，验证数据流是否正常")

        sys.exit(app.exec())
        
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
