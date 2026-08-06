"""Unit tests for the land-holdings imagery review builder.

Pure logic only - projection maths, roster validation, image cropping and HTML
shaping. Nothing here touches the network.

Two things are worth guarding hardest:

* **The Mercator extent baked into each page.** The page places a coordinate
  the reader types in by interpolating against `merc_box`. If that box is
  wrong, or the latitude correction in `view_box` is dropped, the probe lands
  somewhere plausible-looking and wrong - the failure is silent.
* **The precision machinery.** These pages exist to say how well a plot is
  located. A precision that silently defaults, or an uncertainty ring that
  stops being drawn, turns an honest "somewhere in this village" into what
  looks like a survey pin.
"""

from __future__ import annotations

import html as html_mod
import json
import math
import sys
from pathlib import Path

import pytest

pytest.importorskip("PIL", reason="pillow is needed for the review builder")
pytest.importorskip("yaml")

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts" / "python" / "india_land_maps"
sys.path.insert(0, str(SCRIPTS))

import build_site_review as rev  # noqa: E402
from PIL import Image  # noqa: E402

pytestmark = pytest.mark.unit

# Ramanayyapeta, Kakinada - the anchor derived from the deed's own route map.
KAKINADA = (16.9886, 82.2488)


def option_payloads(markup: str) -> list[dict]:
    """Decode the JSON tucked into each <option value='...'>.

    Attribute values are single-quoted and html-escaped, so apostrophes arrive
    as &#x27; - that escaping is exactly what keeps a label like "Teacher's
    Colony" from terminating the attribute early.
    """
    chunks = [c.split("'")[0] for c in markup.split("<option value='")[1:]]
    return [json.loads(html_mod.unescape(c)) for c in chunks if c]


def make_site(**overrides) -> dict:
    site = {
        "key": "demo",
        "title": "Demo site",
        "village": "Demoville",
        "mandal": "Demo",
        "district": "Demo",
        "state": "Demo State",
        "anchor": {"lat": KAKINADA[0], "lon": KAKINADA[1], "precision": "village",
                   "source": "test fixture"},
    }
    site.update(overrides)
    return site


def make_view(name="site", zoom=18, span_m=1200, **overrides) -> dict:
    view = {
        "name": name, "file": f"{name}.jpg", "zoom": zoom,
        "requested_zoom": zoom, "stddev": 40.0, "width": 2100, "height": 2100,
        "ground_m_per_px": 0.571, "span_m": span_m, "missing_tiles": 0,
        "merc_box": {"west": 9155000.0, "east": 9156200.0,
                     "north": 1915600.0, "south": 1914400.0},
        "sha256": "0" * 64,
    }
    view.update(overrides)
    return view


class TestProjection:
    def test_prime_meridian_and_equator_are_the_origin(self):
        assert rev.merc(0.0, 0.0) == pytest.approx((0.0, 0.0), abs=1e-6)

    def test_east_and_north_increase(self):
        x0, y0 = rev.merc(*KAKINADA)
        x_east, _ = rev.merc(KAKINADA[0], KAKINADA[1] + 0.01)
        _, y_north = rev.merc(KAKINADA[0] + 0.01, KAKINADA[1])
        assert x_east > x0
        assert y_north > y0, "north must INCREASE mercator y (it is not a raster row)"

    def test_agrees_with_the_tile_indexer(self):
        """merc() and deg2tile() must describe the same world."""
        from fetch_basemap_tiles import EARTH_CIRCUM, ORIGIN, deg2tile

        z = 16
        x, y = deg2tile(*KAKINADA, z)
        mx, my = rev.merc(*KAKINADA)
        res = EARTH_CIRCUM / (2**z)
        assert x == int((mx + ORIGIN) / res)
        assert y == int((ORIGIN - my) / res)

    def test_longitude_is_linear(self):
        a, _ = rev.merc(0, 45.0)
        b, _ = rev.merc(0, 90.0)
        assert b == pytest.approx(2 * a)


