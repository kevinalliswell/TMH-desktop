from PySide6.QtCore import Qt

from src.ui.models.history_data_table_model import (
    HistoryDataTableModel,
    select_plot_indices,
)


def test_history_table_model_exposes_large_datasets_without_cell_materialization():
    point_count = 100_000
    experiment = {
        "timestamps": [f"sample-{index}" for index in range(point_count)],
        "temperatures": [float(index) for index in range(point_count)],
        "weights": [500.0] * point_count,
        "weight_losses": [0.0] * point_count,
        "gas_flows": {
            "CO": [1.0] * point_count,
            "CO2": [2.0] * point_count,
            "N2": [3.0] * point_count,
            "H2": [4.0] * point_count,
        },
    }
    model = HistoryDataTableModel()

    model.set_experiment(experiment, [index / 60 for index in range(point_count)])

    assert model.rowCount() == point_count
    assert model.columnCount() == 9
    assert model.data(model.index(point_count - 1, 2), Qt.DisplayRole) == "99999.00"


def test_plot_downsampling_is_bounded_and_preserves_endpoints():
    source_indices = list(range(100_000))

    selected = select_plot_indices(source_indices, max_points=2_000)

    assert len(selected) <= 2_000
    assert selected[0] == 0
    assert selected[-1] == 99_999
    assert selected == sorted(set(selected))


def test_plot_downsampling_keeps_small_series_unchanged():
    source_indices = [1, 3, 7]

    assert select_plot_indices(source_indices, max_points=10) == source_indices


def test_plot_downsampling_preserves_measurement_peaks():
    source_indices = list(range(10_000))
    temperatures = [25.0] * 10_000
    temperatures[4_321] = 999.0

    selected = select_plot_indices(
        source_indices,
        series=[temperatures],
        max_points=200,
    )

    assert len(selected) <= 200
    assert 4_321 in selected
