"""
实验控制器模块
遵循PEP8规范，负责实验流程的控制和管理

注意：此模块从 src/ui/experiment/ 迁移至 src/controllers/，
以修复服务层反向依赖 UI 层的架构问题。
"""
import time
import json
import os
import uuid
import logging
from datetime import datetime
from typing import Optional, Callable, Tuple
from PySide6.QtCore import QCoreApplication, QObject, Signal, QTimer

from src.models.experiment_state import (
    ExperimentStateMachine,
    ExperimentPhase,
    InvalidTransitionError,
)
from src.services.experiment_modes import ExperimentType
from src.services.enhanced_experiment_modes import EnhancedExperimentModeManager
from src.services.experiment_type_manager import ExperimentTypeManager
from src.services.database import ExperimentDatabase, ExperimentData
from src.utils.path_manager import PathManager


class ExperimentController(QObject):
    """实验控制器类"""

    # 实验常量
    SAFETY_N2_FLOW_LPM = 5.0  # 安全气氛 N2 流量 (L/min)
    AMBIENT_TEMP_CELSIUS = 25.0  # 默认环境/起始温度 (°C)

    # 信号定义
    status_updated = Signal(str)  # 实验状态更新
    system_message_updated = Signal(str)  # 系统消息更新
    experiment_completed = Signal()  # 实验完成
    experiment_started = Signal()  # 实验开始
    experiment_stopped = Signal()  # 实验停止
    experiment_time_updated = Signal(str)  # 实验计时更新，格式："00:01:23"
    stage_info_updated = Signal(dict)  # 阶段信息更新，包含详细信息

    def __init__(self, device_manager=None, data_handler=None, parent=None):
        """
        初始化实验控制器
        
        Args:
            device_manager: 设备管理器
            data_handler: 数据处理器
            parent: 父对象
        """
        super().__init__(parent)
        
        # 日志
        self.logger = logging.getLogger(__name__)
        
        # 集中式状态机 —— 唯一数据源
        self._sm = ExperimentStateMachine(self)
        
        # 设备管理器
        self.device_manager = device_manager
        
        # 数据处理器
        self.data_handler = data_handler
        
        # 初始化数据库（通过依赖注入支持）
        self._exp_db = None
        
        # 实验相关变量
        self.current_experiment = None
        self.experiment_params = {}
        
        # 初始化实验模式管理器（使用增强版本）
        self.experiment_mode_manager = EnhancedExperimentModeManager()
        self.experiment_type_manager = ExperimentTypeManager()
        self.current_experiment_type = None
        self.current_experiment_type_name = None
        
        # 初始化定时器
        self._init_timers()

        # UI 交互回调（由 UI 层注入，避免在控制器中直接依赖 UI）
        self._confirm_callback: Optional[Callable[[str, str, bool], bool]] = None
        self._input_double_callback: Optional[
            Callable[[str, str, float, float, float, int], Tuple[float, bool]]
        ] = None

    @property
    def exp_db(self):
        """延迟初始化数据库连接"""
        if self._exp_db is None:
            self._exp_db = ExperimentDatabase()
        return self._exp_db

    @exp_db.setter
    def exp_db(self, value):
        """支持依赖注入设置数据库实例"""
        self._exp_db = value

    @property
    def state_machine(self) -> ExperimentStateMachine:
        """暴露状态机供外部（如 DataHandler、Runtime）订阅"""
        return self._sm

    @property
    def initial_weight(self) -> float:
        """从状态机获取初始重量"""
        return self._sm.get_state().initial_weight

    @initial_weight.setter
    def initial_weight(self, value: float):
        """通过状态机更新初始重量（线程安全）"""
        self._sm.update_state_silent(initial_weight=value)

    def set_interaction_callbacks(
        self,
        confirm_callback: Optional[Callable[[str, str, bool], bool]] = None,
        input_double_callback: Optional[
            Callable[[str, str, float, float, float, int], Tuple[float, bool]]
        ] = None,
    ) -> None:
        """注入 UI 交互回调，避免在控制器中直接依赖 UI。"""
        self._confirm_callback = confirm_callback
        self._input_double_callback = input_double_callback
    
    def set_data_handler(self, data_handler):
        """设置数据处理器"""
        self.data_handler = data_handler
    
    def _init_timers(self) -> None:
        """初始化定时器"""
        # 实验阶段定时器
        self.stage_timer = QTimer(self)
        self.stage_timer.timeout.connect(self.update_experiment_stage)
        
        # 实验运行时长定时器
        self.experiment_duration_updater = QTimer(self)
        self.experiment_duration_updater.timeout.connect(
            self._update_experiment_time_internal
        )

    def cleanup(self) -> None:
        """清理资源，断开信号连接，停止定时器"""
        try:
            # 停止定时器
            if self.stage_timer.isActive():
                self.stage_timer.stop()
            if self.experiment_duration_updater.isActive():
                self.experiment_duration_updater.stop()

            # 断开定时器信号连接
            try:
                self.stage_timer.timeout.disconnect(self.update_experiment_stage)
            except (RuntimeError, TypeError):
                pass
            try:
                self.experiment_duration_updater.timeout.disconnect(
                    self._update_experiment_time_internal
                )
            except (RuntimeError, TypeError):
                pass

            self.logger.debug("ExperimentController 资源已清理")
        except Exception as e:
            self.logger.error(f"ExperimentController 清理失败: {e}")
    
    def check_experiment_params(self) -> bool:
        """
        检查实验参数是否已设置
        
        Returns:
            bool: 参数是否有效
        """
        try:
            # 从实验设置配置文件读取
            config_path = PathManager.get_config_path("exp_settings.config")
            if not os.path.exists(config_path):
                return False

            # 读取JSON配置文件
            with open(config_path, 'r', encoding='utf-8') as f:
                params = json.load(f)

            if not params:
                return False

            # 检查必要参数
            required_fields = {
                "sample_id": "name",
                "sample_name": "sample_name",
                "sample_weight": "sample_weight",
                "notes": "description",
                "operator": "operator",
                "experiment_type": "experiment_type"
            }

            # 转换参数
            self.experiment_params = {}
            missing_fields = []

            for config_key, param_key in required_fields.items():
                if config_key not in params:
                    missing_fields.append(config_key)
                    continue

                value = params[config_key]

                # 特殊处理样品重量（确保是浮点数）
                if config_key == "sample_weight":
                    try:
                        value = float(value)
                        if value <= 0:
                            return False
                    except (ValueError, TypeError):
                        return False
                elif not str(value).strip():  # 检查其他字段是否为空
                    missing_fields.append(config_key)
                    continue

                self.experiment_params[param_key] = value

            if missing_fields:
                return False

            # 保存其他可能有用的参数
            self.experiment_params["project_name"] = params.get("project_name", "")
            self.experiment_params["date"] = params.get("date", "")

            # 设置初始重量
            self.initial_weight = self.experiment_params["sample_weight"]

            return True

        except (json.JSONDecodeError, Exception) as e:
            self.logger.error(f"加载实验参数失败: {str(e)}")
            return False
    
    def set_experiment_mode(self, experiment_type: ExperimentType) -> bool:
        """
        设置实验模式
        
        Args:
            experiment_type: 实验类型
            
        Returns:
            bool: 设置是否成功
        """
        if self.experiment_mode_manager.set_experiment_mode(experiment_type):
            self.current_experiment_type = experiment_type
            self.current_experiment_type_name = experiment_type.value
            self.logger.info(f"设置实验模式: {experiment_type.value}")
            return True
        return False
    
    def set_experiment_mode_by_id(self, mode_id: str) -> bool:
        """
        根据模式ID设置实验模式（支持自定义模式）
        
        Args:
            mode_id: 模式ID
            
        Returns:
            bool: 设置是否成功
        """
        try:
            # 导入ExperimentType（在函数开始就导入，避免作用域问题）
            from src.services.experiment_modes import ExperimentType
            
            # 获取类型信息
            type_info = self.experiment_type_manager.get_type_by_id(mode_id)
            if not type_info:
                self.logger.error(f"未找到实验类型: {mode_id}")
                return False
            
            # 标准模式使用原有的设置方法
            if self.experiment_type_manager.is_standard_type(mode_id):
                mode_mapping = {
                    "GB_13241_2017": ExperimentType.REDUCIBILITY,
                    "GB_13242_2017": ExperimentType.LOW_TEMP_DEGRADATION,
                    "GB_13240_2018": ExperimentType.FREE_SWELLING
                }
                
                if mode_id in mode_mapping:
                    return self.set_experiment_mode(mode_mapping[mode_id])
                else:
                    self.logger.error(f"标准模式ID映射失败: {mode_id}")
                    return False
            
            # 自定义模式
            elif self.experiment_type_manager.is_custom_type(mode_id):
                # 使用增强的实验模式管理器设置自定义实验
                if self.experiment_mode_manager.set_custom_experiment_mode(mode_id):
                    self.current_experiment_type = None  # 自定义模式不使用标准枚举
                    self.current_experiment_type_name = type_info.name
                    self.logger.info(f"设置自定义实验模式: {type_info.name}")
                    return True
                else:
                    self.logger.error(f"设置自定义实验模式失败: {mode_id}")
                    return False
            
            else:
                self.logger.error(f"未知的实验类型: {mode_id}")
                return False
                
        except Exception as e:
            self.logger.error(f"设置实验模式失败: {str(e)}")
            return False
    
    def _check_device_availability(self) -> dict:
        """
        检查设备可用性
        
        Returns:
            dict: 包含设备状态信息的字典
        """
        status = {
            'has_any_device': False,
            'available_devices': [],
            'missing_devices': [],
            'has_mfc': False,
            'has_balance': False,
            'has_temperature': False
        }
        
        if not self.device_manager:
            status['missing_devices'] = ['设备管理器未初始化']
            return status
        
        try:
            # 检查MFC设备
            if (hasattr(self.device_manager, 'multi_mfc') and 
                self.device_manager.multi_mfc and 
                hasattr(self.device_manager.multi_mfc, 'serial_port_available') and
                self.device_manager.multi_mfc.serial_port_available):
                status['has_mfc'] = True
                status['available_devices'].append('质量流量计')
            else:
                status['missing_devices'].append('质量流量计')
            
            # 检查天平设备
            if (hasattr(self.device_manager, 'balance') and 
                self.device_manager.balance and 
                hasattr(self.device_manager.balance, 'serial_port_available') and
                self.device_manager.balance.serial_port_available):
                status['has_balance'] = True
                status['available_devices'].append('电子天平')
            else:
                status['missing_devices'].append('电子天平')
            
            # 检查温控设备
            if (hasattr(self.device_manager, 'temp') and 
                self.device_manager.temp and 
                hasattr(self.device_manager.temp, 'serial_port_available') and
                self.device_manager.temp.serial_port_available):
                status['has_temperature'] = True
                status['available_devices'].append('温度控制器')
            else:
                status['missing_devices'].append('温度控制器')
            
            # 至少有一个设备可用才认为系统可以运行
            status['has_any_device'] = len(status['available_devices']) > 0
            
        except Exception as e:
            self.logger.error(f"检查设备状态时发生错误: {e}")
            status['missing_devices'].append('设备状态检查失败')
        
        return status

    def _create_experiment_record(
        self, experiment_record: ExperimentData | None = None
    ) -> ExperimentData:
        """创建实验数据记录（提取公共逻辑）"""
        experiment = experiment_record or ExperimentData(
            experiment_id=str(uuid.uuid4()),
            experiment_name=self.experiment_params["name"],
            sample_name=self.experiment_params["sample_name"],
            sample_weight=self.experiment_params["sample_weight"],
            start_time=datetime.now().isoformat(),
            description=self.experiment_params["description"],
            operator=self.experiment_params.get("operator", ""),
            experiment_type=self.experiment_params.get("experiment_type", "")
        )
        if not self.exp_db.create_experiment(experiment):
            raise Exception("创建实验记录失败")
        return experiment

    def _begin_experiment_common(self) -> None:
        """实验启动的公共逻辑（提取自 start_experiment 和 _dev_start_experiment）"""
        now = time.time()
        self._sm.transition_to(
            ExperimentPhase.RUNNING,
            experiment_id=self.current_experiment.experiment_id,
            experiment_type_name=self.current_experiment_type_name or "",
            initial_weight=self.initial_weight,
            experiment_start_time=now,
            stage_start_time=now,
            elapsed_seconds=0,
            current_stage_index=0,
            total_stages=len(self.experiment_mode_manager.get_experiment_stages()),
        )

        # 启动实验计时器
        self.experiment_duration_updater.start(1000)

        # 启动阶段定时器
        self.stage_timer.start(1000)  # 每秒检查一次

        # 执行第一个阶段
        self.execute_current_experiment_stage()

    def _get_experiment_display_name(self) -> str:
        """获取实验显示名称（提取公共逻辑）"""
        if self.current_experiment_type:
            return (self.current_experiment_type.value.split(' ')[0]
                    if ' ' in self.current_experiment_type.value
                    else self.current_experiment_type.value)
        return self.current_experiment_type_name or "未知实验"

    def _finish_experiment_common(self, status_prefix: str, system_message: str,
                                   via_phase: ExperimentPhase = ExperimentPhase.STOPPING) -> None:
        """实验结束的公共逻辑（提取自 stop_experiment 和 complete_experiment）"""
        # 先转入中间阶段（STOPPING 或 COMPLETING）
        try:
            self._sm.transition_to(via_phase)
        except InvalidTransitionError:
            pass  # 可能已经处于目标阶段

        # 停止定时器
        self.stage_timer.stop()
        self.experiment_duration_updater.stop()

        # 更新数据库中的实验结束时间
        if self.current_experiment:
            end_time = datetime.now().isoformat()
            self.exp_db.update_experiment(self.current_experiment.experiment_id, end_time)
            self.current_experiment.end_time = end_time
            self.logger.info(f"实验结束，已更新结束时间: {end_time}")

        # 切换到安全的N2气氛
        self._set_safety_atmosphere()

        # 转入 IDLE
        try:
            self._sm.transition_to(ExperimentPhase.IDLE)
        except InvalidTransitionError:
            self._sm.reset()  # 异常兜底：强制重置

        # 发送信号
        exp_name = self._get_experiment_display_name()
        self.status_updated.emit(f"{status_prefix}-{exp_name}")
        self.system_message_updated.emit(system_message)

    def start_experiment(self, experiment_record: ExperimentData | None = None) -> bool:
        """
        开始自动实验
        
        Returns:
            bool: 启动是否成功
        """
        # 检查前提条件
        if not self.check_experiment_params():
            self.logger.warning("实验参数未设置或不完整")
            return False
            
        # 检查实验模式是否已选择（标准实验或自定义实验）
        if not self.current_experiment_type and not self.experiment_mode_manager.is_custom_mode():
            self.logger.warning("实验模式未选择")
            return False
        
        if self._sm.is_running:
            self.logger.warning("实验已在运行中")
            return False
        
        try:
            # 转入 CONFIGURING 阶段
            self._sm.transition_to(ExperimentPhase.CONFIGURING)

            # 创建实验数据对象
            self.current_experiment = self._create_experiment_record(experiment_record)
            self.experiment_mode_manager.current_stage_index = 0

            # 执行公共启动逻辑（内部会转到 RUNNING）
            self._begin_experiment_common()
            
            # 发送信号
            exp_name = self._get_experiment_display_name()
            self.status_updated.emit(f"实验运行中-{exp_name}")
            self.system_message_updated.emit(
                f"开始实验: {self.experiment_params['sample_name']}"
            )
            self.experiment_started.emit()
            
            # 记录实验信息
            if self.current_experiment_type:
                self.logger.info(f"开始实验: {self.current_experiment_type.value}")
            else:
                self.logger.info(f"开始自定义实验: {self.current_experiment_type_name}")
            self.logger.info(f"实验ID: {self.current_experiment.experiment_id}")
            
            return True
            
        except InvalidTransitionError as e:
            self.logger.error(f"启动实验失败（状态转换错误）: {e}")
            return False
        except Exception as e:
            self.logger.error(f"启动实验失败: {str(e)}")
            # 出错后尝试回到 IDLE
            try:
                self._sm.transition_to(ExperimentPhase.IDLE)
            except InvalidTransitionError:
                self._sm.reset()
            return False

    def _dev_start_experiment(self) -> bool:
        """开发模式：启动实验，模拟正式实验流程"""
        try:
            # 转入 CONFIGURING 阶段
            self._sm.transition_to(ExperimentPhase.CONFIGURING)

            # 创建实验数据对象
            self.current_experiment = self._create_experiment_record()

            # 执行公共启动逻辑（内部会转到 RUNNING）
            self._begin_experiment_common()

            self.logger.info(f"==============================================实验类型: {self.current_experiment_type}")
            
            self.status_updated.emit(f"实验运行中-{self.current_experiment_type_name}")
            self.system_message_updated.emit(
                f"开始实验: {self.experiment_params['sample_name']}"
            )
            self.experiment_started.emit()
            
            # 记录实验信息
            if self.current_experiment_type:
                self.logger.info(f"开始实验: {self.current_experiment_type.value}")
            else:
                self.logger.info(f"开始自定义实验: {self.current_experiment_type_name}")
            self.logger.info(f"实验ID: {self.current_experiment.experiment_id}")
            return True
        except Exception as e:
            self.logger.error(f"启动实验失败: {str(e)}")
            try:
                self._sm.transition_to(ExperimentPhase.IDLE)
            except InvalidTransitionError:
                self._sm.reset()
            return False
    
    def stop_experiment(self) -> bool:
        """停止自动实验"""
        if not self._sm.is_running:
            return False

        self._finish_experiment_common(
            "实验已停止", "用户手动停止实验",
            via_phase=ExperimentPhase.STOPPING,
        )
        self.experiment_stopped.emit()
        self.logger.info("实验已停止")
        return True
    
    def execute_current_experiment_stage(self) -> None:
        """执行当前实验阶段"""
        if not self._sm.is_running:
            return
        
        current_stage = self.experiment_mode_manager.get_current_stage_settings()
        if not current_stage:
            # 实验完成
            self.complete_experiment()
            return
        
        # 设置气体流量
        gas_flows = self.experiment_mode_manager.get_gas_flow_for_mfc(
            current_stage.gas_settings
        )
        if self.device_manager:
            # 获取设备连接状态用于判断是否为开发模式
            connection_status = self.device_manager.get_connection_status()
            is_connected = connection_status[0] if connection_status else False
            
            for gas, flow in gas_flows.items():
                result = self.device_manager.set_flow(gas, flow)
                if not result and not is_connected:
                    self.logger.info(f"开发模式：跳过 {gas} 流量设置 ({flow:.1f}L/min)")
                elif not result:
                    self.logger.warning(f"流量设置失败：{gas} -> {flow:.1f}L/min")
        
        # 更新状态显示
        stage_name = f"{current_stage.stage.value}-{current_stage.description}"
        self.status_updated.emit(f"实验运行中-{stage_name}")
        
        gas_info = ", ".join([
            f"{gas}:{flow:.1f}L/min" 
            for gas, flow in gas_flows.items() if flow > 0
        ])
        self.system_message_updated.emit(
            f"执行阶段: {current_stage.description}, 气体: {gas_info}"
        )
        
        self.logger.info(f"执行阶段: {current_stage.description}")
        self.logger.info(f"气体设置: {gas_flows}")
        
        # 通过状态机更新阶段开始时间和阶段索引
        self._sm.update_state_silent(
            stage_start_time=time.time(),
            current_stage_index=self.experiment_mode_manager.current_stage_index,
            total_stages=len(self.experiment_mode_manager.get_experiment_stages()),
        )
    
    def get_sample_temperature(self) -> float:
        """
        获取样品温度（T8）
        
        Returns:
            float: 样品温度值，如果无法获取则返回0.0
        """
        try:
            if self.device_manager:
                # 从设备管理器获取温度数据
                status = self.device_manager.get_status()
                frames = status.get("frames") or {}
                temp_frame = frames.get("temperature")
                if temp_frame:
                    temps = getattr(temp_frame, "payload", {}).get("temperatures", {}) or {}
                    t8_temp = temps.get("T8")
                    if t8_temp is not None and isinstance(t8_temp, (int, float)):
                        return float(t8_temp)
            
            # 如果设备管理器不可用，尝试从数据处理器获取
            if self.data_handler and hasattr(self.data_handler, 'get_latest_temperature'):
                temp_data = self.data_handler.get_latest_temperature()
                if temp_data and "T8" in temp_data:
                    t8_temp = temp_data["T8"]
                    if t8_temp is not None and isinstance(t8_temp, (int, float)):
                        return float(t8_temp)
                        
        except Exception as e:
            self.logger.warning(f"获取样品温度T8失败: {str(e)}")
        
        return 0.0
    
    def update_experiment_stage(self) -> None:
        """
        更新实验阶段状态
        每秒更新一次
        """
        if not self._sm.is_running:
            return
        
        current_stage = self.experiment_mode_manager.get_current_stage_settings()
        if not current_stage:
            self.logger.info("实验阶段为空")
            return
        
        # 获取当前样品温度（T8）
        current_temp = self.get_sample_temperature()
        
        # 从状态机获取阶段开始时间（线程安全）
        state = self._sm.get_state()
        elapsed_time = time.time() - state.stage_start_time
        
        # 发送详细的阶段信息更新信号
        self._emit_stage_info_update(current_stage, current_temp, elapsed_time)
        
        # 检查是否可以进入下一阶段
        self.logger.debug(f"当前温度: {current_temp:.1f}°C (目标: {current_stage.target_temp}±{current_stage.temp_tolerance}°C)")
        self.logger.debug(f"经过时间: {elapsed_time/60:.1f}min (要求: {current_stage.duration}min)")
        
        if self.experiment_mode_manager.can_advance_stage(current_temp, elapsed_time):
            # 进入下一阶段
            next_stage = self.experiment_mode_manager.advance_to_next_stage()
            if next_stage:
                self.logger.info(f"阶段切换: 温度{current_temp:.1f}°C，时间{elapsed_time/60:.1f}min，进入下一阶段")
                self.execute_current_experiment_stage()
            else:
                # 实验完成
                self.logger.info(f"实验完成: 温度{current_temp:.1f}°C，总时间{elapsed_time/60:.1f}min")
                self.complete_experiment()
    
    def complete_experiment(self) -> None:
        """完成实验"""
        self._finish_experiment_common(
            "实验完成", "实验自动完成，已切换到N₂保护",
            via_phase=ExperimentPhase.COMPLETING,
        )
        self.experiment_completed.emit()
        self.logger.info("实验已完成")
    
    def control_gas_flow(self, gas_name: str, flow_value: float) -> bool:
        """
        控制气体流量
        
        Args:
            gas_name: 气体名称
            flow_value: 流量值 (L/min)
            
        Returns:
            bool: 控制是否成功
        """
        try:
            # 直接传递流量值，不需要额外缩放
            # MultiMFCClient.set_sp_value 会自动处理设备通信协议所需的缩放
            if self.device_manager:
                success = self.device_manager.set_flow(gas_name, flow_value)
                if success:
                    self.system_message_updated.emit(
                        f"手动设置{gas_name}流量: {flow_value:.2f}L/min"
                    )
                    self.logger.info(f"成功设置{gas_name}流量: {flow_value:.2f}L/min")
                    return True
                else:
                    self.system_message_updated.emit(
                        f"设置{gas_name}流量失败"
                    )
                    self.logger.error(f"设置{gas_name}流量失败")
                    return False
            else:
                self.logger.error("设备管理器未初始化，无法控制气体流量")
                self.system_message_updated.emit("设备管理器未初始化")
                return False

        except Exception as e:
            self.logger.error(f"设置{gas_name}流量失败: {str(e)}")
            self.system_message_updated.emit(f"错误: 设置{gas_name}流量失败 - {str(e)}")
            return False
    
    def tare_balance(self, parent_widget=None, skip_confirmation=False) -> bool:
        """
        天平清零（带确认对话框）
        
        Args:
            parent_widget: 父窗口，用于显示确认对话框
            skip_confirmation: 是否跳过确认对话框（用于在设置初始重量流程中自动去皮）
        
        Returns:
            bool: 清零是否成功
        """
        try:
            # 如果不跳过确认，先显示确认对话框
            if not skip_confirmation:
                if not self._confirm_callback:
                    self.logger.warning("未设置 UI 确认回调，无法执行天平去皮")
                    self.system_message_updated.emit("缺少 UI 确认回调，无法执行天平去皮")
                    return False

                confirmed = self._confirm_callback(
                    "确认天平去皮",
                    "确定要执行天平去皮操作吗？\n\n去皮后天平读数将归零，当前重量值将丢失。",
                    False,
                )

                if not confirmed:
                    self.logger.info("用户取消了天平去皮操作")
                    self.system_message_updated.emit("已取消天平去皮操作")
                    return False
            
            if self.device_manager:
                tare_success = self.device_manager.tare_balance()
                if not tare_success:
                    self.logger.warning("天平清零失败，设备未确认去皮命令")
                    self.system_message_updated.emit("天平清零失败，设备未确认去皮命令")
                    return False
                
                # 天平清零后，将初始重量设为0（因为天平已清零）
                self.set_initial_weight(0.0)
                    
                self.logger.info("天平清零成功，初始重量已设为0.0g")
                self.system_message_updated.emit("天平清零成功")
                return True
            else:
                self.logger.warning("未连接设备控制器，无法进行天平清零")
                self.system_message_updated.emit("警告: 设备未连接，无法进行天平清零")
                return False
        except Exception as e:
            self.logger.error(f"天平清零失败: {str(e)}")
            self.system_message_updated.emit(f"错误: 天平清零失败 - {str(e)}")
            return False
    
    def set_initial_weight(self, weight: float) -> None:
        """
        设置初始重量
        
        Args:
            weight: 重量值
        """
        self.initial_weight = weight
        self.logger.info(f"设置初始重量: {weight:.3f}g")
        
        # 同时将初始重量传递给数据处理器，用于失重计算
        if self.data_handler and hasattr(self.data_handler, 'set_initial_weight'):
            self.data_handler.set_initial_weight(weight)
            self.logger.info(f"已将初始重量 {weight:.3f}g 传递给数据处理器")
    
    def manual_set_initial_weight(self, parent_widget=None) -> bool:
        """
        手动设置初始重量 - 优化版本
        1. 先执行天平去皮
        2. 提示用户输入样品重量
        3. 将输入重量加到当前天平读数上
        4. 开始计算失重和失重率
        
        Args:
            parent_widget: 父窗口
            
        Returns:
            bool: 设置是否成功
        """
        try:
            # 第一步：执行天平去皮（跳过确认对话框，因为这是设置初始重量流程的一部分）
            self.system_message_updated.emit("正在执行天平去皮...")
            tare_success = self.tare_balance(parent_widget, skip_confirmation=True)
            
            if not tare_success:
                self.system_message_updated.emit("天平去皮失败，无法设置初始重量")
                return False
                
            # 让事件循环处理待处理事件，使天平读数稳定
            QCoreApplication.processEvents()
            
            # 第二步：获取当前天平读数（去皮后应该接近0）
            current_balance_weight = 0.0
            if self.device_manager and hasattr(self.device_manager, 'balance'):
                try:
                    current_balance_weight = self.device_manager.balance.get_current_weight() or 0.0
                except Exception as e:
                    self.logger.warning(f"获取天平读数失败: {str(e)}")
                    current_balance_weight = 0.0
            
            # 第三步：提示用户输入样品重量
            if not self._input_double_callback:
                self.logger.warning("未设置 UI 输入回调，无法获取样品重量")
                self.system_message_updated.emit("缺少 UI 输入回调，无法获取样品重量")
                return False

            sample_weight, ok = self._input_double_callback(
                "设置样品初始重量",
                f"天平已完成去皮操作\n当前天平读数: {current_balance_weight:.3f}g\n\n请输入样品的初始重量(g):",
                0.0,
                0.0,
                10000.0,
                3,
            )
            
            if not ok:
                self.system_message_updated.emit("用户取消了样品重量输入")
                return False
                
            # 第四步：计算总的初始重量（当前天平读数 + 样品重量）
            total_initial_weight = current_balance_weight + sample_weight
            
            # 设置初始重量
            self.set_initial_weight(total_initial_weight)
            
            # 发送成功消息
            success_msg = f"初始重量设置成功！\n天平读数: {current_balance_weight:.3f}g\n样品重量: {sample_weight:.3f}g\n总初始重量: {total_initial_weight:.3f}g"
            self.system_message_updated.emit(success_msg)
            self.logger.info(f"手动设置初始重量成功 - 天平读数: {current_balance_weight:.3f}g, 样品重量: {sample_weight:.3f}g, 总重量: {total_initial_weight:.3f}g")
            
            return True
            
        except Exception as e:
            error_msg = f"设置初始重量过程中发生错误：{str(e)}"
            self.system_message_updated.emit(error_msg)
            self.logger.error(error_msg)
            return False
    
    def _set_safety_atmosphere(self) -> None:
        """设置安全气氛"""
        if self.device_manager:
            self.device_manager.set_flow('N2', self.SAFETY_N2_FLOW_LPM)
            self.device_manager.set_flow('CO', 0.0)
            self.device_manager.set_flow('CO2', 0.0)
            self.device_manager.set_flow('H2', 0.0)
    
    def _update_experiment_time_internal(self) -> None:
        """内部实验时间更新"""
        state = self._sm.get_state()
        new_elapsed = state.elapsed_seconds + 1
        self._sm.update_state_silent(elapsed_seconds=new_elapsed)
        
        # 发送计时更新信号
        time_str = self.get_experiment_duration_string()
        self.experiment_time_updated.emit(time_str)

    def _dev_get_experiment_realtime_data(self) -> dict:
        """开发模式：获取实验实时数据"""
        return {
            "experiment_id": self.current_experiment.experiment_id,
            "experiment_name": self.current_experiment.experiment_name,
            "sample_name": self.experiment_params['sample_name'],
        }
    
    def get_experiment_duration_string(self) -> str:
        """
        获取实验用时字符串
        
        Returns:
            str: 实验用时
        """
        elapsed = self._sm.get_state().elapsed_seconds
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def get_current_experiment_stage_name(self) -> str:
        """
        获取当前实验阶段名称
        
        Returns:
            str: 阶段名称
        """
        if not self._sm.is_running or not self.current_experiment_type:
            return "无实验"
        
        current_stage = self.experiment_mode_manager.get_current_stage_settings()
        if current_stage:
            return f"{current_stage.stage.value}-{current_stage.description}"
        else:
            return "实验完成"
    
    def is_experiment_running(self) -> bool:
        """
        检查实验是否运行中
        
        Returns:
            bool: 是否运行中
        """
        return self._sm.is_running
    
    def get_initial_weight(self) -> float:
        """
        获取初始重量
        
        Returns:
            float: 初始重量
        """
        return self._sm.get_state().initial_weight
    
    def get_current_experiment_type(self) -> Optional[ExperimentType]:
        """
        获取当前实验类型
        
        Returns:
            ExperimentType: 当前实验类型
        """
        return self.current_experiment_type
    
    def _emit_stage_info_update(self, current_stage, current_temp: float, elapsed_time: float) -> None:
        """
        发送详细的阶段信息更新信号
        
        Args:
            current_stage: 当前阶段设置
            current_temp: 当前温度
            elapsed_time: 经过时间（秒）
        """
        try:
            # 获取所有实验阶段
            all_stages = self.experiment_mode_manager.get_experiment_stages()
            stage_index = self.experiment_mode_manager.current_stage_index
            
            # 构建详细的阶段信息
            stage_info = {
                "current_stage_index": stage_index + 1,  # 从1开始计数
                "total_stages": len(all_stages),
                "stage_name": current_stage.stage.value,
                "stage_description": current_stage.description,
                "current_temp": current_temp,
                "target_temp": current_stage.target_temp,
                "temp_tolerance": current_stage.temp_tolerance,
                "elapsed_time_seconds": elapsed_time,
                "elapsed_time_minutes": elapsed_time / 60.0,
                "duration_minutes": current_stage.duration,
                "progress_percent": self._calculate_stage_progress(current_stage, current_temp, elapsed_time)
            }
            
            # 发送信号
            self.stage_info_updated.emit(stage_info)
            
        except Exception as e:
            self.logger.error(f"发送阶段信息更新失败: {str(e)}")
    
    def _calculate_stage_progress(self, stage, current_temp: float, elapsed_time: float) -> float:
        """
        计算阶段进度百分比
        
        Args:
            stage: 阶段设置
            current_temp: 当前温度
            elapsed_time: 经过时间（秒）
            
        Returns:
            float: 进度百分比 (0-100)
        """
        try:
            # 如果是固定时间阶段，基于时间计算进度
            if stage.duration > 0:
                time_progress = min(100.0, (elapsed_time / (stage.duration * 60)) * 100)
                return time_progress
            
            # 如果是温度阶段（升温或冷却），基于温度计算进度
            elif stage.heating_rate != 0:
                temp_diff = abs(stage.target_temp - self.AMBIENT_TEMP_CELSIUS)
                current_diff = abs(current_temp - self.AMBIENT_TEMP_CELSIUS)
                if temp_diff > 0:
                    temp_progress = min(100.0, (current_diff / temp_diff) * 100)
                    return temp_progress
            
            # 默认返回0
            return 0.0
            
        except Exception as e:
            self.logger.error(f"计算阶段进度失败: {str(e)}")
            return 0.0
    
    def get_detailed_stage_info(self) -> dict:
        """
        获取详细的阶段信息（用于初始化显示）
        
        Returns:
            dict: 详细阶段信息
        """
        try:
            state = self._sm.get_state()
            if not state.is_running:
                return {
                    "current_stage_index": 0,
                    "total_stages": 0,
                    "stage_name": "无实验",
                    "stage_description": "实验未开始",
                    "current_temp": 0.0,
                    "target_temp": 0.0,
                    "temp_tolerance": 0.0,
                    "elapsed_time_seconds": 0.0,
                    "elapsed_time_minutes": 0.0,
                    "duration_minutes": 0.0,
                    "progress_percent": 0.0
                }
            
            current_stage = self.experiment_mode_manager.get_current_stage_settings()
            if not current_stage:
                return self._get_default_stage_info()
            
            current_temp = self.get_sample_temperature()
            elapsed_time = time.time() - state.stage_start_time
            
            return {
                "current_stage_index": self.experiment_mode_manager.current_stage_index + 1,
                "total_stages": len(self.experiment_mode_manager.get_experiment_stages()),
                "stage_name": current_stage.stage.value,
                "stage_description": current_stage.description,
                "current_temp": current_temp,
                "target_temp": current_stage.target_temp,
                "temp_tolerance": current_stage.temp_tolerance,
                "elapsed_time_seconds": elapsed_time,
                "elapsed_time_minutes": elapsed_time / 60.0,
                "duration_minutes": current_stage.duration,
                "progress_percent": self._calculate_stage_progress(current_stage, current_temp, elapsed_time)
            }
            
        except Exception as e:
            self.logger.error(f"获取详细阶段信息失败: {str(e)}")
            return self._get_default_stage_info()
    
    def _get_default_stage_info(self) -> dict:
        """获取默认阶段信息"""
        return {
            "current_stage_index": 0,
            "total_stages": 0,
            "stage_name": "未知",
            "stage_description": "获取阶段信息失败",
            "current_temp": 0.0,
            "target_temp": 0.0,
            "temp_tolerance": 0.0,
            "elapsed_time_seconds": 0.0,
            "elapsed_time_minutes": 0.0,
            "duration_minutes": 0.0,
            "progress_percent": 0.0
        }
