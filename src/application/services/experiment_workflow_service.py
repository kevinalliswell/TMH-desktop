from __future__ import annotations

import os
import time
import uuid
from datetime import datetime

from src.application.dto import ExperimentCommandResult, ExperimentStartResult
from src.application.ports import DeviceHubPort
from src.services.database import ExperimentData
from src.utils.path_manager import PathManager


class ExperimentWorkflowService:
    """Coordinates experiment startup/stop flows outside the view layer."""

    def __init__(
        self,
        device_manager: DeviceHubPort,
        experiment_api,
        experiment_file_manager,
        experiment_type_manager,
        logger,
    ):
        self.device_manager = device_manager
        self.experiment_api = experiment_api
        self.experiment_file_manager = experiment_file_manager
        self.experiment_type_manager = experiment_type_manager
        self.logger = logger

    def validate_device_availability(self) -> ExperimentCommandResult:
        """Check whether all required devices are running and fresh."""
        if not self.device_manager:
            return ExperimentCommandResult(False, "设备管理器未初始化")

        device_statuses = self.device_manager.get_all_status()
        devices_without_data = []

        for device_name, status in device_statuses.items():
            if not status.get("running", False):
                devices_without_data.append(f"{device_name} (未运行)")
                continue

            last_update_ts = status.get("last_update_ts")
            if last_update_ts is None:
                devices_without_data.append(f"{device_name} (无数据)")
                continue

            current_time = time.time()
            if current_time - last_update_ts > 10:
                devices_without_data.append(f"{device_name} (数据过期)")
                self.logger.warning(
                    f"设备 {device_name} 数据过期: {current_time - last_update_ts:.1f}秒前"
                )

        if devices_without_data:
            device_list = "\n".join(devices_without_data)
            return ExperimentCommandResult(
                False,
                f"以下设备无数据或数据过期，无法开始实验：\n\n{device_list}\n\n"
                "请确保所有设备正常运行并获取到最新数据后再开始实验。",
            )

        self.logger.info(f"所有设备数据检查通过，共检查 {len(device_statuses)} 个设备")
        return ExperimentCommandResult(True, "设备状态检查通过")

    def create_experiment_record(self, experiment_params: dict) -> ExperimentStartResult:
        """Create and persist the experiment metadata file before startup."""
        experiment_data = ExperimentData(
            experiment_id=str(uuid.uuid4()),
            experiment_name=experiment_params["project_name"],
            sample_name=experiment_params["sample_name"],
            sample_weight=experiment_params["sample_weight"],
            start_time=datetime.now().isoformat(),
            description=experiment_params["notes"],
            operator=experiment_params["operator"],
            experiment_type=experiment_params["experiment_type"],
        )

        self.logger.info(f"实验数据: {experiment_data}")

        filename = self.experiment_file_manager.generate_filename(experiment_data)
        experiments_dir = PathManager.get_data_path("experiments")
        os.makedirs(experiments_dir, exist_ok=True)
        filepath = os.path.join(experiments_dir, filename)

        if not self.experiment_file_manager.save_experiment(filepath, experiment_data):
            return ExperimentStartResult(False, "保存实验文件失败！")

        self.logger.info(f"实验文件已保存：{filepath}")
        return ExperimentStartResult(
            True,
            "实验文件已保存",
            experiment_id=experiment_data.experiment_id,
            experiment_data=experiment_data,
            experiment_file_path=filepath,
        )

    def configure_experiment_mode(self, experiment_params: dict) -> ExperimentCommandResult:
        """Configure experiment mode on the experiment API."""
        mode_id = experiment_params.get("experiment_mode_id")
        if not mode_id:
            return ExperimentCommandResult(False, "实验模式ID不能为空！")

        if not self.experiment_api.set_experiment_mode_by_id(mode_id):
            return ExperimentCommandResult(False, "设置实验模式失败！")

        type_info = self.experiment_type_manager.get_type_by_id(mode_id)
        if type_info:
            self.logger.info(f"设置实验模式成功: {type_info.name}")
        else:
            self.logger.info(f"设置实验模式成功: {mode_id}")
        return ExperimentCommandResult(True, "设置实验模式成功")

    def start_experiment(self, experiment_params: dict) -> ExperimentStartResult:
        """Run non-UI startup orchestration after the page has prepared the API."""
        readiness = self.validate_device_availability()
        if not readiness.success:
            return ExperimentStartResult(False, readiness.message)

        start_record = self.create_experiment_record(experiment_params)
        if not start_record.success:
            return start_record

        mode_result = self.configure_experiment_mode(experiment_params)
        if not mode_result.success:
            self._remove_startup_file(start_record.experiment_file_path)
            return ExperimentStartResult(
                False,
                mode_result.message,
                experiment_id=start_record.experiment_id,
                experiment_data=start_record.experiment_data,
                experiment_file_path=start_record.experiment_file_path,
            )

        if not self.experiment_api.start_experiment(start_record.experiment_data):
            self._remove_startup_file(start_record.experiment_file_path)
            return ExperimentStartResult(
                False,
                "启动实验失败！",
                experiment_id=start_record.experiment_id,
                experiment_data=start_record.experiment_data,
                experiment_file_path=start_record.experiment_file_path,
            )

        self.logger.info("实验已成功启动")
        return ExperimentStartResult(
            True,
            "实验已开始",
            experiment_id=start_record.experiment_id,
            experiment_data=start_record.experiment_data,
            experiment_file_path=start_record.experiment_file_path,
        )

    def _remove_startup_file(self, filepath: str | None) -> None:
        """Remove a pre-created experiment file after startup fails."""
        if not filepath:
            return
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                self.logger.info(f"已清理启动失败产生的实验文件: {filepath}")
        except OSError as exc:
            self.logger.warning(f"清理启动失败实验文件失败: {exc}")

    def stop_experiment(self) -> ExperimentCommandResult:
        """Stop the running experiment."""
        if not self.experiment_api.is_experiment_running():
            return ExperimentCommandResult(False, "没有正在运行的实验")

        if not self.experiment_api.stop_experiment():
            return ExperimentCommandResult(False, "停止实验失败")

        self.logger.info("实验已停止")
        return ExperimentCommandResult(True, "实验已停止")

    def apply_protective_gas(self) -> ExperimentCommandResult:
        """Switch hardware outputs to the default protective gas setup."""
        if not self.device_manager:
            return ExperimentCommandResult(False, "设备管理器未初始化")

        self.device_manager.set_flow("N2", 5.0)
        self.device_manager.set_flow("CO", 0.0)
        self.device_manager.set_flow("CO2", 0.0)
        self.device_manager.set_flow("H2", 0.0)
        return ExperimentCommandResult(True, "已切换到N₂保护气氛")
