"""Tests for dividing an irregular roadside parcel.

The case that matters is the one an area calculation cannot see: a parcel whose
average depth clears a minimum-frontage rule comfortably while one of its road
edges does not.  Getting that wrong does not produce an error, it produces a
layout that is refused at the planning counter after the earthwork is paid for.

Figures are pinned against a real measured parcel — 120 ft between two roads,
58.0 / 60.5 / 63.5 ft deep at west, middle and east — and against hand
calculation, not against this module's own output.
"""

from __future__ import annotations

import pytest

from assethold.property.subdivide import FT_PER_M, Lot, Parcel


@pytest.fixture
def parcel() -> Parcel:
    """120 ft between two roads; south boundary encroached, deepest at the west."""
    return Parcel(stations=[0, 60, 120], depths=[58.0, 60.5, 63.5])


class TestArea:
    def test_trapezoidal_area_matches_hand_calculation(self, parcel):
        # west half (58.0 + 60.5)/2 * 60 = 3555; east half (60.5 + 63.5)/2 * 60 = 3720
        assert parcel.area_between(0, 60) == pytest.approx(3555.0)
        assert parcel.area_between(60, 120) == pytest.approx(3720.0)
        assert parcel.area_sqft == pytest.approx(7275.0)
        assert parcel.area_sqyd == pytest.approx(808.333, abs=1e-3)

    def test_a_rectangle_is_the_degenerate_case(self):
        p = Parcel([0, 120], [64.0, 64.0])
        assert p.area_sqft == pytest.approx(120 * 64.0)

    def test_deficit_against_a_deed_area(self, parcel):
        assert parcel.deficit_sqyd(851.667) == pytest.approx(43.333, abs=1e-3)

    def test_deficit_as_a_depth_reads_better_than_an_area(self, parcel):
        # 43.33 sq yd over a 120 ft edge is 3.25 ft of depth, on average
        assert parcel.mean_depth_lost(851.667) == pytest.approx(3.25, abs=1e-2)

    def test_area_is_additive_across_an_arbitrary_cut(self, parcel):
        cut = 49.3
        assert parcel.area_between(0, cut) + parcel.area_between(
            cut, 120
        ) == pytest.approx(parcel.area_sqft)


class TestFrontageRule:
    """The check that decides the layout."""

    def test_three_lots_fail_on_the_shallow_edge(self, parcel):
        c = parcel.check_frontage(3, "west", minimum_m=6.0)
        assert not c.passes
        assert c.frontage_ft == pytest.approx(58.0 / 3)
        assert c.frontage_m == pytest.approx(5.8928, abs=1e-4)
        assert c.shortfall_m == pytest.approx(0.1072, abs=1e-4)

    def test_the_same_three_lots_pass_on_the_deep_edge(self, parcel):
        assert parcel.check_frontage(3, "east", minimum_m=6.0).passes

    def test_average_depth_would_have_passed_and_that_is_the_trap(self, parcel):
        """Mean depth is 60.67 ft; three lots off *that* clears 6 m easily.

        The rule bites on the shortest edge, so an area- or average-based
        check gives the wrong answer with no warning.
        """
        mean_depth = parcel.area_sqft / parcel.width_ft
        assert mean_depth / 3 * 0.3048 > 6.0  # the misleading calculation
        assert not parcel.check_frontage(3, "west").passes  # the real one

    def test_two_lots_clear_the_shallow_edge(self, parcel):
        c = parcel.check_frontage(2, "west", minimum_m=6.0)
        assert c.passes
        assert c.frontage_ft == pytest.approx(29.0)

    def test_edge_needed_says_how_short_the_survey_is(self, parcel):
        c = parcel.check_frontage(3, "west", minimum_m=6.0)
        assert c.edge_needed_ft == pytest.approx(3 * 6.0 * FT_PER_M)
        assert c.edge_needed_ft == pytest.approx(59.055, abs=1e-3)
        # a resurvey finding 1'-1" more would restore the third lot
        assert c.edge_needed_ft - 58.0 == pytest.approx(1.055, abs=1e-3)

    def test_max_lots_differs_between_the_two_edges(self, parcel):
        assert parcel.max_lots_on_edge("west") == 2
        assert parcel.max_lots_on_edge("east") == 3

    def test_a_looser_rule_restores_the_third_lot(self, parcel):
        assert parcel.check_frontage(3, "west", minimum_m=5.5).passes

    def test_zero_lots_is_rejected(self, parcel):
        with pytest.raises(ValueError):
            parcel.check_frontage(0, "west")


