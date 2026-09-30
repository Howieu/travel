# Roadbook JSON Schema

Each file in `roadbooks/` is a JSON object with this shape:

```json
{
  "trip": {
    "slug": "paris-weekend",
    "title": "Paris Weekend",
    "destination": "Paris",
    "startDate": "2026-09-10",
    "endDate": "2026-09-12",
    "pace": "standard",
    "interests": ["museum", "food"],
    "mustGo": ["Louvre Museum"],
    "avoid": ["tight transfers"],
    "coverImage": "https://example.com/paris.jpg",
    "legacyPaths": ["france/paris.html"]
  },
  "sourceRecords": [
    {
      "id": "note-001",
      "type": "pasted-note",
      "platform": "user",
      "title": "Paris notes",
      "url": null,
      "excerpt": "Evidence used for planning.",
      "accessStatus": "user-summary",
      "confidence": "medium"
    }
  ],
  "lodging": [],
  "transport": [],
  "days": [
    {
      "date": "2026-09-10",
      "title": "Arrival + Walk",
      "summary": "Keep the first afternoon flexible.",
      "stops": [
        {
          "time": "14:00",
          "name": "Louvre Museum",
          "type": "museum",
          "description": "Book ahead and keep an arrival buffer.",
          "durationMinutes": 150,
          "mustGo": true,
          "deadline": "Leave before 18:00",
          "fallback": "Skip the interior if arrival is late.",
          "image": "https://example.com/louvre.jpg",
          "mapQueries": {
            "amap": "卢浮宫 巴黎",
            "google": "Louvre Museum Paris",
            "apple": "Louvre Museum Paris"
          },
          "links": [{"label": "Official site", "url": "https://example.com/louvre"}],
          "source": "pasted notes",
          "sourceIds": ["note-001"],
          "confidence": "medium",
          "options": [
            {
              "name": "Parallel choice",
              "description": "Shown beside the other choices.",
              "deadline": "Pick one",
              "mapQueries": {
                "amap": "卢浮宫 巴黎",
                "google": "Louvre Museum Paris",
                "apple": "Louvre Museum Paris"
              }
            }
          ]
        }
      ]
    }
  ],
  "warnings": ["Verify opening hours before departure."]
}
```

Required fields: `trip.title`, `trip.destination`, `days[].date`, and `days[].stops[].name`. Keep old-style `source` for human display, but prefer stable `sourceIds` for evidence tracing. Optional fields can be omitted; the renderer supplies safe defaults.

`trip.legacyPaths` is optional. Each value must be a relative `.html` path without `..`; the builder creates a redirect so existing GitHub Pages links remain valid after migration.

`stops[].options` is optional. When present, the builder shows those choices side by side, each with its own map buttons. Use it for mutually exclusive endings, not for stops the traveler should visit in sequence.
