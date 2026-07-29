#!/usr/bin/env python3
"""Convert the original static travel pages into editable roadbook JSON files."""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, unquote_plus, urlparse


TAG_RE = re.compile(r"<[^>]+>")


def clean_text(fragment: str) -> str:
    value = TAG_RE.sub(" ", fragment)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def first_match(pattern: str, value: str, default: str = "", flags: int = re.S | re.I) -> str:
    match = re.search(pattern, value, flags)
    return clean_text(match.group(1)) if match else default


def attr_value(fragment: str, attribute: str) -> str:
    match = re.search(rf"\b{re.escape(attribute)}=[\"']([^\"']*)[\"']", fragment, re.I)
    return html.unescape(match.group(1)).strip() if match else ""


def extract_links(fragment: str) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    for match in re.finditer(r"<a\b([^>]*)>(.*?)</a>", fragment, re.S | re.I):
        url = attr_value(match.group(1), "href")
        label = clean_text(match.group(2))
        if url.startswith(("http://", "https://")):
            links.append({"label": label or "Open link", "url": url})
    return links


def map_query(url: str, key: str) -> str:
    query = parse_qs(urlparse(url).query)
    return unquote_plus(query.get(key, [""])[0]).strip()


def split_links(links: list[dict[str, str]], stop_name: str) -> tuple[dict[str, str], list[dict[str, str]]]:
    maps = {"amap": stop_name, "google": stop_name, "apple": stop_name}
    extras: list[dict[str, str]] = []
    for link in links:
        label = link["label"].lower()
        url = link["url"]
        host = urlparse(url).netloc.lower()
        if "google" in label or "google." in host:
            maps["google"] = map_query(url, "query") or map_query(url, "q") or stop_name
        elif "apple" in label or "maps.apple.com" in host:
            maps["apple"] = map_query(url, "q") or stop_name
        elif "高德" in link["label"] or "amap" in host:
            maps["amap"] = map_query(url, "keyword") or map_query(url, "q") or stop_name
        else:
            extras.append(link)
    return maps, extras


def day_label(raw_title: str, index: int) -> tuple[str, str]:
    match = re.match(r"Day\s*(\d+)\s*(?:[·:—-]\s*)?(.*)", raw_title, re.I)
    if match:
        suffix = match.group(2).strip()
        return f"Day {match.group(1)}", suffix or raw_title
    return f"Day {index}", raw_title


def extract_fallback(description: str) -> tuple[str, str]:
    sentences = [item.strip() for item in re.split(r"(?<=[。！？；])", description) if item.strip()]
    fallback_sentences = [
        item
        for item in sentences
        if re.search(r"(如果|若|来不及|延误|天气|备选)", item)
        and re.search(r"(跳过|缩短|改为|叫车|取消|留在|回酒店|不去|备选)", item)
    ]
    if not fallback_sentences:
        return description, ""
    fallback = " ".join(fallback_sentences)
    remaining = " ".join(item for item in sentences if item not in fallback_sentences).strip()
    return remaining or "按现场情况安排停留。", fallback


def parse_stop(fragment: str) -> dict:
    name = first_match(r"<h3[^>]*>(.*?)</h3>", fragment, "Unnamed stop")
    description_fragment = re.search(r"<p[^>]*>(.*?)</p>", fragment, re.S | re.I)
    description_html = description_fragment.group(1) if description_fragment else ""
    deadline = first_match(r"<span[^>]*class=[\"'][^\"']*deadline[^\"']*[\"'][^>]*>(.*?)</span>", description_html)
    description_html = re.sub(
        r"<span[^>]*class=[\"'][^\"']*deadline[^\"']*[\"'][^>]*>.*?</span>",
        "",
        description_html,
        flags=re.S | re.I,
    )
    image_match = re.search(r"<img\b([^>]*)>", fragment, re.S | re.I)
    image = attr_value(image_match.group(1), "src") if image_match else ""
    links_fragment = first_match(
        r"<div[^>]*class=[\"'][^\"']*stop-links[^\"']*[\"'][^>]*>(.*?)</div>",
        fragment,
        "",
    )
    raw_links_match = re.search(
        r"<div[^>]*class=[\"'][^\"']*stop-links[^\"']*[\"'][^>]*>(.*?)</div>",
        fragment,
        re.S | re.I,
    )
    links = extract_links(raw_links_match.group(1) if raw_links_match else links_fragment)
    maps, extra_links = split_links(links, name)
    description, fallback = extract_fallback(clean_text(description_html) or "按现场情况安排停留。")
    stop = {
        "time": first_match(r"<div[^>]*class=[\"'][^\"']*time[^\"']*[\"'][^>]*>(.*?)</div>", fragment, "flexible"),
        "name": name,
        "description": description,
        "mapQueries": maps,
        "source": "Migrated personal roadbook",
        "sourceIds": ["legacy-route"],
        "confidence": "high",
    }
    if deadline:
        stop["deadline"] = deadline
    if fallback:
        stop["fallback"] = fallback
    if image.startswith(("http://", "https://")):
        stop["image"] = image
    if extra_links:
        stop["links"] = extra_links
    return stop


