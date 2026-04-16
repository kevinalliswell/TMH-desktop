## 📊 TMH系统数据采集逻辑完整梳理

### 🏗️ 1. 系统架构概览

TMH系统采用分层架构设计，包含以下核心组件：
- **设备层**: 三类物理设备（温控器、天平、流量计）
- **通信层**: 设备客户端（TempClient、BalanceClient、MultiMFCClient） 
- **数据处理层**: DataHandler 负责数据校验、清洗和分发
- **UI层**: 实时显示、图表绘制、数据表格
- **存储层**: SQLite数据库持久化存储

### 🔌 2. 设备通信协议与数据格式

#### 2.1 温控器 (TempClient)
- **通信协议**: Modbus RTU (RS485)
- **数据采集**: 9个温度点 (T1-T9)
- **数据格式**:
```python
{
    "T1": 850.0,      # 一区温度PV
    "T2": 855.0,      # 一区温度SV  
    "T3": 860.0,      # 二区温度PV
    "T4": 865.0,      # 二区温度SV
    "T5": 870.0,      # 三区温度PV
    "T6": 875.0,      # 三区温度SV
    "T7": 880.0,      # 测温1
    "T8": 885.0,      # 测温2 (主要温度)
    "T9": 890.0,      # 测温3
    "timestamp": 1699123456.789
}
```

#### 2.2 电子天平 (BalanceClient)
- **通信协议**: RS232
- **数据采集**: 稳定重量值 (标识为"G S")
- **数据格式**:
```python
{
    "weight": 495.123,    # 单位: 克
    "timestamp": 1699123456.789
}
```

#### 2.3 质量流量计 (MultiMFCClient)
- **通信协议**: Modbus RTU (RS485)
- **数据采集**: 四种气体的PV/SV值
- **数据格式**:
```python
{
    "channels": {          # 当前值(PV)
        "CO": 2.5,
        "CO2": 1.8, 
        "N2": 15.0,        # N2值需乘以10
        "H2": 0.5
    },
    "setpoints": {         # 设定值(SV)
        "CO": 2.5,
        "CO2": 1.8,
        "N2": 15.0,
        "H2": 0.5
    },
    "timestamp": 1699123456.789
}
```

### 🔄 3. 数据处理流程

#### 3.1 数据采集线程
每个设备客户端运行独立线程，定期采集数据：
- **温控器**: 1.0秒间隔
- **天平**: 0.1秒间隔  
- **流量计**: 1.0秒间隔

#### 3.2 数据处理器 (DataHandler)
负责统一处理来自三个设备的数据：

```python
def _data_processing_loop(self):
    # 1. 获取设备状态
    status = self.device_manager.get_status()
    
    # 2. 数据校验和清洗
    temp_payload = _valid_temperature_payload(status.get('temperature'))
    weight_payload = _valid_weight_payload(status.get('weight'))
    flows_payload = _valid_flows_payload(status.get('flows'))
    
    # 3. 发送UI信号
    if temp_payload:
        self.temperature_data_updated.emit(temp_payload)
    if weight_payload:
        self.weight_data_updated.emit(weight_payload)
    if flows_payload:
        self.flow_data_updated.emit(flows_payload)
    
    # 4. 缓存到数据库队列
    if self.experiment_running:
        self.data_buffer.put_nowait(bundle)
```

### 📈 4. UI数据显示

#### 4.1 实时曲线绘制 (PlotDockWidget)
使用PyQtGraph绘制实时曲线：
- **温度曲线**: T1-T9九条曲线，不同颜色区分
- **流量曲线**: CO/CO2/N2/H2四条曲线
- **重量曲线**: 单条绿色曲线

```python
def update_curve(self, name: str, x_data: list, y_data: list):
    """更新曲线数据"""
    if name in self.curves:
        self.curves[name].setData(x_data, y_data)
```

#### 4.2 实时数值显示 (MonitorPanel)
显示当前数值的数字面板：
- 温度、重量、流量的实时数值
- 彩色背景，易于识别

#### 4.3 数据表格 (DataTablePanel)
记录历史数据的表格：
- 时间、温度、重量、失重、流量等列
- 实验状态和系统消息

### 💾 5. 数据库存储结构

#### 5.1 数据库表结构
```sql
-- 温度数据表
CREATE TABLE temperature_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL,
    T1 REAL, T2 REAL, T3 REAL, T4 REAL, T5 REAL,
    T6 REAL, T7 REAL, T8 REAL, T9 REAL
);

-- 重量数据表  
CREATE TABLE weight_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL,
    weight REAL
);

-- 流量数据表
CREATE TABLE flow_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL,
    gas_type TEXT,
    PV REAL,
    SV REAL
);
```

#### 5.2 批量写入机制
- **触发条件**: 仅在实验运行时保存数据
- **批量间隔**: 默认60秒批量写入
- **数据缓冲**: 使用队列缓存，防止内存溢出

### 🔧 6. 数据质量保证

#### 6.1 数据校验
```python
def _has_numeric_value(d: Optional[dict]) -> bool:
    """检查是否包含有效数值"""
    if not isinstance(d, dict):
        return False
    for v in d.values():
        if isinstance(v, (int, float)) and v is not None:
            return True
    return False
```

#### 6.2 错误处理
- **通信异常**: 重试机制，最大重试3次
- **数据异常**: 忽略无效数据，保持上一个有效值
- **队列满**: 清除旧数据，保留最新数据

### 📊 7. 性能优化特性

- **节流机制**: UI更新间隔1秒，防止界面卡顿
- **数据去重**: 仅在数据变化时更新界面
- **内存管理**: 限制数据缓冲区大小，防止内存泄漏
- **线程安全**: 使用锁保护共享数据结构

### 🎯 8. 关键特点总结

1. **实时性**: 所有数据都是实时采集，无模拟数据
2. **稳定性**: 完善的错误处理和重连机制
3. **可扩展性**: 模块化设计，易于添加新设备
4. **数据完整性**: 严格的数据校验和时间戳同步
5. **用户体验**: 多种展示方式（曲线、数值、表格）

这套数据采集系统为TMH热重分析实验提供了可靠的数据基础，确保实验数据的准确性和完整性。