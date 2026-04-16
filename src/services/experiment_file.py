# src/services/experiment_file.py
import os
from datetime import datetime
from typing import Dict, Optional, Any
from dataclasses import asdict
from .database import ExperimentData
from ..utils.path_manager import PathManager
import json


class ExperimentFile:
    """实验文件管理"""

    def __init__(self):
        self.file_extension = ".exp"

    def generate_filename(self, data: ExperimentData) -> str:
        """生成实验文件名"""
        # 格式：实验名称_样品名称_日期时间.exp
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"{data.experiment_name}_{data.sample_name}_{date_str}"
        # 替换非法字符
        safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in base_name)
        return safe_name + self.file_extension

    def save_experiment(self, filepath: str, data: ExperimentData) -> bool:
        """保存实验文件"""
        try:
            # 确保目录存在
            PathManager.ensure_file_directory_exists(filepath)

            # 转换数据为字典
            exp_dict = asdict(data)

            # 添加文件格式版本信息
            file_data = {
                "version": "1.0",
                "format": "TMH_Experiment",
                "created_at": datetime.now().isoformat(),
                "data": exp_dict
            }

            # 保存为JSON文件
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(file_data, f, indent=4, ensure_ascii=False)

            return True

        except Exception as e:
            print(f"保存实验文件失败: {e}")
            return False

    def load_experiment(self, filepath: str) -> Optional[ExperimentData]:
        """加载实验文件"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                file_data = json.load(f)

            # 检查文件格式
            if (file_data.get("format") != "TMH_Experiment" or
                    not file_data.get("version", "").startswith("1.")):
                raise ValueError("不支持的文件格式")

            # 转换为ExperimentData对象
            exp_dict = file_data["data"]
            return ExperimentData(**exp_dict)

        except Exception as e:
            print(f"加载实验文件失败: {e}")
            return None

    def export_data(self, data: ExperimentData, filepath: str, format: str = "csv") -> bool:
        """导出实验数据"""
        try:
            if not data.timestamps:  # 没有实验数据
                return False

            if format.lower() == "csv":
                return self._export_csv(data, filepath)
            elif format.lower() == "txt":
                return self._export_txt(data, filepath)
            elif format.lower() == "xlsx":
                return self._export_xlsx(data, filepath)
            else:
                raise ValueError(f"不支持的导出格式: {format}")

        except Exception as e:
            print(f"导出数据失败: {e}")
            return False

    def _export_csv(self, data: ExperimentData, filepath: str) -> bool:
        """导出为CSV格式"""
        import csv

        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                # 写入实验信息
                writer.writerow(["实验信息"])
                writer.writerow(["实验名称", data.experiment_name])
                writer.writerow(["样品名称", data.sample_name])
                writer.writerow(["样品重量(g)", data.sample_weight])
                writer.writerow(["开始时间", data.start_time])
                writer.writerow(["结束时间", data.end_time or ""])
                writer.writerow(["描述", data.description])
                writer.writerow([])

                # 写入数据表头
                headers = ["时间", "温度(℃)", "重量(g)", "失重(%)",
                           "CO(L/min)", "CO₂(L/min)", "N₂(L/min)", "H₂(L/min)"]
                writer.writerow(headers)

                # 写入数据
                for i in range(len(data.timestamps)):
                    row = [
                        data.timestamps[i],
                        data.temperatures[i],
                        data.weights[i],
                        data.weight_losses[i],
                        data.gas_flows["CO"][i],
                        data.gas_flows["CO2"][i],
                        data.gas_flows["N2"][i],
                        data.gas_flows["H2"][i]
                    ]
                    writer.writerow(row)

            return True

        except Exception as e:
            print(f"导出CSV失败: {e}")
            return False

    def _export_txt(self, data: ExperimentData, filepath: str) -> bool:
        """导出为TXT格式"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                # 写入实验信息
                f.write("实验信息:\n")
                f.write(f"实验名称: {data.experiment_name}\n")
                f.write(f"样品名称: {data.sample_name}\n")
                f.write(f"样品重量: {data.sample_weight}g\n")
                f.write(f"开始时间: {data.start_time}\n")
                f.write(f"结束时间: {data.end_time or ''}\n")
                f.write(f"描述: {data.description}\n\n")

                # 写入数据表头
                f.write("时间\t温度(℃)\t重量(g)\t失重(%)\t")
                f.write("CO(L/min)\tCO₂(L/min)\tN₂(L/min)\tH₂(L/min)\n")

                # 写入数据
                for i in range(len(data.timestamps)):
                    f.write(f"{data.timestamps[i]}\t")
                    f.write(f"{data.temperatures[i]:.1f}\t")
                    f.write(f"{data.weights[i]:.4f}\t")
                    f.write(f"{data.weight_losses[i]:.2f}\t")
                    f.write(f"{data.gas_flows['CO'][i]:.2f}\t")
                    f.write(f"{data.gas_flows['CO2'][i]:.2f}\t")
                    f.write(f"{data.gas_flows['N2'][i]:.2f}\t")
                    f.write(f"{data.gas_flows['H2'][i]:.2f}\n")

            return True

        except Exception as e:
            print(f"导出TXT失败: {e}")
            return False

    def _export_xlsx(self, data: ExperimentData, filepath: str) -> bool:
        """导出为Excel格式"""
        try:
            import pandas as pd

            # 创建实验信息sheet
            info_data = {
                "项目": ["实验名称", "样品名称", "样品重量(g)", "开始时间",
                         "结束时间", "描述"],
                "内容": [data.experiment_name, data.sample_name, data.sample_weight,
                         data.start_time, data.end_time or "", data.description]
            }
            info_df = pd.DataFrame(info_data)

            # 创建实验数据sheet
            exp_data = {
                "时间": data.timestamps,
                "温度(℃)": data.temperatures,
                "重量(g)": data.weights,
                "失重(%)": data.weight_losses,
                "CO(L/min)": data.gas_flows["CO"],
                "CO₂(L/min)": data.gas_flows["CO2"],
                "N₂(L/min)": data.gas_flows["N2"],
                "H₂(L/min)": data.gas_flows["H2"]
            }
            exp_df = pd.DataFrame(exp_data)

            # 创建Excel文件
            with pd.ExcelWriter(filepath) as writer:
                info_df.to_excel(writer, sheet_name="实验信息", index=False)
                exp_df.to_excel(writer, sheet_name="实验数据", index=False)

            return True

        except Exception as e:
            print(f"导出Excel失败: {e}")
            return False

    def generate_report(self, data: ExperimentData, filepath: str, format: str = "pdf") -> bool:
        """生成实验报告"""
        try:
            if not data.timestamps:  # 没有实验数据
                return False

            if format.lower() == "pdf":
                return self._generate_pdf_report(data, filepath)
            elif format.lower() == "docx":
                return self._generate_docx_report(data, filepath)
            elif format.lower() == "xlsx":
                return self._generate_xlsx_report(data, filepath)
            else:
                raise ValueError(f"不支持的报告格式: {format}")

        except Exception as e:
            print(f"生成报告失败: {e}")
            return False

    def _generate_pdf_report(self, data: ExperimentData, filepath: str) -> bool:
        """生成PDF报告"""
        print("PDF报告生成功能尚未实现")
        return False

    def _generate_docx_report(self, data: ExperimentData, filepath: str) -> bool:
        """生成DOCX报告"""
        print("DOCX报告生成功能尚未实现")
        return False

    def _generate_xlsx_report(self, data: ExperimentData, filepath: str) -> bool:
        """生成XLSX报告"""


