# PRD: rahu-kalam-ics

**Version:** 1.0 · **Date:** 2026-07-22 · **Status:** Ready for implementation
**License:** MIT
**Reference implementation:** `rahu_kalam_ics.py` (single-file core + CLI)

---

## 1. One-liner

Free, open-source, auto-updating Rahu Kalam calendar feeds that anyone can
add to Google Calendar (or any iCalendar client) in under a minute — computed
from sunrise/sunset astronomy, with zero dependencies and zero hosting cost.

## 2. Problem

Rahu Kalam is a daily ~90-minute inauspicious window in Hindu tradition. It is
one of eight equal segments of the daytime (sunrise → sunset), so its timing
**shifts every day and differs by city**. Consequences:

- Google Calendar's built-in "calendars of interest" only carries universal
  feeds (holidays, moon phases, sports). A location-dependent daily window
  doesn't fit that model, so no one-click option exists.
- Existing solutions are closed mobile apps or websites users must check
  manually every day. There is no public, subscribable, auditable feed.
- A naive recurring calendar event (e.g., "Mon 7:30–9:00 AM weekly") drifts
  30–60+ minutes from the true window across seasons and latitudes.

## 3. Goals

| # | Goal | Measure |
|---|------|---------|
| G1 | One-click adoption | User subscribes via URL in < 60 seconds, never needs to re-import |
| G2 | Accuracy | Within ±2 min of NOAA civil-sunrise math; within ~±5 min of major panchang sites |
| G3 | Zero cost, zero maintenance | Runs entirely on GitHub Actions + GitHub Pages free tier |
| G4 | Trustworthy & auditable | Fully open source, no scraping, no tracking, deterministic output |
| G5 | Universal coverage | Curated city presets (Appendix C); script handles any lat/lon on Earth |

## 4. Non-goals

- Full panchang data (tithi, nakshatra, choghadiya, festivals).
- Astrological interpretation, predictions, or muhurta recommendations.
- Mobile apps or accounts of any kind.
- Scraping third-party panchang websites (their pages are copyrighted; the
  underlying astronomy is public knowledge and is computed locally instead).
- Push notifications (users can enable per-calendar notifications in their
  own client; feeds MUST NOT embed `VALARM`).

## 5. Users

- **Observant individuals** who want the window visible while scheduling
  meetings, travel, signings, or ceremonies.
- **Families/teams** sharing one subscribed calendar (times auto-localize).
- **Diaspora users** in DST timezones (US, UK, AU) where manual mental math
  is error-prone.
- **Self-hosters/contributors** who fork the repo for their town or tradition.

## 6. User stories

1. As a user, I paste a URL under *Google Calendar → Other calendars → From
   URL* and see accurate daily Rahu Kalam for my city forever after.
2. As a user, I download a `.ics` for my city and import it once if I prefer
   a static copy.
3. As a power user, I run one command with `--lat/--lon` to generate a feed
   for a location that has no preset.
4. As a contributor, I add my city with a small pull request (name,
   coordinates, timezone) and CI publishes it automatically.

## 7. Functional requirements

Priorities: **P0** = must ship in v1, **P1** = should ship soon after,
**P2** = stretch.

**FR-1 (P0) — CLI generator.** A single-file Python script that emits an
RFC 5545 `.ics` given a location and date range.
Inputs: `--city <preset>` OR (`--lat --lon [--tz] [--name]`), `--start`
(default: today), `--days` (default: 730), `--zenith` (default: 90.833),
`--out` (default: `rahu-kalam-<slug>.ics`). Exit non-zero with a clear
message on invalid input.

**FR-2 (P0) — City presets.** Built-in presets (Appendix C): slug →
(lat to 4 d.p., lon east-positive to 4 d.p., IANA timezone). Contributors
extend via PR.

**FR-3 (P0) — Correct algorithm.** Exactly as specified in §8. Golden-fixture
tests in §11 MUST pass.

