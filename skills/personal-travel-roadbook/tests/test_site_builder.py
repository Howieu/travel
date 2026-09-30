from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from build_site import BuildError, build_site, validate_roadbook  # noqa: E402


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def sample_route(title: str = "Paris Weekend") -> dict:
    return {
        "trip": {
            "title": title,
            "destination": "Paris",
            "startDate": "2026-09-10",
            "endDate": "2026-09-12",
            "pace": "standard",
            "interests": ["museum", "food"],
            "mustGo": ["Louvre Museum"],
            "avoid": ["tight transfers"],
            "slug": "paris-weekend",
            "coverImage": "https://example.com/paris.jpg",
        },
        "days": [
            {
                "date": "2026-09-10",
                "title": "Arrival < Walk",
                "summary": "Keep the first afternoon flexible.",
                "stops": [
                    {
                        "time": "14:00",
                        "name": "Louvre < Museum",
                        "type": "museum",
                        "description": "Book ahead & keep a buffer.",
                        "durationMinutes": 150,
                        "mustGo": True,
                        "deadline": "Leave before 18:00",
                        "fallback": "Skip the interior if arrival is late.",
                        "mapQueries": {
                            "amap": "卢浮宫 巴黎",
                            "google": "Louvre Museum Paris",
                            "apple": "Louvre Museum Paris",
                        },
                        "image": "https://example.com/louvre.jpg",
                        "links": [{"label": "Official site", "url": "https://example.com/louvre"}],
                        "source": "pasted notes",
                        "sourceIds": ["note-001"],
                        "confidence": "medium",
                    }
                ],
            }
        ],
        "sourceRecords": [
            {
                "id": "note-001",
                "type": "pasted-note",
                "platform": "user",
                "title": "Paris notes",
                "excerpt": "Museum and food preferences.",
                "accessStatus": "user-summary",
                "confidence": "medium",
            }
        ],
        "lodging": [{"name": "Hotel Example", "address": "Paris", "checkIn": "2026-09-10"}],
        "transport": [{"type": "train", "from": "London", "to": "Paris", "departAt": "08:00"}],
        "warnings": ["Verify museum hours before departure."],
    }


def test_validate_roadbook_reports_required_field_paths() -> None:
    errors = validate_roadbook({"trip": {"title": "Missing fields"}, "days": [{"stops": [{}]}]})

    assert "missing trip.destination" in errors
    assert "days[1] missing date" in errors
    assert "days[1].stops[1] missing name" in errors


def test_build_site_renders_escaped_content_maps_sources_and_fallbacks(tmp_path: Path) -> None:
    input_dir = tmp_path / "roadbooks"
    output_dir = tmp_path / "dist"
    input_dir.mkdir()
    write_json(input_dir / "paris.json", sample_route())
    config_path = tmp_path / "site.config.json"
    write_json(
        config_path,
        {
            "title": "My Travel Collection",
            "description": "Personal routes",
            "author": "Howieu",
            "theme": {"primaryColor": "#123456", "showSources": True},
        },
    )

    result = build_site(config_path, input_dir, output_dir)

    assert result.route_count == 1
    assert (output_dir / "index.html").exists()
    assert (output_dir / "routes" / "paris-weekend" / "index.html").exists()
    assert (output_dir / "routes" / "paris-weekend" / "roadbook.json").exists()
    assert (output_dir / "assets" / "roadbook.css").exists()

    collection = (output_dir / "index.html").read_text(encoding="utf-8")
    route = (output_dir / "routes" / "paris-weekend" / "index.html").read_text(encoding="utf-8")
    assert "My Travel Collection" in collection
    assert "routes/paris-weekend/index.html" in collection
    assert "Louvre &lt; Museum" in route
    assert "https://uri.amap.com/search?keyword=%E5%8D%A2%E6%B5%AE%E5%AE%AB+%E5%B7%B4%E9%BB%8E" in route
    assert 'class="map-primary"' in route
    assert "高德导航" in route
    assert 'class="map-secondary"' in route
    assert "Google 地图" in route
    assert "Apple 地图" in route
    assert route.index("高德导航") < route.index("Google 地图")
    assert "Skip the interior if arrival is late." in route
    assert "Paris notes" in route
    assert "#123456" in route


