#!/usr/bin/env python3
"""
自定义实验集成测试
验证自定义实验配置优化方案
"""

import sys
import os
import logging
from unittest.mock import Mock, MagicMock

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.controllers.experiment_controller import ExperimentController
from src.services.enhanced_experiment_modes import EnhancedExperimentModeManager
from src.services.experiment_type_manager import ExperimentTypeManager


class MockDeviceManager:
    """模拟设备管理器"""
    
    def __init__(self):
        self.flow_settings = {}
        self.set_flow_calls = []
        self.temperature = 25.0
        self.weight = 500.0
        
        # 模拟设备连接状态
        self.multi_mfc = Mock()
        self.multi_mfc.serial_port_available = True
        
        self.balance = Mock()
        self.balance.serial_port_available = True
        
        self.temp = Mock()
        self.temp.serial_port_available = True
    
    def set_flow(self, gas: str, flow: float):
        """模拟设置气体流量"""
        self.flow_settings[gas] = flow
        self.set_flow_calls.append((gas, flow))
        print(f"    [设备] 设置 {gas} 流量: {flow:.1f} L/min")
    
    def get_temperature(self) -> float:
        """模拟获取温度"""
        return self.temperature
    
    def get_weight(self) -> float:
        """模拟获取重量"""
        return self.weight


def test_enhanced_experiment_mode_manager():
    """测试增强的实验模式管理器"""
    print("=" * 60)
    print("测试增强的实验模式管理器")
    print("=" * 60)
    
    # 创建增强的实验模式管理器
    manager = EnhancedExperimentModeManager()
    
    # 测试自定义实验程序加载
    custom_programs = manager.list_custom_programs()
    print(f"加载的自定义实验程序数量: {len(custom_programs)}")
    
    for program_id in custom_programs[:3]:  # 只显示前3个
        program = manager.get_custom_program(program_id)
        if program:
            print(f"  - {program_id}: {program.name}")
            print(f"    阶段数量: {len(program.stages)}")
    
    # 测试设置自定义实验模式
    test_mode_id = "CUSTOM_HIGH_TEMP_TEST"
    print(f"\n设置自定义实验模式: {test_mode_id}")
    
    success = manager.set_custom_experiment_mode(test_mode_id)
    print(f"设置结果: {'成功' if success else '失败'}")
    
    if success:
        print(f"是否为自定义模式: {manager.is_custom_mode()}")
        print(f"当前自定义类型: {manager.get_current_custom_type()}")
        
        # 获取阶段信息
        stages = manager.get_experiment_stages()
        print(f"实验阶段数量: {len(stages)}")
        
        for i, stage in enumerate(stages):
            print(f"阶段 {i+1}: {stage.stage.value}")
            print(f"  描述: {stage.description}")
            print(f"  目标温度: {stage.target_temp}°C")
            print(f"  持续时间: {stage.duration} 分钟")
            print(f"  气体设置: {stage.gas_settings}")
            print()
        
        # 测试阶段执行
        print("测试阶段执行...")
        manager.current_stage_index = 0
        current_stage = manager.get_current_stage_settings()
        
        if current_stage:
            print(f"当前阶段: {current_stage.stage.value}")
            print(f"阶段描述: {current_stage.description}")
            print(f"目标温度: {current_stage.target_temp}°C")
            print(f"气体设置: {current_stage.gas_settings}")
        else:
            print("无法获取当前阶段设置")


def test_enhanced_experiment_controller():
    """测试增强的实验控制器"""
    print("\n" + "=" * 60)
    print("测试增强的实验控制器")
    print("=" * 60)
    
    # 创建模拟设备管理器
    device_manager = MockDeviceManager()
    
    # 创建增强的实验控制器
    controller = ExperimentController(device_manager=device_manager)
    
    # 测试标准实验模式
    print("测试标准实验模式...")
    success = controller.set_experiment_mode_by_id("GB_13241_2017")
    print(f"设置标准实验模式: {'成功' if success else '失败'}")
    
    if success:
        print(f"当前模式: {controller.current_experiment_type_name}")
        print(f"是否为自定义模式: {controller.experiment_mode_manager.is_custom_mode()}")
        
        # 获取阶段信息
        stages = controller.experiment_mode_manager.get_experiment_stages()
        print(f"标准实验阶段数量: {len(stages)}")
    
    # 测试自定义实验模式
    print("\n测试自定义实验模式...")
    success = controller.set_experiment_mode_by_id("CUSTOM_HIGH_TEMP_TEST")
    print(f"设置自定义实验模式: {'成功' if success else '失败'}")
    
    if success:
        print(f"当前模式: {controller.current_experiment_type_name}")
        print(f"是否为自定义模式: {controller.experiment_mode_manager.is_custom_mode()}")
        print(f"自定义类型ID: {controller.experiment_mode_manager.get_current_custom_type()}")
        
        # 获取阶段信息
        stages = controller.experiment_mode_manager.get_experiment_stages()
        print(f"自定义实验阶段数量: {len(stages)}")
        
        # 显示前两个阶段的详细信息
        for i, stage in enumerate(stages[:2]):
            print(f"阶段 {i+1}: {stage.stage.value}")
            print(f"  描述: {stage.description}")
            print(f"  目标温度: {stage.target_temp}°C")
            print(f"  持续时间: {stage.duration} 分钟")
            print(f"  气体设置: {stage.gas_settings}")
            print()