class TestViewBox:
    def test_box_is_square_in_mercator(self):
        west, south, east, north = rev.view_box(*KAKINADA, 600)
        assert (east - west) == pytest.approx(north - south)

    def test_box_is_centred_on_the_point(self):
        west, south, east, north = rev.view_box(*KAKINADA, 600)
        cx, cy = rev.merc(*KAKINADA)
        assert (west + east) / 2 == pytest.approx(cx)
        assert (south + north) / 2 == pytest.approx(cy)

    def test_half_width_is_ground_metres_not_mercator_metres(self):
        """The cos(lat) correction is the whole point - drop it and every view
        is ~5% too small at this latitude, silently."""
        lat, lon = KAKINADA
        west, _, east, _ = rev.view_box(lat, lon, 600)
        mercator_width = east - west
        ground_width = mercator_width * math.cos(math.radians(lat))
        assert ground_width == pytest.approx(1200, rel=1e-9)
        assert mercator_width > 1200, "mercator metres must be the inflated ones"

    def test_correction_grows_with_latitude(self):
        near_equator = rev.view_box(1.0, 0.0, 600)
        far_north = rev.view_box(60.0, 0.0, 600)
        assert (far_north[2] - far_north[0]) > (near_equator[2] - near_equator[0])


class TestDistance:
    def test_zero_distance(self):
        assert rev.haversine_m(KAKINADA, KAKINADA) == pytest.approx(0.0, abs=1e-6)

    def test_one_degree_of_latitude(self):
        d = rev.haversine_m((16.0, 82.0), (17.0, 82.0))
        assert d == pytest.approx(111195, rel=0.001)

    def test_rtc_colony_to_stadium(self):
        """The two ends of the road named in the Ramanayyapeta route map."""
        d = rev.haversine_m((16.9931923, 82.2501521), (16.9839757, 82.2474330))
        assert 1000 < d < 1120

    def test_symmetric(self):
        a, b = (16.9, 82.2), (17.1, 82.4)
        assert rev.haversine_m(a, b) == pytest.approx(rev.haversine_m(b, a))