class TestDivision:
    def test_equal_area_line_is_not_the_proportional_midpoint(self, parcel):
        """2 lots west + 3 east: proportional would be 48 ft, the answer is 49.3."""
        offset = parcel.equal_area_offset(2, 3)
        assert offset == pytest.approx(49.30, abs=0.01)
        assert offset != pytest.approx(120 * 2 / 5, abs=0.5)

    def test_equal_area_division_gives_five_matching_lots(self, parcel):
        lots = parcel.divide(2, 3)
        assert len(lots) == 5
        areas = [l.area_sqyd for l in lots]
        assert all(a == pytest.approx(161.667, abs=1e-3) for a in areas)
        assert sum(a for a in areas) == pytest.approx(parcel.area_sqyd)

    def test_equal_areas_do_not_mean_equal_frontages(self, parcel):
        """The whole point: equal lots, unequal road frontages."""
        lots = parcel.divide(2, 3)
        west = [l for l in lots if l.edge == "west"]
        east = [l for l in lots if l.edge == "east"]
        assert west[0].frontage_ft == pytest.approx(29.0)
        assert east[0].frontage_ft == pytest.approx(21.167, abs=1e-3)
        assert west[0].area_sqyd == pytest.approx(east[0].area_sqyd)

    def test_every_lot_clears_the_rule_in_the_chosen_layout(self, parcel):
        for lot in parcel.divide(2, 3):
            assert lot.frontage_m >= 6.0

    def test_holding_the_line_on_a_title_boundary_gives_unequal_lots(self, parcel):
        """Avoids amalgamating two titles, at the cost of two ticket sizes."""
        lots = parcel.divide(2, 3, equal_area=False, offset=60.0)
        assert [round(l.area_sqyd, 2) for l in lots] == [
            197.5,
            197.5,
            137.78,
            137.78,
            137.78,
        ]
        assert sum(l.area_sqft for l in lots) == pytest.approx(parcel.area_sqft)

    def test_a_dividing_line_outside_the_parcel_is_rejected(self, parcel):
        with pytest.raises(ValueError):
            parcel.divide(2, 3, equal_area=False, offset=130.0)

    def test_lot_depth_reflects_which_side_of_the_line_it_is(self, parcel):
        lots = parcel.divide(2, 3)
        assert lots[0].depth_ft == pytest.approx(49.30, abs=0.01)
        assert lots[-1].depth_ft == pytest.approx(70.70, abs=0.01)
        assert lots[0].depth_ft + lots[-1].depth_ft == pytest.approx(120.0)


class TestCorners:
    def test_shared_corners_are_counted_once(self, parcel):
        """5 lots x 4 corners is 20; a surveyor sets 12."""
        assert parcel.corner_count(2, 3) == 12

    def test_a_single_lot_has_only_the_outer_corners(self, parcel):
        assert parcel.corner_count(1, 1) == 6


class TestConstruction:
    def test_mismatched_inputs_are_rejected(self):
        with pytest.raises(ValueError):
            Parcel([0, 60, 120], [58.0, 63.5])

    def test_unsorted_stations_are_rejected(self):
        with pytest.raises(ValueError):
            Parcel([0, 120, 60], [58.0, 60.5, 63.5])

    def test_a_negative_depth_is_rejected(self):
        with pytest.raises(ValueError):
            Parcel([0, 120], [58.0, -1.0])

    def test_depth_outside_the_parcel_is_rejected(self, parcel):
        with pytest.raises(ValueError):
            parcel.depth_at(200.0)

    def test_interpolation_is_linear_between_stations(self, parcel):
        assert parcel.depth_at(30) == pytest.approx(59.25)
        assert parcel.depth_at(49.3) == pytest.approx(60.054, abs=1e-3)
