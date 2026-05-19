# Travel Routes

This repository hosts my personal travel itinerary pages as static HTML sites through GitHub Pages.

Live site: https://howieu.github.io/travel/

## How to Use

Open the main travel index first:

```text
https://howieu.github.io/travel/
```

From there, choose a country or route. Each route is a standalone HTML page with itinerary details, map links, and embedded map views where available.

## Direct Links

| Route | URL |
| --- | --- |
| UK / London | https://howieu.github.io/travel/uk/london.html |
| UK / London map | https://howieu.github.io/travel/uk/map.html |
| France | https://howieu.github.io/travel/france/ |
| France + Switzerland | https://howieu.github.io/travel/france-switzerland/ |
| France + Switzerland: Rigi | https://howieu.github.io/travel/france-switzerland/rigi.html |
| France + Switzerland: Zurich | https://howieu.github.io/travel/france-switzerland/zurich.html |
| Italy + Switzerland | https://howieu.github.io/travel/italy-switzerland/ |
| Netherlands | https://howieu.github.io/travel/netherlands/ |
| Norway | https://howieu.github.io/travel/norway/ |
| Spain | https://howieu.github.io/travel/spain/ |
| Barcelona map | https://howieu.github.io/travel/spain/barcelona-map.html |

## Repository Structure

```text
.
├── .nojekyll
├── README.md
├── index.html                  # Main travel landing page
├── uk/
│   ├── london.html
│   └── map.html
├── london/
│   ├── index.html
│   └── map.html
├── france/
│   └── index.html
├── france-switzerland/
│   ├── index.html
│   ├── day2.html
│   ├── first.html
│   ├── plan.html
│   ├── rigi.html
│   └── zurich.html
├── italy-switzerland/
│   └── index.html
├── netherlands/
│   └── index.html
├── norway/
│   └── index.html
└── spain/
    ├── index.html
    └── barcelona-map.html
```

## Adding a New Trip

1. Create a folder using a clear lowercase country or route name, for example `japan/` or `portugal-spain/`.
2. Add the page inside that folder, for example `japan/tokyo.html` or `portugal-spain/index.html`.
3. Keep extra pages inside the same folder, for example `map.html` or `day2.html`.
4. Update the root `index.html` so the new trip appears on the main landing page.
5. Update this README with the new direct link.

## Local Preview

The pages are static HTML and can be previewed without a build step:

```bash
python3 -m http.server 8000
```

Then open:

```text
http://localhost:8000/
```

## Notes

- `.nojekyll` is included so GitHub Pages serves the static HTML files directly.
- Most pages depend on external services such as Google Maps, Apple Maps, OpenStreetMap, Leaflet, or CDN-hosted libraries.
- Old route-specific repositories have been consolidated into this repository; use the links above as the stable entry points.
