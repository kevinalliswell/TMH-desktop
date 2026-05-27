from __future__ import annotations

import json

from src.application.dto import (
    DatabaseIntegrityStatusDTO,
    ExperimentDetailDTO,
    ExperimentSummaryDTO,
)
from src.services.database import ExperimentDatabase
from src.utils.logger import get_logger


class HistoryQueryService:
    """Application service for experiment history querying and maintenance."""

    def __init__(self, repository=None):
        self.logger = get_logger(__name__)
        self.repository = repository or ExperimentDatabase()

    def list_experiments(self) -> list[ExperimentSummaryDTO]:
        experiments = []
        for experiment in self.repository.get_all_experiments():
            experiments.append(
                ExperimentSummaryDTO(
                    experiment_id=experiment.experiment_id,
                    experiment_name=experiment.experiment_name,
                    sample_name=experiment.sample_name,
                    sample_weight=float(experiment.sample_weight or 0.0),
                    start_time=experiment.start_time,
                    end_time=experiment.end_time,
                    operator=experiment.operator,
                    experiment_type=experiment.experiment_type,
                    description=experiment.description,
                )
            )
        return experiments

    def get_experiment_detail(self, experiment_id: str) -> ExperimentDetailDTO | None:
        experiment = self.repository.get_experiment(experiment_id)
        if experiment is None:
            self.logger.warning(f"未找到实验记录: {experiment_id}")
            return None

        detail = ExperimentDetailDTO(
            experiment_id=experiment.experiment_id,
            experiment_name=experiment.experiment_name,
            sample_name=experiment.sample_name,
            sample_weight=float(experiment.sample_weight or 0.0),
            start_time=experiment.start_time,
            end_time=experiment.end_time,
            operator=experiment.operator,
            experiment_type=experiment.experiment_type,
            description=experiment.description,
            analysis_results=self._parse_analysis_results(experiment.analysis_results_json),
        )

        for point in self.repository.get_experiment_data(experiment_id):
            timestamp = point.get("timestamp")
            if not timestamp:
                continue
            detail.timestamps.append(timestamp)
            detail.temperatures.append(self._safe_float(point.get("temperature")))
            detail.weights.append(self._safe_float(point.get("weight")))
            detail.weight_losses.append(self._safe_float(point.get("weight_loss")))
            detail.gas_flows["CO"].append(self._safe_float(point.get("co_flow")))
            detail.gas_flows["CO2"].append(self._safe_float(point.get("co2_flow")))
            detail.gas_flows["N2"].append(self._safe_float(point.get("n2_flow")))
            detail.gas_flows["H2"].append(self._safe_float(point.get("h2_flow")))

        return detail

    def delete_experiment(self, experiment_id: str) -> bool:
        return bool(self.repository.delete_experiment(experiment_id))

    def update_analysis_results(self, experiment_id: str, analysis_results: dict) -> bool:
        return bool(self.repository.update_experiment_analysis_results(experiment_id, analysis_results))

    def validate_database_integrity(self) -> DatabaseIntegrityStatusDTO:
        raw = self.repository.validate_database_integrity()
        return DatabaseIntegrityStatusDTO(
            experiment_count=int(raw.get("experiment_count", 0)),
            data_count=int(raw.get("data_count", 0)),
            orphaned_data=int(raw.get("orphaned_data", 0)),
            experiment_columns=list(raw.get("experiment_columns", [])),
            data_columns=list(raw.get("data_columns", [])),
            is_valid=bool(raw.get("is_valid", False)),
            error=str(raw.get("error", "")),
        )

    def repair_database(self) -> bool:
        return bool(self.repository.repair_database())

    def _parse_analysis_results(self, raw_json: str | None) -> dict | None:
        if not raw_json:
            return None
        try:
            parsed = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            self.logger.error(f"分析结果 JSON 解析失败: {exc}")
            return None

        if not isinstance(parsed, dict):
            return None

        sieve_input_masses = {}
        for key in (
            "mass_gt_6_3",
            "mass_3_15_to_6_3",
            "mass_0_5_to_3_15",
            "mass_lt_0_5",
        ):
            if key in parsed:
                sieve_input_masses[key] = parsed.get(key)
        if sieve_input_masses and "sieve_input_masses" not in parsed:
            parsed["sieve_input_masses"] = sieve_input_masses

        return parsed

    @staticmethod
    def _safe_float(value, default: float = 0.0) -> float:
        try:
            return float(value) if value is not None else default
        except (TypeError, ValueError):
            return default
