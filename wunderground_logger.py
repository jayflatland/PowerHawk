#!/usr/bin/env python
"""Download our weather station's history from Weather Underground into daily CSV logs.

Keeps today's log refreshed and backfills past days, newest first, back to when the
power logs start.  The API key is read from wunderground.key (gitignored) before every
request, so the key can be replaced without a restart.

Three API endpoints, chosen for how long the API caches each:
  history/all            24 hours from the first request for a date, so asking for a day
                         still in progress freezes it.  Only used for finished days,
                         starting a little after midnight.  YYYY-MM-DD_weather.csv
  observations/all/1day  15 minutes.  Today's full 5-minute readings.  Also _weather.csv
  observations/current   5 seconds.  The latest single reading, so the webserver isn't
                         15+ minutes behind.  Its fields differ (instant values, not
                         5-minute summaries), so it has its own YYYY-MM-DD_weather_current.csv
"""

import csv
import datetime
import json
import os
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode

STATION_ID = "KKSOLATH251"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KEY_FILE = os.path.join(BASE_DIR, "wunderground.key")
LOG_DIR = os.path.join(BASE_DIR, "logs")
BUDGET_FILE = os.path.join(LOG_DIR, ".wunderground_requests.json")

FIRST_DAY = datetime.date(2021, 3, 14)  # first power log
TODAY_REFRESH_SECONDS = 15 * 60  # how long the API caches it
CURRENT_REFRESH_SECONDS = 5 * 60
FINALIZE_AFTER_MINUTES = 20  # past midnight, so yesterday's last readings have landed
REQUEST_SPACING_SECONDS = 2.5  # API allows 30 requests/minute
# API allows 1500 requests/day.  Backfill stops at BACKFILL_LIMIT, leaving room
# for refreshing today (96/day) and current (288/day) under DAILY_LIMIT.
BACKFILL_LIMIT = 1000
DAILY_LIMIT = 1400

TOP_FIELDS = ['solarRadiationHigh', 'uvHigh', 'winddirAvg', 'humidityHigh', 'humidityLow', 'humidityAvg', 'qcStatus']
IMPERIAL_FIELDS = ['tempHigh', 'tempLow', 'tempAvg', 'windspeedHigh', 'windspeedLow', 'windspeedAvg',
                   'windgustHigh', 'windgustLow', 'windgustAvg', 'dewptHigh', 'dewptLow', 'dewptAvg',
                   'windchillHigh', 'windchillLow', 'windchillAvg', 'heatindexHigh', 'heatindexLow', 'heatindexAvg',
                   'pressureMax', 'pressureMin', 'pressureTrend', 'precipRate', 'precipTotal']
COLUMNS = ['ts', 'epoch'] + TOP_FIELDS + IMPERIAL_FIELDS

CURRENT_TOP_FIELDS = ['solarRadiation', 'uv', 'winddir', 'humidity', 'qcStatus']
CURRENT_IMPERIAL_FIELDS = ['temp', 'heatIndex', 'dewpt', 'windChill', 'windSpeed', 'windGust', 'pressure',
                           'precipRate', 'precipTotal']
CURRENT_COLUMNS = ['ts', 'epoch'] + CURRENT_TOP_FIELDS + CURRENT_IMPERIAL_FIELDS


def log_path(day):
    return os.path.join(LOG_DIR, f"{day}_weather.csv")


def current_log_path(datestr):
    return os.path.join(LOG_DIR, f"{datestr}_weather_current.csv")


def load_budget():
    today = str(datetime.date.today())
    try:
        with open(BUDGET_FILE) as f:
            budget = json.load(f)
        if budget.get('date') == today:
            return budget
    except (OSError, ValueError):
        pass
    return {'date': today, 'count': 0}


def spend_request():
    budget = load_budget()
    budget['count'] += 1
    with open(BUDGET_FILE, "w") as f:
        json.dump(budget, f)
    return budget['count']


def get_observations(endpoint, **params):
    """Observations from one API endpoint, oldest first ([] if the station has none)."""
    with open(KEY_FILE) as f:
        key = f.read().strip()
    url = f"https://api.weather.com/v2/pws/{endpoint}?" + urlencode({
        'stationId': STATION_ID, 'format': 'json', 'units': 'e', 'apiKey': key, **params})
    spend_request()
    with urllib.request.urlopen(url, timeout=30) as r:
        if r.status == 204:
            return []
        obs = json.load(r).get('observations', [])
    return sorted(obs, key=lambda o: o['epoch'])


def fetch_finished_day(day):
    return get_observations("history/all", date=day.strftime('%Y%m%d'))


def fetch_today(day):
    # Just after midnight this can still be a cached copy of yesterday, so keep only this day's readings
    return [o for o in get_observations("observations/all/1day") if o.get('obsTimeLocal', '').startswith(str(day))]


