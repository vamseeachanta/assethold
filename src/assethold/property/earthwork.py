"""
earthwork.py — fill and road-formation quantities for a small development, in
the units a tractor driver is actually paid in.

Three things go wrong on jobs this size, and each has a function here whose
whole purpose is to stop it.

**1. Ordered volume is not in-place volume.**  Earth is bought loose and ends up
compacted, so the volume to *order* is the finished volume times a shrinkage
allowance.  Every quantity this module returns is an ordered volume — what to
ask for, not what ends up in the ground.  Mixing the two under-orders by 10-15%
and the shortfall only appears when the site finishes below level.

**2. The trailer is not the size everyone says it is.**  Haulage is counted in
"loads" and a load is nominally 100 cft, but trailers vary and nobody measures
one.  An 80 cft trailer turns a 589-load job into 737 and the difference shows
up nowhere except a site that never reaches level.  ``loads`` takes the trailer
capacity as an explicit argument for that reason, and ``trailer_capacity``
computes it from the three dimensions someone can go and measure.

**3. Road length is guessed, and it is the largest single unknown.**  A road is
formed for the frontage *plus* a tie-in to wherever it meets a made road, and
that run is usually paced long after the earth is ordered.  At full layout width
a running foot is well over a load of earth, so a hundred feet of unanticipated
run is a six-figure quantity error.  ``per_running_foot`` exists to make that
adder explicit and ``road_length_table`` to turn a paced distance straight into
a load count.

Everything is in feet and cubic feet, because that is what the trade quotes in
on this subcontinent; ``cubic_metres`` converts for anyone who needs SI.

Pure standard library.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

CFT_PER_M3 = 35.3146667
NOMINAL_TRAILER_CFT = 100.0

# Defaults are conventional allowances, not measurements. Override them when a
# contractor states his own, and record which was used.
DEFAULT_EARTH_SHRINKAGE = 1.12
DEFAULT_GRAVEL_LOOSE = 1.25


def cubic_metres(cft: float) -> float:
    """
    >>> round(cubic_metres(32592), 1)
    922.9
    """
    return cft / CFT_PER_M3


def trailer_capacity(length_ft: float, width_ft: float, height_ft: float) -> float:
    """Actual capacity of a trailer from its inside dimensions.

    Measure it before the first load, not after the last.

    >>> trailer_capacity(8, 5, 2.5)
    100.0
    >>> trailer_capacity(8, 5, 2.0)
    80.0
    """
    return length_ft * width_ft * height_ft


def loads(volume_cft: float, trailer_cft: float = NOMINAL_TRAILER_CFT) -> float:
    """Trailer loads for a volume, at a stated trailer capacity.

    >>> round(loads(32592), 1)
    325.9
    >>> round(loads(32592, trailer_cft=80), 1)
    407.4
    """
    if trailer_cft <= 0:
        raise ValueError("trailer capacity must be positive")
    return volume_cft / trailer_cft


def haul_days(
    total_loads: float, trailers: int = 3, loads_per_trailer_per_day: int = 8
) -> float:
    """Working days of haulage. Excludes JCB, roller and settlement time.

    >>> round(haul_days(546), 1)
    22.8
    """
    if trailers < 1 or loads_per_trailer_per_day < 1:
        raise ValueError("need at least one trailer doing at least one load")
    return total_loads / (trailers * loads_per_trailer_per_day)


@dataclass(frozen=True)
class Quantity:
    """An ordered quantity, with the basis it was computed from."""

    label: str
    basis: str
    cft: float
    shrinkage: float

    @property
    def m3(self) -> float:
        return cubic_metres(self.cft)

    def loads(self, trailer_cft: float = NOMINAL_TRAILER_CFT) -> float:
        return loads(self.cft, trailer_cft)


def fill(
    area_sqft: float, depth_ft: float, shrinkage: float = DEFAULT_EARTH_SHRINKAGE
) -> Quantity:
    """Earth to order to raise an area by a given depth.

    >>> q = fill(7275, 4.0)
    >>> round(q.cft)
    32592
    >>> round(q.loads())
    326
    """
    return Quantity(
        label=f"Fill {depth_ft:g} ft",
        basis=f"{area_sqft:,.0f} sq ft x {depth_ft:g} ft x {shrinkage:g}",
        cft=area_sqft * depth_ft * shrinkage,
        shrinkage=shrinkage,
    )


def road_formation(
    length_ft: float,
    width_ft: float = 33.0,
    rise_ft: float = 5.0,
    wearing_course_ft: float = 0.75,
    earth_shrinkage: float = DEFAULT_EARTH_SHRINKAGE,
    gravel_loose: float = DEFAULT_GRAVEL_LOOSE,
) -> Tuple[Quantity, Quantity]:
    """Earth and gravel to form a road raised ``rise_ft``.

    ``rise_ft`` is the finished formation level; the gravel wearing course sits
    within it, so the earth beneath is ``rise_ft - wearing_course_ft``.  Reading
    the rise as earth *plus* a course on top over-orders by the course depth on
    the whole area.

    >>> earth, gravel = road_formation(70)
    >>> round(earth.cft), round(gravel.cft)
    (10996, 2166)
    >>> round(earth.loads()), round(gravel.loads())
    (110, 22)
    """
    if wearing_course_ft >= rise_ft:
        raise ValueError("wearing course cannot be as deep as the whole rise")
    earth_depth = rise_ft - wearing_course_ft
    return (
        Quantity(
            label="Road earth",
            basis=f"{length_ft:g} x {width_ft:g} x {earth_depth:g} x {earth_shrinkage:g}",
            cft=length_ft * width_ft * earth_depth * earth_shrinkage,
            shrinkage=earth_shrinkage,
        ),
        Quantity(
            label="Road gravel",
            basis=f"{length_ft:g} x {width_ft:g} x {wearing_course_ft:g} x {gravel_loose:g}",
            cft=length_ft * width_ft * wearing_course_ft * gravel_loose,
            shrinkage=gravel_loose,
        ),
    )


def per_running_foot(
    width_ft: float = 33.0,
    rise_ft: float = 5.0,
    wearing_course_ft: float = 0.75,
    earth_shrinkage: float = DEFAULT_EARTH_SHRINKAGE,
    gravel_loose: float = DEFAULT_GRAVEL_LOOSE,
) -> Tuple[float, float]:
    """Earth and gravel, in cft, for one running foot of road.

    The adder to reach for the moment a road turns out longer than assumed.

    >>> earth, gravel = per_running_foot()
    >>> round(earth, 1), round(gravel, 1)
    (157.1, 30.9)
    """
    earth, gravel = road_formation(
        1.0, width_ft, rise_ft, wearing_course_ft, earth_shrinkage, gravel_loose
    )
    return earth.cft, gravel.cft


def road_length_table(
    frontage_ft: float,
    runs_ft: Sequence[float] = (0, 25, 50, 75, 100, 150),
    width_ft: float = 33.0,
    rise_ft: float = 5.0,
    wearing_course_ft: float = 0.75,
    trailer_cft: float = NOMINAL_TRAILER_CFT,
) -> List[dict]:
    """A lookup from a paced tie-in run to a load count.

    Hand this to whoever is going to walk the road: they pace the distance from
    the frontage to the made road, find the row, and read off what to order.

    >>> t = road_length_table(58.0, runs_ft=(0, 50))
    >>> [(r["run_ft"], round(r["earth_loads"]), round(r["gravel_loads"])) for r in t]
    [(0, 91, 18), (50, 170, 33)]
    """
    rows = []
    for run in runs_ft:
        total = frontage_ft + run
        earth, gravel = road_formation(
            total, width_ft, rise_ft, wearing_course_ft
        )
        rows.append(
            {
                "run_ft": run,
                "total_length_ft": total,
                "earth_cft": earth.cft,
                "earth_loads": earth.loads(trailer_cft),
                "gravel_cft": gravel.cft,
                "gravel_loads": gravel.loads(trailer_cft),
            }
        )
    return rows


def compaction_layers(depth_ft: float, layer_in: float = 9.0) -> int:
    """Compacted layers a fill depth should be placed in.

    Tipped in one lift and levelled, fill of any depth settles unevenly for
    years.  This is the number of watered-and-rolled passes to insist on.

    >>> compaction_layers(4.0)
    6
    >>> compaction_layers(4.25)
    6
    """
    import math

    return int(math.ceil(depth_ft * 12.0 / layer_in))