def test_choice_options_render_side_by_side(tmp_path: Path) -> None:
    input_dir = tmp_path / "roadbooks"
    output_dir = tmp_path / "dist"
    input_dir.mkdir()
    route = sample_route()
    route["days"][0]["stops"][0]["options"] = [
        {"name": "East", "description": "Stay east.", "mapQueries": {"amap": "东", "google": "East"}},
        {"name": "West", "description": "Walk west.", "mapQueries": {"amap": "西", "google": "West"}},
        {"name": "Hung Hom", "description": "Continue east.", "mapQueries": {"amap": "红磡", "google": "Hung Hom"}},
    ]
    write_json(input_dir / "paris.json", route)
    config_path = tmp_path / "site.config.json"
    write_json(config_path, {"title": "Routes"})

    build_site(config_path, input_dir, output_dir)

    html = (output_dir / "routes" / "paris-weekend" / "index.html").read_text(encoding="utf-8")
    assert html.count('class="choice-card"') == 3
    assert "choice-row" in html


def test_build_site_supports_multiple_routes_and_default_theme(tmp_path: Path) -> None:
    input_dir = tmp_path / "roadbooks"
    output_dir = tmp_path / "dist"
    input_dir.mkdir()
    first = sample_route("Paris Weekend")
    second = sample_route("Paris Food Route")
    second["trip"]["slug"] = "paris-food"
    write_json(input_dir / "paris.json", first)
    write_json(input_dir / "food.json", second)
    config_path = tmp_path / "site.config.json"
    write_json(config_path, {"title": "Routes"})

    result = build_site(config_path, input_dir, output_dir)

    assert result.route_count == 2
    collection = (output_dir / "index.html").read_text(encoding="utf-8")
    assert "routes/paris-weekend/index.html" in collection
    assert "routes/paris-food/index.html" in collection
    assert "#0f766e" in (output_dir / "routes" / "paris-food" / "index.html").read_text(encoding="utf-8")


def test_build_site_rejects_invalid_json_before_writing_pages(tmp_path: Path) -> None:
    input_dir = tmp_path / "roadbooks"
    output_dir = tmp_path / "dist"
    input_dir.mkdir()
    write_json(input_dir / "bad.json", {"trip": {"title": "Bad"}, "days": []})
    config_path = tmp_path / "site.config.json"
    write_json(config_path, {})

    with pytest.raises(BuildError, match="bad.json: missing trip.destination"):
        build_site(config_path, input_dir, output_dir)

    assert not output_dir.exists()


def test_build_site_redacts_known_booking_sensitive_fields(tmp_path: Path) -> None:
    input_dir = tmp_path / "roadbooks"
    output_dir = tmp_path / "dist"
    input_dir.mkdir()
    route = sample_route("Private Booking Route")
    route["trip"]["slug"] = "private-booking-route"
    route["transport"][0].update(
        {
            "passengerName": "Traveler Name",
            "bookingReference": "SECRET-123",
            "passportNumber": "P1234567",
            "phone": "+8613800000000",
            "email": "traveler@example.com",
            "paymentDetails": "card ending 1234",
        }
    )
    write_json(input_dir / "private.json", route)
    config_path = tmp_path / "site.config.json"
    write_json(config_path, {})

    build_site(config_path, input_dir, output_dir)

    output = (output_dir / "routes" / "private-booking-route" / "roadbook.json").read_text(encoding="utf-8")
    for secret in ("Traveler Name", "SECRET-123", "P1234567", "+8613800000000", "traveler@example.com", "card ending 1234"):
        assert secret not in output


def test_build_site_preserves_legacy_route_urls_with_redirects(tmp_path: Path) -> None:
    input_dir = tmp_path / "roadbooks"
    output_dir = tmp_path / "dist"
    input_dir.mkdir()
    route = sample_route("Legacy Paris Route")
    route["trip"]["legacyPaths"] = ["france/paris.html"]
    write_json(input_dir / "paris.json", route)
    config_path = tmp_path / "site.config.json"
    write_json(config_path, {"title": "Routes"})

    build_site(config_path, input_dir, output_dir)

    redirect = (output_dir / "france" / "paris.html").read_text(encoding="utf-8")
    assert "../routes/paris-weekend/index.html" in redirect
    assert (output_dir / ".nojekyll").exists()


@pytest.mark.parametrize("legacy_path", ["../private.html", "/absolute.html", "routes/conflict.html", "not-html.txt"])
def test_build_site_rejects_unsafe_legacy_paths(tmp_path: Path, legacy_path: str) -> None:
    input_dir = tmp_path / "roadbooks"
    output_dir = tmp_path / "dist"
    input_dir.mkdir()
    route = sample_route("Unsafe Legacy Route")
    route["trip"]["legacyPaths"] = [legacy_path]
    write_json(input_dir / "unsafe.json", route)
    config_path = tmp_path / "site.config.json"
    write_json(config_path, {})

    with pytest.raises(BuildError, match="unsafe legacy path"):
        build_site(config_path, input_dir, output_dir)

    assert not output_dir.exists()
