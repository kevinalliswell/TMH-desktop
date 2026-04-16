# test_experiment_info_export.py
"""
实验信息导出功能测试
"""

import sys
import os
import tempfile
import unittest
from PySide6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem
from PySide6.QtCore import Qt

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from utils.data_saver import DataSaver, DataExportDialog


class TestExperimentInfoExport(unittest.TestCase):
    """实验信息导出测试"""
    
    def setUp(self):
        """测试前准备"""
        if not QApplication.instance():
            self.app = QApplication([])
        else:
            self.app = QApplication.instance()
        
        # 创建测试数据表格
        self.test_table = QTableWidget(3, 4)
        self.test_table.setHorizontalHeaderLabels(["时间", "温度", "流量", "重量"])
        
        # 添加测试数据
        test_data = [
            ["2024-01-01 10:00:00", "25.5", "1.2", "100.0"],
            ["2024-01-01 10:01:00", "26.0", "1.3", "100.1"],
            ["2024-01-01 10:02:00", "26.5", "1.4", "100.2"]
        ]
        
        for row, row_data in enumerate(test_data):
            for col, value in enumerate(row_data):
                item = QTableWidgetItem(value)
                self.test_table.setItem(row, col, item)
        
        # 创建测试实验信息
        self.test_experiment_info = {
            "experiment_id": "TEST-001",
            "experiment_name": "铁矿石还原性实验",
            "sample_name": "测试样品A",
            "sample_weight": 100.5,
            "experiment_type": "还原性实验",
            "operator": "张三",
            "start_time": "2024-01-01 10:00:00",
            "end_time": "2024-01-01 12:00:00",
            "description": "这是一个测试实验",
            "experiment_params": {
                "temperature": 900,
                "gas_flow": 2.5,
                "pressure": 1.0
            },
            "analysis_results": {
                "reduction_degree": 85.5,
                "reduction_rate": 1.2,
                "weight_loss": 15.2
            }
        }
    
    def test_csv_export_with_experiment_info(self):
        """测试带实验信息的CSV导出"""
        saver = DataSaver()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp_file:
            file_path = tmp_file.name
        
        try:
            success = saver.save_data(
                self.test_table, 
                file_path, 
                'csv', 
                include_headers=True,
                experiment_info=self.test_experiment_info
            )
            self.assertTrue(success)
            
            # 验证文件内容
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
                # 检查实验信息
                self.assertIn("实验信息", content)
                self.assertIn("TEST-001", content)
                self.assertIn("铁矿石还原性实验", content)
                self.assertIn("测试样品A", content)
                self.assertIn("100.500 g", content)
                # 检查数据表头
                self.assertIn("时间", content)
                self.assertIn("温度", content)
                # 检查数据
                self.assertIn("25.5", content)
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)
    
    def test_txt_export_with_experiment_info(self):
        """测试带实验信息的TXT导出"""
        saver = DataSaver()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp_file:
            file_path = tmp_file.name
        
        try:
            success = saver.save_data(
                self.test_table, 
                file_path, 
                'txt', 
                include_headers=True,
                experiment_info=self.test_experiment_info
            )
            self.assertTrue(success)
            
            # 验证文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # 检查实验信息
                self.assertIn("实验信息", content)
                self.assertIn("TEST-001", content)
                self.assertIn("铁矿石还原性实验", content)
                # 检查数据
                self.assertIn("25.5", content)
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)
    
    def test_xls_export_with_experiment_info(self):
        """测试带实验信息的Excel导出"""
        saver = DataSaver()
        
        # 检查依赖
        if not saver.check_dependencies()['openpyxl']:
            self.skipTest("openpyxl not available")
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlsx', delete=False) as tmp_file:
            file_path = tmp_file.name
        
        try:
            success = saver.save_data(
                self.test_table, 
                file_path, 
                'xls', 
                include_headers=True,
                experiment_info=self.test_experiment_info
            )
            self.assertTrue(success)
            
            # 验证文件存在
            self.assertTrue(os.path.exists(file_path))
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)
    
    def test_experiment_info_formatting(self):
        """测试实验信息格式化"""
        saver = DataSaver()
        formatted_info = saver._format_experiment_info(self.test_experiment_info)
        
        # 检查基本信息
        self.assertIn(["实验信息", ""], formatted_info)
        self.assertIn(["实验ID", "TEST-001"], formatted_info)
        self.assertIn(["实验名称", "铁矿石还原性实验"], formatted_info)
        self.assertIn(["样品名称", "测试样品A"], formatted_info)
        self.assertIn(["样品重量", "100.500 g"], formatted_info)
        
        # 检查实验参数
        self.assertIn(["实验参数", ""], formatted_info)
        self.assertIn(["temperature", "900"], formatted_info)
        
        # 检查分析结果
        self.assertIn(["分析结果", ""], formatted_info)
        self.assertIn(["reduction_degree", "85.5"], formatted_info)
    
    def test_export_dialog_with_experiment_info(self):
        """测试带实验信息的导出对话框"""
        # 这个测试需要GUI环境，所以只测试方法调用
        try:
            success = DataExportDialog.show_export_dialog(
                self.test_table, 
                None, 
                self.test_experiment_info
            )
            # 由于是对话框，用户可能取消，所以不检查返回值
            self.assertIsInstance(success, bool)
        except Exception as e:
            # 如果对话框无法显示（比如在无头环境中），这是正常的
            self.assertIn("QDialog", str(e))
    
    def test_empty_experiment_info(self):
        """测试空实验信息"""
        saver = DataSaver()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp_file:
            file_path = tmp_file.name
        
        try:
            success = saver.save_data(
                self.test_table, 
                file_path, 
                'csv', 
                include_headers=True,
                experiment_info=None
            )
            self.assertTrue(success)
            
            # 验证文件内容（应该只有数据，没有实验信息）
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
                # 不应该包含实验信息
                self.assertNotIn("实验信息", content)
                # 但应该包含数据
                self.assertIn("时间", content)
                self.assertIn("25.5", content)
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)


if __name__ == '__main__':
    unittest.main()
