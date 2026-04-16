#!/usr/bin/env python3
"""
自定义实验使用示例
演示如何使用优化后的自定义实验功能
"""

import sys
import os
from unittest.mock import Mock

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.ui.experiment.experiment_controller import ExperimentController


def create_mock_device_manager():
    """创建模拟设备管理器"""
    device_manager = Mock()
    device_manager.set_flow = Mock()
    device_manager.get_temperature = Mock(return_value=25.0)
    device_manager.get_weight = Mock(return_value=500.0)
    
    # 模拟设备连接状态
    device_manager.multi_mfc = Mock()
    device_manager.multi_mfc.serial_port_available = True
    device_manager.balance = Mock()
    device_manager.balance.serial_port_available = True
    device_manager.temp = Mock()
    device_manager.temp.serial_port_available = True
    
    return device_manager


def example_1_basic_custom_experiment():
    """示例1: 基本自定义实验使用"""
    print("=" * 60)
    print("示例1: 基本自定义实验使用")
    print("=" * 60)
    
    # 创建实验控制器
    device_manager = create_mock_device_manager()
    controller = ExperimentController(device_manager=device_manager)
    
    # 设置自定义实验模式
    custom_mode_id = "CUSTOM_HIGH_TEMP_TEST"
    print(f"设置自定义实验模式: {custom_mode_id}")
    
    success = controller.set_experiment_mode_by_id(custom_mode_id)
    print(f"设置结果: {'成功' if success else '失败'}")
    
    if success:
        print(f"当前模式: {controller.current_experiment_type_name}")
        print(f"是否为自定义模式: {controller.experiment_mode_manager.is_custom_mode()}")
        
        # 获取实验阶段信息
        stages = controller.experiment_mode_manager.get_experiment_stages()
        print(f"实验阶段数量: {len(stages)}")
        
        # 显示阶段详情
        for i, stage in enumerate(stages):
            print(f"\n阶段 {i+1}: {stage.stage.value}")
            print(f"  描述: {stage.description}")
            print(f"  目标温度: {stage.target_temp}°C")
            print(f"  持续时间: {stage.duration} 分钟")
            print(f"  气体设置: CO={stage.gas_settings.CO}, CO2={stage.gas_settings.CO2}, N2={stage.gas_settings.N2}, H2={stage.gas_settings.H2}")


def example_2_custom_vs_standard():
    """示例2: 自定义实验与标准实验对比"""
    print("\n" + "=" * 60)
    print("示例2: 自定义实验与标准实验对比")
    print("=" * 60)
    
    device_manager = create_mock_device_manager()
    controller = ExperimentController(device_manager=device_manager)
    
    # 测试标准实验
    print("1. 标准实验 (GB/T 13241-2017)")
    controller.set_experiment_mode_by_id("GB_13241_2017")
    standard_stages = controller.experiment_mode_manager.get_experiment_stages()
    print(f"   阶段数量: {len(standard_stages)}")
    print(f"   第1阶段目标温度: {standard_stages[0].target_temp}°C")
    print(f"   第1阶段N2流量: {standard_stages[0].gas_settings.N2} L/min")
    
    # 测试自定义实验
    print("\n2. 自定义实验 (CUSTOM_HIGH_TEMP_LONG_REDUCTION)")
    controller.set_experiment_mode_by_id("CUSTOM_HIGH_TEMP_LONG_REDUCTION")
    custom_stages = controller.experiment_mode_manager.get_experiment_stages()
    print(f"   阶段数量: {len(custom_stages)}")
    print(f"   第1阶段目标温度: {custom_stages[0].target_temp}°C")
    print(f"   第1阶段N2流量: {custom_stages[0].gas_settings.N2} L/min")
    
    # 对比分析
    print("\n3. 对比分析")
    print(f"   温度差异: {custom_stages[0].target_temp - standard_stages[0].target_temp}°C")
    print(f"   N2流量差异: {custom_stages[0].gas_settings.N2 - standard_stages[0].gas_settings.N2} L/min")


def example_3_stage_execution():
    """示例3: 阶段执行模拟"""
    print("\n" + "=" * 60)
    print("示例3: 阶段执行模拟")
    print("=" * 60)
    
    device_manager = create_mock_device_manager()
    controller = ExperimentController(device_manager=device_manager)
    
    # 设置自定义实验
    custom_mode_id = "CUSTOM_MODIFIED_REDUCIBILITY"
    print(f"设置自定义实验模式: {custom_mode_id}")
    
    success = controller.set_experiment_mode_by_id(custom_mode_id)
    if not success:
        print("设置失败，无法继续")
        return
    
    print(f"当前模式: {controller.current_experiment_type_name}")
    
    # 获取阶段信息
    stages = controller.experiment_mode_manager.get_experiment_stages()
    print(f"实验阶段数量: {len(stages)}")
    
    # 模拟执行各个阶段
    print("\n模拟执行实验阶段...")
    for i, stage in enumerate(stages):
        print(f"\n--- 执行阶段 {i+1}: {stage.stage.value} ---")
        print(f"描述: {stage.description}")
        print(f"目标温度: {stage.target_temp}°C")
        print(f"持续时间: {stage.duration} 分钟")
        
        # 模拟设置气体流量
        if stage.gas_settings.CO > 0:
            device_manager.set_flow("CO", stage.gas_settings.CO)
        if stage.gas_settings.CO2 > 0:
            device_manager.set_flow("CO2", stage.gas_settings.CO2)
        if stage.gas_settings.N2 > 0:
            device_manager.set_flow("N2", stage.gas_settings.N2)
        if stage.gas_settings.H2 > 0:
            device_manager.set_flow("H2", stage.gas_settings.H2)
        
        print(f"总流量: {stage.gas_settings.total_flow} L/min")
    
    # 显示设备调用历史
    print(f"\n设备管理器接收到的流量设置调用次数: {device_manager.set_flow.call_count}")


def example_4_list_available_custom_experiments():
    """示例4: 列出可用的自定义实验"""
    print("\n" + "=" * 60)
    print("示例4: 列出可用的自定义实验")
    print("=" * 60)
    
    device_manager = create_mock_device_manager()
    controller = ExperimentController(device_manager=device_manager)
    
    # 获取自定义实验列表
    custom_programs = controller.experiment_mode_manager.list_custom_programs()
    print(f"可用的自定义实验数量: {len(custom_programs)}")
    
    print("\n自定义实验列表:")
    for i, program_id in enumerate(custom_programs, 1):
        program = controller.experiment_mode_manager.get_custom_program(program_id)
        if program:
            print(f"{i:2d}. {program_id}")
            print(f"    名称: {program.name}")
            print(f"    描述: {program.description}")
            print(f"    阶段数: {len(program.stages)}")
            print()


def main():
    """主函数"""
    print("自定义实验使用示例")
    print("=" * 60)
    
    try:
        # 示例1: 基本使用
        example_1_basic_custom_experiment()
        
        # 示例2: 对比分析
        example_2_custom_vs_standard()
        
        # 示例3: 阶段执行
        example_3_stage_execution()
        
        # 示例4: 列出可用实验
        example_4_list_available_custom_experiments()
        
        print("\n" + "=" * 60)
        print("所有示例执行完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"执行过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
