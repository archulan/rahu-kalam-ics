#!/usr/bin/env python3
"""Generate RFC 5545 Rahu Kalam calendar feeds from sunrise/sunset astronomy.

Rahu Kalam is one of eight equal segments of the daytime (sunrise to sunset) in
Hindu tradition, so its window shifts every day and differs by location. This
module computes the window locally with the NOAA solar-position algorithm and
emits a subscribable ``.ics`` feed. It has zero third-party dependencies and is
importable (no side effects at import time) so the core can be reused elsewhere.

All event instants are absolute UTC. Clients localise them, so no VTIMEZONE and
no per-event alarm (VALARM) are emitted; the calendar is a passive information
feed that never blocks scheduling.
"""

import argparse
import math
import os
import re
import sys
from collections import namedtuple
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


# --- Configuration ----------------------------------------------------------

# Weekday (Python date.weekday(): Mon=0 .. Sun=6) -> 1-indexed daytime octave
# that Rahu Kalam occupies. This mapping is the defining table of the tradition.
RAHU_SEGMENTS = {0: 2, 1: 7, 2: 5, 3: 6, 4: 4, 5: 3, 6: 8}

# 90.833 deg is civil sunrise: the geometric zenith of the sun's upper limb once
# atmospheric refraction is accounted for. 90.0 approximates centre-of-disk
# conventions some panchang traditions use; exposed via --zenith.
DEFAULT_ZENITH = 90.833

# Two years keeps a monthly regeneration schedule far ahead of any client's slow
# feed refresh while staying well under the ~1 MB per-feed budget.
DEFAULT_DAYS = 730

# Fold content lines at 74 octets, one below the RFC 5545 hard ceiling of 75, so
# the leading space a continuation line carries never pushes it over the limit.
FOLD_LIMIT = 74

PRODID = "-//rahu-kalam-ics//NONSGML rahu-kalam-ics//EN"

# Shown in clients (X-WR-CALDESC) and mirrored in the README and landing page.
# Factual and non-prescriptive: it states the convention and takes no religious
# position, per the project's cultural-sensitivity commitment.
DISCLAIMER = (
    "Astronomically computed Rahu Kalam timings. Panchang traditions define "
    "sunrise differently (upper limb with refraction vs centre of disk), which "
    "produces legitimate variations of a few minutes between sources. This feed "
    "uses civil sunrise (zenith 90.833 degrees) and takes no position on "
    "religious interpretation."
)

DESCRIPTION = (
    "Rahu Kalam window for {city}, computed locally from sunrise and sunset. "
    "Timings vary slightly between panchang traditions."
)


City = namedtuple("City", ["name", "lat", "lon", "tz"])

