# tmh-comm

TMH 通讯标准包，提供 RS485(Modbus-CPL/Modbus-RTU) 与 RS232(天平 ASCII) 的读写与数据格式标准化。  
可独立安装并复用。

## 安装

```bash
pip install -e packages/tmh_comm
```

## 标准化数据格式

所有解析输出统一为 `StandardFrame`：

```json
{
  "device_type": "mfc|temp|balance",
  "model": "MQV0020BS|MQV0005BS|CQM-V|<your-model>",
  "protocol": "modbus-cpl|modbus-rtu|rs232-ascii",
  "bus": "RS485|RS232",
  "payload": { "..." : "..." },
  "timestamp": 1699123456.789,
  "meta": {
    "port": "COM12",
    "baudrate": 9600,
    "slave_address": 1
  }
}
```

## 快速示例

### MFC (Modbus-CPL over RS485)

```python
from tmh_comm.protocols.mfc_cpl import MfcCplProtocol
from tmh_comm.standard import build_mfc_frame

proto = MfcCplProtocol()
cmd = proto.build_read(register_addr=1206, num_bytes=2, slave_address=1)

# response = serial.read(...)
value = proto.parse_response(response, expected_slave=1)
frame = build_mfc_frame(
    model="MQV0020BS",
    gas_type="H2",
    pv=value,
    sv=None,
    meta={"port": "COM12", "baudrate": 19200, "slave_address": 1}
)
```

### 温控仪表 (Modbus RTU over RS485)

```python
from tmh_comm.protocols.temp_rtu import TempRtuProtocol
from tmh_comm.standard import build_temp_frame

proto = TempRtuProtocol()
cmd = proto.build_read_all(slave_address=0)

# response = serial.read(...)
temps = proto.parse_read_all(response, scale=0.1)
frame = build_temp_frame(
    model="TEMP-CTRL",
    temperatures=temps,
    meta={"port": "COM10", "baudrate": 9600, "slave_address": 0}
)
```

### 天平 (RS232 ASCII)

```python
from tmh_comm.protocols.balance_rs232 import BalanceRs232Protocol
from tmh_comm.standard import build_balance_frame

proto = BalanceRs232Protocol()
weight = proto.parse_line("+00015.1 G S")
frame = build_balance_frame(
    model="BALANCE-1200",
    weight=weight,
    meta={"port": "COM15", "baudrate": 1200}
)
```
