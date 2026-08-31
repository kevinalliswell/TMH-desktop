"""Shared serializers for tabular CSV, text, and Excel exports."""

from __future__ import annotations

import csv
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    OPENPYXL_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only in minimal installations
    OPENPYXL_AVAILABLE = False


ProgressCallback = Callable[[int], None]
Rows = Sequence[Sequence[object]]


class TabularExporter:
    """Serialize row-oriented data with one encoding and missing-value policy."""

    @staticmethod
    def write_csv(path: str | Path, rows: Rows, progress: ProgressCallback | None = None) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            TabularExporter._write_delimited_rows(writer, rows, progress)

    @staticmethod
    def write_text(path: str | Path, rows: Rows, progress: ProgressCallback | None = None) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
            TabularExporter._write_delimited_rows(writer, rows, progress)

    @staticmethod
    def _write_delimited_rows(writer, rows: Rows, progress: ProgressCallback | None) -> None:
        total = len(rows)
        for index, row in enumerate(rows, 1):
            writer.writerow(["" if value is None else value for value in row])
            if progress and total:
                progress(int(index / total * 100))

    @staticmethod
    def write_xlsx(
        path: str | Path,
        sheets: Mapping[str, Rows],
        *,
        header_rows: Mapping[str, int] | None = None,
        progress: ProgressCallback | None = None,
    ) -> None:
        if not OPENPYXL_AVAILABLE:
            raise RuntimeError("未安装openpyxl库")

        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        workbook = Workbook()
        workbook.remove(workbook.active)
        total_rows = sum(len(rows) for rows in sheets.values())
        written_rows = 0
        header_rows = header_rows or {}

        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(
            start_color="366092",
            end_color="366092",
            fill_type="solid",
        )
        header_alignment = Alignment(horizontal="center", vertical="center")

        for sheet_name, rows in sheets.items():
            worksheet = workbook.create_sheet(title=sheet_name)
            header_row = header_rows.get(sheet_name)
            for row_index, row in enumerate(rows, 1):
                for column_index, value in enumerate(row, 1):
                    cell = worksheet.cell(row=row_index, column=column_index, value=value)
                    cell.alignment = header_alignment
                    if row_index == header_row:
                        cell.font = header_font
                        cell.fill = header_fill
                written_rows += 1
                if progress and total_rows:
                    progress(int(written_rows / total_rows * 100))
            TabularExporter._fit_columns(worksheet)

        workbook.save(target)

    @staticmethod
    def _fit_columns(worksheet) -> None:
        for column in worksheet.columns:
            max_length = max(
                (len(str(cell.value)) for cell in column if cell.value is not None),
                default=0,
            )
            worksheet.column_dimensions[column[0].column_letter].width = min(
                max_length + 2,
                50,
            )