# Preset locations: slug -> City(name, latitude north-positive, longitude
# east-positive, IANA timezone). Coordinates are city-centre values to 4 d.p.;
# sub-kilometre scatter between sources is irrelevant to sunrise/sunset timing.
# Use Asia/Kolkata (never the deprecated Asia/Calcutta) for Indian cities.
CITIES = {
    "chennai": City("Chennai", 13.0827, 80.2707, "Asia/Kolkata"),
    "bengaluru": City("Bengaluru", 12.9716, 77.5946, "Asia/Kolkata"),
    "hyderabad": City("Hyderabad", 17.3850, 78.4867, "Asia/Kolkata"),
    "mumbai": City("Mumbai", 19.0760, 72.8777, "Asia/Kolkata"),
    "delhi": City("Delhi", 28.6139, 77.2090, "Asia/Kolkata"),
    "kolkata": City("Kolkata", 22.5726, 88.3639, "Asia/Kolkata"),
    "pune": City("Pune", 18.5204, 73.8567, "Asia/Kolkata"),
    "ahmedabad": City("Ahmedabad", 23.0225, 72.5714, "Asia/Kolkata"),
    "coimbatore": City("Coimbatore", 11.0168, 76.9558, "Asia/Kolkata"),
    "madurai": City("Madurai", 9.9252, 78.1198, "Asia/Kolkata"),
    "tiruchirappalli": City("Tiruchirappalli", 10.7905, 78.7047, "Asia/Kolkata"),
    "visakhapatnam": City("Visakhapatnam", 17.6868, 83.2185, "Asia/Kolkata"),
    "vijayawada": City("Vijayawada", 16.5062, 80.6480, "Asia/Kolkata"),
    "kochi": City("Kochi", 9.9312, 76.2673, "Asia/Kolkata"),
    "thiruvananthapuram": City("Thiruvananthapuram", 8.5241, 76.9366, "Asia/Kolkata"),
    "mysuru": City("Mysuru", 12.2958, 76.6394, "Asia/Kolkata"),
    "jaipur": City("Jaipur", 26.9124, 75.7873, "Asia/Kolkata"),
    "lucknow": City("Lucknow", 26.8467, 80.9462, "Asia/Kolkata"),
    "chandigarh": City("Chandigarh", 30.7333, 76.7794, "Asia/Kolkata"),
    "nagpur": City("Nagpur", 21.1458, 79.0882, "Asia/Kolkata"),
    "surat": City("Surat", 21.1702, 72.8311, "Asia/Kolkata"),
    "indore": City("Indore", 22.7196, 75.8577, "Asia/Kolkata"),
    "singapore": City("Singapore", 1.3521, 103.8198, "Asia/Singapore"),
    "kuala-lumpur": City("Kuala Lumpur", 3.1390, 101.6869, "Asia/Kuala_Lumpur"),
    "dubai": City("Dubai", 25.2048, 55.2708, "Asia/Dubai"),
    "london": City("London", 51.5074, -0.1278, "Europe/London"),
    "new-york": City("New York", 40.7128, -74.0060, "America/New_York"),
    "san-jose": City("San Jose", 37.3382, -121.8863, "America/Los_Angeles"),
    "toronto": City("Toronto", 43.6532, -79.3832, "America/Toronto"),
    "sydney": City("Sydney", -33.8688, 151.2093, "Australia/Sydney"),
}


# --- Astronomy --------------------------------------------------------------

def _julian_century(dt_utc):
    """Return Julian centuries from J2000.0 for an aware UTC datetime."""

    y, m, d = dt_utc.year, dt_utc.month, dt_utc.day

    # Fliegel-style civil-to-Julian conversion; shift Jan/Feb into the prior year
    # so the month term stays monotonic.
    if m <= 2:
        y -= 1
        m += 12

    a = y // 100
    b = 2 - a + a // 4
    jd0 = math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + d + b - 1524.5
    day_fraction = (dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0) / 24.0

    return (jd0 + day_fraction - 2451545.0) / 36525.0


def _solar_declination_and_eot(jc):
    """Return (declination_deg, equation_of_time_min) via the NOAA algorithm."""

    mean_long = (280.46646 + jc * (36000.76983 + jc * 0.0003032)) % 360.0
    mean_anom = 357.52911 + jc * (35999.05029 - 0.0001537 * jc)
    eccentricity = 0.016708634 - jc * (0.000042037 + 0.0000001267 * jc)

    anom_r = math.radians(mean_anom)
    center = (
        math.sin(anom_r) * (1.914602 - jc * (0.004817 + 0.000014 * jc))
        + math.sin(2 * anom_r) * (0.019993 - 0.000101 * jc)
        + math.sin(3 * anom_r) * 0.000289
    )

    true_long = mean_long + center
    omega = 125.04 - 1934.136 * jc
    apparent_long = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))

    seconds = 21.448 - jc * (46.8150 + jc * (0.00059 - jc * 0.001813))
    mean_obliquity = 23.0 + (26.0 + seconds / 60.0) / 60.0
    obliquity = mean_obliquity + 0.00256 * math.cos(math.radians(omega))

    declination = math.degrees(
        math.asin(math.sin(math.radians(obliquity)) * math.sin(math.radians(apparent_long)))
    )

    y = math.tan(math.radians(obliquity / 2.0)) ** 2
    long_r = math.radians(mean_long)
    eot = 4 * math.degrees(
        y * math.sin(2 * long_r)
        - 2 * eccentricity * math.sin(anom_r)
        + 4 * eccentricity * y * math.sin(anom_r) * math.cos(2 * long_r)
        - 0.5 * y * y * math.sin(4 * long_r)
        - 1.25 * eccentricity * eccentricity * math.sin(2 * anom_r)
    )

    return declination, eot


