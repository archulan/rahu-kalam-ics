# rahu-kalam-ics

Free, open-source, auto-updating Rahu Kalam calendar feeds you can add to Google
Calendar (or any iCalendar client) in under a minute. Timings are computed
locally from sunrise/sunset astronomy. Zero dependencies, no tracking, no
hosting cost.

Rahu Kalam is one of eight equal segments of the daytime (sunrise to sunset), so
the window shifts every day and differs by location. A fixed weekly event drifts
30 to 60+ minutes across seasons and latitudes; these feeds stay accurate because
every day is computed from the sun's position.

## Subscribe (recommended)

1. Find your city on the [subscribe page](https://archulan.github.io/rahu-kalam-ics/),
   or use the URL pattern below.
2. In Google Calendar: **Other calendars** -> **+** -> **From URL**, paste the
   `https://...ics` link, then **Add calendar**.
3. Done. The feed refreshes itself; you never re-import.

**Subscribe vs import.** Subscribing (From URL) keeps the calendar in sync as new
days are added. Importing a downloaded `.ics` is a one-time static copy that will
not update.

Feed URL pattern:

```
https://archulan.github.io/rahu-kalam-ics/<city>.ics
```

A few cities:

| City | Subscribe URL |
|------|---------------|
| Colombo | `https://archulan.github.io/rahu-kalam-ics/colombo.ics` |
| Jaffna | `https://archulan.github.io/rahu-kalam-ics/jaffna.ics` |
| Chennai | `https://archulan.github.io/rahu-kalam-ics/chennai.ics` |
| Bengaluru | `https://archulan.github.io/rahu-kalam-ics/bengaluru.ics` |
| Mumbai | `https://archulan.github.io/rahu-kalam-ics/mumbai.ics` |
| Delhi | `https://archulan.github.io/rahu-kalam-ics/delhi.ics` |

Run `python rahu_kalam_ics.py --list` for every available slug, or see the
subscribe page for all of them.

## Generate a feed for any location

The generator is a single stdlib-only Python file (Python 3.9+):

```
python rahu_kalam_ics.py --lat 13.0827 --lon 80.2707 --tz Asia/Kolkata --name Chennai
```

Options:

- `--city <slug>` use a built-in preset instead of coordinates
- `--start YYYY-MM-DD` first day (default: today, UTC)
- `--days N` horizon (default: 730)
- `--zenith D` sunrise definition (default: `90.833`, civil sunrise with
  refraction; `90.0` approximates centre-of-disk conventions some panchang
  traditions use)
- `--out PATH` output file
- `--all --out docs` regenerate every preset into a directory

## Accuracy and cultural sensitivity

Different panchang traditions define sunrise differently (upper limb with
refraction vs centre of disk), which produces legitimate variations of a few
minutes between sources. This project publishes astronomically computed timings,
states its convention (civil sunrise, zenith 90.833 degrees), offers `--zenith`
to switch, and takes no position on religious interpretation. It is not a
substitute for a full panchang.

## Contributing

Add your city with a small pull request. See [CONTRIBUTING.md](CONTRIBUTING.md);
a coordinate source is required.

## How it works

Sunrise and sunset are computed with the NOAA solar-position algorithm, the
daytime is divided into eight equal segments, and the segment for each weekday is
selected per tradition. Events are absolute UTC instants, so clients localise
them correctly across time zones and daylight saving with no extra handling. Full
specification in [PRD.md](PRD.md).

## License

[MIT](LICENSE).
