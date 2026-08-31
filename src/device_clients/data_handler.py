# data_handler.py
import threading
import time
import sqlite3
import math
from PySide6.QtCore import QObject, Signal
import queue
from datetime import datetime
from src.utils.logger import get_logger

class DataHandler(QObject):
    DATA_BUFFER_SIZE = 1000  # 数据缓冲区最大容量

    # 定义信号，用于向UI发送数据
    temperature_data_updated = Signal(dict)
    weight_data_updated = Signal(dict)
    flow_data_updated = Signal(dict)
    all_data_updated = Signal(dict)  # 所有数据的汇总信号（实时显示用）
    experiment_data_sampled = Signal(dict)  # 实验数据采样信号（图表和表格用）
    
    def __init__(self, db_path, save_interval=60, device_manager=None, experiment_db=None,
                 state_machine=None, snapshot_provider=None):
        """
        初始化数据处理器
        
        Args:
            db_path (str): 数据库文件路径
            save_interval (int): 数据保存间隔(秒)
            device_manager: 可选，设备管理器实例（支持依赖注入）
            experiment_db: 可选，实验数据库实例（支持依赖注入）
            state_machine: 可选，集中式状态机（ExperimentStateMachine）
        """
        super().__init__()
        self.db_path = db_path
        self.save_interval = save_interval
        self.device_manager = device_manager
        self.snapshot_provider = snapshot_provider
        self._injected_experiment_db = experiment_db
        self._sm = state_machine  # 集中式状态机引用
        self._latest_snapshot_bundle = None

        # 设置数据缓冲区最大容量，防止内存溢出
        self.data_buffer = queue.Queue(maxsize=self.DATA_BUFFER_SIZE)
        self.stop_event = threading.Event()
        
        # 初始化日志
        self.logger = get_logger("数据处理器")
        
        # 数据库写入重试配置
        self.db_max_retries = 3
        self.db_retry_delay = 0.5  # 秒
        
        # 加载配置
        self.data_collection_interval = self._load_data_collection_interval()  # 0.2秒
        self.sampling_interval = self._load_sampling_interval()  # 1.0秒
        
        # 初始化数据库
        self._init_database()
        
        # 线程状态标志
        self.is_running = False
        self.data_thread = None
        self.db_thread = None
        
        # 实验数据库连接（用于保存实验相关数据）
        self.experiment_db = None
        self._init_experiment_db()
    
    def _load_data_collection_interval(self):
        """加载设备通信间隔配置"""
        try:
            from ..utils.path_manager import PathManager
            import json
            
            config_path = PathManager.get_config_path('comm_config.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            interval = config.get('PERFORMANCE_CONFIG', {}).get('data_collection_interval', 0.2)
            self.logger.info(f"设备通信间隔设置为: {interval}秒")
            return interval
            
        except Exception as e:
            self.logger.warning(f"加载设备通信配置失败，使用默认值0.2秒: {e}")
            return 0.2
    
    def _load_sampling_interval(self):
        """加载实验数据采样间隔配置"""
        try:
            from ..utils.path_manager import PathManager
            import json
            
            config_path = PathManager.get_config_path('comm_config.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            interval = config.get('SAMPLING', {}).get('interval_s', 1.0)
            self.logger.info(f"实验数据采样间隔设置为: {interval}秒")
            return interval
            
        except Exception as e:
            self.logger.warning(f"加载采样配置失败，使用默认值1.0秒: {e}")
            return 1.0
    
    def _init_experiment_db(self):
        """初始化实验数据库连接（优先使用注入的实例）"""
        if self._injected_experiment_db is not None:
            self.experiment_db = self._injected_experiment_db
            self.logger.info("使用注入的实验数据库实例")
            return
        try:
            from ..services.database import ExperimentDatabase
            self.experiment_db = ExperimentDatabase()
            self.logger.info("实验数据库连接初始化成功")
        except Exception as e:
            self.logger.error(f"实验数据库连接初始化失败: {e}")
            self.experiment_db = None
    
    def set_device_manager(self, device_manager):
        """设置设备管理器"""
        self.device_manager = device_manager
        if hasattr(device_manager, "get_snapshots"):
            self.snapshot_provider = device_manager

    def set_snapshot_provider(self, snapshot_provider):
        """设置标准化快照提供者"""
        self.snapshot_provider = snapshot_provider

    def latest_snapshot_bundle(self):
        """获取最近一次标准化快照集合"""
        if self._latest_snapshot_bundle is not None:
            return self._latest_snapshot_bundle
        if self.snapshot_provider and hasattr(self.snapshot_provider, "get_snapshots"):
            return self.snapshot_provider.get_snapshots()
        return None
    
    def start(self):
        """启动数据处理与保存"""
        if not self.device_manager:
            raise ValueError("Device manager not set")
        
        if self.is_running:
            return  # 如果已经在运行，直接返回
        
        # 重置停止事件
        self.stop_event.clear()
        
        # 创建新的线程。
        # daemon=True 是最后一道保险：stop() 正常路径仍会 signal + join 并完成
        # 最终落盘，但当某个线程卡在 SQLite 写入时，非守护线程会让解释器在
        # threading._shutdown() 里无超时地等下去，进程永远退不掉。
        self.data_thread = threading.Thread(target=self._data_processing_loop, daemon=True)
        self.db_thread = threading.Thread(target=self._db_saving_loop, daemon=True)
        
        # 启动线程
        self.data_thread.start()
        self.db_thread.start()
        self.is_running = True

    def start_monitor_device_thread(self):
        """启动设备监控线程（兼容原有接口）"""
        self.start()

    def set_state_machine(self, state_machine):
        """设置集中式状态机引用"""
        self._sm = state_machine

    @property
    def is_experiment_running(self) -> bool:
        """从状态机查询实验运行状态（线程安全）"""
        if self._sm:
            return self._sm.is_running
        return False

    @property
    def current_experiment_id(self) -> str:
        """从状态机查询当前实验 ID"""
        if self._sm:
            return self._sm.get_state().experiment_id
        return ""

    @property
    def experiment_start_time(self) -> float:
        """从状态机查询实验开始时间"""
        if self._sm:
            return self._sm.get_state().experiment_start_time
        return 0.0

    @property
    def initial_weight(self) -> float:
        """从状态机查询初始重量"""
        if self._sm:
            return self._sm.get_state().initial_weight
        return 0.0

    def stop(self):
        """停止数据处理与保存"""
        if not self.is_running:
            return  # 如果已经停止，直接返回
        
        self.stop_event.set()
        
        # 等待线程结束
        if self.data_thread and self.data_thread.is_alive():
            self.data_thread.join(timeout=3.0)
            if self.data_thread.is_alive():
                self.logger.warning("数据处理线程未能在预期时间内停止")
        if self.db_thread and self.db_thread.is_alive():
            self.db_thread.join(timeout=3.0)
            if self.db_thread.is_alive():
                self.logger.warning("数据库保存线程未能在预期时间内停止")

        # 数据线程可能在数据库线程执行最终落盘后才放入最后一个样本；
        # 两个 join 之后由调用线程再兜底落盘一次，关闭程序时也不遗留队列数据。
        remaining_data = []
        self._drain_data_buffer(remaining_data)
        if remaining_data:
            self._save_data_batch(remaining_data)
            self._close_thread_db_connection()
        
        # 重置线程和状态
        self.data_thread = None
        self.db_thread = None
        self.is_running = False
        
        self.logger.info("数据处理器已停止")
    
    def _init_database(self):
        """初始化SQLite数据库结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建温度数据表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS temperature_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL,
            T1 REAL, T2 REAL, T3 REAL, T4 REAL, T5 REAL, 
            T6 REAL, T7 REAL, T8 REAL, T9 REAL
        )
        ''')
        
        # 创建重量数据表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS weight_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL,
            weight REAL
        )
        ''')
        
        # 创建流量数据表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS flow_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL,
            gas_type TEXT,
            PV REAL,
            SV REAL
        )
        ''')
        
        conn.commit()
        conn.close()
    
    def _data_processing_loop(self):
        """数据处理主循环，支持双重时间间隔"""
        last_realtime_data = None
        last_sample_time = 0
        
        while not self.stop_event.is_set():
            try:
                current_time = time.time()
                data = self._get_current_snapshot_payload()
                
                # 1. 实时数据处理（用于监控面板显示）
                if data != last_realtime_data:
                    # 发送实时数据信号（用于监控面板）
                    self.all_data_updated.emit(data)
                    last_realtime_data = data
                
                # 2. 实验数据采样（用于图表和数据表格）
                if current_time - last_sample_time >= self.sampling_interval:
                    # 发送采样数据信号（用于图表和表格）
                    self.experiment_data_sampled.emit(data)
                    
                    # 将数据放入保存缓冲区（处理缓冲区满的情况）
                    try:
                        self.data_buffer.put(data, block=False)
                    except queue.Full:
                        self.logger.warning("数据缓冲区已满(1000条)，丢弃旧数据以腾出空间")
                        try:
                            self.data_buffer.get_nowait()
                            self.data_buffer.put(data, block=False)
                        except (queue.Empty, queue.Full):
                            self.logger.error("无法将数据放入缓冲区，数据可能丢失")
                    
                    # 如果实验运行中，同时保存到实验数据库
                    if self.is_experiment_running and self.current_experiment_id:
                        self._save_experiment_data_point(data, current_time)
                    
                    last_sample_time = current_time
                    self.logger.debug(f"实验数据采样: {data}")
                
                # 使用设备通信间隔
                self.stop_event.wait(self.data_collection_interval)
                
            except Exception as e:
                self.logger.error(f"数据处理出错: {str(e)}")
                self.stop_event.wait(1)

    def _get_current_snapshot_payload(self):
        """获取当前采样数据，同时更新标准化快照缓存。"""
        if self.snapshot_provider:
            if hasattr(self.snapshot_provider, "get_snapshots"):
                self._latest_snapshot_bundle = self.snapshot_provider.get_snapshots()
            if hasattr(self.snapshot_provider, "get_status_legacy"):
                return self.snapshot_provider.get_status_legacy()

        if not self.device_manager:
            raise ValueError("Device manager not set")

        if hasattr(self.device_manager, "get_snapshots"):
            self._latest_snapshot_bundle = self.device_manager.get_snapshots()
        return self.device_manager.get_status()
    
    def _db_saving_loop(self):
        """数据库保存主循环，按照指定间隔保存数据"""
        last_save_time = time.time()
        batch_data = []
        
        try:
            while not self.stop_event.is_set():
                try:
                    # 获取所有可用数据
                    self._drain_data_buffer(batch_data)
                    
                    # 检查是否到达保存间隔
                    now = time.time()
                    if now - last_save_time >= self.save_interval and batch_data:
                        self._save_data_batch(batch_data)
                        batch_data = []
                        last_save_time = now
                    
                    # 短暂休眠；停止时立即唤醒，以便执行最终落盘。
                    self.stop_event.wait(1)
                    
                except Exception as e:
                    self.logger.error(f"数据保存出错: {str(e)}")
                    self.stop_event.wait(1)
        finally:
            # 停止信号可能在保存周期到达前触发，必须落盘剩余批次。
            self._drain_data_buffer(batch_data)
            if batch_data:
                self._save_data_batch(batch_data)
            # 线程结束时关闭数据库连接
            self._close_thread_db_connection()

    def _drain_data_buffer(self, batch_data):
        """将当前队列快照移入批次，避免 Queue.empty() 的竞态。"""
        while True:
            try:
                batch_data.append(self.data_buffer.get_nowait())
            except queue.Empty:
                return
    
    def _save_data_batch(self, data_batch):
        """保存一批数据到数据库（增强版：重试机制 + executemany优化）
        
        Args:
            data_batch (list): 数据列表，每项是一个设备状态字典
        """
        if not data_batch:
            return
        
        # 使用重试机制
        for attempt in range(self.db_max_retries):
            try:
                self._save_data_batch_internal(data_batch)
                return  # 保存成功，退出
            except Exception as e:
                if attempt < self.db_max_retries - 1:
                    self.logger.warning(f"数据库写入失败 (尝试 {attempt + 1}/{self.db_max_retries}): {str(e)}，将重试")
                    time.sleep(self.db_retry_delay)
                else:
                    self.logger.error(f"数据库写入失败，已重试 {self.db_max_retries} 次: {str(e)}")
    
    def _get_db_connection(self):
        """获取数据库连接（线程内复用，减少连接开销）"""
        if not hasattr(self, '_thread_local'):
            import threading as _threading
            self._thread_local = _threading.local()
        
        conn = getattr(self._thread_local, 'db_conn', None)
        if conn is None:
            conn = sqlite3.connect(self.db_path, timeout=10.0)
            self._thread_local.db_conn = conn
            self.logger.debug("创建新的线程本地数据库连接")
        return conn

    def _close_thread_db_connection(self):
        """关闭当前线程的数据库连接"""
        if hasattr(self, '_thread_local'):
            conn = getattr(self._thread_local, 'db_conn', None)
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
                self._thread_local.db_conn = None

    def _save_data_batch_internal(self, data_batch):
        """内部方法：实际执行数据库批量保存（使用executemany优化）
        
        Args:
            data_batch (list): 数据列表，每项是一个设备状态字典
        """
        if not data_batch:
            return
        
        # 使用线程本地连接，减少频繁创建/关闭连接的开销
        conn = self._get_db_connection()
        cursor = conn.cursor()
        
        try:
            # 开始事务
            conn.execute("BEGIN TRANSACTION")
            
            # 准备批量插入的数据
            temp_data_list = []
            weight_data_list = []
            flow_data_list = []
            
            for data in data_batch:
                frames = data.get("frames") or {}

                # 收集温度数据（完全基于 frames）
                temp_frame = frames.get("temperature")
                if temp_frame:
                    temps = getattr(temp_frame, "payload", {}).get("temperatures", {})
                    timestamp = getattr(temp_frame, "timestamp", time.time())
                    temp_data_list.append((
                        timestamp,
                        temps.get("T1"),
                        temps.get("T2"),
                        temps.get("T3"),
                        temps.get("T4"),
                        temps.get("T5"),
                        temps.get("T6"),
                        temps.get("T7"),
                        temps.get("T8"),
                        temps.get("T9")
                    ))
                
                # 收集重量数据（完全基于 frames）
                weight_frame = frames.get("weight")
                if weight_frame:
                    weight_val = getattr(weight_frame, "payload", {}).get("weight")
                    timestamp = getattr(weight_frame, "timestamp", time.time())
                    weight_data_list.append((
                        timestamp,
                        weight_val
                    ))
                
                # 收集流量数据（完全基于 frames）
                flow_frames = frames.get("flows") or {}
                for gas_type, flow_frame in flow_frames.items():
                    if not flow_frame:
                        continue
                    payload = getattr(flow_frame, "payload", {})
                    timestamp = getattr(flow_frame, "timestamp", time.time())
                    flow_data_list.append((
                        timestamp,
                        gas_type,
                        payload.get("pv"),
                        payload.get("sv")
                    ))
            
            # 使用executemany批量插入，提高效率
            if temp_data_list:
                cursor.executemany(
                    '''
                    INSERT INTO temperature_data 
                    (timestamp, T1, T2, T3, T4, T5, T6, T7, T8, T9)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    temp_data_list
                )
            
            if weight_data_list:
                cursor.executemany(
                    '''
                    INSERT INTO weight_data 
                    (timestamp, weight)
                    VALUES (?, ?)
                    ''',
                    weight_data_list
                )
            
            if flow_data_list:
                cursor.executemany(
                    '''
                    INSERT INTO flow_data 
                    (timestamp, gas_type, PV, SV)
                    VALUES (?, ?, ?, ?)
                    ''',
                    flow_data_list
                )
            
            # 提交事务
            conn.commit()
            total_records = len(temp_data_list) + len(weight_data_list) + len(flow_data_list)
            self.logger.info(f"已保存{len(data_batch)}批数据，共{total_records}条记录到数据库")
            
        except Exception as e:
            # 回滚事务
            try:
                conn.rollback()
            except Exception:
                # 连接可能已损坏，关闭并重置以便下次重建
                self._close_thread_db_connection()
            self.logger.error(f"保存数据到数据库失败: {str(e)}")
            raise  # 重新抛出异常供重试机制处理
    
    def _save_experiment_data_point(self, data: dict, timestamp: float):
        """
        保存单个实验数据点到实验数据库
        
        Args:
            data: 设备数据字典
            timestamp: 时间戳
        """
        if not self.experiment_db or not self.is_experiment_running or not self.current_experiment_id:
            return
            
        try:
            # 提取所需数据
            frames = data.get("frames") or {}
            temperature_data = {}
            weight_data = {}
            flows_data = {}

            temp_frame = frames.get("temperature")
            if temp_frame:
                temperature_data = getattr(temp_frame, "payload", {}).get("temperatures", {}) or {}

            weight_frame = frames.get("weight")
            if weight_frame:
                weight_data = {"weight": getattr(weight_frame, "payload", {}).get("weight")}

            flow_frames = frames.get("flows") or {}
            for gas_type, flow_frame in flow_frames.items():
                if not flow_frame:
                    continue
                payload = getattr(flow_frame, "payload", {})
                flows_data[gas_type] = {"PV": payload.get("pv")}
            
            # 获取样品温度（假设T8是样品温度）。数据库数值列保持非空，
            # 同时用 data_quality 区分真实的 0 和设备无有效读数时的兜底值。
            sample_temp, temperature_valid = self._coerce_numeric_sample(
                temperature_data.get("T8") if temperature_data else None
            )
            
            # 获取重量数据（天平断线时 weight 可能为 None，dict.get 的默认值不会生效，
            # 需显式兜底为 0.0，否则后续减重率计算会 TypeError 并静默丢弃整点数据）
            current_weight, weight_valid = self._coerce_numeric_sample(
                (weight_data or {}).get("weight")
            )
            if not weight_valid:
                current_weight = None

            # 计算减重率
            weight_loss = None
            if weight_valid and self.initial_weight and self.initial_weight > 0:
                weight_loss = ((self.initial_weight - current_weight) / self.initial_weight) * 100
            
            # 获取气体流量数据
            flow_samples = {}
            for gas_type in ("CO", "CO2", "N2", "H2"):
                flow_data = flows_data.get(gas_type)
                raw_value = (
                    flow_data.get("PV")
                    if isinstance(flow_data, dict)
                    else flow_data
                )
                flow_samples[gas_type] = self._coerce_numeric_sample(raw_value)

            co_flow, co_valid = flow_samples["CO"]
            co2_flow, co2_valid = flow_samples["CO2"]
            n2_flow, n2_valid = flow_samples["N2"]
            h2_flow, h2_valid = flow_samples["H2"]
            
            # 计算实验持续时间
            experiment_duration = ""
            if self.experiment_start_time:
                duration_seconds = int(timestamp - self.experiment_start_time)
                hours = duration_seconds // 3600
                minutes = (duration_seconds % 3600) // 60
                seconds = duration_seconds % 60
                experiment_duration = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            
            # 构建数据点
            data_point = {
                'timestamp': datetime.fromtimestamp(timestamp).isoformat(),
                'experiment_duration': experiment_duration,
                'temperature': sample_temp,
                'weight': current_weight,
                'weight_loss': weight_loss,
                'co_flow': co_flow,
                'co2_flow': co2_flow,
                'n2_flow': n2_flow,
                'h2_flow': h2_flow,
                'experiment_status': '运行中',
                'system_message': '数据采集',
                'data_quality': {
                    'temperature': temperature_valid,
                    'weight': weight_valid,
                    'flows': {
                        'CO': co_valid,
                        'CO2': co2_valid,
                        'N2': n2_valid,
                        'H2': h2_valid,
                    },
                },
            }
            
            # 保存到实验数据库
            success = self.experiment_db.add_experiment_data(self.current_experiment_id, data_point)
            if success:
                self.logger.debug(f"实验数据点已保存到数据库: {self.current_experiment_id}")
            else:
                self.logger.warning(f"保存实验数据点到数据库失败: {self.current_experiment_id}")
                
        except Exception as e:
            self.logger.error(f"保存实验数据点失败: {e}")

    @staticmethod
    def _coerce_numeric_sample(value):
        """Return a finite numeric value and whether the source reading was valid."""
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return 0.0, False

        if not math.isfinite(numeric_value):
            return 0.0, False
        return numeric_value, True