def sun_rise_set_utc(lat, lon, d, tz, zenith=DEFAULT_ZENITH):
    """Sunrise and sunset as aware UTC datetimes for local calendar date ``d``.

    The solar terms are anchored at the civil-noon instant of ``d`` in ``tz`` and
    the resulting solar transit is snapped to the occurrence within 12 h of that
    anchor. This keeps the window on the correct civil day even for dateline
    zones whose civil offset differs sharply from their longitude (UTC+13/+14,
    e.g. Samoa), where a longitude-only anchor would land on the adjacent day and
    apply the wrong weekday segment.

    Returns ``None`` on polar day/night, where the sun never crosses the chosen
    horizon (``|cos H| > 1``) and there is no daytime octave to divide.
    """

    civil_noon_utc = datetime.combine(d, time(12, 0), ZoneInfo(tz)).astimezone(timezone.utc)
    declination, eot = _solar_declination_and_eot(_julian_century(civil_noon_utc))

    lat_r = math.radians(lat)
    decl_r = math.radians(declination)
    cos_h = (
        math.cos(math.radians(zenith)) / (math.cos(lat_r) * math.cos(decl_r))
        - math.tan(lat_r) * math.tan(decl_r)
    )
    if abs(cos_h) > 1:
        return None

    hour_angle = math.degrees(math.acos(cos_h))

    # Solar noon in UTC minutes past midnight (longitude east-positive), placed on
    # the anchor's UTC date and then wrapped to the transit nearest civil noon.
    midnight = datetime(civil_noon_utc.year, civil_noon_utc.month, civil_noon_utc.day, tzinfo=timezone.utc)
    solar_noon = midnight + timedelta(minutes=720 - 4 * lon - eot)
    while solar_noon - civil_noon_utc > timedelta(hours=12):
        solar_noon -= timedelta(days=1)
    while civil_noon_utc - solar_noon > timedelta(hours=12):
        solar_noon += timedelta(days=1)

    # 4 minutes of time per degree of hour angle. timedelta keeps the instants
    # correct even when they roll onto an adjacent UTC date.
    sunrise = solar_noon - timedelta(minutes=4 * hour_angle)
    sunset = solar_noon + timedelta(minutes=4 * hour_angle)

    return sunrise, sunset


def rahu_window(lat, lon, d, tz, zenith=DEFAULT_ZENITH, segments=RAHU_SEGMENTS):
    """Return (start_utc, end_utc) for the Rahu Kalam octave on date ``d``.

    Returns ``None`` on polar days. ``segments`` is injectable so sibling feeds
    (Yamagandam, Gulika) can reuse this engine with a different octave table.
    """

    times = sun_rise_set_utc(lat, lon, d, tz, zenith)
    if times is None:
        return None

    sunrise, sunset = times
    segment = (sunset - sunrise) / 8
    n = segments[d.weekday()]
    start = sunrise + (n - 1) * segment

    return start, start + segment


# --- ICS output -------------------------------------------------------------

