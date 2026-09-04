"""
subdivide.py — divide an irregular roadside parcel into lots that clear a
minimum-frontage rule.

The arithmetic is trivial.  What is not trivial, and what this module exists to
make hard to get wrong, is that **frontage and area are two different
constraints and the binding one is usually frontage.**

A parcel bounded by a road is almost never the rectangle its deed describes.
Once an opposite boundary has been encroached — or was simply never straight —
the depth varies along the road, and then:

  * dividing the parcel into *n* equal-area lots does **not** give *n* equal
    frontages;
  * the minimum-frontage rule bites on the **shortest** road edge, not the mean;
  * so a parcel whose *average* depth comfortably clears the rule can still fail
    at one end, and the failure is invisible in any area-based calculation.

A worked case: a parcel 120 ft between two roads, measured 58.0 ft deep at the
west road, 60.5 ft at the midpoint and 63.5 ft at the east road.  Three lots off
the east road get 21.2 ft of frontage each and clear a 6 m minimum; three off the
west road get 19.3 ft — 5.89 m — and fail it by eleven centimetres.  The parcel
supports five lots, not six, and no amount of looking at the 808 sq yd total
would have said so.

``Parcel.check_frontage`` is therefore the function to reach for first, and
``max_lots_on_edge`` answers the question that actually decides a layout.

Area is by the trapezoidal rule between measured stations, which assumes the
boundary runs straight from one station to the next.  It usually does not.
Three stations on a 120 ft edge is a sketch, not a survey — treat the result as
good enough to plan on and not good enough to register on, and see
``survey_measure.py`` for closing a real metes-and-bounds traverse.

Pure standard library.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

FT_PER_M = 1 / 0.3048
SQFT_PER_SQYD = 9.0  # a "gajam" / square yard


@dataclass(frozen=True)
class Lot:
    """One lot in a division.

    ``frontage`` is measured on the road edge — the dimension a planning rule
    tests.  ``depth`` runs away from that road.  ``area_sqft`` is the true
    trapezoidal area, which will differ from ``frontage * depth`` whenever the
    lot is not a rectangle.
    """

    name: str
    edge: str
    frontage_ft: float
    depth_ft: float
    area_sqft: float

    @property
    def area_sqyd(self) -> float:
        return self.area_sqft / SQFT_PER_SQYD

    @property
    def frontage_m(self) -> float:
        return self.frontage_ft * 0.3048


@dataclass(frozen=True)
class FrontageCheck:
    """Result of testing a proposed division against a minimum-frontage rule."""

    n_lots: int
    frontage_ft: float
    frontage_m: float
    minimum_m: float
    passes: bool
    shortfall_m: float
    edge_needed_ft: float

    def __str__(self) -> str:  # pragma: no cover - convenience only
        verdict = "clears" if self.passes else "FAILS"
        return (
            f"{self.n_lots} lots -> {self.frontage_ft:.2f} ft "
            f"({self.frontage_m:.2f} m) each, {verdict} the "
            f"{self.minimum_m:.2f} m minimum"
        )


class Parcel:
    """A parcel measured as depths at stations along a baseline.

    ``stations`` are distances along the baseline (typically the north
    boundary), ``depths`` the perpendicular depth measured at each.  The first
    and last stations are the two side edges; where those sides front roads,
    their depths *are* the road frontages.

    >>> p = Parcel(stations=[0, 60, 120], depths=[58.0, 60.5, 63.5])
    >>> round(p.area_sqft, 1)
    7275.0
    >>> round(p.area_sqyd, 2)
    808.33
    >>> p.frontage("west"), p.frontage("east")
    (58.0, 63.5)
    """

    def __init__(self, stations: Sequence[float], depths: Sequence[float]):
        if len(stations) != len(depths):
            raise ValueError("stations and depths must be the same length")
        if len(stations) < 2:
            raise ValueError("need at least two stations")
        if list(stations) != sorted(stations):
            raise ValueError("stations must increase along the baseline")
        if any(d <= 0 for d in depths):
            raise ValueError("depths must be positive")
        self.stations = [float(s) for s in stations]
        self.depths = [float(d) for d in depths]

    # -- geometry -----------------------------------------------------------

    @property
    def width_ft(self) -> float:
        """Baseline length — the distance between the two side edges."""
        return self.stations[-1] - self.stations[0]

    def depth_at(self, x: float) -> float:
        """Depth at any point on the baseline, interpolated between stations.

        >>> p = Parcel([0, 60, 120], [58.0, 60.5, 63.5])
        >>> round(p.depth_at(49.3), 3)
        60.054
        """
        if x < self.stations[0] or x > self.stations[-1]:
            raise ValueError(f"{x} is outside the parcel")
        for i in range(len(self.stations) - 1):
            x0, x1 = self.stations[i], self.stations[i + 1]
            if x0 <= x <= x1:
                d0, d1 = self.depths[i], self.depths[i + 1]
                if x1 == x0:
                    return d0
                return d0 + (d1 - d0) * (x - x0) / (x1 - x0)
        raise AssertionError("unreachable")

    def area_between(self, x0: float, x1: float) -> float:
        """Trapezoidal area of the strip between two baseline offsets.

        >>> p = Parcel([0, 60, 120], [58.0, 60.5, 63.5])
        >>> round(p.area_between(0, 60), 1)
        3555.0
        >>> round(p.area_between(60, 120), 1)
        3720.0
        """
        if x1 < x0:
            x0, x1 = x1, x0
        cuts = [x0] + [s for s in self.stations if x0 < s < x1] + [x1]
        total = 0.0
        for a, b in zip(cuts, cuts[1:]):
            total += (self.depth_at(a) + self.depth_at(b)) / 2 * (b - a)
        return total

    @property
    def area_sqft(self) -> float:
        return self.area_between(self.stations[0], self.stations[-1])

    @property
    def area_sqyd(self) -> float:
        return self.area_sqft / SQFT_PER_SQYD

    def frontage(self, edge: str) -> float:
        """Depth at one side edge — the road frontage where that side is a road.

        ``edge`` is "start"/"west"/"left" or "end"/"east"/"right"; the compass
        names are aliases for the two ends of the baseline and carry no bearing.
        """
        e = edge.lower()
        if e in ("start", "west", "left", "first"):
            return self.depths[0]
        if e in ("end", "east", "right", "last"):
            return self.depths[-1]
        raise ValueError(f"unknown edge {edge!r}")

    def deficit_sqyd(self, stated_sqyd: float) -> float:
        """How far the measured area falls short of a stated (deed) area.

        Positive means the ground is smaller than the paper.

        >>> p = Parcel([0, 60, 120], [58.0, 60.5, 63.5])
        >>> round(p.deficit_sqyd(851.667), 2)
        43.33
        """
        return stated_sqyd - self.area_sqyd

    def mean_depth_lost(self, stated_sqyd: float) -> float:
        """Deficit expressed as an average depth lost along the baseline.

        More legible than an area when arguing about an encroached boundary.

        >>> p = Parcel([0, 60, 120], [58.0, 60.5, 63.5])
        >>> round(p.mean_depth_lost(851.667), 2)
        3.25
        """
        return self.deficit_sqyd(stated_sqyd) * SQFT_PER_SQYD / self.width_ft

    # -- the frontage rule --------------------------------------------------

    def check_frontage(
        self, n_lots: int, edge: str, minimum_m: float = 6.0
    ) -> FrontageCheck:
        """Test *n* lots off one edge against a minimum-frontage rule.

        This is the check that decides a layout, and the one an area-based
        calculation silently skips.

        >>> p = Parcel([0, 60, 120], [58.0, 60.5, 63.5])
        >>> c = p.check_frontage(3, "west")
        >>> c.passes, round(c.frontage_m, 2)
        (False, 5.89)
        >>> round(c.edge_needed_ft, 2)
        59.06
        >>> p.check_frontage(3, "east").passes
        True
        >>> p.check_frontage(2, "west").passes
        True
        """
        if n_lots < 1:
            raise ValueError("n_lots must be at least 1")
        edge_ft = self.frontage(edge)
        each_ft = edge_ft / n_lots
        each_m = each_ft * 0.3048
        needed_ft = minimum_m * FT_PER_M * n_lots
        return FrontageCheck(
            n_lots=n_lots,
            frontage_ft=each_ft,
            frontage_m=each_m,
            minimum_m=minimum_m,
            passes=each_m >= minimum_m,
            shortfall_m=max(0.0, minimum_m - each_m),
            edge_needed_ft=needed_ft,
        )

    def max_lots_on_edge(self, edge: str, minimum_m: float = 6.0) -> int:
        """Most lots one edge will carry without breaking the frontage rule.

        >>> p = Parcel([0, 60, 120], [58.0, 60.5, 63.5])
        >>> p.max_lots_on_edge("west"), p.max_lots_on_edge("east")
        (2, 3)
        """
        edge_ft = self.frontage(edge)
        return int(edge_ft / (minimum_m * FT_PER_M) + 1e-9)

    # -- dividing -----------------------------------------------------------

    def equal_area_offset(self, n_start: int, n_end: int) -> float:
        """Baseline offset of the dividing line that makes every lot equal.

        Splits the parcel into a start-edge group of ``n_start`` lots and an
        end-edge group of ``n_end``, choosing the dividing line so that all
        ``n_start + n_end`` lots have the same area.  On a parcel of varying
        depth this line is *not* at the proportional midpoint.

        >>> p = Parcel([0, 60, 120], [58.0, 60.5, 63.5])
        >>> round(p.equal_area_offset(2, 3), 2)
        49.3
        """
        if n_start < 1 or n_end < 1:
            raise ValueError("both groups need at least one lot")
        target = self.area_sqft * n_start / (n_start + n_end)
        lo, hi = self.stations[0], self.stations[-1]
        for _ in range(200):
            mid = (lo + hi) / 2
            if self.area_between(self.stations[0], mid) < target:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    def divide(
        self,
        n_start: int,
        n_end: int,
        start_edge: str = "west",
        end_edge: str = "east",
        equal_area: bool = True,
        offset: Optional[float] = None,
    ) -> List[Lot]:
        """Lay out the lots.

        With ``equal_area`` the dividing line is solved so every lot matches;
        pass ``offset`` instead to put it somewhere specific — on an existing
        title boundary, say, which avoids having to amalgamate two parcels
        before re-dividing them.

        Lots within a group are cut by equal fractions of both bounding edges,
        which on a straight-sided figure gives exactly equal areas.

        >>> p = Parcel([0, 60, 120], [58.0, 60.5, 63.5])
        >>> lots = p.divide(2, 3)
        >>> [round(l.area_sqyd, 2) for l in lots]
        [161.67, 161.67, 161.67, 161.67, 161.67]
        >>> round(lots[0].frontage_ft, 2), round(lots[-1].frontage_ft, 2)
        (29.0, 21.17)

        Held on the title line instead, the lots come out unequal:

        >>> lots = p.divide(2, 3, equal_area=False, offset=60.0)
        >>> [round(l.area_sqyd, 2) for l in lots]
        [197.5, 197.5, 137.78, 137.78, 137.78]
        """
        if offset is None:
            offset = (
                self.equal_area_offset(n_start, n_end)
                if equal_area
                else (self.stations[0] + self.stations[-1]) / 2
            )
        x0, x1 = self.stations[0], self.stations[-1]
        if not x0 < offset < x1:
            raise ValueError("dividing line falls outside the parcel")

        lots: List[Lot] = []
        n = 1
        start_area = self.area_between(x0, offset)
        for i in range(n_start):
            lots.append(
                Lot(
                    name=f"Lot {n}",
                    edge=start_edge,
                    frontage_ft=self.depths[0] / n_start,
                    depth_ft=offset - x0,
                    area_sqft=start_area / n_start,
                )
            )
            n += 1
        end_area = self.area_between(offset, x1)
        for i in range(n_end):
            lots.append(
                Lot(
                    name=f"Lot {n}",
                    edge=end_edge,
                    frontage_ft=self.depths[-1] / n_end,
                    depth_ft=x1 - offset,
                    area_sqft=end_area / n_end,
                )
            )
            n += 1
        return lots

    def corner_count(self, n_start: int, n_end: int) -> int:
        """Distinct boundary stones a division needs.

        Shared corners are counted once — which is what a surveyor sets, and
        typically well under the four-per-lot a contractor will quote.

        >>> Parcel([0, 60, 120], [58.0, 60.5, 63.5]).corner_count(2, 3)
        12
        """
        outer = 4
        on_start_edge = n_start - 1
        on_end_edge = n_end - 1
        on_baselines = 2  # dividing line meets the two long boundaries
        on_dividing_line = (n_start - 1) + (n_end - 1)
        return outer + on_start_edge + on_end_edge + on_baselines + on_dividing_line
