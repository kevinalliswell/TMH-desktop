# DataHandler线程分离使用指南

## 概述

DataHandler类已重构，将数据监控线程和数据库处理线程完全分离，提供更精细的线程控制能力。

## 新增方法

### 1. 设备监控线程控制

#### `start_monitor_device_thread()`
启动设备监控线程，负责从设备采集数据并发送UI信号。

```python
data_handler = DataHandler(db_path)
data_handler.set_device_manager(device_manager)
data_handler.start_monitor_device_thread()
```

**特点**:
- 需要先设置device_manager
- 负责数据采集和UI信号发送
- 不依赖数据库线程

#### `stop_monitor_device_thread()`
停止设备监控线程。

```python
data_handler.stop_monitor_device_thread()
```

### 2. 数据库保存线程控制

#### `start_save_db_thread()`
启动数据库保存线程，负责将数据写入数据库。

```python
data_handler.start_save_db_thread()
```

**特点**:
- 不需要设备管理器
- 独立于监控线程运行
- 可以单独启动/停止

#### `stop_save_db_thread()`
停止数据库保存线程。

```python
data_handler.stop_save_db_thread()
```

### 3. 状态检查方法

#### `is_monitor_running()`
检查设备监控线程是否在运行。

```python
if data_handler.is_monitor_running():
    print("设备监控线程正在运行")
```

#### `is_db_running()`
检查数据库保存线程是否在运行。

```python
if data_handler.is_db_running():
    print("数据库保存线程正在运行")
```

#### `is_running()`
检查是否有任何线程在运行。

```python
if data_handler.is_running():
    print("有线程在运行")
```

#### `get_thread_status()`
获取详细的线程状态信息。

```python
status = data_handler.get_thread_status()
print(f"监控线程运行: {status['monitor_thread_running']}")
print(f"数据库线程运行: {status['db_thread_running']}")
print(f"监控线程存活: {status['monitor_thread_alive']}")
print(f"数据库线程存活: {status['db_thread_alive']}")
print(f"缓冲区大小: {status['buffer_size']}")
```

## 使用场景

### 场景1: 仅监控设备，不保存数据

```python
# 只启动监控线程，用于实时显示数据
data_handler.start_monitor_device_thread()
# 不启动数据库线程，数据不会保存到数据库
```

### 场景2: 仅保存数据，不实时监控

```python
# 只启动数据库线程，用于批量保存数据
data_handler.start_save_db_thread()
# 不启动监控线程，不会发送UI信号
```

### 场景3: 分阶段控制

```python
# 阶段1: 先启动监控，观察设备状态
data_handler.start_monitor_device_thread()
time.sleep(10)  # 观察10秒

# 阶段2: 开始保存数据
data_handler.start_save_db_thread()

# 阶段3: 停止监控，继续保存
data_handler.stop_monitor_device_thread()
time.sleep(5)  # 继续保存5秒

# 阶段4: 停止所有
data_handler.stop_save_db_thread()
```

### 场景4: 错误恢复

```python
# 监控线程出错时，可以单独重启
if not data_handler.is_monitor_running():
    data_handler.start_monitor_device_thread()

# 数据库线程出错时，可以单独重启
if not data_handler.is_db_running():
    data_handler.start_save_db_thread()
```

## 向后兼容性

原有的`start()`和`stop()`方法仍然可用，保持向后兼容：

```python
# 原有方式仍然有效
data_handler.start()  # 启动所有线程
data_handler.stop()   # 停止所有线程
```

## 线程安全

- 每个线程都有独立的停止事件
- 线程状态标志确保不会重复启动
- 使用适当的超时时间避免死锁

## 最佳实践

### 1. 启动顺序
```python
# 推荐：先启动数据库线程，再启动监控线程
data_handler.start_save_db_thread()
data_handler.start_monitor_device_thread()
```

### 2. 停止顺序
```python
# 推荐：先停止监控线程，再停止数据库线程
data_handler.stop_monitor_device_thread()
data_handler.stop_save_db_thread()
```

### 3. 错误处理
```python
try:
    data_handler.start_monitor_device_thread()
except ValueError as e:
    print(f"启动失败: {e}")
    # 检查是否设置了device_manager
```

### 4. 状态监控
```python
# 定期检查线程状态
status = data_handler.get_thread_status()
if not status['monitor_thread_alive'] and status['monitor_thread_running']:
    print("监控线程异常退出，需要重启")
    data_handler.start_monitor_device_thread()
```

## 注意事项

1. **设备管理器依赖**: 监控线程需要先设置device_manager
2. **数据库路径**: 数据库线程需要有效的数据库路径
3. **线程生命周期**: 确保在程序退出前停止所有线程
4. **资源清理**: 停止线程后会自动清理相关资源

## 示例代码

```python
#!/usr/bin/env python3
"""DataHandler线程分离使用示例"""

from device_clients.data_handler import DataHandler

def main():
    # 创建DataHandler实例
    data_handler = DataHandler("test.db", save_interval=10)
    
    # 设置设备管理器（如果需要监控）
    # data_handler.set_device_manager(device_manager)
    
    try:
        # 启动数据库保存线程
        data_handler.start_save_db_thread()
        print("数据库保存线程已启动")
        
        # 启动设备监控线程（需要设备管理器）
        # data_handler.start_monitor_device_thread()
        # print("设备监控线程已启动")
        
        # 检查状态
        status = data_handler.get_thread_status()
        print(f"线程状态: {status}")
        
        # 运行一段时间
        import time
        time.sleep(5)
        
    finally:
        # 清理资源
        data_handler.stop()
        print("所有线程已停止")

if __name__ == "__main__":
    main()
```

---

**更新日期**: 2024年12月  
**版本**: v1.0  
**维护者**: TMH开发团队
