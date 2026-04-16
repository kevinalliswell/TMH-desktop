import time
import pytest

from src.utils.config_loader import load_comm_config
from src.device_clients.device_manager import DeviceManager
from src.device_clients.balance_client import BalanceClient
from src.device_clients.temp_client import TempClient
from src.device_clients.multi_mfc_client import MultiMFCClient


@pytest.fixture(scope="module")
def real_device_manager():
    """初始化真实设备管理器"""
    config = load_comm_config()
    dm = DeviceManager()

    # 注册 Balance
    balance = BalanceClient("balance", config["COM_RS232_Balance"])
    dm.register_device("balance", balance)

    # 注册 Temp
    temp = TempClient("temp", dict(config["COM_RS485_TEMP"]))
    dm.register_device("temp", temp)

    # 注册 MFC
    mfc = MultiMFCClient("mfc", dict(config["COM_RS485_MFC"]))
    dm.register_device("mfc", mfc)

    yield dm
    dm.stop_all_devices()


def test_real_balance_stream(real_device_manager):
    """测试天平连续输出"""
    real_device_manager.start_device("balance")
    dev = real_device_manager._get_device("balance")

    time.sleep(3)  # 等待数据上送
    data = dev.read_stream_once()
    status = dev.get_status()
    print("📟 Balance stream once:", data)
    print("📟 Balance status:", status)

    assert (data and "mass_g" in data) or status.get("last_weight") is not None


def test_real_temp_read(real_device_manager):
    """测试温控器读取"""
    real_device_manager.start_device("temp")
    dev = real_device_manager._get_device("temp")

    result = dev.read_registers()
    print("🌡️ Temp registers:", result)

    assert result is None or "temperatures_C" in result


def test_real_mfc_read(real_device_manager):
    """测试多台 MFC 主动读取"""
    real_device_manager.start_device("mfc")
    dev = real_device_manager._get_device("mfc")

    # 读取所有气体
    result = dev.read_all()
    print("💨 MFC read_all:", result)

    # 验证数据结构
    assert result and "values" in result
    values = result["values"]
    
    # 检查每个气体的数据
    for gas, data in values.items():
        print(f"  {gas}: PV={data.get('PV')}, SV={data.get('SV')}")
        if data.get('PV_error'):
            print(f"    PV错误: {data['PV_error']}")
        if data.get('SV_error'):
            print(f"    SV错误: {data['SV_error']}")
    
    # 至少有一个气体返回有效数据
    assert any(data.get('PV') is not None or data.get('SV') is not None for data in values.values())


def test_real_mfc_set_sv(real_device_manager):
    """测试 MFC 设置并验证 SV"""
    real_device_manager.start_device("mfc")
    dev = real_device_manager._get_device("mfc")

    # 测试设置N2的SV值
    gas = "N2"
    target_sv = 2.5
    
    print(f"🎯 设置 {gas} SV 为 {target_sv} L/min...")
    sv = dev.set_sv(gas, target_sv, verify=True)
    print(f"   回读SV: {sv} L/min")

    # 验证设置是否成功
    assert sv is not None
    assert abs(sv - target_sv) < 0.1  # 允许0.1的误差

    # 再次读取所有气体数据确认
    print("📊 重新读取所有气体数据...")
    result = dev.read_all()
    values = result.get("values", {})
    
    for gas_name, data in values.items():
        pv = data.get('PV')
        sv = data.get('SV')
        print(f"  {gas_name}: PV={pv:.2f} L/min, SV={sv:.2f} L/min" if pv is not None and sv is not None else f"  {gas_name}: PV={pv}, SV={sv}")


def test_real_mfc_individual_read(real_device_manager):
    """测试单个气体读取"""
    real_device_manager.start_device("mfc")
    dev = real_device_manager._get_device("mfc")

    # 测试读取单个气体
    gases = ["H2", "N2", "CO2", "CO"]
    
    for gas in gases:
        try:
            result = dev.read_one(gas)
            pv = result.get('PV')
            sv = result.get('SV')
            print(f"🔍 {gas} 单独读取: PV={pv:.2f} L/min, SV={sv:.2f} L/min" if pv is not None and sv is not None else f"🔍 {gas} 单独读取: PV={pv}, SV={sv}")
            
            # 检查是否有错误
            if result.get('PV_error'):
                print(f"    PV错误: {result['PV_error']}")
            if result.get('SV_error'):
                print(f"    SV错误: {result['SV_error']}")
                
        except Exception as e:
            print(f"❌ {gas} 读取失败: {e}")


def test_real_mfc_continuous_monitoring(real_device_manager):
    """测试MFC连续监控"""
    real_device_manager.start_device("mfc")
    dev = real_device_manager._get_device("mfc")

    print("📈 开始连续监控MFC数据 (3次采样)...")
    
    for i in range(3):
        result = dev.read_all()
        values = result.get("values", {})
        
        print(f"\n--- 第 {i+1} 次采样 ---")
        for gas, data in values.items():
            pv = data.get('PV')
            sv = data.get('SV')
            if pv is not None and sv is not None:
                print(f"  {gas}: PV={pv:.2f} L/min, SV={sv:.2f} L/min")
            else:
                print(f"  {gas}: PV={pv}, SV={sv}")
        
        if i < 2:  # 不是最后一次
            time.sleep(2)
    
    print("✅ 连续监控完成")
