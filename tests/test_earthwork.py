"""Unit tests for earthwork fill and road-formation quantities.

The module's own docstring names three ways jobs of this size go wrong, and each
is a way to under-order earth by an amount nobody notices until the site
finishes below level. The tests below pin exactly those, because a numeric error
here is not caught by anything downstream — it is paid for in trailer loads.

The module carries doctests. They pass, but ``pytest.ini`` does not enable
``--doctest-modules``, so they never run in the default suite; the first test
here collects them explicitly so they cannot rot unnoticed.
"""

from __future__ import annotations

import doctest

import pytest

from assethold.property import earthwork
from assethold.property.earthwork import (
    DEFAULT_EARTH_SHRINKAGE,
    NOMINAL_TRAILER_CFT,
    Quantity,
    compaction_layers,
    cubic_metres,
    fill,
    haul_days,
    loads,
    per_running_foot,
    road_formation,
    road_length_table,
    trailer_capacity,
)


def test_module_doctests_all_pass():
    """The worked examples in the docstrings are executable and correct."""
    results = doctest.testmod(earthwork, verbose=False)
    assert results.failed == 0, f"{results.failed} doctest(s) failed"
    assert results.attempted > 0, "no doctests collected — did they get removed?"


# ---------------------------------------------------------------------------
# Failure mode 1: ordered volume is not in-place volume
# ---------------------------------------------------------------------------


def test_fill_orders_more_than_the_finished_volume():
    """Earth is bought loose and ends up compacted; the order carries shrinkage."""
    in_place = 7275 * 4.0
    q = fill(7275, 4.0)
    assert q.cft == pytest.approx(in_place * DEFAULT_EARTH_SHRINKAGE)
    assert q.cft > in_place
    assert q.cft == pytest.approx(32592.0, abs=1.0)


def test_ignoring_shrinkage_under_orders_by_a_material_margin():
    """Guards the trap: the shortfall only shows up when the site finishes low."""
    shortfall = fill(7275, 4.0).cft - fill(7275, 4.0, shrinkage=1.0).cft
    assert shortfall == pytest.approx(7275 * 4.0 * 0.12)
    assert shortfall / fill(7275, 4.0).cft > 0.10  # >10% of the order


def test_quantity_records_the_basis_it_was_computed_from():
    """An order quantity without its basis cannot be checked by anyone else."""
    q = fill(7275, 4.0)
    assert "7,275" in q.basis and "4" in q.basis and "1.12" in q.basis
    assert q.shrinkage == DEFAULT_EARTH_SHRINKAGE
    assert q.label.startswith("Fill")


def test_quantity_converts_to_cubic_metres_and_loads():
    q = fill(7275, 4.0)
    assert q.m3 == pytest.approx(cubic_metres(q.cft))
    assert q.m3 == pytest.approx(922.9, abs=0.1)
    assert q.loads() == pytest.approx(q.cft / NOMINAL_TRAILER_CFT)


def test_quantity_is_frozen():
    """An ordered quantity should not be mutated after it is recorded."""
    with pytest.raises(Exception):
        fill(7275, 4.0).cft = 1.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Failure mode 2: the trailer is not the size everyone says it is
# ---------------------------------------------------------------------------


def test_trailer_capacity_from_measured_dimensions():
    assert trailer_capacity(8, 5, 2.5) == pytest.approx(100.0)
    assert trailer_capacity(8, 5, 2.0) == pytest.approx(80.0)


def test_smaller_trailer_materially_increases_the_load_count():
    """An 80 cft trailer turns a 326-load job into 407 — 25% more haulage."""
    nominal = loads(32592)
    actual = loads(32592, trailer_cft=80)
    assert nominal == pytest.approx(325.9, abs=0.1)
    assert actual == pytest.approx(407.4, abs=0.1)
    assert actual / nominal == pytest.approx(100 / 80)


def test_loads_rejects_a_nonsensical_trailer():
    for bad in (0, -10):
        with pytest.raises(ValueError):
            loads(1000, trailer_cft=bad)


def test_haul_days_scales_with_fleet_and_rate():
    assert haul_days(546) == pytest.approx(546 / 24)
    assert haul_days(546, trailers=6) == pytest.approx(haul_days(546) / 2)
    assert haul_days(546, loads_per_trailer_per_day=16) == pytest.approx(
        haul_days(546) / 2
    )


