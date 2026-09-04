# Land development — earthwork & subdivision

Two modules for taking a small, irregular land parcel from "we own this" to "here is
what to order and how many lots it supports".

- **[`earthwork`](#earthwork)** — fill and road-formation quantities, in the units a
  tractor driver is actually paid in.
- **[`subdivide`](#subdivision)** — dividing a roadside parcel into lots that clear a
  minimum-frontage rule.

See the [land subdivision guide](../guides/land-subdivision.md) for how they fit together
and the mistakes each is built to prevent.

!!! warning "These produce order quantities, not estimates"
    Every volume `earthwork` returns is an **ordered** volume — what to ask for, including
    shrinkage — not the finished in-place volume. Mixing the two under-orders by 10–15%,
    and the shortfall only becomes visible when the site finishes below level.

---

## earthwork

::: assethold.property.earthwork.fill
    options:
      show_root_heading: true
      show_source: true
      docstring_style: google

::: assethold.property.earthwork.Quantity
    options:
      show_root_heading: true
      members_order: source

::: assethold.property.earthwork.road_formation
    options:
      show_root_heading: true
      show_source: true

::: assethold.property.earthwork.per_running_foot
    options:
      show_root_heading: true
      show_source: true

::: assethold.property.earthwork.road_length_table
    options:
      show_root_heading: true
      show_source: true

::: assethold.property.earthwork.trailer_capacity
    options:
      show_root_heading: true
      show_source: true

::: assethold.property.earthwork.loads
    options:
      show_root_heading: true
      show_source: true

::: assethold.property.earthwork.haul_days
    options:
      show_root_heading: true

::: assethold.property.earthwork.compaction_layers
    options:
      show_root_heading: true
      show_source: true

::: assethold.property.earthwork.cubic_metres
    options:
      show_root_heading: true

---

## Subdivision

::: assethold.property.subdivide.Parcel
    options:
      show_root_heading: true
      show_source: true
      members_order: source

::: assethold.property.subdivide.Lot
    options:
      show_root_heading: true

::: assethold.property.subdivide.FrontageCheck
    options:
      show_root_heading: true
