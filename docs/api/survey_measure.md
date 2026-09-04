# survey_measure

Measure a parcel from its deed calls and its survey drawing.

Two independent capabilities that are most useful together:

- **`traverse`** walks the metes-and-bounds calls from a deed or ALTA field note and
  closes the figure. The closure error and recomputed area are a free check on the
  surveyor's stated acreage.
- **`RasterFrame`** registers a scanned or plotted survey sheet to that closed traverse,
  so anything visible on the drawing — a building, a pavement edge, a detention basin —
  can be measured in feet rather than scaled by eye.

See the [parcel measurement guide](../guides/parcel-measurement.md) for the end-to-end
workflow, the verification steps that matter, and the failure modes.

!!! warning "Check the registration before trusting a measurement"
    Two mis-picked corner pixels put every downstream area wrong while the overlay still
    looks plausible. Always call [`RasterFrame.check_bearing`][] against a recorded
    bearing, and draw the closed traverse back onto its own drawing with
    [`Canvas`][] before believing a number.

## Bearings and traverses

::: assethold.property.survey_measure.parse_bearing
    options:
      show_root_heading: true
      show_source: true
      docstring_style: google

::: assethold.property.survey_measure.traverse
    options:
      show_root_heading: true
      show_source: true

::: assethold.property.survey_measure.closure_error
    options:
      show_root_heading: true

::: assethold.property.survey_measure.polygon_area
    options:
      show_root_heading: true

::: assethold.property.survey_measure.circular_segment_area
    options:
      show_root_heading: true
      show_source: true

::: assethold.property.survey_measure.acres
    options:
      show_root_heading: true

## Reading the drawing

::: assethold.property.survey_measure.read_png_gray
    options:
      show_root_heading: true

::: assethold.property.survey_measure.GrayImage
    options:
      show_root_heading: true

::: assethold.property.survey_measure.widest_dark_run
    options:
      show_root_heading: true
      show_source: true

::: assethold.property.survey_measure.fit_line_robust
    options:
      show_root_heading: true
      show_source: true

::: assethold.property.survey_measure.intersect
    options:
      show_root_heading: true

## Registering the drawing to the ground

::: assethold.property.survey_measure.RasterFrame
    options:
      show_root_heading: true
      show_source: true
      members_order: source

::: assethold.property.survey_measure.to_baseline_frame
    options:
      show_root_heading: true
      show_source: true

## Geometry helpers

::: assethold.property.survey_measure.segment_intersection
    options:
      show_root_heading: true

::: assethold.property.survey_measure.inset_polygon
    options:
      show_root_heading: true
      show_source: true

## Overlay rendering

::: assethold.property.survey_measure.Canvas
    options:
      show_root_heading: true
      members_order: source