@pytest.mark.parametrize("trailers,rate", [(0, 8), (3, 0), (-1, 8)])
def test_haul_days_rejects_an_impossible_fleet(trailers, rate):
    with pytest.raises(ValueError):
        haul_days(546, trailers=trailers, loads_per_trailer_per_day=rate)


# ---------------------------------------------------------------------------
# Failure mode 3: road length is guessed, and it is the largest unknown
# ---------------------------------------------------------------------------


def test_road_formation_places_the_wearing_course_inside_the_rise():
    """Reading the rise as earth *plus* a course on top over-orders the earth."""
    earth, gravel = road_formation(70)
    assert earth.cft == pytest.approx(70 * 33 * (5.0 - 0.75) * 1.12)
    assert gravel.cft == pytest.approx(70 * 33 * 0.75 * 1.25)
    over_ordered = 70 * 33 * 5.0 * 1.12  # the mistake
    assert over_ordered - earth.cft == pytest.approx(70 * 33 * 0.75 * 1.12)


def test_road_formation_rejects_a_course_deeper_than_the_rise():
    with pytest.raises(ValueError):
        road_formation(70, rise_ft=0.75, wearing_course_ft=0.75)
    with pytest.raises(ValueError):
        road_formation(70, rise_ft=0.5, wearing_course_ft=0.75)


def test_per_running_foot_is_the_adder_for_an_underestimated_run():
    """A running foot is well over a load of earth — so a paced run matters."""
    earth, gravel = per_running_foot()
    assert earth == pytest.approx(157.1, abs=0.1)
    assert gravel == pytest.approx(30.9, abs=0.1)
    assert earth > NOMINAL_TRAILER_CFT  # over one load per foot of road

    # 100 ft of unanticipated run is a five-figure cubic-foot error.
    assert 100 * earth == pytest.approx(15708, abs=5)


def test_per_running_foot_is_consistent_with_road_formation():
    earth_ft, gravel_ft = per_running_foot()
    earth, gravel = road_formation(250.0)
    assert earth.cft == pytest.approx(earth_ft * 250.0)
    assert gravel.cft == pytest.approx(gravel_ft * 250.0)


def test_road_length_table_turns_a_paced_run_into_a_load_count():
    rows = road_length_table(58.0, runs_ft=(0, 50))
    assert [r["run_ft"] for r in rows] == [0, 50]
    assert rows[0]["total_length_ft"] == pytest.approx(58.0)
    assert rows[1]["total_length_ft"] == pytest.approx(108.0)
    assert round(rows[0]["earth_loads"]) == 91
    assert round(rows[1]["earth_loads"]) == 170
    assert round(rows[0]["gravel_loads"]) == 18
    assert round(rows[1]["gravel_loads"]) == 33


def test_road_length_table_respects_a_measured_trailer():
    """The table must not silently assume the nominal trailer."""
    big = road_length_table(58.0, runs_ft=(0,))[0]
    small = road_length_table(58.0, runs_ft=(0,), trailer_cft=80)[0]
    assert small["earth_cft"] == pytest.approx(big["earth_cft"])  # volume unchanged
    assert small["earth_loads"] == pytest.approx(big["earth_loads"] * 100 / 80)


# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------


def test_compaction_layers_rounds_up_to_a_whole_pass():
    """A part-layer still has to be placed, watered and rolled."""
    assert compaction_layers(4.0) == 6  # 48 in / 9 in
    assert compaction_layers(4.25) == 6  # 51 in -> 5.67, still 6 passes
    assert compaction_layers(4.6) == 7  # 55.2 in -> 6.13, needs a 7th
    assert compaction_layers(0.5) == 1


def test_compaction_layers_honours_a_stated_layer_thickness():
    assert compaction_layers(4.0, layer_in=6.0) == 8
    assert compaction_layers(4.0, layer_in=12.0) == 4


def test_cubic_metres_conversion():
    assert cubic_metres(35.3146667) == pytest.approx(1.0)
    assert cubic_metres(32592) == pytest.approx(922.9, abs=0.1)


def test_quantity_can_be_constructed_directly_and_stays_consistent():
    q = Quantity(label="x", basis="y", cft=1000.0, shrinkage=1.12)
    assert q.loads(trailer_cft=100) == pytest.approx(10.0)
    assert q.m3 == pytest.approx(1000.0 / 35.3146667)
