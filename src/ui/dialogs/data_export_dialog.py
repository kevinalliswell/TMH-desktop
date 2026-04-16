# src/ui/dialogs/data_export_dialog.py
"""
数据导出对话框 - UI 层组件
负责展示导出选项界面，调用 DataSaver 执行实际保存操作
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QCheckBox, QMessageBox, QTableWidget, QFileDialog
)

from src.utils.data_saver import DataSaver


class DataExportDialog:
    """
    数据导出对话框
    提供格式选择和保存选项
    """

    @staticmethod
    def show_export_dialog(data_table: QTableWidget, parent=None,
                           experiment_info: dict = None) -> bool:
        """
        显示数据导出对话框

        Args:
            data_table: 要导出的数据表格
            parent: 父窗口
            experiment_info: 实验信息字典

        Returns:
            bool: 是否成功导出
        """
        dialog = QDialog(parent)
        dialog.setWindowTitle("导出实验数据")
        dialog.setModal(True)
        dialog.resize(400, 200)

        layout = QVBoxLayout()

        # 格式选择
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("导出格式:"))
        format_combo = QComboBox()
        format_combo.addItems(['CSV', 'XLS', 'TXT'])
        format_layout.addWidget(format_combo)
        layout.addLayout(format_layout)

        # 选项
        include_headers = QCheckBox("包含表头")
        include_headers.setChecked(True)
        layout.addWidget(include_headers)

        # 按钮
        button_layout = QHBoxLayout()
        export_btn = QPushButton("导出")
        cancel_btn = QPushButton("取消")
        button_layout.addWidget(export_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

        dialog.setLayout(layout)

        # 连接信号
        export_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)

        if dialog.exec() == QDialog.Accepted:
            format_type = format_combo.currentText().lower()

            # 在 UI 层从 QTableWidget 提取纯数据
            data = DataSaver.extract_table_data_from_widget(
                data_table, include_headers=include_headers.isChecked()
            )

            # 获取保存路径
            file_path = DataExportDialog._get_save_file_path(
                format_type, experiment_info
            )
            if not file_path:
                return False

            # 使用纯数据层的 DataSaver 保存
            saver = DataSaver()

            def on_progress(progress):
                export_btn.setText(f"导出中... {progress}%")

            def on_finished(success, message):
                if success:
                    QMessageBox.information(dialog, "成功", message)
                else:
                    QMessageBox.critical(dialog, "错误", message)

            saver.set_progress_callback(on_progress)
            saver.set_finished_callback(on_finished)

            return saver.save_data(
                data,
                file_path=file_path,
                format_type=format_type,
                experiment_info=experiment_info
            )

        return False

    @staticmethod
    def _get_save_file_path(format_type: str,
                            experiment_info: dict = None) -> str:
        """获取保存文件路径"""
        if experiment_info:
            default_name = DataSaver.generate_filename(experiment_info, format_type)
        else:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            default_name = f"实验数据_{timestamp}.{format_type.lower()}"

        filters = {
            'csv': "CSV文件 (*.csv)",
            'xls': "Excel文件 (*.xlsx)",
            'txt': "文本文件 (*.txt)"
        }

        file_path, _ = QFileDialog.getSaveFileName(
            None,
            f"保存实验数据为{format_type.upper()}格式",
            default_name,
            filters.get(format_type.lower(), "所有文件 (*.*)")
        )

        return file_path if file_path else None
