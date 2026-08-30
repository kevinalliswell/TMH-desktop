from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from src.application.dto import ExperimentDetailDTO
from src.application.services.history_query_service import HistoryQueryService
from src.utils.logger import get_logger
from src.utils.path_manager import PathManager
from src.utils.audit import audit, AuditCategory, AuditResult


class UnsupportedReportTypeError(ValueError):
    """Raised when an experiment type does not map to a supported report template."""


class ReportExportService:
    """Handles experiment data export and HTML report generation."""

    _EQUIPMENT_LOOP = ("{% for item in equipment %}\n            <tr>\n                <td>{{ loop.index }}</td>\n"
                       "                <td>{{ item.name }}</td>\n                <td>{{ item.model }}</td>\n"
                       "                <td>{{ item.precision }}</td>\n                <td>{{ item.equipment_no }}</td>\n"
                       "            </tr>\n            {% endfor %}")
    _CONDITIONS_LOOP = ("{% for item in test_conditions %}\n            <tr>\n                <td>{{ item.parameter }}</td>\n"
                        "                <td>{{ item.standard_value }}</td>\n                <td>{{ item.actual_value }}</td>\n"
                        "            </tr>\n            {% endfor %}")

    def __init__(self, history_query_service=None, exports_dir: str | None = None, resources_dir: str | None = None):
        self.logger = get_logger(__name__)
        self.history_query_service = history_query_service or HistoryQueryService()
        self.exports_dir = Path(exports_dir or PathManager.get_exports_path())
        self.templates_dir = Path(resources_dir or PathManager.get_resources_path()) / "templates"

    def default_export_dir(self) -> str:
        return str(self.exports_dir)

    def export_experiment_data(self, experiment_id: str, filepath: str, export_format: str | None = None) -> str:
        detail = self._require_experiment_detail(experiment_id)
        path = Path(filepath)
        fmt = (export_format or path.suffix.lstrip(".")).lower()

        if fmt == "csv":
            self._export_csv(detail, path)
        elif fmt == "txt":
            self._export_txt(detail, path)
        elif fmt == "xlsx":
            self._export_xlsx(detail, path)
        else:
            audit(AuditCategory.EXPORT, "export_data", result=AuditResult.FAILURE,
                  experiment_id=experiment_id, format=fmt)
            raise ValueError(f"不支持的文件格式: {fmt}")

        audit(AuditCategory.EXPORT, "export_data",
              experiment_id=experiment_id, format=fmt, path=str(path))
        return str(path)

    def generate_html_report(self, experiment_id: str) -> str:
        detail = self._require_experiment_detail(experiment_id)
        category = self.detect_experiment_category(detail.experiment_type)

        if category == "rdi":
            content = self._build_rdi_report(detail)
            prefix = "RDI报告"
        elif category == "reducibility":
            content = self._build_reducibility_report(detail)
            prefix = "还原性报告"
        elif category == "expansion":
            content = self._build_expansion_report(detail)
            prefix = "膨胀报告"
        else:
            raise UnsupportedReportTypeError(
                f"实验 '{detail.experiment_name}' (类型: {detail.experiment_type or '未知类型'}) 暂不支持报告生成"
            )

        saved_path = self._save_html_report(
            content,
            prefix=prefix,
            experiment_name=detail.experiment_name,
            experiment_id=detail.experiment_id,
        )
        audit(AuditCategory.EXPORT, "generate_report",
              experiment_id=detail.experiment_id, report_category=category, path=saved_path)
        return saved_path

    @staticmethod
    def detect_experiment_category(experiment_type: str) -> str:
        normalized = (experiment_type or "").strip().lower()
        if "rdi" in normalized or "13242" in normalized or "粉化" in normalized:
            return "rdi"
        if "还原" in normalized or "13241" in normalized or "reducibility" in normalized:
            return "reducibility"
        if "膨胀" in normalized or "13240" in normalized or "swelling" in normalized:
            return "expansion"
        return "unknown"

    def _require_experiment_detail(self, experiment_id: str) -> ExperimentDetailDTO:
        detail = self.history_query_service.get_experiment_detail(experiment_id)
        if detail is None:
            raise ValueError(f"未找到实验ID: {experiment_id}")
        return detail

    def _export_csv(self, detail: ExperimentDetailDTO, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["实验信息"])
            writer.writerow(["实验名称", detail.experiment_name])
            writer.writerow(["样品名称", detail.sample_name])
            writer.writerow(["样品重量(g)", detail.sample_weight])
            writer.writerow(["开始时间", detail.start_time])
            writer.writerow(["结束时间", detail.end_time or ""])
            writer.writerow(["描述", detail.description])
            writer.writerow([])
            writer.writerow(["时间", "温度(℃)", "重量(g)", "失重(%)", "CO(L/min)", "CO₂(L/min)", "N₂(L/min)", "H₂(L/min)"])
            for row in self._iter_series_rows(detail):
                writer.writerow(row)

    def _export_txt(self, detail: ExperimentDetailDTO, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            handle.write("实验信息:\n")
            handle.write(f"实验名称: {detail.experiment_name}\n")
            handle.write(f"样品名称: {detail.sample_name}\n")
            handle.write(f"样品重量: {detail.sample_weight}g\n")
            handle.write(f"开始时间: {detail.start_time}\n")
            handle.write(f"结束时间: {detail.end_time or ''}\n")
            handle.write(f"描述: {detail.description}\n\n")
            handle.write("时间\t温度(℃)\t重量(g)\t失重(%)\tCO(L/min)\tCO₂(L/min)\tN₂(L/min)\tH₂(L/min)\n")
            for row in self._iter_series_rows(detail):
                handle.write(
                    f"{row[0]}\t{row[1]:.1f}\t{row[2]:.4f}\t{row[3]:.2f}\t{row[4]:.2f}\t{row[5]:.2f}\t{row[6]:.2f}\t{row[7]:.2f}\n"
                )

    def _export_xlsx(self, detail: ExperimentDetailDTO, path: Path) -> None:
        import pandas as pd

        path.parent.mkdir(parents=True, exist_ok=True)
        info_df = pd.DataFrame(
            {
                "项目": ["实验名称", "样品名称", "样品重量(g)", "开始时间", "结束时间", "描述", "操作员", "实验类型"],
                "内容": [
                    detail.experiment_name,
                    detail.sample_name,
                    detail.sample_weight,
                    detail.start_time,
                    detail.end_time or "",
                    detail.description,
                    detail.operator,
                    detail.experiment_type,
                ],
            }
        )
        data_df = pd.DataFrame(
            {
                "时间": detail.timestamps,
                "温度(℃)": detail.temperatures,
                "重量(g)": detail.weights,
                "失重(%)": detail.weight_losses,
                "CO(L/min)": detail.gas_flows["CO"],
                "CO₂(L/min)": detail.gas_flows["CO2"],
                "N₂(L/min)": detail.gas_flows["N2"],
                "H₂(L/min)": detail.gas_flows["H2"],
            }
        )
        with pd.ExcelWriter(path) as writer:
            info_df.to_excel(writer, sheet_name="实验信息", index=False)
            data_df.to_excel(writer, sheet_name="实验数据", index=False)

    def _iter_series_rows(self, detail: ExperimentDetailDTO):
        for index, timestamp in enumerate(detail.timestamps):
            yield [
                timestamp,
                self._get_value(detail.temperatures, index),
                self._get_value(detail.weights, index),
                self._get_value(detail.weight_losses, index),
                self._get_value(detail.gas_flows["CO"], index),
                self._get_value(detail.gas_flows["CO2"], index),
                self._get_value(detail.gas_flows["N2"], index),
                self._get_value(detail.gas_flows["H2"], index),
            ]

    def _build_rdi_report(self, detail: ExperimentDetailDTO) -> str:
        report = self._load_template("iron_ore_rdi_report_template.html")
        analysis = detail.analysis_results or {}
        report = self._fill_report_header(report, detail, analysis, self._test_date(detail))

        default_equip = [
            {"name": "铁矿石冶金性能综合检测设备", "model": "TMH-LPF-900", "precision": "±5℃", "equipment_no": "TMH-LPF-900"},
            {"name": "电子天平", "model": "FA2104N", "precision": "0.01g", "equipment_no": "BAL-001"},
            {"name": "标准筛", "model": "GB/T 6003.1", "precision": "", "equipment_no": "SIEVE-001"},
            {"name": "筛分机", "model": "ZS-200", "precision": "", "equipment_no": "SIFTER-001"},
        ]
        report = report.replace(self._EQUIPMENT_LOOP, self._build_equipment_html(self._get_val(analysis, "equipment", default_equip)))

        default_cond = [
            {"parameter": "试样质量", "standard_value": "500±1g", "actual_value": f"{detail.sample_weight:.1f}g"},
            {"parameter": "试样粒度", "standard_value": "10-12.5mm", "actual_value": "10-12.5mm"},
            {"parameter": "还原温度", "standard_value": "500±10℃", "actual_value": "500℃"},
            {"parameter": "还原气体", "standard_value": "CO:30%, CO₂:20%, N₂:50%", "actual_value": "CO:30%, CO₂:20%, N₂:50%"},
            {"parameter": "气体流量", "standard_value": "15±0.5L/min", "actual_value": "15.0L/min"},
            {"parameter": "还原时间", "standard_value": "60min", "actual_value": "60min"},
            {"parameter": "转鼓转速", "standard_value": "30±1r/min", "actual_value": "30r/min"},
            {"parameter": "转鼓时间", "standard_value": "10min", "actual_value": "10min"},
        ]
        report = report.replace(self._CONDITIONS_LOOP, self._build_conditions_html(self._get_val(analysis, "test_conditions", default_cond)))

        sieve_inputs = self._get_val(analysis, "sieve_input_masses", {})
        rdi_indices = self._get_val(analysis, "calculated_rdi_indices", {})
        drum_mass = float(self._get_val(
            analysis,
            "drum_sample_weight_g",
            self._get_val(analysis, "initial_sample_weight_g", detail.sample_weight or 500.0),
        ))
        plus_3_15 = self._get_val(sieve_inputs, "mass_gt_6_3", 0.0) + self._get_val(sieve_inputs, "mass_3_15_to_6_3", 0.0)
        minus_3_15 = self._get_val(sieve_inputs, "mass_0_5_to_3_15", 0.0)
        minus_0_5 = self._get_val(sieve_inputs, "mass_lt_0_5", 0.0)
        rdi_minus_3_15 = self._percentage_or_none(rdi_indices.get("RDI-3.15"))
        if rdi_minus_3_15 is None:
            rdi_plus_3_15 = self._percentage_or_none(rdi_indices.get("RDI+3.15"))
            if rdi_plus_3_15 is not None:
                rdi_minus_3_15 = 100.0 - rdi_plus_3_15
        rdi_0_5 = self._percentage_or_none(rdi_indices.get("RDI-0.5"))
        rdi_minus_3_15_text = self._format_optional_number(rdi_minus_3_15)
        rdi_0_5_text = self._format_optional_number(rdi_0_5)

        results_html = (f"<tr><td>1</td><td>{drum_mass:.2f}</td><td>{plus_3_15:.2f}</td>"
                        f"<td>{minus_3_15:.2f}</td><td>{minus_0_5:.2f}</td>"
                        f"<td>{rdi_minus_3_15_text}</td><td>{rdi_0_5_text}</td></tr>\n")
        report = report.replace(
            "{% for item in test_results %}\n            <tr>\n                <td>{{ loop.index }}</td>\n"
            "                <td>{{ item.mass_before }}</td>\n                <td>{{ item.mass_plus_3_15 }}</td>\n"
            "                <td>{{ item.mass_minus_3_15_plus_0_5 }}</td>\n                <td>{{ item.mass_minus_0_5 }}</td>\n"
            "                <td>{{ item.rdi_minus_3_15 }}</td>\n                <td>{{ item.rdi_minus_0_5 }}</td>\n"
            "            </tr>\n            {% endfor %}",
            results_html,
        )
        report = report.replace("{{ avg_results.rdi_minus_3_15 }}", rdi_minus_3_15_text)
        report = report.replace("{{ avg_results.rdi_minus_0_5 }}", rdi_0_5_text)
        rdi_minus_summary = (
            "RDI-3.15未测得"
            if rdi_minus_3_15 is None
            else f"RDI-3.15为{rdi_minus_3_15_text}%"
        )
        rdi_0_5_summary = (
            "RDI-0.5未测得"
            if rdi_0_5 is None
            else f"RDI-0.5为{rdi_0_5_text}%"
        )
        report = report.replace(
            "{{ conclusion }}",
            self._get_val(
                analysis,
                "conclusion",
                f"根据GB/T 13242-2017标准，该铁矿石样品的低温还原粉化指数{rdi_minus_summary}，{rdi_0_5_summary}。",
            ),
        )
        return self._fill_report_footer(report, detail, self._test_date(detail))

    def _build_reducibility_report(self, detail: ExperimentDetailDTO) -> str:
        report = self._load_template("iron_ore_reducibility_report_template.html")
        analysis = detail.analysis_results or {}
        report = self._fill_report_header(report, detail, analysis, self._test_date(detail))

        default_equip = [
            {"name": "铁矿石冶金性能综合检测设备", "model": "TMH-LPF-900", "precision": "±5℃", "equipment_no": "TMH-LPF-900"},
            {"name": "电子天平", "model": "FA2104N", "precision": "0.1mg", "equipment_no": "BAL-001"},
            {"name": "气体流量控制器", "model": "MFC-100", "precision": "±1%", "equipment_no": "MFC-001"},
        ]
        report = report.replace(self._EQUIPMENT_LOOP, self._build_equipment_html(self._get_val(analysis, "equipment", default_equip)))

        cc = self._get_val(analysis, "chemical_composition", {})
        for key, default in [("TFe", "65.2"), ("FeO", "0.5"), ("SiO2", "4.8"), ("Al2O3", "1.2"), ("CaO", "0.8"), ("MgO", "0.3"), ("LOI", "2.1")]:
            report = report.replace(f"{{{{ chemical_composition.{key} }}}}", str(self._get_val(cc, key, default)))

        default_cond = [
            {"parameter": "还原温度", "standard_value": "900±10℃", "actual_value": "900℃"},
            {"parameter": "还原气体", "standard_value": "CO:30%, CO₂:20%, N₂:50%", "actual_value": "CO:30%, CO₂:20%, N₂:50%"},
            {"parameter": "气体流量", "standard_value": "15±0.5L/min", "actual_value": "15.0L/min"},
            {"parameter": "试样质量", "standard_value": "500±1g", "actual_value": f"{detail.sample_weight}g"},
        ]
        report = report.replace(self._CONDITIONS_LOOP, self._build_conditions_html(self._get_val(analysis, "test_conditions", default_cond)))

        mass_before = float(self._get_val(analysis, "initial_weight", detail.sample_weight))
        mass_after = float(self._get_val(analysis, "final_weight", mass_before * 0.95))
        final_red = float(self._get_val(analysis, "final_reduction_degree", 1.67))
        red_idx = float(self._get_val(analysis, "reduction_index", 0.01))
        results_html = (
            f"<tr><td>1</td><td>{mass_before:.1f}</td><td>{mass_after:.1f}</td>"
            f"<td>{final_red*0.3:.2f}</td><td>{final_red*0.6:.2f}</td><td>{final_red*0.9:.2f}</td><td>{final_red:.2f}</td>"
            f"<td>{final_red*0.3:.2f}</td><td>{final_red*0.6:.2f}</td><td>{final_red*0.9:.2f}</td><td>{final_red:.2f}</td>"
            f"<td>{red_idx:.3f}</td></tr>\n"
        )
        report = report.replace(
            "{% for item in test_results %}\n            <tr>\n                <td>{{ loop.index }}</td>\n"
            "                <td>{{ item.mass_before }}</td>\n                <td>{{ item.mass_after }}</td>\n"
            "                <td>{{ item.oxygen_loss_30min }}</td>\n                <td>{{ item.oxygen_loss_60min }}</td>\n"
            "                <td>{{ item.oxygen_loss_90min }}</td>\n                <td>{{ item.oxygen_loss_final }}</td>\n"
            "                <td>{{ item.red_degree_30min }}</td>\n                <td>{{ item.red_degree_60min }}</td>\n"
            "                <td>{{ item.red_degree_90min }}</td>\n                <td>{{ item.red_degree_final }}</td>\n"
            "                <td>{{ item.red_rate }}</td>\n"
            "            </tr>\n            {% endfor %}",
            results_html,
        )
        report = report.replace("{{ reducibility_indices.RI }}", f"{final_red:.2f}")
        report = report.replace("{{ reducibility_indices.dRdt }}", f"{red_idx:.3f}")
        report = report.replace("{{ reducibility_indices.R60 }}", f"{final_red*0.6:.2f}")
        report = report.replace("{{ reducibility_indices.t40 }}", "45")
        report = report.replace("{{ reducibility_indices.t50 }}", "60")
        report = report.replace("{{ reducibility_indices.t70 }}", "90")
        report = report.replace(
            "{{ conclusion }}",
            f"根据GB/T 13241-2017标准，该铁矿石样品的还原性指数为{final_red:.2f}%，还原速率为{red_idx:.3f}%/min。",
        )
        return self._fill_report_footer(report, detail, self._test_date(detail))

    def _build_expansion_report(self, detail: ExperimentDetailDTO) -> str:
        report = self._load_template("pellet_free_swelling_index_report_template.html")
        analysis = detail.analysis_results or {}
        report = self._fill_report_header(report, detail, analysis, self._test_date(detail))

        default_equip = [
            {"name": "铁矿石冶金性能综合检测设备", "model": "TMH-LPF-900", "precision": "±5℃", "equipment_no": "TMH-LPF-900"},
            {"name": "电子天平", "model": "FA2104N", "precision": "0.1mg", "equipment_no": "BAL-001"},
            {"name": "游标卡尺", "model": "0-200mm", "precision": "0.02mm", "equipment_no": "CAL-001"},
            {"name": "气体流量控制器", "model": "MFC-200", "precision": "±1%", "equipment_no": "MFC-002"},
        ]
        report = report.replace(self._EQUIPMENT_LOOP, self._build_equipment_html(self._get_val(analysis, "equipment", default_equip)))

        cc = self._get_val(analysis, "chemical_composition", {})
        for key, default in [("TFe", "65.5"), ("FeO", "0.3"), ("SiO2", "4.2"), ("Al2O3", "1.0"), ("CaO", "1.2"), ("MgO", "0.5"), ("Basicity", "0.29")]:
            report = report.replace(f"{{{{ chemical_composition.{key} }}}}", str(self._get_val(cc, key, default)))

        default_cond = [
            {"parameter": "还原温度", "standard_value": "1000±10℃", "actual_value": "1000℃"},
            {"parameter": "还原气体", "standard_value": "CO:30%, CO₂:20%, N₂:50%", "actual_value": "CO:30%, CO₂:20%, N₂:50%"},
            {"parameter": "气体流量", "standard_value": "15±0.5L/min", "actual_value": "15.0L/min"},
            {"parameter": "球团数量", "standard_value": "10个", "actual_value": "10个"},
            {"parameter": "球团直径", "standard_value": "10-12mm", "actual_value": "10-12mm"},
        ]
        report = report.replace(self._CONDITIONS_LOOP, self._build_conditions_html(self._get_val(analysis, "test_conditions", default_cond)))

        init_vol = float(self._get_val(analysis, "initial_volume", 100.0))
        final_vol = float(self._get_val(analysis, "final_volume", 120.0))
        exp_idx = float(self._get_val(analysis, "expansion_index", 20.0))
        init_d = (init_vol * 6 / 3.14159) ** (1 / 3)
        final_d = (final_vol * 6 / 3.14159) ** (1 / 3)
        report = report.replace(
            "{% for item in test_results %}\n            <tr>\n                <td>{{ item.pellet_no }}</td>\n"
            "                <td>{{ item.before_diameter }}</td>\n                <td>{{ item.before_volume }}</td>\n"
            "                <td>{{ item.after_diameter }}</td>\n                <td>{{ item.after_volume }}</td>\n"
            "                <td>{{ item.swelling_index }}</td>\n"
            "            </tr>\n            {% endfor %}",
            f"<tr><td>1</td><td>{init_d:.2f}</td><td>{init_vol:.1f}</td><td>{final_d:.2f}</td><td>{final_vol:.1f}</td><td>{exp_idx:.2f}</td></tr>\n",
        )
        report = report.replace(
            "{% for item in pellet_description %}\n            <tr>\n                <td>{{ item.pellet_no }}</td>\n"
            "                <td>{{ item.appearance }}</td>\n                <td>{{ item.cracks }}</td>\n"
            "                <td>{{ item.strength_evaluation }}</td>\n"
            "            </tr>\n            {% endfor %}",
            "<tr><td>1</td><td>球团表面光滑，无明显缺陷</td><td>无裂纹</td><td>强度良好</td></tr>\n",
        )
        report = report.replace(
            "{{ conclusion }}",
            f"根据GB/T 13240-2017标准，该球团样品的自由膨胀指数为{exp_idx:.2f}%，符合标准要求。",
        )
        return self._fill_report_footer(report, detail, self._test_date(detail))

    def _load_template(self, filename: str) -> str:
        template_path = self.templates_dir / filename
        if not template_path.exists():
            raise FileNotFoundError(f"报告模板文件缺失: {template_path}")
        return template_path.read_text(encoding="utf-8")

    def _fill_report_header(self, content: str, detail: ExperimentDetailDTO, analysis: dict, test_date: str) -> str:
        content = content.replace("{{ report_info.report_no }}", str(self._get_val(analysis, "report_no", detail.experiment_id[:8])))
        content = content.replace("{{ test_date }}", str(self._get_val(analysis, "test_date", test_date)))
        content = content.replace("{{ report_info.client }}", str(self._get_val(analysis, "client", "委托单位")))
        content = content.replace("{{ report_info.sample_name }}", detail.sample_name)
        content = content.replace("{{ report_info.sample_no }}", str(self._get_val(analysis, "sample_no", detail.experiment_id[:8])))
        content = content.replace("{{ report_info.receiving_date }}", str(self._get_val(analysis, "receiving_date", test_date)))
        content = content.replace("{{ report_info.report_date }}", datetime.now().strftime("%Y-%m-%d"))
        content = content.replace("{{ report_info.sample_status }}", str(self._get_val(analysis, "sample_status", "正常")))
        return content

    def _fill_report_footer(self, content: str, detail: ExperimentDetailDTO, test_date: str) -> str:
        content = content.replace("{{ tester }}", detail.operator or "测试人员")
        content = content.replace("{{ test_date }}", test_date)
        content = content.replace("{{ reviewer }}", "审核人员")
        content = content.replace("{{ review_date }}", datetime.now().strftime("%Y-%m-%d"))
        content = content.replace("{{ lab_info.name }}", "TMH实验室")
        content = content.replace("{{ lab_info.address }}", "北京市海淀区学院路30号")
        content = content.replace("{{ lab_info.phone }}", "010-62312345")
        content = content.replace("{{ lab_info.postal_code }}", "100083")
        return content

    def _save_html_report(self, content: str, prefix: str, experiment_name: str, experiment_id: str) -> str:
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(char if char.isalnum() else "_" for char in experiment_name)
        filename = f"{prefix}_{safe_name}_{experiment_id[:8]}_{datetime.now().strftime('%Y%m%d%H%M%S')}.html"
        path = self.exports_dir / filename
        path.write_text(content, encoding="utf-8")
        self.logger.info(f"成功生成报告: {path}")
        return str(path)

    def _build_equipment_html(self, equipment_list: list) -> str:
        rows = ""
        for index, equipment in enumerate(equipment_list):
            rows += (
                f"<tr><td>{index + 1}</td>"
                f"<td>{self._get_val(equipment, 'name')}</td>"
                f"<td>{self._get_val(equipment, 'model')}</td>"
                f"<td>{self._get_val(equipment, 'precision')}</td>"
                f"<td>{self._get_val(equipment, 'equipment_no')}</td></tr>\n"
            )
        return rows

    def _build_conditions_html(self, conditions_list: list) -> str:
        rows = ""
        for condition in conditions_list:
            rows += (
                f"<tr><td>{self._get_val(condition, 'parameter')}</td>"
                f"<td>{self._get_val(condition, 'standard_value')}</td>"
                f"<td>{self._get_val(condition, 'actual_value')}</td></tr>\n"
            )
        return rows

    @staticmethod
    def _test_date(detail: ExperimentDetailDTO) -> str:
        if detail.start_time:
            try:
                return datetime.fromisoformat(detail.start_time).strftime("%Y-%m-%d")
            except ValueError:
                return detail.start_time
        return ""

    @staticmethod
    def _get_val(data_dict, key, default=""):
        if not isinstance(data_dict, dict):
            return default
        return data_dict.get(key, default)

    @staticmethod
    def _percentage_or_none(value) -> float | None:
        try:
            percentage = float(value)
        except (TypeError, ValueError):
            return None
        return percentage if 0.0 <= percentage <= 100.0 else None

    @staticmethod
    def _format_optional_number(value: float | None) -> str:
        return "未测得" if value is None else f"{value:.2f}"

    @staticmethod
    def _get_value(items: list[float], index: int, default: float = 0.0) -> float:
        return items[index] if index < len(items) else default
