# Measuring a parcel from its deed and its survey drawing

How to establish, defensibly, how much land there is and where on it you can build —
starting from documents you already hold, without commissioning a field survey.

The question this answers in practice: *a piece of ground on our site looks usable — how
big is it, and is it actually available?* Getting that wrong in either direction is
expensive, so the method below is built around **checks that can fail**, not around
producing a number.

Module: [`assethold.property.survey_measure`](../api/survey_measure.md).
Pure standard library — no Pillow, no numpy.

---

## The short version

```python
from assethold.property.survey_measure import (
    acres, circular_segment_area, closure_error, polygon_area, traverse,
)

CALLS = [                       # metes and bounds, straight off the field note
    ("N 61-43-40 E", 135.92),
    ("S 28-16-20 E", 326.36),
    ("S 72-11-54 W", 303.40),
    ("N 01-22-43 E", 223.28),   # chord of a right-of-way curve
    ("N 00-15-58 E", 77.85),
    ("N 30-59-49 E", 17.19),    # cut-back corner
]

pts = traverse(CALLS)
area = polygon_area(pts) - circular_segment_area(5750.00, 223.29)

print(closure_error(pts))       # 0.005 ft
print(area, acres(area))        # 68076.6 sq ft, 1.5628 ac
```

If the closure error is large, stop. Either a call was transcribed wrongly or you are
not looking at the parcel you think you are. **That is the point of doing this.**

---

## Step 1 — close the traverse

Walk the calls. A correctly transcribed description returns to its point of beginning.

- **Closure under ~0.05 ft**: the description is internally consistent.
- **Closure of feet or more**: a transposed digit, a missed call, or a bearing quadrant
  read wrongly. A single transposed distance typically throws closure by tens of feet,
  which is exactly why this check is worth the two minutes.

Then compare the computed area with the acreage the surveyor stated. Agreement to a
square foot or two means you have the right parcel and the right calls.

### Curves

Right-of-way boundaries are usually curved. Walk the **chord**, then correct with
`circular_segment_area(radius, arc_length)`:

- arc bulges **into** the parcel (the usual case for a road curving inward) → **subtract**
- arc bulges **away** → **add**

Getting the sign wrong misses by twice the segment. On a long, shallow curve that is a
couple of hundred square feet — small enough to look plausible and still be wrong.

---

## Step 2 — register the drawing

Render the survey sheet to PNG (`pdftoppm -r 200 -png survey.pdf out`), then find the
boundary line work. Boundary lines are plotted **heavier** than dimension lines, leaders
and text, so the widest dark run inside a narrow search band is almost always the boundary:

```python
samples = []
for y in range(600, 2300, 4):
    x_guess = 993 + (y - 509) * 1028 / 1853          # rough line, from eyeballing
    hit = widest_dark_run(img, y, int(x_guess - 38), int(x_guess + 38), min_width=4)
    if hit:
        samples.append((y, hit[0]))
m, c, kept = fit_line_robust(samples)                 # outlier rejection included
```

Intersect two fitted boundary lines to get a corner. Two corners of a boundary line of
known length fix scale and rotation:

```python
frame = RasterFrame(origin_px=NE, end_px=SE, baseline_ft=326.36, interior_px=(700, 1400))
frame.check_bearing("S 28-16-20 E", tolerance_deg=0.5)   # raises if registration is off
```

### Why (u, v) and not pixels

`RasterFrame` measures along the baseline (`u`) and perpendicular to it (`v`). Site
improvements are almost always laid out square to a property line, so in this frame a
building wall or a pavement edge becomes a **constant-`u` or constant-`v` line** — which
is what makes it findable by scanning rather than by clicking.

---

## Step 3 — verify before measuring anything

Three checks, in increasing order of how much they tell you:

| Check | What it catches |
|---|---|
| `check_bearing()` against the recorded bearing | Corner pixels picked from the wrong line. Agreement to ~0.05° is normal; approaching 1° means every downstream number is suspect. |
| Scan for a **dimension you did not use to build the frame** | Systematic scale error. Example: scanning put a building wall 16.7 ft off the property line where the surveyor had dimensioned 16.0 ft. |
| Draw the closed traverse back onto the drawing with `Canvas` | Everything else. A frame that is off is obvious at a glance in a way a residual in degrees is not. |

**Do the third one every time.** It costs one function call and it is the check most
likely to catch the mistake you did not anticipate.

---

## Step 4 — measure the thing you actually care about

Scan along `u` or `v` to locate walls and pavement edges:

```python
frame.scan_profile(img, fixed=50.0, axis="u", lo=60.0, hi=280.0)
# -> [(103.2, 103.6), (211.6, 212.2)]  building's north and south walls, in feet
```

Digitised polygons are then just `polygon_area`. `inset_polygon` applies a uniform
setback for a building line — reliable for convex-ish parcels and modest insets; a deep
inset on a sharp wedge will self-intersect and needs a real straight-skeleton.

### Judge your own precision honestly

A traverse-derived area is **exact** — it comes from the recorded description.
An area bounded partly by something you digitised off a drawing is **not**, and the
error is dominated by how well you read that edge, not by the registration.

A useful self-check: if you digitise a feature that ought to be straight, the read points
should fall in a narrow band. Nine points landing within 16 ft across a 300 ft site says
the edge is real and the reads are consistent. Points scattered over 60 ft say you are
reading noise.

State the resulting tolerance. `±5%` on a digitised area is honest; presenting it to four
significant figures is not.

---

## Failure modes worth knowing

| Symptom | Cause |
|---|---|
| Closure error of tens of feet | Transposed digit in a distance, or a bearing quadrant flipped |
| Area off by a few hundred sq ft, closure fine | Curve segment added instead of subtracted |
| Bearing residual approaching 1° | Corner picked off a dimension line rather than the boundary |
| `widest_dark_run` returns `None` | Search band missed the line, or `min_width` set above the line weight |
| `fit_line_robust` fits nonsense | Search band caught a text block; narrow it, or raise `min_width` |
| Overlay looks right, areas are wrong | Baseline length wrong — check you used the recorded distance, not a scaled one |

## Rendering the source drawing

`pdftoppm` crops **in pixels at the requested dpi**, which is the clean way to zoom into
one corner of a large sheet:

```
pdftoppm -r 300 -x 2500 -y 3000 -W 3000 -H 2700 -png survey.pdf crop
```

Raising `-r` on a **vector** drawing recovers real detail. On a PDF that merely wraps a
**scan**, resolution is capped by the embedded raster — check with `pdfimages -list`
before rendering at 1000 dpi and wondering why the text is still illegible.

## Client data

Per the convention already established in `modules/net_lease`, this repository holds
**abstracted models and methods, not client-identifying data**. Parcel descriptions,
addresses, owners and tenants belong in the relevant private repository. The traverse in
the test suite is real — so that the recomputed area can be pinned against an acreage a
licensed surveyor certified — but carries no location, plat reference or owner.
