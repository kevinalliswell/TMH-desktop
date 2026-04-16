#!/usr/bin/env python3
"""
数据库修复验证脚本
用于测试数据库修复后的数据加载功能
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.services.database import ExperimentDatabase, ExperimentData
from datetime import datetime
import json

def test_database_fix():
    """测试数据库修复功能"""
    print("=" * 50)
    print("数据库修复验证测试")
    print("=" * 50)
    
    # 初始化数据库
    db = ExperimentDatabase()
    
    # 1. 验证数据库完整性
    print("\n1. 验证数据库完整性...")
    integrity_info = db.validate_database_integrity()
    print(f"   实验记录数量: {integrity_info.get('experiment_count', 0)}")
    print(f"   数据点数量: {integrity_info.get('data_count', 0)}")
    print(f"   孤立数据记录: {integrity_info.get('orphaned_data', 0)}")
    print(f"   数据库状态: {'正常' if integrity_info.get('is_valid') else '存在问题'}")
    
    # 2. 测试数据加载
    print("\n2. 测试数据加载...")
    experiments = db.get_all_experiments()
    print(f"   成功加载 {len(experiments)} 个实验记录")
    
    if experiments:
        # 测试第一个实验的数据加载
        first_exp = experiments[0]
        print(f"   测试实验: {first_exp.experiment_name} (ID: {first_exp.experiment_id})")
        
        data_points = db.get_experiment_data(first_exp.experiment_id)
        print(f"   数据点数量: {len(data_points)}")
        
        if data_points:
            # 验证数据点结构
            sample_point = data_points[0]
            print("   数据点字段:")
            for key, value in sample_point.items():
                print(f"     {key}: {value} (类型: {type(value).__name__})")
            
            # 验证数据类型
            print("\n   数据类型验证:")
            try:
                temp = float(sample_point.get('temperature', 0))
                weight = float(sample_point.get('weight', 0))
                print(f"     温度: {temp}℃ ✅")
                print(f"     重量: {weight}g ✅")
            except (ValueError, TypeError) as e:
                print(f"     数据类型错误: {e} ❌")
    
    # 3. 测试数据库修复功能
    print("\n3. 测试数据库修复功能...")
    if not integrity_info.get('is_valid', False):
        print("   发现数据库问题，尝试修复...")
        if db.repair_database():
            print("   数据库修复成功 ✅")
            
            # 重新验证
            integrity_info_after = db.validate_database_integrity()
            print(f"   修复后孤立记录: {integrity_info_after.get('orphaned_data', 0)}")
        else:
            print("   数据库修复失败 ❌")
    else:
        print("   数据库状态正常，无需修复 ✅")
    
    # 4. 创建测试数据（如果数据库为空）
    if len(experiments) == 0:
        print("\n4. 创建测试数据...")
        test_experiment = ExperimentData(
            experiment_id="test_001",
            experiment_name="测试实验",
            sample_name="测试样品",
            sample_weight=100.0,
            start_time=datetime.now().isoformat(),
            end_time=datetime.now().isoformat(),
            description="数据库修复测试",
            operator="测试用户",
            experiment_type="测试类型"
        )
        
        if db.create_experiment(test_experiment):
            print("   测试实验创建成功 ✅")
            
            # 添加测试数据点
            test_data = {
                'timestamp': datetime.now().isoformat(),
                'temperature': 25.5,
                'weight': 100.0,
                'weight_loss': 0.0,
                'co_flow': 0.0,
                'co2_flow': 0.0,
                'n2_flow': 5.0,
                'h2_flow': 0.0
            }
            
            if db.add_experiment_data(test_experiment.experiment_id, test_data):
                print("   测试数据点添加成功 ✅")
            else:
                print("   测试数据点添加失败 ❌")
        else:
            print("   测试实验创建失败 ❌")
    
    print("\n" + "=" * 50)
    print("测试完成")
    print("=" * 50)

if __name__ == "__main__":
    test_database_fix()