class TestBlankness:
    def test_uniform_image_scores_zero(self):
        flat = Image.new("RGB", (256, 256), (204, 204, 204))
        assert rev.blankness(flat) == pytest.approx(0.0, abs=1e-9)

    def test_uniform_image_trips_the_blank_threshold(self):
        """This is how a 'map data not available' tile is caught."""
        flat = Image.new("RGB", (256, 256), (204, 204, 204))
        assert rev.blankness(flat) < rev.BLANK_STDDEV

    def test_varied_image_clears_the_threshold(self):
        img = Image.new("RGB", (256, 256))
        img.putdata([(0, 0, 0) if (i // 16) % 2 else (255, 255, 255)
                     for i in range(256 * 256)])
        assert rev.blankness(img) > rev.BLANK_STDDEV


class TestCrop:
    def test_crop_fractions_map_to_pixels(self, tmp_path):
        src = Image.new("RGB", (1000, 800), "white")
        dst = tmp_path / "out.jpg"
        rev._finish(src, dst, [0.0, 0.0, 0.5, 0.25])
        assert Image.open(dst).size == (500, 200)

    def test_no_crop_keeps_the_frame(self, tmp_path):
        src = Image.new("RGB", (400, 300), "white")
        dst = tmp_path / "out.jpg"
        rev._finish(src, dst, None)
        assert Image.open(dst).size == (400, 300)

    def test_oversized_images_are_bounded(self, tmp_path):
        src = Image.new("RGB", (4000, 5000), "white")
        dst = tmp_path / "out.jpg"
        rev._finish(src, dst, None)
        assert max(Image.open(dst).size) == rev.MAX_PLAN_PX


class TestValidation:
    def test_a_good_roster_passes(self):
        assert rev.validate({"sites": [make_site()]}) == []

    def test_missing_key_is_caught(self):
        site = make_site()
        del site["key"]
        assert any("missing key" in p for p in rev.validate({"sites": [site]}))

    def test_duplicate_keys_are_caught(self):
        problems = rev.validate({"sites": [make_site(), make_site()]})
        assert any("duplicate key" in p for p in problems)

    def test_non_numeric_anchor_is_caught(self):
        site = make_site(anchor={"lat": "16.98", "lon": 82.24})
        assert any("numeric" in p for p in rev.validate({"sites": [site]}))

    def test_out_of_range_anchor_is_caught(self):
        site = make_site(anchor={"lat": 916.98, "lon": 82.24})
        assert any("out of range" in p for p in rev.validate({"sites": [site]}))

    def test_unknown_precision_is_caught(self):
        """A typo must fail loudly - silently defaulting would understate how
        badly a plot is located."""
        site = make_site(anchor={"lat": 16.9, "lon": 82.2, "precision": "approx"})
        assert any("unknown precision" in p for p in rev.validate({"sites": [site]}))

    def test_every_precision_has_a_ring_and_a_note(self):
        assert set(rev.UNCERTAINTY) == set(rev.PRECISION_NOTE)

    @pytest.mark.parametrize("crop", [[0.5, 0, 0.2, 1], [0, 0, 2, 1], [0, 0, 1]])
    def test_bad_crops_are_caught(self, crop):
        site = make_site(plans=[{"src": "a.jpg", "caption": "c", "crop": crop}])
        assert any("bad crop" in p for p in rev.validate({"sites": [site]}))

    def test_incomplete_candidate_is_caught(self):
        site = make_site(candidates=[{"label": "somewhere", "lat": 16.9}])
        assert any("candidate needs" in p for p in rev.validate({"sites": [site]}))


class TestShotHtml:
    def test_mercator_box_is_embedded_and_parseable(self):
        """The page cannot place a typed coordinate without this."""
        view = make_view()
        markup = rev.shot_html(view, "assets/demo/site.jpg", 20.0)
        raw = markup.split("data-box='")[1].split("'")[0]
        assert json.loads(raw.replace("&quot;", '"')) == view["merc_box"]

    def test_anchor_marker_sits_at_the_centre(self):
        """The mosaic is built centred on the anchor, so 50/50 is not a guess."""
        markup = rev.shot_html(make_view(), "x.jpg", 20.0)
        assert 'class="mark dot" style="left:50%;top:50%"' in markup

    def test_probe_and_offscreen_targets_exist(self):
        markup = rev.shot_html(make_view(), "x.jpg", 20.0)
        assert "mark probe" in markup and "offscreen" in markup

    def test_ring_is_drawn_when_uncertainty_is_material(self):
        markup = rev.shot_html(make_view(), "x.jpg", 40.0)
        assert "mark ring" in markup

    def test_tiny_ring_is_suppressed(self):
        """An exact pin on a 4 km view would draw a ring smaller than the dot."""
        markup = rev.shot_html(make_view(span_m=4000), "x.jpg", 1.5)
        assert "mark ring" not in markup


class TestPicker:
    def test_anchor_is_always_offered(self):
        markup = rev.picker_html(make_site())
        assert "Anchor (as published" in markup

    def test_candidates_are_offered_with_their_coordinates(self):
        site = make_site(candidates=[
            {"label": "RTC Colony", "lat": 16.9931923, "lon": 82.2501521},
        ])
        markup = rev.picker_html(site)
        assert "RTC Colony" in markup and "16.9931923" in markup

    def test_option_payloads_are_valid_json(self):
        site = make_site(candidates=[{"label": "A", "lat": 1.0, "lon": 2.0}])
        parsed = option_payloads(rev.picker_html(site))
        assert {"label": "A", "lat": 1.0, "lon": 2.0} in parsed

    def test_quotes_in_a_label_do_not_break_the_option(self):
        """Real labels contain apostrophes - "Teacher's Colony" is in the
        roster. An unescaped one would truncate the attribute and take the
        coordinate with it."""
        site = make_site(candidates=[
            {"label": "Teacher's Colony \"north\"", "lat": 1.0, "lon": 2.0},
        ])
        markup = rev.picker_html(site)
        assert "Teacher's Colony" not in markup, "raw apostrophe must not survive"
        labels = [p["label"] for p in option_payloads(markup)]
        assert "Teacher's Colony \"north\"" in labels

    def test_free_entry_field_is_present(self):
        markup = rev.picker_html(make_site())
        assert 'id="coord"' in markup and 'id="readout"' in markup


class TestSitePage:
    def test_precision_badge_is_rendered(self):
        page = rev.site_page(make_site(), [make_view()], [], None, None)
        assert 'class="pill p-village">village anchor' in page

    def test_non_exact_anchors_carry_the_warning(self):
        page = rev.site_page(make_site(), [make_view()], [], None, None)
        assert "The marker is not the plot." in page
        assert "1000 m in radius" in page

    def test_exact_anchors_do_not(self):
        site = make_site(anchor={"lat": 16.9, "lon": 82.2, "precision": "exact"})
        page = rev.site_page(site, [make_view()], [], None, None)
        assert "The marker is not the plot." not in page

    def test_roster_can_override_the_ring(self):
        site = make_site(anchor={"lat": 16.9, "lon": 82.2, "precision": "locality",
                                 "uncertainty_m": 700})
        page = rev.site_page(site, [make_view()], [], None, None)
        assert "700 m in radius" in page

    def test_zoom_fallback_is_disclosed(self):
        view = make_view(zoom=18, requested_zoom=19)
        page = rev.site_page(make_site(), [view], [], None, None)
        assert "no imagery here at z19" in page

    def test_matching_zoom_says_nothing(self):
        page = rev.site_page(make_site(), [make_view(zoom=18, requested_zoom=18)],
                             [], None, None)
        assert "no imagery here" not in page

    def test_anchor_is_exposed_to_the_probe_script(self):
        page = rev.site_page(make_site(), [make_view()], [], None, None)
        assert "data-anchor=" in page and "16.9886" in page

    def test_html_in_roster_text_is_escaped(self):
        site = make_site(ground_handles=["<script>alert(1)</script>"])
        page = rev.site_page(site, [make_view()], [], None, None)
        assert "<script>alert(1)</script>" not in page
        assert "&lt;script&gt;" in page

    def test_document_links_use_the_precomputed_href(self):
        site = make_site(docs=[{"path": "koti/deed.pdf", "label": "Deed",
                                "href": "../koti/deed.pdf"}])
        page = rev.site_page(site, [make_view()], [], None, None)
        assert 'href="../koti/deed.pdf"' in page

    def test_navigation_links_both_ways(self):
        page = rev.site_page(make_site(), [make_view()], [],
                             ("prev_key", "Prev"), ("next_key", "Next"))
        assert 'href="prev_key.html"' in page and 'href="next_key.html"' in page


class TestIndexPage:
    def test_precision_tally_counts_sites(self):
        entries = [
            {"key": "a", "title": "A", "owner": "", "village": "", "mandal": "",
             "district": "", "extent": "", "survey": "", "precision": "exact"},
            {"key": "b", "title": "B", "owner": "", "village": "", "mandal": "",
             "district": "", "extent": "", "survey": "", "precision": "village"},
            {"key": "c", "title": "C", "owner": "", "village": "", "mandal": "",
             "district": "", "extent": "", "survey": "", "precision": "village"},
        ]
        page = rev.index_page(entries)
        assert "3 sites" in page
        assert "1 exact" in page and "2 village" in page

    def test_every_precision_is_explained(self):
        page = html_mod.unescape(rev.index_page([]))
        for note in rev.PRECISION_NOTE.values():
            assert note in page


class TestViewScales:
    def test_three_fixed_scales_ordered_widest_first(self):
        halves = [half for _, _, half in rev.VIEWS]
        assert halves == sorted(halves, reverse=True)

    def test_zoom_increases_as_the_view_narrows(self):
        zooms = [z for _, z, _ in rev.VIEWS]
        assert zooms == sorted(zooms)

    def test_fallback_floor_is_below_every_requested_zoom(self):
        assert rev.MIN_ZOOM < min(z for _, z, _ in rev.VIEWS)
