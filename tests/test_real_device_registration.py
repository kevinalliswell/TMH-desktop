# test_real_device_registration.py
"""
测试真实设备注册功能
"""
import sys
from src.utils.config_loader import load_comm_config
from src.device_clients.device_manager import DeviceManager
from src.device_clients.balance_client import BalanceClient
from src.device_clients.temp_client import TempClient
from src.device_clients.multi_mfc_client import MultiMFCClient

def test_config_loading():
    """测试配置加载"""
    print("🔧 测试配置加载...")
    
    comm_cfg = load_comm_config()
    
    # 检查必要的配置键
    required_keys = ["COM_RS485_MFC", "COM_RS485_TEMP", "COM_RS232_Balance", "PERFORMANCE_CONFIG"]
    
    for key in required_keys:
        if key in comm_cfg:
            print(f"✅ 找到配置: {key}")
        else:
            print(f"❌ 缺少配置: {key}")
    
    return comm_cfg

def test_device_creation():
    """测试设备创建"""
    print("\n🔧 测试设备创建...")
    
    comm_cfg = load_comm_config()
    dm = DeviceManager()
    
    try:
        # 测试天平设备
        balance_cfg = comm_cfg.get("COM_RS232_Balance", {})
        if balance_cfg:
            balance_client = BalanceClient("Balance", balance_cfg)
            dm.register_device("Balance", balance_client)
            print("✅ 天平设备创建成功")
        else:
            print("❌ 天平配置缺失")
        
        # 测试温度设备
        temp_cfg = comm_cfg.get("COM_RS485_TEMP", {})
        if temp_cfg:
            temp_client = TempClient("Temp", temp_cfg)
            dm.register_device("Temp", temp_client)
            print("✅ 温度设备创建成功")
        else:
            print("❌ 温度配置缺失")
        
        # 测试MFC设备
        mfc_cfg = comm_cfg.get("COM_RS485_MFC", {})
        if mfc_cfg:
            mfc_client = MultiMFCClient("MFC", mfc_cfg)
            dm.register_device("MFC", mfc_client)
            print("✅ MFC设备创建成功")
        else:
            print("❌ MFC配置缺失")
        
        print(f"\n📊 已注册设备: {dm.list_devices()}")
        
    except Exception as e:
        print(f"❌ 设备创建失败: {e}")
        return False
    
    return True

def test_performance_config():
    """测试性能配置"""
    print("\n🔧 测试性能配置...")
    
    comm_cfg = load_comm_config()
    perf_cfg = comm_cfg.get("PERFORMANCE_CONFIG", {})
    
    data_collection_interval = perf_cfg.get("data_collection_interval", 0.5)
    heartbeat_timeout = perf_cfg.get("heartbeat_timeout", 5.0)
    
    print(f"✅ 数据采集间隔: {data_collection_interval}s")
    print(f"✅ 心跳超时: {heartbeat_timeout}s")
    
    return True

def main():
    """主测试函数"""
    print("🚀 开始测试真实设备注册...")
    
    try:
        # 测试配置加载
        config_ok = test_config_loading()
        
        # 测试设备创建
        device_ok = test_device_creation()
        
        # 测试性能配置
        perf_ok = test_performance_config()
        
        if config_ok and device_ok and perf_ok:
            print("\n✅ 所有测试通过！真实设备注册功能正常")
        else:
            print("\n❌ 部分测试失败，请检查配置和代码")
            
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
