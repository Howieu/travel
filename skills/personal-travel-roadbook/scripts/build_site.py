#!/usr/bin/env python3
"""Build a portable static travel-roadbook collection from JSON files."""

from __future__ import annotations

import argparse
import html
import json
import posixpath
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import quote_plus, urlparse


DEFAULT_THEME = {
    "primaryColor": "#0f766e",
    "accentColor": "#f59e0b",
    "backgroundColor": "#f5f7f8",
    "showSources": True,
    "showConfidence": True,
    "language": "zh-CN",
    "logo": "",
    "defaultCoverImage": "",
}

SENSITIVE_KEYS = {
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


class BuildError(ValueError):
    """Raised when input data cannot be rendered safely."""


@dataclass(frozen=True)
class Route:
    slug: str
    data: dict
    source_name: str


@dataclass(frozen=True)
class BuildResult:
    output_dir: Path
    route_count: int


def text(value: object, default: str = "") -> str:
    return default if value is None else str(value)


def esc(value: object, default: str = "") -> str:
    return html.escape(text(value, default), quote=True)


def slugify(value: str) -> str:
    slug = re.sub(r"[^\w-]+", "-", value.strip().lower(), flags=re.UNICODE).strip("-")
    return slug or "roadbook"


def safe_external_url(value: object) -> str:
    candidate = text(value).strip()
    parsed = urlparse(candidate)
    return candidate if parsed.scheme in {"http", "https"} and parsed.netloc else ""


def redact_sensitive(value: object) -> object:
    """Remove common booking/identity fields before data reaches JSON or HTML."""
    if isinstance(value, dict):
        return {
            key: redact_sensitive(item)
            for key, item in value.items()
            if re.sub(r"[^a-z0-9]", "", str(key).lower()) not in SENSITIVE_KEYS
        }
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    return value


def color(value: object, fallback: str) -> str:
    candidate = text(value).strip()
    if re.fullmatch(r"#[0-9a-fA-F]{3,8}", candidate) or re.fullmatch(
        r"(?:rgb|rgba|hsl|hsla)\([^)]*\)", candidate
    ):
        return candidate
    return fallback


def validate_roadbook(data: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["roadbook must be an object"]

    trip = data.get("trip")
    if not isinstance(trip, dict):
        return ["missing trip object"]
    for field in ("title", "destination"):
        if not trip.get(field):
            errors.append(f"missing trip.{field}")

    days = data.get("days")
    if not isinstance(days, list) or not days:
        return errors + ["missing days"]
    for day_index, day in enumerate(days, start=1):
        if not isinstance(day, dict):
            errors.append(f"days[{day_index}] is not an object")
            continue
        if not day.get("date"):
            errors.append(f"days[{day_index}] missing date")
        stops = day.get("stops")
        if not isinstance(stops, list) or not stops:
            errors.append(f"days[{day_index}] missing stops")
            continue
        for stop_index, stop in enumerate(stops, start=1):
            if not isinstance(stop, dict):
                errors.append(f"days[{day_index}].stops[{stop_index}] is not an object")
            elif not stop.get("name"):
                errors.append(f"days[{day_index}].stops[{stop_index}] missing name")
    return errors


def map_links(stop: dict) -> list[tuple[str, str]]:
    queries = stop.get("mapQueries") or {}
    name = text(stop.get("name"), "Trip stop")
    amap = text(queries.get("amap"), name)
    google = text(queries.get("google"), name)
    apple = text(queries.get("apple"), google or name)
    return [
        ("高德", f"https://uri.amap.com/search?keyword={quote_plus(amap)}"),
        ("Google Maps", f"https://www.google.com/maps/search/?api=1&query={quote_plus(google)}"),
        ("Apple Maps", f"https://maps.apple.com/?q={quote_plus(apple)}"),
    ]


def all_stops(data: dict) -> list[dict]:
    stops: list[dict] = []
    for day in data.get("days", []):
        if isinstance(day, dict):
            stops.extend(stop for stop in day.get("stops", []) if isinstance(stop, dict))
    return stops


def source_records(data: dict) -> list[dict]:
    records = data.get("sourceRecords", data.get("sources", []))
    return [record for record in records if isinstance(record, dict)] if isinstance(records, list) else []


def route_slug(data: dict, source_name: str) -> str:
    trip = data.get("trip", {})
    return slugify(text(trip.get("slug")) or text(trip.get("title")) or Path(source_name).stem)


def legacy_paths(route: Route) -> list[PurePosixPath]:
    trip = route.data.get("trip", {})
    raw_paths = trip.get("legacyPaths", trip.get("legacyPath", []))
    if isinstance(raw_paths, str):
        raw_paths = [raw_paths]
    if not isinstance(raw_paths, list):
        raise BuildError(f"{route.source_name}: trip.legacyPaths must be a string or list")

    paths: list[PurePosixPath] = []
    for raw_path in raw_paths:
        candidate = PurePosixPath(text(raw_path).strip())
        if (
            not text(raw_path).strip()
            or candidate.is_absolute()
            or ".." in candidate.parts
            or candidate.suffix.lower() != ".html"
            or candidate == PurePosixPath("index.html")
            or candidate.parts[0] in {"assets", "routes"}
        ):
            raise BuildError(f"{route.source_name}: unsafe legacy path: {raw_path}")
        paths.append(candidate)
    return paths


def theme(config: dict) -> dict:
    merged = dict(DEFAULT_THEME)
    configured = config.get("theme")
    if isinstance(configured, dict):
        merged.update(configured)
    merged["primaryColor"] = color(merged.get("primaryColor"), DEFAULT_THEME["primaryColor"])
    merged["accentColor"] = color(merged.get("accentColor"), DEFAULT_THEME["accentColor"])
    merged["backgroundColor"] = color(merged.get("backgroundColor"), DEFAULT_THEME["backgroundColor"])
    return merged


def theme_style(config: dict) -> str:
    selected = theme(config)
    return (
        f' style="--primary:{esc(selected["primaryColor"])};'
        f'--accent:{esc(selected["accentColor"])};'
        f'--page-bg:{esc(selected["backgroundColor"])}"'
    )


def route_dates(trip: dict) -> str:
    start = text(trip.get("startDate"))
    end = text(trip.get("endDate"))
    return f"{start} — {end}" if start and end else start or end or "日期待定"


def render_map_links(stop: dict) -> str:
    links = [
        f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(label)}</a>'
        for label, url in map_links(stop)
    ]
    for link in stop.get("links") or []:
        if isinstance(link, dict):
            url = safe_external_url(link.get("url"))
            if url:
                links.append(
                    f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">'
                    f'{esc(link.get("label"), "打开链接")}</a>'
                )
    return "".join(links)


def render_stop(stop: dict, selected_theme: dict) -> str:
    image = safe_external_url(stop.get("image") or stop.get("imageUrl"))
    image_html = ""
    if image:
        image_html = (
            f'<figure class="stop-media"><img src="{esc(image)}" alt="{esc(stop.get("name"))}" '
            'loading="lazy" decoding="async" referrerpolicy="no-referrer">'
            f'<figcaption>Representative image: {esc(stop.get("name"))}</figcaption></figure>'
        )
    duration = stop.get("durationMinutes")
    duration_text = f"{int(duration)} 分钟" if isinstance(duration, (int, float)) else ""
    badges = "".join(
        item
        for item in [
            '<span class="badge must">必去</span>' if stop.get("mustGo") else "",
            f'<span class="badge">{esc(stop.get("type"), "地点")}</span>',
            f'<span class="badge">{esc(duration_text)}</span>' if duration_text else "",
        ]
        if item
    )
    deadline = (
        f'<p class="deadline"><strong>时间提醒：</strong>{esc(stop.get("deadline"))}</p>'
        if stop.get("deadline")
        else ""
    )
    fallback = (
        f'<p class="fallback"><strong>备选：</strong>{esc(stop.get("fallback"))}</p>'
        if stop.get("fallback")
        else ""
    )
    confidence = ""
    if selected_theme.get("showConfidence", True) and (stop.get("source") or stop.get("confidence")):
        confidence = (
            f'<p class="source">来源：{esc(stop.get("source"), "用户资料")} · '
            f'置信度：{esc(stop.get("confidence"), "unknown")}</p>'
        )
    return f"""
    <article class="stop">
      <div class="time">{esc(stop.get("time"), "灵活")}</div>
      <div class="stop-body">
        <div class="stop-heading"><h3>{esc(stop.get("name"))}</h3><div class="badges">{badges}</div></div>
        {image_html}
        <p>{esc(stop.get("description"), "按现场情况安排停留。")}</p>
        {deadline}{fallback}
        <div class="stop-links">{render_map_links(stop)}</div>
        {confidence}
      </div>
    </article>
    """.strip()


def render_info_cards(data: dict) -> str:
    sections: list[str] = []
    lodging = data.get("lodging") or []
    if lodging:
        cards = []
        for item in lodging:
            if not isinstance(item, dict):
                continue
            dates = " / ".join(filter(None, [text(item.get("checkIn")), text(item.get("checkOut"))]))
            notes = f'<p>{esc(item.get("notes"))}</p>' if item.get("notes") else ""
            cards.append(
                f'<article class="info-card"><h3>{esc(item.get("name"), "住宿")}</h3>'
                f'<p class="muted">{esc(dates)}</p><p>{esc(item.get("address"))}</p>{notes}</article>'
            )
        if cards:
            sections.append(f'<section class="info-section"><h2>住宿</h2><div class="info-grid">{"".join(cards)}</div></section>')
    transport = data.get("transport") or []
    if transport:
        cards = []
        for item in transport:
            if not isinstance(item, dict):
                continue
            route = " → ".join(filter(None, [text(item.get("from")), text(item.get("to"))]))
            schedule = " / ".join(filter(None, [text(item.get("departAt")), text(item.get("arriveAt"))]))
            cards.append(
                f'<article class="info-card"><h3>{esc(item.get("type"), "交通")}</h3>'
                f'<p class="muted">{esc(route)}</p><p>{esc(schedule)}</p>'
                f'{f"<p>{esc(item.get("notes"))}</p>" if item.get("notes") else ""}</article>'
            )
        if cards:
            sections.append(f'<section class="info-section"><h2>交通</h2><div class="info-grid">{"".join(cards)}</div></section>')
    return "".join(sections)


def render_sources(data: dict, selected_theme: dict) -> str:
    if not selected_theme.get("showSources", True):
        return ""
    cards = []
    for record in source_records(data):
        url = safe_external_url(record.get("url"))
        link = f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">打开来源</a>' if url else ""
        meta = " · ".join(
            filter(None, [text(record.get("id")), text(record.get("platform")), text(record.get("accessStatus")), text(record.get("confidence"))])
        )
        cards.append(
            f'<article class="source-card"><h3>{esc(record.get("title") or record.get("id"), "资料来源")}</h3>'
            f'<p class="muted">{esc(meta)}</p><p>{esc(record.get("excerpt"))}</p>{link}</article>'
        )
    if not cards:
        return ""
    return f'<section class="info-section source-section" id="sources"><h2>资料来源</h2><div class="info-grid">{"".join(cards)}</div></section>'


def render_route(route: Route, config: dict) -> str:
    data = route.data
    trip = data["trip"]
    selected_theme = theme(config)
    stops = all_stops(data)
    cover = safe_external_url(trip.get("coverImage") or selected_theme.get("defaultCoverImage"))
    hero_style = f' style="background-image:linear-gradient(90deg,rgba(0,0,0,.72),rgba(0,0,0,.18)),url(\'{esc(cover)}\')"' if cover else ""
    interests = " · ".join(text(item) for item in trip.get("interests", []) if item)
    day_nav = []
    day_sections = []
    for day in data.get("days", []):
        day_id = slugify(f'{text(day.get("date"))}-{text(day.get("title"))}')
        day_nav.append(f'<a href="#{esc(day_id)}">{esc(day.get("title"), "当天路线")}</a>')
        stops_html = "".join(render_stop(stop, selected_theme) for stop in day.get("stops", []))
        day_sections.append(
            f'<section class="day-card" id="{esc(day_id)}"><div class="day-head">'
            f'<p class="eyebrow">{esc(day.get("date"))}</p><h2>{esc(day.get("title"), "当日路线")}</h2>'
            f'<p>{esc(day.get("summary"))}</p></div><div class="timeline">{stops_html}</div></section>'
        )
    warning_items = "".join(f"<li>{esc(item)}</li>" for item in data.get("warnings", []) if item)
    warnings = f'<section class="warnings"><h2>出发前确认</h2><ul>{warning_items}</ul></section>' if warning_items else ""
    first_map = render_map_links(stops[0]).split("</a>", 1)[0] + "</a>" if stops else ""
    return f"""<!doctype html>
<html lang="{esc(selected_theme.get("language"), "zh-CN")}">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{esc(trip.get("title"))} · {esc(trip.get("destination"))}">
  <title>{esc(trip.get("title"))}</title><link rel="icon" href="data:,"><link rel="stylesheet" href="../../assets/roadbook.css">
</head>
<body{theme_style(config)}>
  <nav class="topnav"><a class="brand" href="../../index.html">{esc(config.get("author") or "Travel Roadbook")}</a><div class="nav-links"><a href="../../index.html">合集</a>{"".join(day_nav)}<a href="#sources">来源</a></div></nav>
  <header class="hero"{hero_style}><div class="hero-inner"><p class="eyebrow">Travel Roadbook</p><h1>{esc(trip.get("title"))}</h1><p>{esc(trip.get("destination"))} · {esc(route_dates(trip))} · {esc(trip.get("pace"), "standard")}</p><p>{esc(interests)}</p><div class="hero-actions"><a class="button primary" href="#route-start">开始行程</a>{f'<span class="hero-map">{first_map}</span>' if first_map else ""}</div></div></header>
  <main class="layout"><aside class="side-panel"><div class="summary"><div><b>{len(data.get("days", []))}</b><span>天</span></div><div><b>{len(stops)}</b><span>个节点</span></div><div><b>{len(source_records(data))}</b><span>份资料</span></div></div>{render_info_cards(data)}{render_sources(data, selected_theme)}{warnings}</aside><section class="days" id="route-start"><section class="intro"><p class="eyebrow">Personal route</p><h2>今天只看下一步</h2><p>把攻略、预订和风险提醒压缩成一张可执行的路线面板。地图、时间缓冲和备选方案都在每个地点下面。</p></section>{"".join(day_sections)}</section></main>
  <footer class="site-footer">Generated as a static roadbook. 出发前请确认实时营业时间和交通安排。</footer>
</body></html>"""


def render_collection(routes: list[Route], config: dict) -> str:
    selected_theme = theme(config)
    cards = []
    for route in routes:
        trip = route.data["trip"]
        days = route.data.get("days", [])
        first_day = days[0] if days else {}
        categories = " · ".join(text(item) for item in trip.get("interests", [])[:3] if item)
        summary = text(first_day.get("summary")) or text(trip.get("destination"))
        cards.append(
            f'<a class="collection-card" href="routes/{esc(route.slug)}/index.html">'
            f'<span>{esc(categories, "Travel Roadbook")}</span><h2>{esc(trip.get("title"))}</h2>'
            f'<p>{esc(summary)}</p><small>{esc(route_dates(trip))} · {len(days)} 天</small></a>'
        )
    logo = safe_external_url(selected_theme.get("logo"))
    logo_html = f'<img src="{esc(logo)}" alt="{esc(config.get("author"), "Logo")}">' if logo else ""
    empty = '<p class="empty-state">还没有路线。把第一个 roadbook JSON 放进 roadbooks/ 后重新构建。</p>' if not cards else ""
    return f"""<!doctype html>
<html lang="{esc(selected_theme.get("language"), "zh-CN")}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(config.get("title"), "Travel Roadbook Collection")}</title><link rel="icon" href="data:,"><link rel="stylesheet" href="assets/roadbook.css"></head>
<body class="collection"{theme_style(config)}><header class="collection-hero">{logo_html}<p class="eyebrow">{esc(config.get("author"), "Travel Collection")}</p><h1>{esc(config.get("title"), "Travel Roadbook Collection")}</h1><p>{esc(config.get("description"), "按目的地和路线整理的个人旅行路书。")}</p></header><main class="collection-grid">{empty}{"".join(cards)}</main><footer class="site-footer">Static travel roadbook collection</footer></body></html>"""


def render_legacy_redirect(route: Route, legacy_path: PurePosixPath) -> str:
    parent = str(legacy_path.parent)
    target = posixpath.relpath(f"routes/{route.slug}/index.html", parent if parent != "." else ".")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="0; url={esc(target)}">
  <link rel="canonical" href="{esc(target)}">
  <link rel="icon" href="data:,">
  <title>{esc(route.data["trip"].get("title"))}</title>
</head>
<body>
  <p>路线已迁移。<a href="{esc(target)}">打开新版路书</a></p>
</body>
</html>"""


def read_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    try:
        value = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BuildError(f"invalid config JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise BuildError("site config must be an object")
    return value


def load_routes(input_dir: Path) -> list[Route]:
    if not input_dir.exists():
        raise BuildError(f"roadbook input directory does not exist: {input_dir}")
    routes: list[Route] = []
    seen: set[str] = set()
    for source_path in sorted(input_dir.glob("*.json")):
        try:
            data = json.loads(source_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise BuildError(f"{source_path.name}: invalid JSON: {exc}") from exc
        data = redact_sensitive(data)
        errors = validate_roadbook(data)
        if errors:
            raise BuildError(f"{source_path.name}: {errors[0]}")
        slug = route_slug(data, source_path.name)
        if slug in seen:
            raise BuildError(f"duplicate route slug: {slug}")
        seen.add(slug)
        routes.append(Route(slug, data, source_path.name))
    return routes


def copy_output(staging: Path, output_dir: Path) -> None:
    if output_dir.exists():
        if not output_dir.is_dir():
            raise BuildError(f"output path is not a directory: {output_dir}")
        shutil.rmtree(output_dir)
    shutil.move(str(staging), str(output_dir))


def build_site(config_path: Path, input_dir: Path, output_dir: Path) -> BuildResult:
    config = read_config(Path(config_path))
    routes = load_routes(Path(input_dir))
    skill_dir = Path(__file__).resolve().parents[1]
    css_source = skill_dir / "assets" / "roadbook.css"
    if not css_source.exists():
        raise BuildError(f"missing bundled stylesheet: {css_source}")

    output_dir = Path(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}-", dir=str(output_dir.parent)))
    try:
        (staging / "assets").mkdir(parents=True)
        (staging / "routes").mkdir(parents=True)
        shutil.copy2(css_source, staging / "assets" / "roadbook.css")
        seen_legacy_paths: set[PurePosixPath] = set()
        for route in routes:
            route_dir = staging / "routes" / route.slug
            route_dir.mkdir(parents=True)
            (route_dir / "index.html").write_text(render_route(route, config), encoding="utf-8")
            (route_dir / "roadbook.json").write_text(json.dumps(route.data, ensure_ascii=False, indent=2), encoding="utf-8")
            for legacy_path in legacy_paths(route):
                if legacy_path in seen_legacy_paths:
                    raise BuildError(f"duplicate legacy path: {legacy_path}")
                seen_legacy_paths.add(legacy_path)
                redirect_path = staging.joinpath(*legacy_path.parts)
                redirect_path.parent.mkdir(parents=True, exist_ok=True)
                redirect_path.write_text(render_legacy_redirect(route, legacy_path), encoding="utf-8")
        (staging / "index.html").write_text(render_collection(routes, config), encoding="utf-8")
        (staging / ".nojekyll").write_text("", encoding="utf-8")
        copy_output(staging, output_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return BuildResult(output_dir=output_dir, route_count=len(routes))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a static personal travel-roadbook collection.")
    parser.add_argument("--config", required=True, type=Path, help="Path to site.config.json")
    parser.add_argument("--input", required=True, type=Path, help="Directory containing route JSON files")
    parser.add_argument("--out", required=True, type=Path, help="Output static-site directory")
    args = parser.parse_args(argv)
    try:
        result = build_site(args.config, args.input, args.out)
    except BuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"built {result.route_count} route(s) at {result.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
