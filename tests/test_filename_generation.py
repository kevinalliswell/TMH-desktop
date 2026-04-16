# test_filename_generation.py
"""
测试文件名生成功能
"""

import sys
import os
from PySide6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from utils.data_saver import DataSaver

def test_filename_generation():
    """测试文件名生成功能"""
    app = QApplication([])
    
    # 创建测试表格
    table = QTableWidget(2, 3)
    table.setHorizontalHeaderLabels(['时间', '温度', '重量'])
    table.setItem(0, 0, QTableWidgetItem('10:00'))
    table.setItem(0, 1, QTableWidgetItem('25.5'))
    table.setItem(0, 2, QTableWidgetItem('100.0'))
    
    # 测试不同的实验信息
    test_cases = [
        {
            "name": "标准实验信息",
            "experiment_info": {
                'experiment_id': 'EXP-001',
                'experiment_name': '铁矿石还原性实验',
                'sample_name': '样品A',
                'sample_weight': 100.0,
                'experiment_type': '还原性实验',
                'operator': '张三',
                'start_time': '2024-01-01 10:00:00',
                'end_time': '2024-01-01 12:00:00',
                'description': '测试实验'
            }
        },
        {
            "name": "包含特殊字符的实验信息",
            "experiment_info": {
                'experiment_name': '铁矿石/还原性实验<>测试',
                'sample_name': '样品A:B',
                'operator': '李四/王五',
                'experiment_type': '还原性实验|测试',
                'start_time': '2024-01-01 10:00:00'
            }
        },
        {
            "name": "长名称实验信息",
            "experiment_info": {
                'experiment_name': '这是一个非常长的实验名称用来测试文件名长度限制功能',
                'sample_name': '这是一个非常长的样品名称用来测试文件名长度限制功能',
                'operator': '这是一个非常长的操作员名称用来测试文件名长度限制功能',
                'experiment_type': '这是一个非常长的实验类型名称用来测试文件名长度限制功能',
                'start_time': '2024-01-01 10:00:00'
            }
        },
        {
            "name": "ISO时间格式",
            "experiment_info": {
                'experiment_name': 'ISO时间格式测试',
                'sample_name': '样品C',
                'operator': '赵六',
                'experiment_type': '时间测试',
                'start_time': '2024-01-01T10:00:00'
            }
        },
        {
            "name": "缺少部分信息",
            "experiment_info": {
                'experiment_name': '部分信息测试',
                'sample_name': '样品D',
                # 缺少operator和experiment_type
                'start_time': '2024-01-01 10:00:00'
            }
        }
    ]
    
    saver = DataSaver()
    
    for i, test_case in enumerate(test_cases):
        print(f"\n测试用例 {i+1}: {test_case['name']}")
        print("-" * 50)
        
        # 测试CSV格式
        csv_filename = saver._generate_filename_from_experiment_info(
            test_case['experiment_info'], 'csv'
        )
        print(f"CSV文件名: {csv_filename}")
        
        # 测试Excel格式
        xls_filename = saver._generate_filename_from_experiment_info(
            test_case['experiment_info'], 'xls'
        )
        print(f"Excel文件名: {xls_filename}")
        
        # 测试TXT格式
        txt_filename = saver._generate_filename_from_experiment_info(
            test_case['experiment_info'], 'txt'
        )
        print(f"TXT文件名: {txt_filename}")
        
        # 测试实际导出（CSV格式）
        try:
            success = saver.save_data(
                table, 
                None,  # 让系统自动生成文件名
                'csv', 
                True, 
                test_case['experiment_info']
            )
            print(f"实际导出结果: {'成功' if success else '失败'}")
        except Exception as e:
            print(f"实际导出错误: {e}")

if __name__ == '__main__':
    test_filename_generation()
