# tests/test_data_saver.py
"""
数据保存功能测试
"""

import sys
import os
import tempfile
import unittest
from PySide6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem
from PySide6.QtCore import Qt

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.utils.data_saver import DataSaver, DataExportDialog


class TestDataSaver(unittest.TestCase):
    """数据保存器测试"""
    
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
    
    def test_csv_export(self):
        """测试CSV导出"""
        saver = DataSaver()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp_file:
            file_path = tmp_file.name
        
        try:
            success = saver.save_data(self.test_table, file_path, 'csv')
            self.assertTrue(success)
            
            # 验证文件内容
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
                self.assertIn("时间", content)
                self.assertIn("温度", content)
                self.assertIn("25.5", content)
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)
    
    def test_txt_export(self):
        """测试TXT导出"""
        saver = DataSaver()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp_file:
            file_path = tmp_file.name
        
        try:
            success = saver.save_data(self.test_table, file_path, 'txt')
            self.assertTrue(success)
            
            # 验证文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self.assertIn("时间", content)
                self.assertIn("温度", content)
                self.assertIn("25.5", content)
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)
    
    def test_xls_export(self):
        """测试Excel导出"""
        saver = DataSaver()
        
        # 检查依赖
        if not saver.check_dependencies()['openpyxl']:
            self.skipTest("openpyxl not available")
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlsx', delete=False) as tmp_file:
            file_path = tmp_file.name
        
        try:
            success = saver.save_data(self.test_table, file_path, 'xls')
            self.assertTrue(success)
            
            # 验证文件存在
            self.assertTrue(os.path.exists(file_path))
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)
    
    def test_format_support(self):
        """测试格式支持检查"""
        saver = DataSaver()
        
        self.assertTrue(saver.is_format_supported('csv'))
        self.assertTrue(saver.is_format_supported('xls'))
        self.assertTrue(saver.is_format_supported('txt'))
        self.assertFalse(saver.is_format_supported('pdf'))
    
    def test_data_extraction(self):
        """测试数据提取"""
        saver = DataSaver()
        data = saver._extract_table_data(self.test_table, include_headers=True)
        
        self.assertEqual(len(data), 4)  # 3行数据 + 1行表头
        self.assertEqual(len(data[0]), 4)  # 4列
        self.assertEqual(data[0], ["时间", "温度", "流量", "重量"])  # 表头
        self.assertEqual(data[1], ["2024-01-01 10:00:00", "25.5", "1.2", "100.0"])  # 第一行数据


if __name__ == '__main__':
    unittest.main()