def _escape(text):
    """Escape a TEXT property value per RFC 5545 3.3.11.

    Backslash is escaped first so the escape sequences added afterwards are not
    themselves doubled. Colon is deliberately left unescaped (the RFC forbids
    escaping it in TEXT values).
    """

    return (
        text.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def _fold(line):
    """Fold a content line to <=74 UTF-8 octets (RFC 5545 3.1).

    Continuation lines begin with a single space, which is stripped on unfolding.
    Splitting happens only on character boundaries so a multibyte codepoint in a
    city name is never cut in half.
    """

    if len(line.encode("utf-8")) <= FOLD_LIMIT:
        return line

    chunks = []
    current = ""
    current_octets = 0
    # The first line may use the full budget; every continuation line spends one
    # octet on its leading space.
    budget = FOLD_LIMIT

    for ch in line:
        ch_octets = len(ch.encode("utf-8"))
        if current_octets + ch_octets > budget:
            chunks.append(current)
            current = ch
            current_octets = ch_octets
            budget = FOLD_LIMIT - 1
        else:
            current += ch
            current_octets += ch_octets

    chunks.append(current)

    return "\r\n ".join(chunks)


def _fmt_utc(dt):
    """Format an aware datetime as an RFC 5545 UTC date-time (YYYYMMDDTHHMMSSZ)."""

    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_ics(city, slug, events, generation_date):
    """Assemble the VCALENDAR text (CRLF line endings, folded) for one city.

    ``events`` is an iterable of (local_date, start_utc, end_utc). DTSTAMP is
    pinned to 00:00:00Z of ``generation_date`` so month-to-month regeneration
    produces reviewable diffs rather than churn on every line.
    """

    dtstamp = _fmt_utc(
        datetime(generation_date.year, generation_date.month, generation_date.day, tzinfo=timezone.utc)
    )

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:" + PRODID,
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:" + _escape("Rahu Kalam - " + city.name),
        "X-WR-TIMEZONE:" + city.tz,
        "X-WR-CALDESC:" + _escape(DISCLAIMER),
    ]

    for local_date, start_utc, end_utc in events:
        # UID must stay byte-identical across regenerations so subscribed clients
        # update each event in place instead of duplicating it.
        uid = "rahukalam-{0}-{1}@rahu-kalam-ics".format(local_date.isoformat(), slug)
        lines.extend([
            "BEGIN:VEVENT",
            "UID:" + uid,
            "DTSTAMP:" + dtstamp,
            "DTSTART:" + _fmt_utc(start_utc),
            "DTEND:" + _fmt_utc(end_utc),
            "SUMMARY:Rahu Kalam",
            "LOCATION:" + _escape(city.name),
            # TRANSPARENT so the window shows as Free and never blocks a
            # free/busy lookup or scheduling assistant.
            "TRANSP:TRANSPARENT",
            "DESCRIPTION:" + _escape(DESCRIPTION.format(city=city.name)),
            "END:VEVENT",
        ])

    lines.append("END:VCALENDAR")

    return "".join(_fold(line) + "\r\n" for line in lines)


# --- Generation -------------------------------------------------------------

def generate(city, slug, start, days, zenith=DEFAULT_ZENITH, generation_date=None):
    """Produce the ICS text for one city over ``[start, start + days)``.

    Polar dates (no sunrise/sunset) are skipped and emit no event. ``start`` and
    the iterated dates are local calendar dates; their weekday selects the octave.
    """

    if generation_date is None:
        generation_date = datetime.now(timezone.utc).date()

    events = []
    for offset in range(days):
        d = start + timedelta(days=offset)
        window = rahu_window(city.lat, city.lon, d, city.tz, zenith)
        if window is None:
            continue
        events.append((d, window[0], window[1]))

    return build_ics(city, slug, events, generation_date)


# --- CLI --------------------------------------------------------------------

def _slugify(name):
    """Turn a display name into a lowercase, hyphenated, URL/UID-safe slug."""

    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "location"


