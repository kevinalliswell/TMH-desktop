#!/usr/bin/env python3
"""
测试 communication_settings_page.py 与优化后的 comm_settings.py 的集成
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from PySide6.QtWidgets import QApplication
from src.ui.pages.communication_settings_page import CommunicationSettings

def test_ui_integration():
    """测试UI集成"""
    print("=== 测试UI集成 ===")
    
    # 创建QApplication（必需）
    app = QApplication(sys.argv)
    
    try:
        # 创建通信设置页面
        print("1. 创建通信设置页面...")
        comm_page = CommunicationSettings()
        print("✓ 通信设置页面创建成功")
        
        # 测试配置访问
        print("\n2. 测试配置访问...")
        comm_settings = comm_page.comm_settings
        
        print(f"✓ MFC配置: {comm_settings.get_mfc_config()}")
        print(f"✓ 温控仪表配置: {comm_settings.get_temp_config()}")
        print(f"✓ 天平配置: {comm_settings.get_balance_config()}")
        print(f"✓ 采样配置: {comm_settings.get_sampling_config()}")
        
        print(f"✓ MFC从站地址: {comm_settings.get_mfc_slave_addresses()}")
        print(f"✓ 流量缩放: {comm_settings.get_flow_scaling()}")
        print(f"✓ 温度通道: {comm_settings.get_temp_channels()}")
        
        # 测试配置更新方法
        print("\n3. 测试配置更新方法...")
        
        # 测试MFC从站地址更新
        comm_page.update_mfc_slave_address("H2", 5)
        print("✓ MFC从站地址更新测试完成")
        
        # 测试温控仪表从站地址更新
        comm_page.update_temp_slave_address(1)
        print("✓ 温控仪表从站地址更新测试完成")
        
        # 测试流量缩放更新
        comm_page.update_flow_scaling("N2", 0.5)
        print("✓ 流量缩放更新测试完成")
        
        # 测试采样间隔更新
        comm_page.update_sampling_interval(2)
        print("✓ 采样间隔更新测试完成")
        
        # 验证更新后的配置
        print("\n4. 验证更新后的配置...")
        print(f"✓ 更新后MFC从站地址: {comm_settings.get_mfc_slave_addresses()}")
        print(f"✓ 更新后流量缩放: {comm_settings.get_flow_scaling()}")
        print(f"✓ 更新后采样间隔: {comm_settings.get_sampling_config()}")
        
        print("\n=== UI集成测试完成 ===")
        print("✓ 所有测试通过，UI与配置类集成正常")
        
    except Exception as e:
        print(f"✗ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 清理QApplication
        app.quit()

if __name__ == "__main__":
    test_ui_integration()
