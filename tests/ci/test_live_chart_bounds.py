"""The live chart must stay bounded for a multi-hour run.

ChartTabs appended to unbounded lists and re-uploaded the entire history to all
14 curves on every 1 Hz sample — O(n) per second, so the GUI thread saturates
partway through a long GB/T run and never recovers. The history page already
caps points and downsamples; the live page did not.
"""
import pytest

from src.ui.ui_components.chart_tabs import BoundedSeries, ChartTabs


def test_series_stays_within_its_cap():
    series = BoundedSeries(max_points=100)
    for i in range(10_000):
        series.append(float(i), float(i))

    assert len(series) <= 100


def test_series_keeps_the_full_time_span_rather_than_dropping_history():
    """Halving resolution must preserve the start of the run, not evict it."""
    series = BoundedSeries(max_points=100)
    for i in range(10_000):
        series.append(float(i), float(i))

    assert series.x[0] == 0.0, "折半降采样必须保住实验起点，而不是丢弃升温段"
    assert series.x[-1] >= 9_000.0
    assert series.x == sorted(series.x)


def test_series_pairs_stay_aligned():
    series = BoundedSeries(max_points=64)
    for i in range(5_000):
        series.append(float(i), float(i) * 2)

    assert len(series.x) == len(series.y)
    assert all(y == pytest.approx(x * 2) for x, y in zip(series.x, series.y))


def test_series_clear_resets_the_stride():
    series = BoundedSeries(max_points=8)
    for i in range(1_000):
        series.append(float(i), float(i))
    series.clear()

    assert len(series) == 0
    series.append(1.0, 1.0)
    series.append(2.0, 2.0)
    assert series.x == [1.0, 2.0], "清空后必须回到逐点记录，而非保留旧的降采样步长"


def test_small_runs_are_not_downsampled_at_all():
    series = BoundedSeries(max_points=5000)
    for i in range(3_600):  # one hour at 1 Hz
        series.append(float(i), float(i))

    assert len(series) == 3_600
    assert series.x[:3] == [0.0, 1.0, 2.0]


def test_chart_tabs_declares_bounds_matching_the_history_page():
    assert ChartTabs.MAX_LIVE_POINTS == 5000
    assert ChartTabs.MAX_TABLE_ROWS >= 1000


def test_cost_per_append_does_not_grow_with_run_length():
    """Amortised bound: total appended points stay proportional to the cap."""
    series = BoundedSeries(max_points=1000)
    for i in range(100_000):
        series.append(float(i), float(i))

    # With unbounded growth this would be 100k; with halving it stays ~cap.
    assert len(series) <= 1000