class ExpSettings:
    """实验参数配置类"""

    def __init__(self):
        self.config_file = PathManager.get_config_path('exp_settings.configs')
        self.default_settings = {
            "project_name": "",  # 项目名称
            "sample_name": "",  # 样品名称
            "sample_id": "",  # 样品编号
            "sample_weight": 0.0,  # 样品初重(g)
            "experiment_type": "GB/T 13241-2017",  # 实验类型
            "operator": "",  # 操作人员
            "date": "",  # 实验日期
            "notes": "",  # 备注说明
        }
        self.settings = self.load_settings()

    def load_settings(self) -> Dict[str, Any]:
        """加载配置"""
        try:
            if not os.path.exists(self.config_file):
                os.makedirs('configs', exist_ok=True)
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(self.default_settings, f, indent=4)
                return self.default_settings

            with open(self.config_file, 'r', encoding='utf-8') as f:
                loaded_settings = json.load(f)
                # 确保所有字段都存在
                for key, value in self.default_settings.items():
                    if key not in loaded_settings:
                        loaded_settings[key] = value
                return loaded_settings
        except Exception as e:
            print(f"加载实验参数配置失败: {e}")
            return self.default_settings

    def save_settings(self) -> None:
        """保存配置"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"保存实验参数配置失败: {e}")
