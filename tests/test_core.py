"""Test suite for rahu_kalam_ics (T1-T7 plus a dateline correctness test).

Stdlib + pytest only. T1 (golden fixtures) pins the astronomy; the rest guard the
ICS contract, determinism, edge cases, and the CLI.
"""

import os
import re
import sys
from datetime import date, datetime, timedelta, timezone

from zoneinfo import ZoneInfo

import pytest

# Make the single-file module importable without packaging or install.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rahu_kalam_ics as rk


FIXED_GEN_DATE = date(2026, 1, 1)


def _local_minutes(dt, tz):
    """Minutes past local midnight (fractional) for an aware UTC datetime in tz."""

    local = dt.astimezone(ZoneInfo(tz))
    return local.hour * 60 + local.minute + local.second / 60.0


def _hhmm(text):
    """Parse 'HH:MM' into minutes past midnight."""

    hh, mm = text.split(":")
    return int(hh) * 60 + int(mm)


# --- T1: golden fixtures (astronomy pinned to Drik Panchang, within +/-2 min) --

GOLDEN = [
    ("Asia/Kolkata", 28.6139, 77.2090, date(2026, 7, 21), "15:53", "17:36"),  # Delhi, Tue
    ("Asia/Kolkata", 12.9716, 77.5946, date(2026, 7, 19), "17:14", "18:50"),  # Bengaluru, Sun
    ("Asia/Kolkata", 28.6139, 77.2090, date(2026, 5, 25), "07:09", "08:52"),  # Delhi, Mon
]


@pytest.mark.parametrize("tz, lat, lon, d, exp_start, exp_end", GOLDEN)
def test_golden_fixtures(tz, lat, lon, d, exp_start, exp_end):
    start, end = rk.rahu_window(lat, lon, d, tz)
    assert abs(_local_minutes(start, tz) - _hhmm(exp_start)) <= 2
    assert abs(_local_minutes(end, tz) - _hhmm(exp_end)) <= 2


# --- T2: weekday -> segment table -------------------------------------------

def test_weekday_segment_table():
    assert rk.RAHU_SEGMENTS == {0: 2, 1: 7, 2: 5, 3: 6, 4: 4, 5: 3, 6: 8}


def test_segment_index_applied_correctly():
    # For each weekday, the window must start exactly (n-1) segments after sunrise.
    city = rk.CITIES["chennai"]
    for offset in range(7):
        d = date(2026, 3, 2) + timedelta(days=offset)
        sunrise, sunset = rk.sun_rise_set_utc(city.lat, city.lon, d, city.tz)
        segment = (sunset - sunrise) / 8
        n = rk.RAHU_SEGMENTS[d.weekday()]
        start, end = rk.rahu_window(city.lat, city.lon, d, city.tz)
        assert abs((start - (sunrise + (n - 1) * segment)).total_seconds()) < 1
        assert abs((end - start).total_seconds() - segment.total_seconds()) < 1


# --- T3: ICS lint ------------------------------------------------------------

def _ics(city_slug="chennai", days=40):
    city = rk.CITIES[city_slug]
    return rk.generate(city, city_slug, date(2026, 1, 1), days, generation_date=FIXED_GEN_DATE)


def test_ics_crlf_and_octet_limit():
    text = _ics()
    assert "\r\n" in text
    # No bare LF that is not part of a CRLF pair.
    assert "\n" not in text.replace("\r\n", "")
    for line in text.split("\r\n"):
        assert len(line.encode("utf-8")) <= 75


def test_ics_structure_and_required_properties():
    text = _ics()
    assert text.count("BEGIN:VCALENDAR") == 1
    assert text.count("END:VCALENDAR") == 1
    assert text.count("BEGIN:VEVENT") == text.count("END:VEVENT")
    for prop in ("VERSION:2.0", "PRODID:", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
                 "X-WR-CALNAME:", "X-WR-TIMEZONE:", "X-WR-CALDESC:"):
        assert prop in text


def test_event_count_equals_days_minus_polar_skips():
    city = rk.CITIES["chennai"]
    days = 40
    text = rk.generate(city, "chennai", date(2026, 1, 1), days, generation_date=FIXED_GEN_DATE)
    expected = sum(
        1 for offset in range(days)
        if rk.rahu_window(city.lat, city.lon, date(2026, 1, 1) + timedelta(days=offset), city.tz)
        is not None
    )
    assert text.count("BEGIN:VEVENT") == expected
    assert expected == days  # Chennai never has a polar skip


def test_uids_unique_and_scheme():
    text = _ics()
    uids = re.findall(r"UID:(.+)", text)
    assert len(uids) == len(set(uids))
    pattern = re.compile(r"^rahukalam-\d{4}-\d{2}-\d{2}-chennai@rahu-kalam-ics$")
    assert all(pattern.match(u.strip()) for u in uids)


def test_feed_under_one_megabyte():
    # FR-5: each city feed must stay under 1 MB at the default horizon.
    text = _ics(days=730)
    assert len(text.encode("utf-8")) < 1_000_000


