"""
实验控制器模块
遵循PEP8规范，负责实验流程的控制和管理

注意：此模块从 src/ui/experiment/ 迁移至 src/controllers/，
以修复服务层反向依赖 UI 层的架构问题。
"""
import time
import json
import math
import os
import uuid
import logging
import math
from datetime import datetime
from typing import Optional, Callable, Tuple
from PySide6.QtCore import QObject, Signal, QTimer

from src.models.experiment_state import (
    ExperimentStateMachine,
    ExperimentPhase,
    InvalidTransitionError,
)
from src.services.experiment_modes import ExperimentType
from src.services.enhanced_experiment_modes import EnhancedExperimentModeManager
from src.services.experiment_type_manager import ExperimentTypeManager
from src.services.standard_modes import STANDARD_MODES
from src.services.database import ExperimentDatabase, ExperimentData
from src.utils.path_manager import PathManager
from src.utils.audit import audit, AuditCategory, AuditResult


class ExperimentController(QObject):
    """实验控制器类"""

    # 实验常量
    SAFETY_N2_FLOW_LPM = 5.0  # 安全气氛 N2 流量 (L/min)
    SAFETY_FLOW_MAX_ATTEMPTS = 3
    STAGE_FLOW_MAX_ATTEMPTS = 3
    TEMP_READ_FAILURE_ALERT_THRESHOLD = 3
    AMBIENT_TEMP_CELSIUS = 25.0  # 默认环境/起始温度 (°C)

    # 信号定义
    status_updated = Signal(str)  # 实验状态更新
    system_message_updated = Signal(str)  # 系统消息更新
    safety_alert = Signal(str)  # 需要人工处置的高可见气体安全告警
    experiment_completed = Signal()  # 实验完成
    experiment_started = Signal()  # 实验开始
    experiment_stopped = Signal()  # 实验停止
    experiment_time_updated = Signal(str)  # 实验计时更新，格式："00:01:23"
    stage_info_updated = Signal(dict)  # 阶段信息更新，包含详细信息

    def __init__(
        self,
        device_manager=None,
        data_handler=None,
        parent=None,
        experiment_mode_manager=None,
        experiment_type_manager=None,
    ):
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
        self.experiment_mode_manager = (
            experiment_mode_manager or EnhancedExperimentModeManager()
        )
        self.experiment_type_manager = (
            experiment_type_manager
            or ExperimentTypeManager(mode_manager=self.experiment_mode_manager)
        )
        self.current_experiment_type = None
        self.current_experiment_type_name = None
        self._last_safety_error = ""
        self._temperature_read_failures = 0
        self._temperature_fault_alerted = False
        self._initial_weight_source = None
        self._clock = time.monotonic
        self._manual_initial_weight_in_progress = False
        
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

    def _get_registered_device(self, name: str):
        """从设备注册表获取设备，并兼容尚未迁移的测试替身。"""
        if not self.device_manager:
            return None
        getter = getattr(self.device_manager, "get_device", None)
        if callable(getter):
            return getter(name)
        legacy_attributes = {
            "MFC": "multi_mfc",
            "Balance": "balance",
            "Temp": "temp",
        }
        return getattr(self.device_manager, legacy_attributes[name], None)
    
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

            # 备注为可选字段，允许为空，不应阻止实验启动
            optional_fields = {"notes"}

            # 转换参数
            self.experiment_params = {}
            missing_fields = []

            for config_key, param_key in required_fields.items():
                if config_key not in params:
                    if config_key in optional_fields:
                        self.experiment_params[param_key] = ""
                        continue
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
                elif config_key in optional_fields:
                    pass  # 可选字段允许为空
                elif not str(value).strip():  # 检查其他字段是否为空
                    missing_fields.append(config_key)
                    continue

                self.experiment_params[param_key] = value

            if missing_fields:
                return False

            # 保存其他可能有用的参数
            self.experiment_params["project_name"] = params.get("project_name", "")
            self.experiment_params["date"] = params.get("date", "")

            nominal_weight = self.experiment_params["sample_weight"]
            if self._initial_weight_source == "measured":
                self.logger.info(
                    f"保留实测初始重量 {self.initial_weight:.3f}g；"
                    f"表单名义重量为 {nominal_weight:.3f}g"
                )
            else:
                self.initial_weight = nominal_weight
                self._initial_weight_source = "nominal"

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
            audit(AuditCategory.EXPERIMENT, "set_mode", mode=experiment_type.value)
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
            # 获取类型信息
            type_info = self.experiment_type_manager.get_type_by_id(mode_id)
            if not type_info:
                self.logger.error(f"未找到实验类型: {mode_id}")
                return False
            
            # 标准模式使用原有的设置方法
            if self.experiment_type_manager.is_standard_type(mode_id):
                definition = STANDARD_MODES.get(mode_id)
                if definition is None:
                    self.logger.error(f"标准模式ID映射失败: {mode_id}")
                    return False
                return self.set_experiment_mode(definition.experiment_type)
            
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

    def _begin_experiment_common(self) -> bool:
        """执行经过校验的实验启动公共逻辑。"""
        self._temperature_read_failures = 0
        self._temperature_fault_alerted = False
        now = self._clock()
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
        return self.execute_current_experiment_stage()

    def _recover_failed_start(self, error: Exception) -> None:
        """Undo any partially-started runtime state after startup fails."""
        runtime_started = (
            self.stage_timer.isActive()
            or self.experiment_duration_updater.isActive()
            or self._sm.is_running
        )
        self.stage_timer.stop()
        self.experiment_duration_updater.stop()

        if runtime_started:
            try:
                self._set_safety_atmosphere()
            except Exception as safety_error:
                self.logger.error(f"启动失败后设置安全气氛失败: {safety_error}")

        phase = self._sm.phase
        try:
            if phase == ExperimentPhase.CONFIGURING:
                self._sm.transition_to(ExperimentPhase.IDLE)
            elif phase in (ExperimentPhase.RUNNING, ExperimentPhase.STAGE_TRANSITION):
                self._sm.transition_to(
                    ExperimentPhase.ERROR,
                    error_message=str(error),
                )
                self._sm.transition_to(ExperimentPhase.IDLE)
            elif phase in (
                ExperimentPhase.COMPLETING,
                ExperimentPhase.STOPPING,
                ExperimentPhase.ERROR,
            ):
                self._sm.transition_to(ExperimentPhase.IDLE)
        except InvalidTransitionError:
            self._sm.reset()

    def _get_experiment_display_name(self) -> str:
        """获取实验显示名称（提取公共逻辑）"""
        if self.current_experiment_type:
            return (self.current_experiment_type.value.split(' ')[0]
                    if ' ' in self.current_experiment_type.value
                    else self.current_experiment_type.value)
        return self.current_experiment_type_name or "未知实验"

    def _finish_experiment_common(self, status_prefix: str, system_message: str,
                                   via_phase: ExperimentPhase = ExperimentPhase.STOPPING) -> bool:
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
        safety_success = self._set_safety_atmosphere()

        # 转入 IDLE
        try:
            self._sm.transition_to(ExperimentPhase.IDLE)
        except InvalidTransitionError:
            self._sm.reset()  # 异常兜底：强制重置

        # 发送信号
        exp_name = self._get_experiment_display_name()
        self._initial_weight_source = None
        if safety_success:
            self.status_updated.emit(f"{status_prefix}-{exp_name}")
            self.system_message_updated.emit(system_message)
        else:
            # IDLE 状态变更会触发 UI 清理，因此在其后再次广播状态文本，
            # 确保高危告警不会被结束清理覆盖。
            self.status_updated.emit("危险：安全气氛设置失败")
            self.system_message_updated.emit(self._last_safety_error)
        return safety_success

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

        if not self.experiment_mode_manager.get_experiment_stages():
            self.logger.warning("实验模式没有可执行阶段")
            self.system_message_updated.emit("实验模式没有可执行阶段，无法启动实验")
            return False
        
        try:
            # 转入 CONFIGURING 阶段
            self._sm.transition_to(ExperimentPhase.CONFIGURING)

            # 创建实验数据对象
            self.current_experiment = self._create_experiment_record(experiment_record)
            self.experiment_mode_manager.current_stage_index = 0

            # 执行公共启动逻辑（内部会转到 RUNNING）
            if not self._begin_experiment_common():
                audit(
                    AuditCategory.EXPERIMENT,
                    "start",
                    result=AuditResult.FAILURE,
                    error="initial stage gas flow failed",
                )
                return False
            
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

            audit(
                AuditCategory.EXPERIMENT, "start",
                operator=self.experiment_params.get("operator"),
                experiment_id=self.current_experiment.experiment_id,
                sample_name=self.experiment_params.get("sample_name"),
                mode=self.current_experiment_type_name or (
                    self.current_experiment_type.value if self.current_experiment_type else None
                ),
            )

            return True

        except InvalidTransitionError as e:
            self.logger.error(f"启动实验失败（状态转换错误）: {e}")
            self._recover_failed_start(e)
            audit(AuditCategory.EXPERIMENT, "start", result=AuditResult.FAILURE, error=str(e))
            return False
        except Exception as e:
            self.logger.error(f"启动实验失败: {str(e)}")
            self._recover_failed_start(e)
            return False

    def stop_experiment(self) -> bool:
        """停止自动实验"""
        if not self._sm.is_running:
            return False

        safety_success = self._finish_experiment_common(
            "实验已停止", "用户手动停止实验，已切换到N₂保护",
            via_phase=ExperimentPhase.STOPPING,
        )
        self.experiment_stopped.emit()
        self.logger.info("实验已停止")
        audit(
            AuditCategory.EXPERIMENT, "stop",
            result=AuditResult.SUCCESS if safety_success else AuditResult.FAILURE,
            operator=self.experiment_params.get("operator") if self.experiment_params else None,
            experiment_id=getattr(self.current_experiment, "experiment_id", None),
        )
        return safety_success
    
    def execute_current_experiment_stage(self) -> bool:
        """执行当前实验阶段"""
        if not self._sm.is_running:
            return False
        
        current_stage = self.experiment_mode_manager.get_current_stage_settings()
        if not current_stage:
            # 实验完成
            self.complete_experiment()
            return True
        
        # 设置气体流量
        gas_flows = self.experiment_mode_manager.get_gas_flow_for_mfc(
            current_stage.gas_settings
        )
        if self.device_manager:
            # 获取设备连接状态用于判断是否为开发模式
            connection_status = self.device_manager.get_connection_status()
            is_connected = connection_status[0] if connection_status else False
            
            failed_gases = self._set_stage_gas_flows(gas_flows, is_connected)
            if failed_gases:
                return self._abort_stage_for_flow_failure(
                    current_stage,
                    failed_gases,
                )
        
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

        # 仅在阶段气氛全部确认后同步状态机；失败路径已中止实验。
        self._sm.update_state_silent(
            stage_start_time=self._clock(),
            current_stage_index=self.experiment_mode_manager.current_stage_index,
            total_stages=len(self.experiment_mode_manager.get_experiment_stages()),
        )
        return True

    def _set_stage_gas_flows(self, gas_flows: dict, is_connected: bool) -> list[str]:
        """Apply a stage atmosphere, retrying confirmed hardware failures."""
        failed_gases = []
        for gas, flow in gas_flows.items():
            attempts = self.STAGE_FLOW_MAX_ATTEMPTS if is_connected else 1
            success = False
            for attempt in range(1, attempts + 1):
                try:
                    success = bool(self.device_manager.set_flow(gas, flow))
                except Exception as exc:
                    self.logger.error(
                        f"阶段气体设定异常：{gas} -> {flow:.1f}L/min，"
                        f"第 {attempt} 次尝试：{exc}",
                        exc_info=True,
                    )
                    success = False
                if success:
                    break
                if is_connected:
                    self.logger.warning(
                        f"阶段气体设定失败：{gas} -> {flow:.1f}L/min，"
                        f"第 {attempt}/{attempts} 次尝试"
                    )

            if success:
                continue
            # 无论设备当前是否被判定为已连接，未确认的气体设定一律视为失败：
            # is_connected 来自设备实时健康状态，真实断线与开发环境无法区分，
            # 曾经的“开发模式跳过”会让实验带着错误气氛继续运行。
            failed_gases.append(gas)
        return failed_gases

    def _abort_stage_for_flow_failure(self, current_stage, failed_gases: list[str]) -> bool:
        failed_text = "、".join(failed_gases)
        alert_message = (
            f"阶段气体设定失败（阶段：{current_stage.description}；通道：{failed_text}），"
            "实验已中止。请检查气路与设备连接，确认安全气氛后再操作。"
        )
        self.logger.critical(alert_message)
        self.status_updated.emit("实验已中止-阶段气体设定失败")
        self.system_message_updated.emit(alert_message)
        self.safety_alert.emit(alert_message)
        safety_success = self._finish_experiment_common(
            "实验已中止",
            f"{alert_message} 已切换到N₂保护。",
            via_phase=ExperimentPhase.STOPPING,
        )
        self.experiment_stopped.emit()
        audit(
            AuditCategory.GAS,
            "stage_flow",
            result=AuditResult.FAILURE,
            operator=self.experiment_params.get("operator") if self.experiment_params else None,
            experiment_id=getattr(self.current_experiment, "experiment_id", None),
            stage=getattr(current_stage, "description", ""),
            failed_gases=failed_gases,
            safety_atmosphere=safety_success,
        )
        return False
    
    def get_sample_temperature(self) -> Optional[float]:
        """
        获取样品温度（T8）
        
        Returns:
            float | None: 有效样品温度；无读数或非有限值时返回 None
        """
        if self.device_manager:
            try:
                # 从设备管理器获取温度数据
                status = self.device_manager.get_status()
                frames = (status or {}).get("frames") or {}
                temp_frame = frames.get("temperature")
                if temp_frame:
                    temps = getattr(temp_frame, "payload", {}).get("temperatures", {}) or {}
                    temperature = self._finite_temperature(temps.get("T8"))
                    if temperature is not None:
                        return temperature
            except Exception as e:
                self.logger.warning(f"从设备管理器获取样品温度T8失败: {e}")

        try:
            # 如果设备管理器不可用，尝试从数据处理器获取
            if self.data_handler and hasattr(self.data_handler, 'get_latest_temperature'):
                temp_data = self.data_handler.get_latest_temperature()
                if temp_data and "T8" in temp_data:
                    temperature = self._finite_temperature(temp_data["T8"])
                    if temperature is not None:
                        return temperature
        except Exception as e:
            self.logger.warning(f"从数据处理器获取样品温度T8失败: {e}")

        return None

    @staticmethod
    def _finite_temperature(value) -> Optional[float]:
        try:
            temperature = float(value)
        except (TypeError, ValueError):
            return None
        return temperature if math.isfinite(temperature) else None
    
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
        if current_temp is None:
            self._handle_temperature_read_failure()
            return
        self._reset_temperature_read_failure()
        
        # 从状态机获取阶段开始时间（线程安全）
        state = self._sm.get_state()
        elapsed_time = max(0.0, self._clock() - state.stage_start_time)
        
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

    def _handle_temperature_read_failure(self) -> None:
        self._temperature_read_failures += 1
        self.logger.warning(
            "样品温度T8读取失败，暂停本次阶段判定 "
            f"({self._temperature_read_failures}/"
            f"{self.TEMP_READ_FAILURE_ALERT_THRESHOLD})"
        )
        if (
            self._temperature_read_failures < self.TEMP_READ_FAILURE_ALERT_THRESHOLD
            or self._temperature_fault_alerted
        ):
            return

        self._temperature_fault_alerted = True
        message = (
            f"样品温度T8已连续 {self._temperature_read_failures} 次读取失败，"
            "阶段判定已暂停。请立即检查温控仪表、串口与传感器连接。"
        )
        self.logger.critical(message)
        self.status_updated.emit("危险：样品温度读取失败")
        self.system_message_updated.emit(message)
        self.safety_alert.emit(message)

    def _reset_temperature_read_failure(self) -> None:
        if self._temperature_read_failures and self._temperature_fault_alerted:
            self.logger.info("样品温度T8读取已恢复，继续阶段判定")
            self.system_message_updated.emit("样品温度读取已恢复，继续阶段判定")
        self._temperature_read_failures = 0
        self._temperature_fault_alerted = False

    def get_stage_realignment_context(self) -> Optional[dict]:
        """返回当前阶段时钟和可安全执行的人工校正操作。

        直接从控制器实时状态计算，不依赖 UI 缓存，避免恢复操作作用于过期阶段。
        """
        state = self._sm.get_state()
        if state.phase != ExperimentPhase.RUNNING:
            return None

        current_stage = self.experiment_mode_manager.get_current_stage_settings()
        stages = self.experiment_mode_manager.get_experiment_stages()
        stage_index = self.experiment_mode_manager.current_stage_index
        if current_stage is None or not 0 <= stage_index < len(stages):
            return None

        elapsed_seconds = max(0.0, self._clock() - state.stage_start_time)
        duration_minutes = float(current_stage.duration)
        return {
            "current_stage_index": stage_index + 1,
            "total_stages": len(stages),
            "stage_description": current_stage.description,
            "elapsed_minutes": elapsed_seconds / 60.0,
            "duration_minutes": duration_minutes,
            "can_skip": stage_index < len(stages) - 1,
            "can_adjust_elapsed": duration_minutes > 0,
        }

    def _reject_stage_realignment(self, action: str, reason: str, **fields) -> bool:
        """报告并审计被拒绝的人工阶段校正。"""
        self.logger.warning(reason)
        self.system_message_updated.emit(reason)
        audit(
            AuditCategory.EXPERIMENT,
            action,
            result=AuditResult.REJECTED,
            operator=self.experiment_params.get("operator") if self.experiment_params else None,
            experiment_id=getattr(self.current_experiment, "experiment_id", None),
            reason=reason,
            **fields,
        )
        return False

    def skip_to_next_stage(self) -> bool:
        """经明确确认后，人工进入下一个配置阶段。

        最后阶段不可跳过，否则会绕过数据库收尾和保护气氛设置；应继续使用正常的
        完成或停止路径。
        """
        context = self.get_stage_realignment_context()
        if context is None:
            return self._reject_stage_realignment(
                "skip_stage", "仅可在实验稳定运行时校正阶段"
            )
        if not context["can_skip"]:
            return self._reject_stage_realignment(
                "skip_stage",
                "当前已是最后阶段，不能跳过；请使用停止实验完成安全收尾",
                stage_index=context["current_stage_index"],
            )
        if self._confirm_callback is None:
            return self._reject_stage_realignment(
                "skip_stage", "缺少操作确认回调，已拒绝阶段跳转"
            )

        stages = self.experiment_mode_manager.get_experiment_stages()
        from_index = self.experiment_mode_manager.current_stage_index
        from_stage = stages[from_index]
        to_stage = stages[from_index + 1]
        confirmed = self._confirm_callback(
            "确认跳过当前阶段",
            (
                f"即将从第 {from_index + 1} 阶段“{from_stage.description}”\n"
                f"切换到第 {from_index + 2} 阶段“{to_stage.description}”。\n\n"
                "系统将立即应用下一阶段的气体设定。此操作不可撤销，是否继续？"
            ),
            False,
        )
        if not confirmed:
            return self._reject_stage_realignment(
                "skip_stage",
                "用户取消阶段跳转",
                stage_index=from_index + 1,
            )

        latest_context = self.get_stage_realignment_context()
        if (
            latest_context is None
            or latest_context["current_stage_index"] != from_index + 1
        ):
            return self._reject_stage_realignment(
                "skip_stage",
                "确认期间实验阶段已变化，已拒绝过期的阶段跳转",
                requested_from_stage_index=from_index + 1,
                current_stage_index=(
                    latest_context["current_stage_index"] if latest_context else None
                ),
            )

        next_stage = self.experiment_mode_manager.advance_to_next_stage()
        if next_stage is None:
            return self._reject_stage_realignment(
                "skip_stage", "下一阶段不存在，阶段跳转已取消"
            )

        stage_applied = self.execute_current_experiment_stage()
        if stage_applied is False:
            self.logger.error("阶段已选择，但下一阶段设备设定未成功应用")
            audit(
                AuditCategory.EXPERIMENT,
                "skip_stage",
                result=AuditResult.FAILURE,
                operator=(
                    self.experiment_params.get("operator")
                    if self.experiment_params else None
                ),
                experiment_id=getattr(self.current_experiment, "experiment_id", None),
                from_stage_index=from_index + 1,
                to_stage_index=from_index + 2,
                reason="next stage application failed",
            )
            return False
        current_temp = self.get_sample_temperature()
        self._emit_stage_info_update(next_stage, current_temp, 0.0)
        message = f"已校正到第 {from_index + 2} 阶段：{next_stage.description}"
        self.system_message_updated.emit(message)
        self.logger.info(message)
        audit(
            AuditCategory.EXPERIMENT,
            "skip_stage",
            operator=self.experiment_params.get("operator") if self.experiment_params else None,
            experiment_id=getattr(self.current_experiment, "experiment_id", None),
            from_stage_index=from_index + 1,
            from_stage=from_stage.description,
            to_stage_index=from_index + 2,
            to_stage=next_stage.description,
        )
        return True

    def adjust_current_stage_elapsed(self, elapsed_minutes: float) -> bool:
        """经明确确认后，校正固定时长阶段的当前时钟。"""
        context = self.get_stage_realignment_context()
        if context is None:
            return self._reject_stage_realignment(
                "adjust_stage_elapsed", "仅可在实验稳定运行时校正阶段时长"
            )
        if not context["can_adjust_elapsed"]:
            return self._reject_stage_realignment(
                "adjust_stage_elapsed",
                "当前阶段由温度条件驱动，不能通过修改时长推进",
                stage_index=context["current_stage_index"],
            )

        requested_elapsed = elapsed_minutes
        try:
            elapsed_minutes = float(elapsed_minutes)
        except (TypeError, ValueError):
            elapsed_minutes = float("nan")
        duration_minutes = context["duration_minutes"]
        if not math.isfinite(elapsed_minutes) or not 0 <= elapsed_minutes <= duration_minutes:
            return self._reject_stage_realignment(
                "adjust_stage_elapsed",
                f"阶段已用时必须在 0–{duration_minutes:g} 分钟之间",
                requested_elapsed_minutes=(
                    elapsed_minutes if math.isfinite(elapsed_minutes) else repr(requested_elapsed)
                ),
                stage_index=context["current_stage_index"],
            )
        if self._confirm_callback is None:
            return self._reject_stage_realignment(
                "adjust_stage_elapsed", "缺少操作确认回调，已拒绝阶段时长校正"
            )

        confirmed = self._confirm_callback(
            "确认校正阶段时长",
            (
                f"当前第 {context['current_stage_index']} 阶段“{context['stage_description']}”\n"
                f"将已用时校正为 {elapsed_minutes:.1f} 分钟（设定时长 {duration_minutes:g} 分钟）。\n\n"
                "校正后可能在下一次检查时立即进入下一阶段，是否继续？"
            ),
            False,
        )
        if not confirmed:
            return self._reject_stage_realignment(
                "adjust_stage_elapsed",
                "用户取消阶段时长校正",
                requested_elapsed_minutes=elapsed_minutes,
                stage_index=context["current_stage_index"],
            )

        latest_context = self.get_stage_realignment_context()
        if (
            latest_context is None
            or latest_context["current_stage_index"] != context["current_stage_index"]
        ):
            return self._reject_stage_realignment(
                "adjust_stage_elapsed",
                "确认期间实验阶段已变化，已拒绝过期的时长校正",
                requested_stage_index=context["current_stage_index"],
                current_stage_index=(
                    latest_context["current_stage_index"] if latest_context else None
                ),
            )

        now = self._clock()
        self._sm.update_state_silent(stage_start_time=now - elapsed_minutes * 60.0)
        current_stage = self.experiment_mode_manager.get_current_stage_settings()
        self._emit_stage_info_update(
            current_stage,
            self.get_sample_temperature(),
            elapsed_minutes * 60.0,
        )
        message = f"已将第 {context['current_stage_index']} 阶段已用时校正为 {elapsed_minutes:.1f} 分钟"
        self.system_message_updated.emit(message)
        self.logger.info(message)
        audit(
            AuditCategory.EXPERIMENT,
            "adjust_stage_elapsed",
            operator=self.experiment_params.get("operator") if self.experiment_params else None,
            experiment_id=getattr(self.current_experiment, "experiment_id", None),
            stage_index=context["current_stage_index"],
            stage=context["stage_description"],
            previous_elapsed_minutes=context["elapsed_minutes"],
            new_elapsed_minutes=elapsed_minutes,
        )
        return True
    
    def complete_experiment(self) -> None:
        """完成实验"""
        safety_success = self._finish_experiment_common(
            "实验完成", "实验自动完成，已切换到N₂保护",
            via_phase=ExperimentPhase.COMPLETING,
        )
        self.experiment_completed.emit()
        self.logger.info("实验已完成")
        audit(
            AuditCategory.EXPERIMENT, "complete",
            result=AuditResult.SUCCESS if safety_success else AuditResult.FAILURE,
            operator=self.experiment_params.get("operator") if self.experiment_params else None,
            experiment_id=getattr(self.current_experiment, "experiment_id", None),
        )
    
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
            if self.is_experiment_running():
                message = "实验运行中禁止天平清零，以免破坏初始重量和失重数据"
                self.logger.error(message)
                self.system_message_updated.emit(message)
                audit(
                    AuditCategory.BALANCE,
                    "tare",
                    result=AuditResult.REJECTED,
                    operator=self.experiment_params.get("operator") if self.experiment_params else None,
                    reason="experiment_running",
                )
                return False

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
        self._initial_weight_source = "measured" if weight > 0 else None
        self.logger.info(f"设置初始重量: {weight:.3f}g")
    
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
        if self._manual_initial_weight_in_progress:
            self.logger.warning("初始重量设置正在进行，忽略重复请求")
            self.system_message_updated.emit("初始重量设置正在进行，请勿重复操作")
            return False

        self._manual_initial_weight_in_progress = True
        try:
            # 第一步：执行天平去皮（跳过确认对话框，因为这是设置初始重量流程的一部分）
            self.system_message_updated.emit("正在执行天平去皮...")
            tare_success = self.tare_balance(parent_widget, skip_confirmation=True)
            
            if not tare_success:
                self.system_message_updated.emit("天平去皮失败，无法设置初始重量")
                return False
                
            # 第二步：获取当前天平读数（去皮后应该接近0）
            current_balance_weight = 0.0
            balance_device = self._get_registered_device("Balance")
            if balance_device:
                try:
                    current_balance_weight = balance_device.get_current_weight() or 0.0
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
        finally:
            self._manual_initial_weight_in_progress = False
    
    def apply_safety_atmosphere(self) -> tuple[bool, str]:
        """公开的保护气氛入口，供实验流程之外的路径（如实验重置）复用。

        实验流程内部继续调用 ``_set_safety_atmosphere``；此处只是把同一份
        已校验的实现暴露出去，避免再出现第二份不检查返回值的吹扫代码。
        """
        if self._set_safety_atmosphere():
            return True, "已切换到N₂保护气氛"
        return False, self._last_safety_error

    def _set_safety_atmosphere(self) -> bool:
        """设置安全气氛，并对每个失败通道进行有限重试。"""
        targets = (
            ('N2', self.SAFETY_N2_FLOW_LPM),
            ('CO', 0.0),
            ('CO2', 0.0),
            ('H2', 0.0),
        )
        failed_gases = []

        for gas, flow in targets:
            success = False
            for attempt in range(1, self.SAFETY_FLOW_MAX_ATTEMPTS + 1):
                try:
                    success = bool(
                        self.device_manager
                        and self.device_manager.set_flow(gas, flow)
                    )
                except Exception as exc:
                    self.logger.error(
                        f"安全气氛设置异常：{gas} -> {flow:.1f}L/min，"
                        f"第 {attempt} 次尝试：{exc}",
                        exc_info=True,
                    )
                    success = False
                if success:
                    break
                self.logger.warning(
                    f"安全气氛设置失败：{gas} -> {flow:.1f}L/min，"
                    f"第 {attempt}/{self.SAFETY_FLOW_MAX_ATTEMPTS} 次尝试"
                )
            if not success:
                failed_gases.append(gas)

        if not failed_gases:
            self._last_safety_error = ""
            return True

        failed_text = "、".join(failed_gases)
        self._last_safety_error = (
            f"安全气氛设置失败（{failed_text}），可燃气体可能仍在供给。"
            "请立即检查气路与设备连接并人工处置，切勿离开现场。"
        )
        self.logger.critical(self._last_safety_error)
        self.status_updated.emit("危险：安全气氛设置失败")
        self.system_message_updated.emit(self._last_safety_error)
        self.safety_alert.emit(self._last_safety_error)
        return False
    
    def _update_experiment_time_internal(self) -> None:
        """内部实验时间更新"""
        state = self._sm.get_state()
        if not state.is_running:
            return
        new_elapsed = max(0, int(self._clock() - state.experiment_start_time))
        self._sm.update_state_silent(elapsed_seconds=new_elapsed)
        
        # 发送计时更新信号
        time_str = self.get_experiment_duration_string()
        self.experiment_time_updated.emit(time_str)

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
            if current_temp is None:
                return 0.0
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
            elapsed_time = max(0.0, self._clock() - state.stage_start_time)
            
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
                "progress_percent": (
                    self._calculate_stage_progress(current_stage, current_temp, elapsed_time)
                    if current_temp is not None
                    else 0.0
                )
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
