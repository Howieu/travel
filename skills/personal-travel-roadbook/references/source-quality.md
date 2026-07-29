# Source Quality

Use these values consistently:

- `high`: user booking evidence, user-provided exact details, or a readable official source.
- `medium`: readable guide or repeated secondary-source detail that still needs checking.
- `low`: inaccessible link, memory-based suggestion, approximate time, or stale/unclear source.

Use `accessStatus` values `read`, `partial`, `unreadable`, and `user-summary`. Keep an unreadable URL in `sourceRecords` when it influenced the request, but do not extract unsupported facts from it. Add a warning whenever low-confidence information affects timing, opening hours, tickets, or transport.
