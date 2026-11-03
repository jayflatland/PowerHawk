#!/usr/bin/env python
"""Download our weather station's history from Weather Underground into daily CSV logs.

Keeps today's log refreshed every 5 minutes and backfills past days, newest first,
back to when the power logs start.  The API key is read from wunderground.key
(gitignored) before every request, so the key can be replaced without a restart.
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
TODAY_REFRESH_SECONDS = 5 * 60
REQUEST_SPACING_SECONDS = 2.5  # API allows 30 requests/minute
# API allows 1500 requests/day.  Backfill stops at BACKFILL_LIMIT, leaving room
# for refreshing today (288/day) under DAILY_LIMIT.
BACKFILL_LIMIT = 1100
DAILY_LIMIT = 1400

TOP_FIELDS = ['solarRadiationHigh', 'uvHigh', 'winddirAvg', 'humidityHigh', 'humidityLow', 'humidityAvg', 'qcStatus']
IMPERIAL_FIELDS = ['tempHigh', 'tempLow', 'tempAvg', 'windspeedHigh', 'windspeedLow', 'windspeedAvg',
                   'windgustHigh', 'windgustLow', 'windgustAvg', 'dewptHigh', 'dewptLow', 'dewptAvg',
                   'windchillHigh', 'windchillLow', 'windchillAvg', 'heatindexHigh', 'heatindexLow', 'heatindexAvg',
                   'pressureMax', 'pressureMin', 'pressureTrend', 'precipRate', 'precipTotal']
COLUMNS = ['ts', 'epoch'] + TOP_FIELDS + IMPERIAL_FIELDS


def log_path(day):
    return os.path.join(LOG_DIR, f"{day}_weather.csv")


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


def fetch_day(day):
    """All observations for one local day, oldest first ([] if the station has none)."""
    with open(KEY_FILE) as f:
        key = f.read().strip()
    url = "https://api.weather.com/v2/pws/history/all?" + urlencode({
        'stationId': STATION_ID, 'format': 'json', 'units': 'e',
        'date': day.strftime('%Y%m%d'), 'apiKey': key})
    spend_request()
    with urllib.request.urlopen(url, timeout=30) as r:
        if r.status == 204:
            return []
        obs = json.load(r).get('observations', [])
    return sorted(obs, key=lambda o: o['epoch'])


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


error_wait = 0

def download(day):
    """Fetch and save one day.  Returns True on success; on failure waits before returning False."""
    global error_wait
    try:
        obs = fetch_day(day)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            print(f"{day}: HTTP {e.code} - API key rejected, check {KEY_FILE}")
            time.sleep(300)
        elif e.code == 429:
            print(f"{day}: HTTP 429 - rate limited, waiting")
            time.sleep(60)
        else:
            error_wait = min(max(error_wait * 2, 10), 300)
            print(f"{day}: HTTP {e.code}, retrying in {error_wait}s")
            time.sleep(error_wait)
        return False
    except (OSError, ValueError) as e:
        error_wait = min(max(error_wait * 2, 10), 300)
        print(f"{day}: {e}, retrying in {error_wait}s")
        time.sleep(error_wait)
        return False
    error_wait = 0
    write_day(day, obs)
    print(f"{day}: {len(obs)} observations ({load_budget()['count']} requests today)")
    return True


def next_missing_day(cursor):
    while cursor >= FIRST_DAY:
        if not os.path.exists(log_path(cursor)):
            return cursor
        cursor -= datetime.timedelta(days=1)
    return None


def main():
    print(f"Downloading {STATION_ID} weather into {LOG_DIR}")
    current_day = None
    last_today_fetch = 0.0
    backfill_cursor = None
    while True:
        today = datetime.date.today()
        if today != current_day:
            # On startup or after midnight, (re)fetch yesterday: it may have been saved while still in progress
            yesterday = today - datetime.timedelta(days=1)
            if load_budget()['count'] < DAILY_LIMIT and not download(yesterday):
                continue
            current_day = today
            last_today_fetch = 0.0
            backfill_cursor = yesterday - datetime.timedelta(days=1)
        elif time.time() - last_today_fetch >= TODAY_REFRESH_SECONDS:
            if load_budget()['count'] >= DAILY_LIMIT:
                time.sleep(60)
                continue
            if download(today):
                last_today_fetch = time.time()
        else:
            day = next_missing_day(backfill_cursor) if backfill_cursor else None
            if day is None or load_budget()['count'] >= BACKFILL_LIMIT:
                time.sleep(30)
                continue
            backfill_cursor = day
            if download(day):
                backfill_cursor = day - datetime.timedelta(days=1)
        time.sleep(REQUEST_SPACING_SECONDS)


if __name__ == '__main__':
    main()