def parse_legacy_page(path: Path, source_root: Path, base_url: str) -> dict:
    source = path.read_text(encoding="utf-8")
    relative_path = path.relative_to(source_root).as_posix()
    title = first_match(r"<div[^>]*class=[\"'][^\"']*hero-inner[^\"']*[\"'][^>]*>.*?<h1[^>]*>(.*?)</h1>", source)
    if not title:
        title = first_match(r"<title[^>]*>(.*?)</title>", source).removesuffix(" Roadbook")
    hero_block_match = re.search(
        r"<div[^>]*class=[\"'][^\"']*hero-inner[^\"']*[\"'][^>]*>(.*?)</div>\s*</header>",
        source,
        re.S | re.I,
    )
    hero_block = hero_block_match.group(1) if hero_block_match else ""
    summary = first_match(r"<h1[^>]*>.*?</h1>\s*<p[^>]*>(.*?)</p>", hero_block, title)
    interests_match = re.search(r"<div[^>]*class=[\"'][^\"']*chips[^\"']*[\"'][^>]*>(.*?)</div>", hero_block, re.S | re.I)
    interests = [
        clean_text(item)
        for item in re.findall(r"<span[^>]*>(.*?)</span>", interests_match.group(1) if interests_match else "", re.S | re.I)
        if clean_text(item)
    ]
    cover_match = re.search(r"<header[^>]*class=[\"'][^\"']*hero[^\"']*[\"'][^>]*style=[\"'][^\"']*url\(['\"]?([^'\")]+)", source, re.I)
    cover = html.unescape(cover_match.group(1)).strip() if cover_match else ""
    destination_cards = re.findall(r"<div[^>]*class=[\"'][^\"']*summary[^\"']*[\"'][^>]*>(.*?)</div>\s*</div>", source, re.S | re.I)
    destination_values = re.findall(r"<b[^>]*>(.*?)</b>", destination_cards[0], re.S | re.I) if destination_cards else []
    destination = clean_text(destination_values[1]) if len(destination_values) > 1 else title

    days = []
    for day_index, match in enumerate(
        re.finditer(r"<section[^>]*class=[\"'][^\"']*day-card[^\"']*[\"'][^>]*>(.*?)</section>", source, re.S | re.I),
        start=1,
    ):
        fragment = match.group(1)
        raw_title = first_match(r"<div[^>]*class=[\"'][^\"']*day-head[^\"']*[\"'][^>]*>.*?<h2[^>]*>(.*?)</h2>", fragment, f"Day {day_index}")
        date, day_title = day_label(raw_title, day_index)
        summary_text = first_match(
            r"<div[^>]*class=[\"'][^\"']*day-head[^\"']*[\"'][^>]*>.*?<h2[^>]*>.*?</h2>\s*<p[^>]*>(.*?)</p>",
            fragment,
        )
        stops = [
            parse_stop(stop_match.group(1))
            for stop_match in re.finditer(r"<article[^>]*class=[\"'][^\"']*stop[^\"']*[\"'][^>]*>(.*?)</article>", fragment, re.S | re.I)
        ]
        if stops:
            days.append({"date": date, "title": day_title, "summary": summary_text, "stops": stops})

    if not days:
        raise ValueError(f"{relative_path}: no route days found")

    slug = path.stem.lower().replace("_", "-")
    trip = {
        "slug": slug,
        "title": title,
        "destination": destination,
        "pace": "standard",
        "interests": interests,
        "legacyPaths": [relative_path],
    }
    if cover.startswith(("http://", "https://")):
        trip["coverImage"] = cover
    return {
        "trip": trip,
        "sourceRecords": [
            {
                "id": "legacy-route",
                "type": "user-roadbook",
                "platform": "user",
                "title": f"{title} personal route",
                "url": None,
                "excerpt": summary,
                "accessStatus": "user-summary",
                "confidence": "high",
            }
        ],
        "lodging": [],
        "transport": [],
        "days": days,
        "warnings": ["出发前请再次确认实时营业时间、天气和交通安排。"],
    }


def migrate(source_root: Path, output_dir: Path, base_url: str) -> int:
    pages = sorted(
        path
        for path in source_root.rglob("*.html")
        if path.name != "index.html" and ".git" not in path.parts and "dist" not in path.parts
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for page in pages:
        route = parse_legacy_page(page, source_root, base_url)
        destination = output_dir / f'{route["trip"]["slug"]}.json'
        destination.write_text(json.dumps(route, ensure_ascii=False, indent=2), encoding="utf-8")
        count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate legacy travel HTML pages to roadbook JSON.")
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--base-url", default="https://howieu.github.io/travel")
    args = parser.parse_args()
    count = migrate(args.source_root, args.output, args.base_url)
    print(f"migrated {count} route(s) to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