def _write(path, text):
    """Write ``text`` verbatim, preserving the CRLF endings the ICS already contains."""

    # newline="" stops the platform from translating the explicit CRLFs, which
    # would otherwise become CR-CR-LF on some systems and fail an ICS linter.
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def _generate_all(out_dir, start, days, zenith, generation_date):
    """Generate every preset into ``out_dir``; report all failures and fail loudly.

    Collecting every failure before exiting non-zero is friendlier to CI than
    stopping at the first broken city.
    """

    os.makedirs(out_dir, exist_ok=True)
    failures = []

    for slug, city in CITIES.items():
        try:
            ics = generate(city, slug, start, days, zenith, generation_date)
            _write(os.path.join(out_dir, slug + ".ics"), ics)
        except Exception as exc:  # surface which city broke; keep generating the rest
            failures.append(slug)
            print("ERROR generating {0}: {1}".format(slug, exc), file=sys.stderr)

    if failures:
        print("{0} city/cities failed: {1}".format(len(failures), failures), file=sys.stderr)
        return 1

    return 0


def _build_parser():
    """Build the argument parser for the CLI."""

    parser = argparse.ArgumentParser(
        prog="rahu_kalam_ics",
        description="Generate RFC 5545 Rahu Kalam calendar feeds from sunrise/sunset astronomy.",
    )
    parser.add_argument("--city", help="preset city slug (see --list)")
    parser.add_argument("--lat", type=float, help="latitude, north-positive")
    parser.add_argument("--lon", type=float, help="longitude, east-positive")
    parser.add_argument("--tz", help="IANA timezone for a custom location, e.g. Asia/Kolkata")
    parser.add_argument("--name", help="display name for a custom location")
    parser.add_argument("--start", help="start date YYYY-MM-DD (default: today in UTC)")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help="number of days (default: 730)")
    parser.add_argument("--zenith", type=float, default=DEFAULT_ZENITH,
                        help="sunrise zenith in degrees (default: 90.833 civil; 90.0 centre of disk)")
    parser.add_argument("--out", help="output path; a directory when used with --all")
    parser.add_argument("--all", action="store_true", help="generate every preset into the --out directory")
    parser.add_argument("--list", action="store_true", help="list preset city slugs and exit")

    return parser


def main(argv=None):
    """CLI entry point. Returns a process exit code; invalid input exits non-zero."""

    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.list:
        for slug in CITIES:
            print(slug)
        return 0

    if args.start is None:
        start = datetime.now(timezone.utc).date()
    else:
        try:
            start = date.fromisoformat(args.start)
        except ValueError:
            parser.error("--start must be a date in YYYY-MM-DD form, got {0!r}".format(args.start))

    if args.days < 1:
        parser.error("--days must be a positive integer")

    if args.all:
        out_dir = args.out or "docs"
        return _generate_all(out_dir, start, args.days, args.zenith, None)

    # Resolve a single location from either a preset or explicit coordinates.
    if args.city is not None:
        city = CITIES.get(args.city)
        if city is None:
            parser.error("unknown city {0!r}; run with --list to see presets".format(args.city))
        slug = args.city
    elif args.lat is not None or args.lon is not None:
        if args.lat is None or args.lon is None:
            parser.error("--lat and --lon must be given together")
        # tz is optional; default to UTC, which then also defines the local date.
        name = args.name or "Custom {0:.4f},{1:.4f}".format(args.lat, args.lon)
        city = City(name, args.lat, args.lon, args.tz or "UTC")
        slug = _slugify(name)
    else:
        parser.error("provide --city, or --lat and --lon (with optional --tz)")

    try:
        ZoneInfo(city.tz)
    except Exception:
        parser.error("unknown timezone {0!r}".format(city.tz))

    ics = generate(city, slug, start, args.days, args.zenith, None)
    out_path = args.out or "rahu-kalam-{0}.ics".format(slug)
    _write(out_path, ics)
    print("Wrote {0}".format(out_path))

    return 0


if __name__ == "__main__":
    sys.exit(main())