def test_custom_experiment_execution():
    """测试自定义实验执行"""
    print("\n" + "=" * 60)
    print("测试自定义实验执行")
    print("=" * 60)
    
    # 创建模拟设备管理器
    device_manager = MockDeviceManager()
    
    # 创建增强的实验控制器
    controller = ExperimentController(device_manager=device_manager)
    
    # 设置自定义实验模式
    custom_mode_id = "CUSTOM_HIGH_TEMP_LONG_REDUCTION"
    print(f"设置自定义实验模式: {custom_mode_id}")
    
    success = controller.set_experiment_mode_by_id(custom_mode_id)
    print(f"设置结果: {'成功' if success else '失败'}")
    
    if not success:
        print("无法设置自定义实验模式，测试终止")
        return
    
    print(f"当前模式: {controller.current_experiment_type_name}")
    print(f"是否为自定义模式: {controller.experiment_mode_manager.is_custom_mode()}")
    
    # 获取实验阶段
    stages = controller.experiment_mode_manager.get_experiment_stages()
    print(f"实验阶段数量: {len(stages)}")
    
    # 模拟执行各个阶段
    print("\n模拟执行实验阶段...")
    for i, stage in enumerate(stages):
        print(f"\n--- 阶段 {i+1}: {stage.stage.value} ---")
        print(f"描述: {stage.description}")
        print(f"目标温度: {stage.target_temp}°C")
        print(f"持续时间: {stage.duration} 分钟")
        print(f"气体设置: {stage.gas_settings}")
        
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
    
    print(f"\n设备管理器接收到的流量设置调用次数: {len(device_manager.set_flow_calls)}")
    print("流量设置历史:")
    for i, (gas, flow) in enumerate(device_manager.set_flow_calls):
        print(f"  {i+1}. {gas}: {flow} L/min")


def test_custom_vs_standard_comparison():
    """测试自定义实验与标准实验的对比"""
    print("\n" + "=" * 60)
    print("测试自定义实验与标准实验的对比")
    print("=" * 60)
    
    # 创建模拟设备管理器
    device_manager = MockDeviceManager()
    
    # 创建增强的实验控制器
    controller = ExperimentController(device_manager=device_manager)
    
    # 测试标准实验
    print("1. 标准实验 (GB/T 13241-2017)")
    controller.set_experiment_mode_by_id("GB_13241_2017")
    standard_stages = controller.experiment_mode_manager.get_experiment_stages()
    print(f"   阶段数量: {len(standard_stages)}")
    print(f"   是否为自定义模式: {controller.experiment_mode_manager.is_custom_mode()}")
    
    # 测试自定义实验
    print("\n2. 自定义实验 (CUSTOM_HIGH_TEMP_TEST)")
    controller.set_experiment_mode_by_id("CUSTOM_HIGH_TEMP_TEST")
    custom_stages = controller.experiment_mode_manager.get_experiment_stages()
    print(f"   阶段数量: {len(custom_stages)}")
    print(f"   是否为自定义模式: {controller.experiment_mode_manager.is_custom_mode()}")
    
    # 对比分析
    print("\n3. 对比分析")
    print(f"   标准实验阶段数: {len(standard_stages)}")
    print(f"   自定义实验阶段数: {len(custom_stages)}")
    
    if len(standard_stages) > 0 and len(custom_stages) > 0:
        print(f"   标准实验第1阶段目标温度: {standard_stages[0].target_temp}°C")
        print(f"   自定义实验第1阶段目标温度: {custom_stages[0].target_temp}°C")
        print(f"   标准实验第1阶段N2流量: {standard_stages[0].gas_settings.N2} L/min")
        print(f"   自定义实验第1阶段N2流量: {custom_stages[0].gas_settings.N2} L/min")


def main():
    """主测试函数"""
    # 设置日志级别
    logging.basicConfig(level=logging.INFO)
    
    print("自定义实验配置优化方案 - 集成测试")
    print("=" * 60)
    
    try:
        # 测试增强的实验模式管理器
        test_enhanced_experiment_mode_manager()
        
        # 测试增强的实验控制器
        test_enhanced_experiment_controller()
        
        # 测试自定义实验执行
        test_custom_experiment_execution()
        
        # 测试自定义与标准实验对比
        test_custom_vs_standard_comparison()
        
        print("\n" + "=" * 60)
        print("所有测试完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
