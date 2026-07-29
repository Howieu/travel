from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "personal-travel-roadbook"
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from build_site import build_site, validate_roadbook  # noqa: E402


def load_routes() -> list[dict]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted((ROOT / "roadbooks").glob("*.json"))]


def test_migrated_route_inventory_is_complete() -> None:
    routes = load_routes()

    assert len(routes) == 11
    assert sum(len(route["days"]) for route in routes) == 32
    assert sum(len(day["stops"]) for route in routes for day in route["days"]) == 137
    assert all(not validate_roadbook(route) for route in routes)


def test_routes_have_unique_slugs_and_legacy_paths() -> None:
    routes = load_routes()
    slugs = [route["trip"]["slug"] for route in routes]
    legacy_paths = [path for route in routes for path in route["trip"].get("legacyPaths", [])]

    assert len(slugs) == len(set(slugs)) == 11
    assert len(legacy_paths) == len(set(legacy_paths)) == 11


def test_public_route_json_has_no_known_sensitive_keys_or_email_values() -> None:
    sensitive_keys = {
        "passengername",
        "travelername",
        "guestname",
        "customername",
        "fullname",
        "bookingreference",
        "bookingref",
        "confirmationnumber",
        "ordernumber",
        "qrcode",
        "payment",
        "paymentdetails",
        "passport",
        "passportnumber",
        "idnumber",
        "nationalid",
        "phone",
        "phonenumber",
        "email",
        "emailaddress",
        "creditcard",
        "cardnumber",
        "cvv",
        "securitycode",
    }
    email_pattern = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)

    def assert_safe(value: object) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
                assert normalized not in sensitive_keys
                assert_safe(item)
        elif isinstance(value, list):
            for item in value:
                assert_safe(item)
        elif isinstance(value, str):
            assert not email_pattern.search(value)

    for route in load_routes():
        assert_safe(route)


def test_full_collection_builds_with_legacy_redirects(tmp_path: Path) -> None:
    output_dir = tmp_path / "dist"

    result = build_site(ROOT / "site.config.json", ROOT / "roadbooks", output_dir)

    assert result.route_count == 11
    for route in load_routes():
        slug = route["trip"]["slug"]
        assert (output_dir / "routes" / slug / "index.html").exists()
        for legacy_path in route["trip"]["legacyPaths"]:
            assert (output_dir / legacy_path).exists()
