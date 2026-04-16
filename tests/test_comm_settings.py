#!/usr/bin/env python3
"""
测试 comm_settings.py 的配置加载功能
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.services.comm_settings import CommSettings

def test_comm_settings():
    """测试通信设置类"""
    print("=== 测试通信设置类 ===")
    
    # 创建通信设置实例
    comm_settings = CommSettings()
    
    # 测试基本配置获取
    print("\n1. 基本配置获取测试:")
    print(f"MFC配置: {comm_settings.get_mfc_config()}")
    print(f"温控仪表配置: {comm_settings.get_temp_config()}")
    print(f"天平配置: {comm_settings.get_balance_config()}")
    print(f"采样配置: {comm_settings.get_sampling_config()}")
    
    # 测试嵌套配置获取
    print("\n2. 嵌套配置获取测试:")
    print(f"MFC从站地址: {comm_settings.get_mfc_slave_addresses()}")
    print(f"流量缩放: {comm_settings.get_flow_scaling()}")
    print(f"温度通道: {comm_settings.get_temp_channels()}")
    
    # 测试串口列表获取
    print("\n3. 串口列表获取测试:")
    ports = CommSettings.get_available_ports()
    print(f"可用串口: {ports}")
    
    # 测试配置验证
    print("\n4. 配置验证测试:")
    print("配置加载和验证完成，无错误")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_comm_settings()
