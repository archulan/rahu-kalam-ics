# Contributing

Thanks for helping extend the coverage. The most common contribution is adding a
city.

## Add a city

1. Open `rahu_kalam_ics.py` and add one entry to the `CITIES` dictionary:

   ```python
   "my-city": City("My City", 12.3456, 78.9012, "Asia/Kolkata"),
   ```

   - **slug** (the dictionary key): lowercase, hyphenated, URL-safe. It becomes
     the feed filename (`my-city.ics`) and part of every event UID, so it must
     never change once published.
   - **name**: the display name shown in the calendar.
   - **lat**: latitude, north-positive, 4 decimal places.
   - **lon**: longitude, **east-positive**, 4 decimal places (western longitudes
     are negative).
   - **tz**: the IANA timezone name (for example `Asia/Kolkata`, not the
     deprecated `Asia/Calcutta`).

2. **Cite your coordinate source** in the pull request description (a mapping
   service, a gazetteer, or an official source). City-centre coordinates are
   fine; sub-kilometre precision does not affect the timings.

3. Run the tests:

   ```
   pip install pytest
   pytest
   ```

   The suite lints the generated ICS and checks the astronomy against published
   golden fixtures.

## Guidelines

- Keep the core dependency-free and importable. Standard library only.
- Never add network calls, scraping, or analytics anywhere in the repo. The
  astronomy is public knowledge and is computed locally.
- Any change to a section marked **(normative)** in `PRD.md` must update the PRD
  in the same pull request.
- Published feed URLs and event UIDs are a breaking-change boundary. Renaming a
  slug orphans every existing subscriber, so treat slugs as permanent.