**FR-4 (P0) — ICS conformance.** See §9. Output MUST render correctly in
Google Calendar and Apple Calendar.

**FR-5 (P0) — Rolling horizon.** Default 730 days so a monthly regeneration
schedule leaves a large safety margin; each city feed MUST stay < 1 MB.

**FR-6 (P0) — Automated regeneration.** A GitHub Actions workflow on a
monthly cron (plus `workflow_dispatch`) regenerates every preset city into
`docs/` and commits. Workflow MUST fail loudly (non-zero) if any city fails.

**FR-7 (P0) — Hosting.** GitHub Pages serves `docs/`, giving stable URLs:
`https://<owner>.github.io/rahu-kalam-ics/<slug>.ics`. URLs MUST NOT change
once published (renames = breaking change).

**FR-8 (P1) — Landing page.** `docs/index.html`, minimal static HTML/CSS (no
framework, no JS build step): project explanation, per-city subscribe URLs
with copy buttons, `webcal://` links, subscribe-vs-import instructions, and
the accuracy disclaimer from §10. Mobile-friendly.

**FR-9 (P1) — Sunrise convention flag.** `--zenith` exposed and documented:
`90.833` = civil sunrise (upper limb + refraction, default); `90.0`
approximates centre-of-disk conventions used by some panchang traditions.

**FR-10 (P2) — Sibling feeds.** Optional Yamagandam and Gulika Kalam feeds
using the segment tables in Appendix B (same engine, different table).
Gate on the verification acceptance criterion in §11.

**FR-11 (P2) — Arbitrary-location endpoint.** A tiny serverless function
(e.g., Cloudflare Worker) serving `/?lat=&lon=&days=` for the long tail of
locations. Out of scope for v1; design so the core module is importable.

## 8. Algorithm specification (normative)

### 8.1 Rahu Kalam

1. For each **local calendar date** `d`, compute sunrise and sunset as UTC
   instants (§8.2).
