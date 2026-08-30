import math

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QDialogButtonBox,
                                 QLabel, QDoubleSpinBox, QMessageBox)
from PySide6.QtCore import Qt


def suggest_drum_sample_weight(data_points: list[dict], fallback: float) -> float:
    """优先建议最后一个有效的还原后重量，无法取得时回退到记录样重。"""
    for point in reversed(data_points):
        try:
            weight = float(point.get("weight"))
        except (AttributeError, TypeError, ValueError):
            continue
        if math.isfinite(weight) and weight > 0:
            return weight
    return float(fallback)


class RDIAnalysisDialog(QDialog):
    def __init__(
        self,
        experiment_name: str,
        initial_weight_g: float,
        drum_sample_weight_g: float | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(f"低温粉化(RDI)分析参数 - {experiment_name}")
        self.setMinimumWidth(400)

        self.initial_weight_g = initial_weight_g
        self.data = {}

        layout = QVBoxLayout(self)

        form_layout = QFormLayout()
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight) # Labels right aligned

        # Initial weight display (read-only)
        self.initial_weight_label = QLabel(f"{self.initial_weight_g:.2f} g")
        form_layout.addRow("初始样品重量:", self.initial_weight_label)

        # GB/T 13242 的 RDI 分母是还原后装入转鼓的试样质量 m0。
        self.drum_sample_weight_spinbox = QDoubleSpinBox()
        self.drum_sample_weight_spinbox.setRange(0.01, 100000.0)
        self.drum_sample_weight_spinbox.setDecimals(2)
        self.drum_sample_weight_spinbox.setSuffix(" g")
        suggested_drum_mass = drum_sample_weight_g or self.initial_weight_g
        self.drum_sample_weight_spinbox.setValue(suggested_drum_mass)
        form_layout.addRow("入鼓试样质量 (m0):", self.drum_sample_weight_spinbox)

        # Sieve fractions inputs
        self.mass_gt_6_3_spinbox = QDoubleSpinBox()
        self.mass_gt_6_3_spinbox.setRange(0.0, 100000.0)
        self.mass_gt_6_3_spinbox.setDecimals(2)
        self.mass_gt_6_3_spinbox.setSuffix(" g")
        form_layout.addRow(">6.3mm 部分质量:", self.mass_gt_6_3_spinbox)

        self.mass_3_15_to_6_3_spinbox = QDoubleSpinBox()
        self.mass_3_15_to_6_3_spinbox.setRange(0.0, 100000.0)
        self.mass_3_15_to_6_3_spinbox.setDecimals(2)
        self.mass_3_15_to_6_3_spinbox.setSuffix(" g")
        form_layout.addRow("+3.15mm 至 6.3mm 部分质量:", self.mass_3_15_to_6_3_spinbox)

        self.mass_0_5_to_3_15_spinbox = QDoubleSpinBox()
        self.mass_0_5_to_3_15_spinbox.setRange(0.0, 100000.0)
        self.mass_0_5_to_3_15_spinbox.setDecimals(2)
        self.mass_0_5_to_3_15_spinbox.setSuffix(" g")
        form_layout.addRow("+0.5mm 至 3.15mm 部分质量:", self.mass_0_5_to_3_15_spinbox)

        self.mass_lt_0_5_spinbox = QDoubleSpinBox()
        self.mass_lt_0_5_spinbox.setRange(0.0, 100000.0)
        self.mass_lt_0_5_spinbox.setDecimals(2)
        self.mass_lt_0_5_spinbox.setSuffix(" g")
        form_layout.addRow("<0.5mm 部分质量:", self.mass_lt_0_5_spinbox)

        # Total sieved mass display (read-only, updates dynamically)
        self.total_sieved_mass_label = QLabel("0.00 g")
        form_layout.addRow("筛后总回收质量:", self.total_sieved_mass_label)

        # Connect spinboxes to update total sieved mass
        self.mass_gt_6_3_spinbox.valueChanged.connect(self._update_total_sieved_mass)
        self.mass_3_15_to_6_3_spinbox.valueChanged.connect(self._update_total_sieved_mass)
        self.mass_0_5_to_3_15_spinbox.valueChanged.connect(self._update_total_sieved_mass)
        self.mass_lt_0_5_spinbox.valueChanged.connect(self._update_total_sieved_mass)
        self.drum_sample_weight_spinbox.valueChanged.connect(self._update_total_sieved_mass)

        layout.addLayout(form_layout)

        # Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self._update_total_sieved_mass() # Initial calculation

    def _update_total_sieved_mass(self):
        total = (self.mass_gt_6_3_spinbox.value() +
                 self.mass_3_15_to_6_3_spinbox.value() +
                 self.mass_0_5_to_3_15_spinbox.value() +
                 self.mass_lt_0_5_spinbox.value())
        self.total_sieved_mass_label.setText(f"{total:.2f} g")
        
        drum_sample_weight = self.drum_sample_weight_spinbox.value()
        # 回收率应与入鼓质量比较，而不是还原前样重。
        if abs(total - drum_sample_weight) > (drum_sample_weight * 0.1): # 10% threshold for visual cue
            self.total_sieved_mass_label.setStyleSheet("color: red;")
        elif abs(total - drum_sample_weight) > (drum_sample_weight * 0.05): # 5% threshold
             self.total_sieved_mass_label.setStyleSheet("color: orange;")
        else:
            self.total_sieved_mass_label.setStyleSheet("")


    def accept(self):
        self.data['drum_sample_weight_g'] = self.drum_sample_weight_spinbox.value()
        self.data['mass_gt_6_3'] = self.mass_gt_6_3_spinbox.value()
        self.data['mass_3_15_to_6_3'] = self.mass_3_15_to_6_3_spinbox.value()
        self.data['mass_0_5_to_3_15'] = self.mass_0_5_to_3_15_spinbox.value()
        self.data['mass_lt_0_5'] = self.mass_lt_0_5_spinbox.value()
        
        total_sieved_mass = (
            self.data['mass_gt_6_3']
            + self.data['mass_3_15_to_6_3']
            + self.data['mass_0_5_to_3_15']
            + self.data['mass_lt_0_5']
        )
        drum_sample_weight = self.data['drum_sample_weight_g']

        if abs(total_sieved_mass - drum_sample_weight) > (drum_sample_weight * 0.05):
            reply = QMessageBox.warning(self, "数据核对",
                                        f"筛后各部分质量之和 ({total_sieved_mass:.2f}g) 与入鼓试样质量 ({drum_sample_weight:.2f}g) 相差超过5%。\n\n是否仍要继续分析？",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                        QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return # Don't close the dialog

        super().accept()

    def get_data(self) -> dict:
        return self.data

if __name__ == '__main__':
    from PySide6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    # Example usage:
    dialog = RDIAnalysisDialog(experiment_name="TestRDI-001", initial_weight_g=500.0)
    if dialog.exec():
        print("分析参数已获取:", dialog.get_data())
    else:
        print("用户取消输入。")
    sys.exit()