# --- T4: determinism ---------------------------------------------------------

def test_determinism():
    city = rk.CITIES["chennai"]
    a = rk.generate(city, "chennai", date(2026, 1, 1), 60, generation_date=FIXED_GEN_DATE)
    b = rk.generate(city, "chennai", date(2026, 1, 1), 60, generation_date=FIXED_GEN_DATE)
    assert a == b


# --- T5: edge cases ----------------------------------------------------------

def test_equator_windows_near_ninety_minutes():
    city = rk.CITIES["singapore"]
    for d in (date(2026, 1, 15), date(2026, 7, 15)):
        start, end = rk.rahu_window(city.lat, city.lon, d, city.tz)
        minutes = (end - start).total_seconds() / 60.0
        assert 85 <= minutes <= 96


def test_polar_day_is_skipped():
    # Tromso, above the Arctic circle, has no sunset near the solstice.
    result = rk.sun_rise_set_utc(69.6492, 18.9553, date(2026, 6, 21), "Europe/Oslo")
    assert result is None


def test_southern_hemisphere_runs():
    city = rk.CITIES["sydney"]
    start, end = rk.rahu_window(city.lat, city.lon, date(2026, 7, 25), city.tz)
    assert start < end
    assert start.astimezone(ZoneInfo(city.tz)).date() == date(2026, 7, 25)


def test_dst_boundary_new_york():
    # US DST ends 2025-11-02; offsets differ on either side, windows stay sane.
    city = rk.CITIES["new-york"]
    for d in (date(2025, 11, 1), date(2025, 11, 3)):
        start, end = rk.rahu_window(city.lat, city.lon, d, city.tz)
        assert start < end
        assert start.astimezone(ZoneInfo(city.tz)).date() == d


@pytest.mark.parametrize("lat, lon, tz", [
    (-13.8333, -171.7667, "Pacific/Apia"),       # Samoa, UTC+13
    (1.8721, -157.4278, "Pacific/Kiritimati"),   # Kiribati, UTC+14
])
def test_antimeridian_correct_civil_day_and_segment(lat, lon, tz):
    # A longitude-only anchor would tag these on the next civil day (wrong weekday
    # segment). Assert the window lands on the intended date AND uses that
    # weekday's segment offset.
    for offset in range(7):
        d = date(2026, 7, 20) + timedelta(days=offset)
        sunrise, sunset = rk.sun_rise_set_utc(lat, lon, d, tz)
        assert sunrise.astimezone(ZoneInfo(tz)).date() == d
        segment = (sunset - sunrise) / 8
        n = rk.RAHU_SEGMENTS[d.weekday()]
        start, _ = rk.rahu_window(lat, lon, d, tz)
        assert abs((start - (sunrise + (n - 1) * segment)).total_seconds()) < 1
        assert start.astimezone(ZoneInfo(tz)).date() == d


# --- T6: CLI contract --------------------------------------------------------

@pytest.mark.parametrize("argv", [
    ["--city", "atlantis"],              # unknown preset
    ["--lat", "10.0"],                   # lat without lon
    ["--city", "chennai", "--start", "not-a-date"],  # malformed date
    ["--lat", "10.0", "--lon", "20.0", "--tz", "Not/AZone"],  # unknown tz
    [],                                  # nothing specified
])
def test_cli_bad_input_exits_nonzero(argv):
    with pytest.raises(SystemExit) as exc:
        rk.main(argv)
    assert exc.value.code != 0


def test_cli_writes_file(tmp_path):
    out = tmp_path / "chennai.ics"
    code = rk.main(["--city", "chennai", "--days", "5", "--out", str(out)])
    assert code == 0
    assert out.read_bytes().startswith(b"BEGIN:VCALENDAR")


def test_cli_all_generates_every_preset(tmp_path):
    code = rk.main(["--all", "--days", "3", "--out", str(tmp_path)])
    assert code == 0
    produced = {p.stem for p in tmp_path.glob("*.ics")}
    assert produced == set(rk.CITIES)


# --- T7: zenith flag ---------------------------------------------------------

def test_zenith_shifts_window():
    # 90.0 (centre of disk, no refraction) gives a later sunrise and earlier
    # sunset than 90.833, shifting the window edges by roughly 2-4 minutes.
    lat, lon, tz = 28.6139, 77.2090, "Asia/Kolkata"
    d = date(2026, 7, 21)
    sr_default, ss_default = rk.sun_rise_set_utc(lat, lon, d, tz, zenith=90.833)
    sr_tight, ss_tight = rk.sun_rise_set_utc(lat, lon, d, tz, zenith=90.0)

    sunrise_shift = (sr_tight - sr_default).total_seconds() / 60.0
    sunset_shift = (ss_default - ss_tight).total_seconds() / 60.0
    assert 2 <= sunrise_shift <= 6
    assert 2 <= sunset_shift <= 6

    start_default, _ = rk.rahu_window(lat, lon, d, tz, zenith=90.833)
    start_tight, _ = rk.rahu_window(lat, lon, d, tz, zenith=90.0)
    assert start_default != start_tight
