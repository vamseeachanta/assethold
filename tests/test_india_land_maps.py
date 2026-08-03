"""Unit tests for the India land-map fetchers.

Covers the pure logic only - tile/coordinate maths, the AOI parser, OSM feature
classification and GeoJSON/KML shaping, and the portal-probe verdict rules.
Nothing here touches the network.

The georeferencing maths is the part worth guarding hardest: a sign error or a
half-pixel offset in the world file silently puts every mosaic in the wrong
place on the ground, and the output still *looks* fine.
"""

from __future__ import annotations

import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts" / "python" / "india_land_maps"
sys.path.insert(0, str(SCRIPTS))

import fetch_basemap_tiles as tiles  # noqa: E402
import fetch_osm_extract as osm  # noqa: E402
import probe_portals as probe  # noqa: E402

pytestmark = pytest.mark.unit

# Valasapakala GP anchor - OSM node 12496017004.
VALASAPAKALA = (16.9963762, 82.2563312)


class TestTileMaths:
    """XYZ tile indexing and Web Mercator conversion."""

    def test_origin_tile_at_zoom_zero(self):
        assert tiles.deg2tile(0.0, 0.0, 0) == (0, 0)

    def test_equator_prime_meridian_at_zoom_one(self):
        # (0,0) sits exactly on the corner of the four z=1 tiles.
        assert tiles.deg2tile(0.0, 0.0, 1) == (1, 1)

    def test_longitude_increases_x_latitude_decreases_y(self):
        lat, lon = VALASAPAKALA
        x0, y0 = tiles.deg2tile(lat, lon, 14)
        x_east, _ = tiles.deg2tile(lat, lon + 1.0, 14)
        _, y_north = tiles.deg2tile(lat + 1.0, lon, 14)
        assert x_east > x0, "east must increase tile x"
        assert y_north < y0, "north must DECREASE tile y (rows run north->south)"

    def test_tile_count_quadruples_per_zoom(self):
        lat, lon = VALASAPAKALA
        x16, y16 = tiles.deg2tile(lat, lon, 16)
        x17, y17 = tiles.deg2tile(lat, lon, 17)
        assert (x17, y17) == (x16 * 2 + 1, y16 * 2) or (x17 // 2, y17 // 2) == (x16, y16)

    def test_mercator_origin_is_top_left_of_world(self):
        x, y = tiles.tile2merc(0, 0, 5)
        assert x == pytest.approx(-tiles.ORIGIN)
        assert y == pytest.approx(tiles.ORIGIN)

    @pytest.mark.parametrize("z", [10, 14, 16, 18])
    def test_tile_corner_round_trips_within_one_tile(self, z):
        """A point's tile corner must sit within one tile-width of the point itself."""
        lat, lon = VALASAPAKALA
        x, y = tiles.deg2tile(lat, lon, z)
        mx, my = tiles.tile2merc(x, y, z)

        # Project the point independently, then compare.
        px = lon * tiles.EARTH_CIRCUM / 360.0
        py = math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * tiles.EARTH_CIRCUM / (2 * math.pi)
        span = tiles.EARTH_CIRCUM / (2**z)

        assert 0 <= px - mx < span, "point must lie east of its tile's west edge"
        assert 0 <= my - py < span, "point must lie south of its tile's north edge"

    def test_ground_resolution_halves_each_zoom(self):
        res16 = tiles.EARTH_CIRCUM / (2**16) / tiles.TILE_PX
        res17 = tiles.EARTH_CIRCUM / (2**17) / tiles.TILE_PX
        assert res17 == pytest.approx(res16 / 2)
        # z18 is the level that makes plot edges legible; ~0.6 m/px at the equator.
        res18 = tiles.EARTH_CIRCUM / (2**18) / tiles.TILE_PX
        assert 0.55 < res18 < 0.62


class TestAoiParser:
    """The dependency-free YAML subset parser."""

    def _write(self, tmp_path: Path, body: str) -> Path:
        p = tmp_path / "aoi.yaml"
        p.write_text(body, encoding="utf-8")
        return p

    def test_parses_scalars_and_bbox(self, tmp_path):
        aoi = osm.load_aoi(
            self._write(
                tmp_path,
                'name: kakinada_valasapakala\n'
                'output_dir: "data/gis/kv"\n'
                "bbox:\n"
                "  min_lat: 16.982\n"
                "  min_lon: 82.243\n"
                "  max_lat: 17.028\n"
                "  max_lon: 82.300\n",
            )
        )
        assert aoi["name"] == "kakinada_valasapakala"
        assert aoi["output_dir"] == "data/gis/kv"  # quotes stripped
        assert aoi["bbox"] == {
            "min_lat": 16.982,
            "min_lon": 82.243,
            "max_lat": 17.028,
            "max_lon": 82.300,
        }

    def test_ignores_comments_and_blank_lines(self, tmp_path):
        aoi = osm.load_aoi(
            self._write(
                tmp_path,
                "# leading comment\n\nname: x  # trailing comment\n"
                "bbox:\n  min_lat: 1.0  # inline\n",
            )
        )
        assert aoi["name"] == "x"
        assert aoi["bbox"]["min_lat"] == 1.0

    def test_non_numeric_bbox_value_is_skipped_not_fatal(self, tmp_path):
        aoi = osm.load_aoi(
            self._write(tmp_path, "bbox:\n  min_lat: not_a_number\n  min_lon: 5.0\n")
        )
        assert aoi["bbox"] == {"min_lon": 5.0}

    def test_real_repo_aoi_loads(self):
        """The committed Valasapakala AOI must stay parseable by its own parser."""
        cfg = Path(__file__).resolve().parents[1] / "config" / "gis" / "aoi" / "kakinada_valasapakala.yaml"
        if not cfg.exists():  # pragma: no cover - config removed
            pytest.skip("AOI config not present")
        aoi = osm.load_aoi(cfg)
        b = aoi["bbox"]
        assert b["min_lat"] < b["max_lat"] and b["min_lon"] < b["max_lon"]
        # The anchor point must fall inside the declared AOI.
        lat, lon = VALASAPAKALA
        assert b["min_lat"] <= lat <= b["max_lat"]
        assert b["min_lon"] <= lon <= b["max_lon"]


class TestOsmClassification:
    def test_water_wins_over_generic_natural(self):
        assert osm.classify({"natural": "water"}) == "water"

    def test_untagged_is_other(self):
        assert osm.classify({}) == "other"

    @pytest.mark.parametrize(
        "tags,expected",
        [
            ({"place": "village"}, "place"),
            ({"highway": "residential"}, "highway"),
            ({"landuse": "residential"}, "landuse"),
            ({"building": "yes"}, "building"),
            ({"waterway": "drain"}, "waterway"),
            ({"boundary": "administrative"}, "boundary"),
        ],
    )
    def test_single_tag_classes(self, tags, expected):
        assert osm.classify(tags) == expected


class TestGeoJsonShaping:
    def test_node_becomes_point(self):
        gj = osm.to_geojson([{"type": "node", "id": 1, "lat": 17.0, "lon": 82.0, "tags": {"place": "village"}}])
        geom = gj["features"][0]["geometry"]
        assert geom["type"] == "Point"
        assert geom["coordinates"] == [82.0, 17.0], "GeoJSON is lon,lat - not lat,lon"

    def test_open_way_becomes_linestring(self):
        way = {
            "type": "way",
            "id": 2,
            "tags": {"highway": "residential"},
            "geometry": [{"lat": 17.0, "lon": 82.0}, {"lat": 17.1, "lon": 82.1}],
        }
        assert osm.to_geojson([way])["features"][0]["geometry"]["type"] == "LineString"

    def test_closed_way_becomes_polygon(self):
        ring = [
            {"lat": 17.0, "lon": 82.0},
            {"lat": 17.0, "lon": 82.1},
            {"lat": 17.1, "lon": 82.1},
            {"lat": 17.0, "lon": 82.0},
        ]
        feat = osm.to_geojson([{"type": "way", "id": 3, "tags": {"building": "yes"}, "geometry": ring}])["features"][0]
        assert feat["geometry"]["type"] == "Polygon"
        assert feat["geometry"]["coordinates"][0][0] == feat["geometry"]["coordinates"][0][-1]

    def test_degenerate_geometry_is_dropped(self):
        one_node_way = {"type": "way", "id": 4, "tags": {}, "geometry": [{"lat": 1.0, "lon": 2.0}]}
        assert osm.to_geojson([one_node_way])["features"] == []

    def test_osm_layer_tag_does_not_clobber_feature_class(self):
        """Regression: OSM's own `layer` tag (bridges use layer=1) used to
        overwrite the computed class, producing bogus classes named "1"/"-1"."""
        bridge = {
            "type": "way",
            "id": 5,
            "tags": {"highway": "secondary", "bridge": "yes", "layer": "1"},
            "geometry": [{"lat": 17.0, "lon": 82.0}, {"lat": 17.01, "lon": 82.01}],
        }
        props = osm.to_geojson([bridge])["features"][0]["properties"]
        assert props["feature_class"] == "highway"
        assert props["layer"] == "1", "the original OSM layer tag must survive"


class TestKmlOutput:
    def test_kml_is_well_formed_and_foldered(self):
        elements = [
            {"type": "node", "id": 1, "lat": 17.0, "lon": 82.0, "tags": {"place": "village", "name": "Test"}},
            {
                "type": "way",
                "id": 2,
                "tags": {"highway": "residential"},
                "geometry": [{"lat": 17.0, "lon": 82.0}, {"lat": 17.1, "lon": 82.1}],
            },
        ]
        kml = osm.to_kml(osm.to_geojson(elements), "unit-test")
        root = ET.fromstring(kml)  # raises if malformed
        ns = "{http://www.opengis.net/kml/2.2}"
        folders = root.findall(f".//{ns}Folder")
        assert len(folders) == 2, "one folder per feature class"
        assert len(root.findall(f".//{ns}Placemark")) == 2

    def test_special_characters_are_escaped(self):
        node = {"type": "node", "id": 1, "lat": 17.0, "lon": 82.0, "tags": {"place": "village", "name": "A & B <test>"}}
        kml = osm.to_kml(osm.to_geojson([node]), "esc")
        ET.fromstring(kml)  # would raise on unescaped & or <
        assert "A &amp; B" in kml


class TestProbeVerdicts:
    """Verdict rules - the part that decides whether a portal is usable."""

    def test_catch_all_detected_when_bogus_path_matches(self):
        """MeeBhoomi returns an identical login page for a path that cannot exist,
        so HTTP 200 there is not evidence the resource exists."""
        page = {"http_status": 200, "bytes": 82585}
        assert probe.classify("u", page, dict(page), "1.2.3.4") == "CATCH_ALL"

    def test_distinct_sizes_are_not_catch_all(self):
        main = {"http_status": 200, "bytes": 36561}
        control = {"http_status": 404, "bytes": 2667}
        assert probe.classify("u", main, control, "1.2.3.4") == "OK"

    def test_geo_block_is_dns_ok_but_connect_fails(self):
        failed = {"http_status": None, "error": "timed out"}
        assert probe.classify("u", failed, None, "164.100.192.133") == "GEO_BLOCKED"

    def test_no_dns_when_name_does_not_resolve(self):
        failed = {"http_status": None, "error": "nodename nor servname provided"}
        assert probe.classify("u", failed, None, None) == "NO_DNS"

    def test_dead_published_link(self):
        assert probe.classify("u", {"http_status": 404, "bytes": 196}, None, "1.2.3.4") == "GONE_404"

    @pytest.mark.parametrize("code", [401, 403])
    def test_auth_required(self, code):
        assert probe.classify("u", {"http_status": code, "bytes": 10}, None, "1.2.3.4") == "FORBIDDEN"

    def test_other_status_is_reported_verbatim(self):
        assert probe.classify("u", {"http_status": 503, "bytes": 0}, None, "1.2.3.4") == "HTTP_503"

    def test_every_target_is_well_formed(self):
        """Each TARGETS row must carry all six fields, including the documented
        access value - reachability and access are different axes."""
        assert probe.TARGETS, "target list must not be empty"
        seen = set()
        for row in probe.TARGETS:
            assert len(row) == 6, f"expected 6 fields, got {len(row)}: {row[0]}"
            key, label, url, _control, why, access = row
            assert key not in seen, f"duplicate target key {key}"
            seen.add(key)
            assert url.startswith(("http://", "https://"))
            assert label and why and access

    def test_every_verdict_has_a_documented_meaning(self):
        produced = {
            probe.classify("u", {"http_status": 200, "bytes": 1}, None, "1.2.3.4"),
            probe.classify("u", {"http_status": 404, "bytes": 1}, None, "1.2.3.4"),
            probe.classify("u", {"http_status": None}, None, "1.2.3.4"),
            probe.classify("u", {"http_status": None}, None, None),
            probe.classify("u", {"http_status": 403, "bytes": 1}, None, "1.2.3.4"),
        }
        assert produced <= set(probe.VERDICT_NOTE), "undocumented verdict emitted"

    def test_markdown_render_includes_dates_and_access(self):
        snapshot = {
            "probed_on": "2026-08-03",
            "probed_at_utc": "2026-08-03T03:29:03+00:00",
            "vantage_point": "US network (non-Indian egress)",
            "results": [
                {
                    "label": "KAUDA",
                    "url": "https://kauda.ap.gov.in/",
                    "verdict": "GEO_BLOCKED",
                    "access": "india-only",
                    "why_it_matters": "Master plan.",
                    "main": {"http_status": None, "error": "timed out"},
                }
            ],
        }
        md = probe.render_markdown([snapshot])
        assert "## 2026-08-03" in md, "each snapshot must be dated"
        assert "india-only" in md
        assert "GEO_BLOCKED" in md
        assert "US network (non-Indian egress)" in md, "vantage point changes the result"
