# test_mfc_real.py
import time
from src.utils.config_loader import load_comm_config
from src.device_clients.multi_mfc_client import MultiMFCClient


def main():
    # 读取配置
    config = load_comm_config()
    mfc_cfg = config.get("COM_RS485_MFC", {})
    if not mfc_cfg:
        print("❌ 配置文件缺少 COM_RS485_MFC 配置")
        return

    # 初始化 MFC 客户端
    mfc = MultiMFCClient("mfc", mfc_cfg)
    try:
        mfc.start()
        print("✅ MFC 客户端已启动，开始轮询设备数据...\n(按 Ctrl+C 退出)")

        while True:
            result = mfc.read_all()
            values = result.get("values", {})

            print("======================================")
            for gas, data in values.items():
                pv = data.get("PV")
                sv = data.get("SV")
                pv_str = f"{pv:.2f} L/min" if pv is not None else "None"
                sv_str = f"{sv:.2f} L/min" if sv is not None else "None"
                print(f"💨 {gas}: PV={pv_str}, SV={sv_str}")
            print("======================================\n")

            time.sleep(2)

    except KeyboardInterrupt:
        print("\n⏹️ 手动停止测试")

    finally:
        mfc.stop()
        print("🔌 串口已关闭")


if __name__ == "__main__":
    main()