2. `segment = (sunset − sunrise) / 8`.
3. Select segment index `n` by weekday of `d` (local date's weekday):

   | Weekday | Python `weekday()` | Rahu segment (1-indexed) |
   |---|---|---|
   | Monday | 0 | 2 |
   | Tuesday | 1 | 7 |
   | Wednesday | 2 | 5 |
   | Thursday | 3 | 6 |
   | Friday | 4 | 4 |
   | Saturday | 5 | 3 |
   | Sunday | 6 | 8 |

4. `start = sunrise + (n − 1) × segment`; `end = start + segment`.

### 8.2 Sunrise/sunset

NOAA solar position algorithm (as in the NOAA solar calculator): Julian
century from J2000 evaluated at approximate local solar noon; geometric mean
longitude/anomaly, equation of center, apparent longitude, corrected
obliquity, declination, equation of time; hour angle from
`cos H = cos(zenith)/(cos φ · cos δ) − tan φ · tan δ` with zenith 90.833° by
default. Convert to UTC minutes via
`noon = 720 − 4·lon − eqtime` (longitude east-positive), `rise = noon − 4H`,
`set = noon + 4H`. Target accuracy ±1 minute; single-pass evaluation at noon
is acceptable. The prototype implements this and matches published panchang
timings within 1 minute (§11) — treat it as the reference.

### 8.3 Edge cases (normative)

- `|cos H| > 1` (polar day/night): **skip the date**, emit no event.
- Longitudes far east/west may place the UTC instant on the adjacent UTC
  date; datetime arithmetic MUST handle this (no date clamping).
- DST needs **no special handling**: events are absolute UTC instants;
  clients localize. `X-WR-TIMEZONE` is cosmetic metadata only. Do NOT emit
  `VTIMEZONE` blocks.
- Leap days are ordinary dates.

## 9. ICS output specification (normative)

- RFC 5545: CRLF line endings; content lines folded to ≤ 74 octets with
  leading-space continuation.
- Calendar props: `VERSION:2.0`, `PRODID`, `CALSCALE:GREGORIAN`,
  `METHOD:PUBLISH`, `X-WR-CALNAME:Rahu Kalam — <City>`,
  `X-WR-TIMEZONE:<IANA tz>`, `X-WR-CALDESC` carrying the §10 disclaimer.
- Per event: `UID`, `DTSTAMP`, `DTSTART`/`DTEND` in UTC (`...Z` form),
  `SUMMARY:Rahu Kalam`, `LOCATION:<City>`, `TRANSP:TRANSPARENT` (shows as
  Free; never blocks scheduling assistants), short `DESCRIPTION`.
- **UID stability (MUST):** `rahukalam-<YYYY-MM-DD>-<slug>@rahu-kalam-ics`,
  identical across regenerations so subscribed clients update in place
  rather than duplicate.
- **Diff hygiene (SHOULD):** set `DTSTAMP` to 00:00:00Z of the generation
  date so monthly CI commits produce reviewable diffs.
- Escape `,` `;` `\` and newline (`\n`) in text values per RFC 5545.

## 10. Accuracy & cultural-sensitivity notes (must appear in README, CALDESC, and landing page)

Different panchang traditions define sunrise differently (upper limb with
refraction vs. centre of disk), producing legitimate 2–4 minute variations
between sources. This project publishes astronomically computed timings,
states its convention, offers `--zenith` to switch, and takes no position on
religious interpretation. Tone everywhere: respectful, factual, no
predictions or advice.

## 11. Test plan & acceptance criteria

All tests via `pytest`, stdlib + pytest only. CI runs them on every PR.

**T1 (P0) — Golden fixtures.** Computed windows MUST fall within ±2 minutes
of these published Drik Panchang timings (IST):

| City | Coordinates | Local date | Weekday | Expected window |
|---|---|---|---|---|
| Delhi | 28.6139 N, 77.2090 E | 2026-07-21 | Tue | 15:53–17:36 |
| Bengaluru | 12.9716 N, 77.5946 E | 2026-07-19 | Sun | 17:14–18:50 |
| Delhi | 28.6139 N, 77.2090 E | 2026-05-25 | Mon | 07:09–08:52 |

(Prototype achieves ≤ 1 min deviation on all three.)

**T2 (P0) — Weekday mapping.** Unit test the full table in §8.1.

**T3 (P0) — ICS lint.** Generated file: CRLF endings; every line ≤ 75
octets; balanced BEGIN/END; required properties present; event count =
`--days` minus polar skips; UIDs unique and match the scheme.

**T4 (P0) — Determinism.** Two runs with identical args (and pinned
generation date) produce byte-identical output.

**T5 (P0) — Edge cases.** Equator city (Singapore: near-constant ~90-min
windows year-round); high latitude (Tromsø 69.65 N, 18.96 E: polar dates
skipped, no exceptions); southern hemisphere (Sydney) runs cleanly; a DST
city (New York) spot-checked across a DST boundary.

**T6 (P0) — CLI contract.** Bad input (unknown city, lat without lon,
malformed date) exits non-zero with a helpful message.

**T7 (P1) — Zenith flag.** `--zenith 90.0` shifts windows by roughly 2–4
minutes vs. default in a plausible direction.

**T8 (P2 gate) — Sibling tables.** Before shipping FR-10, verify Appendix B
segment tables against at least two independent published panchang sources;
record the sources in the test file.

**Release acceptance:** all P0 tests green; a generated Chennai feed imports
into Google Calendar and renders correct local times; subscribe-by-URL
verified end-to-end from a Pages deployment; workflow dry-run succeeds.

## 12. Repository layout

```
rahu-kalam-ics/
├── rahu_kalam_ics.py          # single-file core + CLI (stdlib only)
├── tests/test_core.py         # T1–T7
├── docs/                      # GitHub Pages root
│   ├── index.html             # FR-8 landing page
│   └── <slug>.ics             # generated feeds (committed by CI)
├── .github/workflows/
│   ├── ci.yml                 # pytest on PRs
│   └── regenerate.yml         # monthly cron → regenerate docs/*.ics
├── README.md                  # usage, subscribe instructions, accuracy notes
├── CONTRIBUTING.md            # how to add a city (coords source required)
├── LICENSE                    # MIT
└── PRD.md                     # this document
```

## 13. Milestones

- **M0 — done.** Validated prototype exists (`rahu_kalam_ics.py`): NOAA
  math, ICS writer, 3 golden fixtures within 1 minute.
- **M1 — Core + tests (P0).** Harden prototype per §§8–9, full T1–T6 suite,
  CONTRIBUTING, README. *Done when CI is green.*
- **M2 — Automation + hosting (P0).** ~30 preset cities, `regenerate.yml`,
  Pages live, subscribe-by-URL verified in Google Calendar. *Done when a
  fresh browser can subscribe to Chennai in < 60 s.*
- **M3 — Landing page (P1).** FR-8 + FR-9 shipped and linked from README.
- **M4 — Stretch (P2).** FR-10 after T8 verification; FR-11 design note.

## 14. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Users dispute timings vs. their preferred source | §10 disclaimer everywhere; `--zenith` flag; document the convention |
| Google refreshes subscribed feeds slowly (can be ~a day) | Irrelevant by design: events are precomputed 730 days ahead |
| Maintainer goes inactive | Scheduled Actions keep feeds fresh unattended for years; MIT license enables forks |
| URL/UID churn breaks subscribers | FR-7 + §9 stability rules treated as breaking-change boundaries |
| Wrong sibling-feed tables damage trust | FR-10 gated behind T8 two-source verification |

## 15. Open questions (non-blocking; decide during M2)

1. Final city list — decided: Sri Lanka (Colombo, Jaffna), Tamil Nadu plus
   the major Indian metros, and the 8 diaspora cities (see Appendix C).
2. Event summary language — English only for v1, or localized summaries
   (e.g., ராகு காலம் / राहु काल) as a variant feed later?
3. Repo/Pages naming — `rahu-kalam-ics` vs. a broader name if sibling feeds
   ship (e.g., `panchang-feeds`).

## 16. Implementation notes

1. Start from the reference `rahu_kalam_ics.py` if provided; otherwise
   implement §8 from scratch — the spec is complete.
2. Write T1 golden-fixture tests **first**; they pin the astronomy.
3. Keep the core zero-dependency and importable (`main()` guard) so FR-11
   can reuse it later.
4. Never add network calls, scraping, or analytics anywhere in the repo.
5. Any deviation from a **(normative)** section requires updating this PRD
   in the same PR.

---

## Appendix A — Standard-times sanity table (for an idealized 06:00–18:00 day)

Mon 07:30–09:00 · Tue 15:00–16:30 · Wed 12:00–13:30 · Thu 13:30–15:00 ·
Fri 10:30–12:00 · Sat 09:00–10:30 · Sun 16:30–18:00. Useful for quick
eyeballing only; real output MUST use computed sunrise/sunset.

## Appendix B — Sibling segment tables (verify per T8 before use)

| Weekday | Yamagandam segment | Gulika Kalam segment |
|---|---|---|
| Monday | 4 | 6 |
| Tuesday | 3 | 5 |
| Wednesday | 2 | 4 |
| Thursday | 1 | 3 |
| Friday | 7 | 2 |
| Saturday | 6 | 1 |
| Sunday | 5 | 7 |

## Appendix C — Preset cities

Sri Lanka: Colombo, Jaffna.
India: Chennai, Bengaluru, Mumbai, Delhi, Coimbatore, Madurai,
Tiruchirappalli.
Diaspora: Singapore, Kuala Lumpur, Dubai, London, New York, San Jose,
Toronto, Sydney.
Each preset PR must cite a coordinate source; lat/lon to 4 decimal places;
IANA timezone required.
