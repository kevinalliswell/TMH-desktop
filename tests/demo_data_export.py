# demo_data_export.py
"""
数据导出功能演示脚本
展示如何使用数据保存功能
"""

import sys
import os
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel
from PySide6.QtCore import Qt

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from ui.ui_components.chart_tabs import ChartTabs
from utils.data_saver import DataSaver, DataExportDialog


class DataExportDemo(QMainWindow):
    """数据导出演示窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TMH数据导出功能演示")
        self.setGeometry(100, 100, 800, 600)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 创建图表标签页
        self.chart_tabs = ChartTabs()
        layout.addWidget(self.chart_tabs)
        
        # 添加演示数据
        self.add_demo_data()
        
        # 设置实验信息
        self.set_demo_experiment_info()
        
        # 创建按钮
        button_layout = QVBoxLayout()
        
        # CSV导出按钮
        csv_btn = QPushButton("导出为CSV格式")
        csv_btn.clicked.connect(self.export_csv)
        button_layout.addWidget(csv_btn)
        
        # Excel导出按钮
        xls_btn = QPushButton("导出为Excel格式")
        xls_btn.clicked.connect(self.export_xls)
        button_layout.addWidget(xls_btn)
        
        # TXT导出按钮
        txt_btn = QPushButton("导出为TXT格式")
        txt_btn.clicked.connect(self.export_txt)
        button_layout.addWidget(txt_btn)
        
        # 导出对话框按钮
        dialog_btn = QPushButton("显示导出对话框")
        dialog_btn.clicked.connect(self.show_dialog)
        button_layout.addWidget(dialog_btn)
        
        # 状态标签
        self.status_label = QLabel("准备就绪")
        self.status_label.setAlignment(Qt.AlignCenter)
        button_layout.addWidget(self.status_label)
        
        layout.addLayout(button_layout)
    
    def add_demo_data(self):
        """添加演示数据"""
        import datetime
        import random
        
        # 启用表格数据写入
        self.chart_tabs.enable_table_data_writing()
        
        # 生成演示数据
        base_time = datetime.datetime.now().timestamp()
        for i in range(10):
            t = base_time + i * 60  # 每分钟一条数据
            
            # 模拟温度数据
            temperatures = {
                'T1': 25.0 + i * 0.5 + random.uniform(-0.5, 0.5),
                'T2': 26.0 + i * 0.3 + random.uniform(-0.3, 0.3),
                'T3': 24.5 + i * 0.4 + random.uniform(-0.4, 0.4),
                'T4': 25.5 + i * 0.6 + random.uniform(-0.6, 0.6),
                'T5': 24.0 + i * 0.2 + random.uniform(-0.2, 0.2),
                'T6': 26.5 + i * 0.7 + random.uniform(-0.7, 0.7),
                'T7': 25.2 + i * 0.4 + random.uniform(-0.4, 0.4),
                'T8': 25.8 + i * 0.8 + random.uniform(-0.8, 0.8),  # 样品温度
                'T9': 24.8 + i * 0.3 + random.uniform(-0.3, 0.3)
            }
            
            # 模拟流量数据
            flows = {
                'N2': {'PV': 1.0 + i * 0.1 + random.uniform(-0.05, 0.05)},
                'CO': {'PV': 0.5 + i * 0.05 + random.uniform(-0.02, 0.02)},
                'CO2': {'PV': 0.3 + i * 0.03 + random.uniform(-0.01, 0.01)},
                'H2': {'PV': 0.8 + i * 0.08 + random.uniform(-0.04, 0.04)}
            }
            
            # 模拟重量数据
            weight = 100.0 + i * 0.1 + random.uniform(-0.05, 0.05)
            
            # 实验状态
            status = "运行中" if i < 8 else "完成"
            prompt = f"数据点 {i+1}" if i < 8 else "实验结束"
            
            # 插入数据到表格
            self.chart_tabs.insert_data_to_table(
                t, temperatures, flows, weight, status, prompt
            )
    
    def set_demo_experiment_info(self):
        """设置演示实验信息"""
        experiment_info = {
            "experiment_id": "DEMO-2024-001",
            "experiment_name": "铁矿石还原性实验演示",
            "sample_name": "演示样品A",
            "sample_weight": 100.0,
            "experiment_type": "还原性实验",
            "operator": "演示用户",
            "start_time": "2024-01-01 10:00:00",
            "end_time": "2024-01-01 12:00:00",
            "description": "这是一个演示实验，展示数据导出功能",
            "experiment_params": {
                "temperature": 900,
                "gas_flow_n2": 2.0,
                "gas_flow_co": 1.0,
                "gas_flow_co2": 0.5,
                "gas_flow_h2": 1.5,
                "pressure": 1.0,
                "duration": 120
            },
            "analysis_results": {
                "reduction_degree": 85.5,
                "reduction_rate": 1.2,
                "weight_loss": 15.2,
                "final_temperature": 920.5
            }
        }
        
        # 设置实验信息到图表组件
        self.chart_tabs.set_experiment_info(experiment_info)
    
    def export_csv(self):
        """导出为CSV格式"""
        success = self.chart_tabs.export_data('csv')
        self.status_label.setText("CSV导出成功" if success else "CSV导出失败")
    
    def export_xls(self):
        """导出为Excel格式"""
        success = self.chart_tabs.export_data('xls')
        self.status_label.setText("Excel导出成功" if success else "Excel导出失败")
    
    def export_txt(self):
        """导出为TXT格式"""
        success = self.chart_tabs.export_data('txt')
        self.status_label.setText("TXT导出成功" if success else "TXT导出失败")
    
    def show_dialog(self):
        """显示导出对话框"""
        success = self.chart_tabs.show_export_dialog()
        self.status_label.setText("导出对话框完成" if success else "导出对话框取消")


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 创建演示窗口
    demo = DataExportDemo()
    demo.show()
    
    print("数据导出功能演示")
    print("1. 点击按钮可以导出不同格式的数据")
    print("2. 数据表格中包含了10条演示数据")
    print("3. 支持CSV、Excel、TXT三种格式")
    print("4. 导出的数据包含完整的实验信息")
    print("5. 可以查看导出对话框的完整功能")
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
