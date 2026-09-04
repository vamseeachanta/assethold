# Subdividing and filling a small land parcel

Taking an irregular roadside parcel to a layout you can price: how many lots it really
supports, and what to order to build it.

Modules: [`assethold.property.subdivide`](../api/land_development.md#subdivision) and
[`assethold.property.earthwork`](../api/land_development.md#earthwork).
Pure standard library.

---

## The one thing that decides the layout

**Frontage and area are two different constraints, and the binding one is almost always
frontage.**

A parcel bounded by a road is rarely the rectangle its deed describes. Once the opposite
boundary has been encroached — or was never straight — the depth varies along the road.
Then:

- dividing into *n* equal-**area** lots does **not** give *n* equal frontages;
- a minimum-frontage rule bites on the **shortest** road edge, not the mean;
- so a parcel whose *average* depth comfortably clears the rule can still fail at one end.

**That failure is invisible in any area-based calculation.** It is the reason to start
with `check_frontage`, not with total square yards.

### A worked case

A parcel 120 ft between two roads, measured at three stations: 58.0 ft deep at the west
road, 60.5 ft at the midpoint, 63.5 ft at the east road.

```python
from assethold.property.subdivide import Parcel

p = Parcel(stations=[0, 60, 120], depths=[58.0, 60.5, 63.5])
p.area_sqft          # 7275.0
p.area_sqyd          # 808.33
p.frontage("west")   # 58.0
p.frontage("east")   # 63.5
```

Three lots off the **east** road get 21.2 ft of frontage each and clear a 6 m minimum.
Three off the **west** road get 19.3 ft — 5.89 m — and **fail by eleven centimetres**.

The parcel supports **five** lots, not six. Nothing about the 808 sq yd total says so.

---

## Step 1 — measure depth at stations, not once

Three stations on a 120 ft edge is a sketch, not a survey. Area is computed by the
trapezoidal rule between stations, which assumes the boundary runs straight from one to
the next — it usually does not.

**Treat the result as good enough to plan on and not good enough to register on.** For a
real metes-and-bounds boundary, close the traverse instead — see the
[parcel measurement guide](parcel-measurement.md).

Record measurements as **conservative estimates** where that is what they are, and say so
in the file. A tape reading reported as a survey figure will be relied on as one.

---

## Step 2 — test frontage before area

`max_lots_on_edge` answers the question that actually decides the layout: given the
minimum frontage rule, how many lots does *this* edge support? Run it on both edges and
take the smaller. The area check is a sanity test afterwards, not the driver.

If the deed area and the measured area disagree, **price on the measured area**. The
shortfall is land standing outside the fence, and a buyer will pay for what is inside it.

---

## Step 3 — order the earth

```python
from assethold.property.earthwork import fill, road_formation, road_length_table

q = fill(area_sqft=7275, depth_ft=4.0)
q.cft          # 32592  — ordered, includes 1.12 shrinkage
q.loads()      # 325.9  — at a nominal 100 cft trailer
q.basis        # "7,275 sq ft x 4 ft x 1.12"
```

Three traps, each with a function whose whole purpose is to stop it:

### 1. Ordered volume is not in-place volume

Earth is bought loose and ends up compacted. Every quantity returned is an **ordered**
volume. Ignoring shrinkage under-orders by 10–15%, and the shortfall appears only when the
site finishes below level.

### 2. The trailer is not the size everyone says it is

A "load" is nominally 100 cft. Trailers vary and nobody measures one. An 80 cft trailer
turns a 326-load job into 407 — **25% more haulage**, appearing nowhere except a site that
never reaches level.

```python
from assethold.property.earthwork import trailer_capacity
trailer_capacity(8, 5, 2.0)   # 80.0 — measure it before the first load
```

### 3. Road length is guessed, and it is the largest single unknown

A road is formed for the frontage **plus** a tie-in to wherever it meets a made road, and
that run is usually paced long after the earth is ordered. At full layout width, one
running foot is **over one trailer load** of earth — so a hundred feet of unanticipated
run is a five-figure cubic-foot error.

`road_length_table` produces a lookup to hand to whoever walks the road: they pace the
distance, find the row, read off what to order.

!!! note "The wearing course sits inside the rise"
    `road_formation` treats `rise_ft` as the finished formation level, with the gravel
    course **within** it — so the earth beneath is `rise_ft - wearing_course_ft`. Reading
    the rise as earth *plus* a course on top over-orders the earth by the course depth
    across the whole road area.

---

## Step 4 — insist on layered compaction

```python
from assethold.property.earthwork import compaction_layers
compaction_layers(4.0)   # 6 passes at 9 in per layer
```

Fill tipped in one lift and levelled settles unevenly for years. This is the number of
watered-and-rolled passes to write into the contractor's scope.

---

## Defaults are conventions, not measurements

`DEFAULT_EARTH_SHRINKAGE = 1.12` and `DEFAULT_GRAVEL_LOOSE = 1.25` are conventional
allowances. **Override them when a contractor states his own, and record which was used.**
A quantity whose basis is not recorded cannot be checked by anyone else, which is why
`Quantity` carries `basis` alongside the number.

## Client data

Parcel identities, owners, deeds and prices belong in the relevant **private** repository.
This module holds the method. See the convention in
[`modules/net_lease`](../api/net_lease.md): *"Abstracted tenant profile — no
client-identifying data."*