def saved_observations(day):
    try:
        with open(log_path(day)) as f:
            return max(sum(1 for line in f) - 1, 0)
    except OSError:
        return 0


def write_day(day, obs):
    # Write then rename, so the webserver never reads a half-written file
    path = log_path(day)
    tmp = path + ".tmp"
    with open(tmp, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for o in obs:
            imperial = o.get('imperial') or {}
            w.writerow([o.get('obsTimeLocal'), o.get('epoch')]
                       + [o.get(k) for k in TOP_FIELDS]
                       + [imperial.get(k) for k in IMPERIAL_FIELDS])
    os.replace(tmp, path)


def save_day(day, fetch):
    obs = fetch(day)
    saved = saved_observations(day)
    if len(obs) < saved:
        # A stale cached response; don't let it replace newer data
        print(f"{day}: got {len(obs)} observations, keeping the {saved} already saved")
        return
    write_day(day, obs)
    print(f"{day}: {len(obs)} observations ({load_budget()['count']} requests today)")


last_current_epoch = None

def save_current():
    global last_current_epoch
    for o in get_observations("observations/current"):
        local = o.get('obsTimeLocal', '')
        # In the first minutes after midnight the daily rain total may not have reset yet.
        # Any rain then still shows up in the next reading's total.
        if o['epoch'] == last_current_epoch or local[11:16] < "00:05":
            continue
        path = current_log_path(local[:10])
        is_new = not os.path.exists(path)
        imperial = o.get('imperial') or {}
        with open(path, "a", newline="") as f:
            w = csv.writer(f)
            if is_new:
                w.writerow(CURRENT_COLUMNS)
            w.writerow([local, o['epoch']]
                       + [o.get(k) for k in CURRENT_TOP_FIELDS]
                       + [imperial.get(k) for k in CURRENT_IMPERIAL_FIELDS])
        last_current_epoch = o['epoch']
        print(f"current {local}: {imperial.get('precipTotal')} in ({load_budget()['count']} requests today)")


error_wait = 0

def attempt(label, action):
    """Run one API action.  Returns True on success; on failure waits before returning False."""
    global error_wait
    try:
        action()
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            print(f"{label}: HTTP {e.code} - API key rejected, check {KEY_FILE}")
            time.sleep(300)
        elif e.code == 429:
            print(f"{label}: HTTP 429 - rate limited, waiting")
            time.sleep(60)
        else:
            error_wait = min(max(error_wait * 2, 10), 300)
            print(f"{label}: HTTP {e.code}, retrying in {error_wait}s")
            time.sleep(error_wait)
        return False
    except (OSError, ValueError) as e:
        error_wait = min(max(error_wait * 2, 10), 300)
        print(f"{label}: {e}, retrying in {error_wait}s")
        time.sleep(error_wait)
        return False
    error_wait = 0
    return True


def download(day, fetch):
    return attempt(day, lambda: save_day(day, fetch))


def next_missing_day(cursor):
    while cursor >= FIRST_DAY:
        if not os.path.exists(log_path(cursor)):
            return cursor
        cursor -= datetime.timedelta(days=1)
    return None


def main():
    print(f"Downloading {STATION_ID} weather into {LOG_DIR}")
    current_day = None
    finalized_day = None
    last_today_fetch = 0.0
    last_current_fetch = 0.0
    backfill_cursor = None
    while True:
        now = datetime.datetime.now()
        today = now.date()
        yesterday = today - datetime.timedelta(days=1)
        if today != current_day:
            current_day = today
            last_today_fetch = 0.0
            backfill_cursor = yesterday - datetime.timedelta(days=1)

        requests_today = load_budget()['count']
        if requests_today >= DAILY_LIMIT:
            time.sleep(60)
            continue
        if finalized_day != yesterday and now.hour * 60 + now.minute >= FINALIZE_AFTER_MINUTES:
            # Yesterday was last saved while still in progress
            if download(yesterday, fetch_finished_day):
                finalized_day = yesterday
        elif time.time() - last_current_fetch >= CURRENT_REFRESH_SECONDS:
            if attempt("current", save_current):
                last_current_fetch = time.time()
        elif time.time() - last_today_fetch >= TODAY_REFRESH_SECONDS:
            if download(today, fetch_today):
                last_today_fetch = time.time()
        else:
            day = next_missing_day(backfill_cursor)
            if day is None or requests_today >= BACKFILL_LIMIT:
                time.sleep(30)
                continue
            backfill_cursor = day
            if download(day, fetch_finished_day):
                backfill_cursor = day - datetime.timedelta(days=1)
        time.sleep(REQUEST_SPACING_SECONDS)


if __name__ == '__main__':
    main()
