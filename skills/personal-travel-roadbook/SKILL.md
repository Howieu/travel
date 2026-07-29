---
name: personal-travel-roadbook
description: Generate and maintain personalized static travel-roadbook collections from user notes, public guide URLs, booking screenshots, hotels, transport details, and travel preferences. Use when a user wants a mobile-readable itinerary site with day-by-day stops, buffers, fallbacks, source evidence, and Amap/Google Maps/Apple Maps links.
---

# Personal Travel Roadbook

Generate an editable JSON source and a portable static website. Keep the workflow grounded in the user's dates, bookings, pace, interests, must-go places, and avoid list; preserve uncertainty instead of inventing live schedules or opening hours.

## Workflow

1. Collect the minimum trip brief. Read [references/input-format.md](references/input-format.md) when the user provides raw materials or asks what to submit.
2. Require destination and travel dates. Ask only for missing facts that block a usable route; hotel details are helpful but not blocking.
3. Read pasted notes and public URLs with the available browser/research tools. If a URL is unreadable, keep it as an `unreadable` source record and ask for pasted text or a screenshot. Never claim to have read a page that was not accessible.
4. Extract only itinerary fields from booking screenshots: dates, times, airports/stations, hotel, and transport constraints. Omit names, booking references, QR codes, payment details, passport/ID data, phone numbers, and email addresses.
5. Read [references/roadbook-schema.md](references/roadbook-schema.md) and generate one `roadbooks/<slug>.json` file per route. Keep `sourceRecords` at the top level and reference them with `sourceIds` where evidence exists.
6. Apply [references/itinerary-rules.md](references/itinerary-rules.md). Respect arrival/departure buffers, pace, must-go priorities, transfer time, and skip/fallback options. Mark unverified times and schedules with low confidence and a warning.
7. Read [references/deployment.md](references/deployment.md), then build the collection:

   ```bash
   python skills/personal-travel-roadbook/scripts/build_site.py \
     --config site.config.json \
     --input roadbooks \
     --out dist
   ```

8. Inspect the generated `dist/index.html` and route pages. Report route count, unreadable sources, and departure checks. Do not deploy or host the site unless the user explicitly asks.

## Output Contract

- `dist/index.html`: collection landing page.
- `dist/routes/<slug>/index.html`: one mobile-readable route page per JSON file.
- `dist/routes/<slug>/roadbook.json`: the editable source copied with the route.
- `dist/assets/roadbook.css`: the bundled visual theme.
- Each stop has Amap, Google Maps, and Apple Maps search links. Extra official links are preserved only when they use `http` or `https`.
- External images are optional. Do not block generation when an image is missing or unavailable.
- Theme values come from `site.config.json`; customize title, description, author, logo, cover image, language, primary color, accent color, and background color without changing the layout.

## References

- [Input format and screenshot privacy](references/input-format.md)
- [Roadbook JSON schema](references/roadbook-schema.md)
- [Itinerary rules](references/itinerary-rules.md)
- [Source quality and uncertainty](references/source-quality.md)
- [Static deployment](references/deployment.md)

## Validation

The builder validates every route before creating the output directory. Required fields are `trip.title`, `trip.destination`, `days[]`, `days[].date`, and `days[].stops[].name`. Fix the reported JSON path and rebuild when validation fails.
