import flask
from flask import request
# import flask_autoindex

import functools
import html
from urllib.parse import urlencode

import numpy as np
import pandas as pd
from pandas import Timestamp, Timedelta
import matplotlib
matplotlib.use('agg')
import matplotlib.pylab as plt

app = flask.Flask("server")

LOG_DIR = "/opt/PowerHawk/logs"
MAX_RANGE = pd.Timedelta(days=90)
PRESETS = [("6h", 6), ("24h", 24), ("3d", 72), ("7d", 168), ("30d", 720), ("90d", 2160)]
PUMP_RUN_TIME = pd.Timedelta(10.0, unit='s')

def img_from_plt(plt):
    import base64
    class StringFile:
        def __init__(self):
            self.totalbuf = b""
        def write(self, buf):
            self.totalbuf += buf
        def seek(self, pos):
            pass  # trick to look like file handle
    string_fd = StringFile()
    plt.savefig(string_fd, edgecolor=plt.gcf().get_edgecolor(), facecolor=plt.gcf().get_facecolor(), format='png')
    return f'<img src="data:image/png;base64,{base64.b64encode(string_fd.totalbuf).decode("utf-8")}">'


def day_summary(datestr):
    """Pump start times and latest log timestamp for one day's log file."""
    #NOTES - we read the power monitor logs.  channel 4 has sump pump.
    df = pd.read_csv(f"{LOG_DIR}/{datestr}_housepower.csv", usecols=['ts', 'amps3', 'amps4'])
    # Logs can have junk lines (power loss mid-write) and a repeated hour when DST ends
    df['ts'] = pd.to_datetime(df['ts'], errors='coerce')
    df = df.dropna(subset=['ts']).sort_values('ts')
    df.set_index(pd.DatetimeIndex(df['ts']), inplace=True)
    # amps3 has no load but picks up the same crosstalk as amps4 (~5% of mains current),
    # so subtracting it leaves just the sump pump.  Median smooths over mid-run current dips.
    amps4_filtered = (df.amps4 - df.amps3).rolling(pd.Timedelta('5s')).median()
    # Hysteresis: on above 1.0A, off below 0.5A, so a weak run hovering near 1.0A isn't counted twice
    running = pd.Series(np.nan, index=df.index)
    running[amps4_filtered > 1.0] = 1
    running[amps4_filtered < 0.5] = 0
    running = running.ffill().fillna(0)
    starts = df.index[(running == 1) & (running.shift(1) == 0)]
    return tuple(starts), df.index.max()

# Finished days never change, so each worker remembers their results
cached_day_summary = functools.lru_cache(maxsize=None)(day_summary)


def load_pump_runs(start, end):
    """Pump runs between start and end, plus the latest log timestamp seen."""
    today = Timestamp('now').normalize()
    starts = []
    latest_ts = None
    # Start a day early so the first run in range gets its downtime from the run before it
    for day in pd.date_range((start - pd.Timedelta(days=1)).normalize(), end.normalize(), freq='D'):
        summary = cached_day_summary if day < today else day_summary
        try:
            day_starts, latest_ts = summary(str(day)[:10])
        except FileNotFoundError:
            continue
        starts.extend(day_starts)

    runs = pd.DataFrame({'ts': pd.DatetimeIndex(starts)})
    runs['downtime'] = (runs.ts - runs.ts.shift(1)) - PUMP_RUN_TIME
    runs['utilization'] = 100.0 * PUMP_RUN_TIME.total_seconds() / (runs['downtime'].dt.total_seconds() + PUMP_RUN_TIME.total_seconds())
    runs = runs[(runs.ts >= start) & (runs.ts <= end)]
    return runs, latest_ts


def parse_time(s):
    t = Timestamp(s)
    if pd.isna(t) or t.tzinfo is not None:
        raise ValueError(f"Bad time: {s}")
    return t


def parse_range(args, now):
    """Returns (start, end) from ?hours=N or ?start=...&end=... (end defaults to now)."""
    start_arg, end_arg = args.get('start', ''), args.get('end', '')
    if start_arg or end_arg:
        end = parse_time(end_arg) if end_arg else now
        start = parse_time(start_arg) if start_arg else end - pd.Timedelta(hours=24)
    else:
        hours = float(args.get('hours', 24.0))
        if not 0 < hours <= MAX_RANGE.total_seconds() / 3600:
            raise ValueError("Hours must be between 0 and 2160 (90 days)")
        start, end = now - pd.Timedelta(hours=hours), now
    if not start < end:
        raise ValueError("Start must be before end")
    if end - start > MAX_RANGE:
        raise ValueError("Range is limited to 90 days")
    return start, end


def fmt_time(t):
    return t.strftime('%Y-%m-%dT%H:%M')


def range_url(start, end, now):
    hours = (end - start).total_seconds() / 3600
    if end >= now:
        return "?" + urlencode({'hours': f"{hours:g}"})
    return "?" + urlencode({'start': fmt_time(start), 'end': fmt_time(end)})


@app.route('/sumppump')
def handle_sumppump():
    import time

    t1 = time.time()
    def lprint(*args):
        print(f"{time.time() - t1:.2f} :", *args)

    now = Timestamp('now')

    try:
        start, end = parse_range(request.args, now)
        error = None
    except (ValueError, OverflowError) as e:
        start, end = now - pd.Timedelta(hours=24), now
        error = str(e)
    live = end >= now
    span = end - start
    span_hours = span.total_seconds() / 3600

    img = ""
    summary = ""
    if error is not None:
        tbl = f"<h3>{html.escape(error)}</h3>"
        latest_ts = None
    else:
        lprint(f"Loading {start} to {end}...")
        runs, latest_ts = load_pump_runs(start, end)
        lprint(f"{len(runs)} runs, latest_ts={latest_ts}")

        if len(runs) > 0:
            lprint("Plotting...")
            plt.figure()
            plt.title("Sump Pump Utilization")
            plt.plot(runs.ts, runs.utilization)
            plt.xlim(start, end)
            plt.xticks(rotation=45)
            plt.ylabel("Percent")
            plt.tight_layout()
            plt.grid()
            img = img_from_plt(plt)
            plt.close()

            if span >= pd.Timedelta(days=7):
                days = pd.date_range(start.normalize(), end.normalize(), freq='D')
                per_day = runs.groupby(runs.ts.dt.normalize()).size().reindex(days, fill_value=0)
                plt.figure()
                plt.title("Sump Pump Runs per Day")
                plt.bar(per_day.index, per_day.values, width=0.8)
                plt.xticks(rotation=45)
                plt.ylabel("Runs")
                plt.tight_layout()
                plt.grid(axis='y')
                img += img_from_plt(plt)
                plt.close()

            valid = runs.dropna()
            summary = f"{len(runs)} runs"
            if len(valid) > 0:
                summary += (f" &middot; avg utilization {valid.utilization.mean():.2f}%"
                            f" &middot; peak {valid.utilization.max():.2f}%"
                            f" &middot; longest gap {valid.downtime.max().round('1s')}")

            # Every run for short ranges, just the latest 10 for long ones
            tbl_runs = runs[::-1] if span <= pd.Timedelta(days=3) else runs[::-1].head(10)
            tbl_runs = tbl_runs.assign(
                ts=tbl_runs.ts.dt.round('1s'),
                downtime=tbl_runs.downtime.dt.round('1s'),
                utilization=tbl_runs.utilization.round(2),
            )
            tbl = tbl_runs.to_html(index=False, classes="downtime")
        elif latest_ts is None:
            tbl = "<h3>NO DATA FOR THIS RANGE</h3>"
        else:
            tbl = "<h3>NO PUMP RUNS IN THIS RANGE</h3>"

    agebox = ""
    if live:
        latest_ts_age_style = "color: white; background-color: red;"
        if latest_ts is not None and not pd.isna(latest_ts):
            latest_ts_age = now - latest_ts
            if latest_ts_age < pd.Timedelta(10.0, unit='s'):
                latest_ts_age_style = "color: black; background-color: #eeeeee;"
            latest_ts_age = latest_ts_age.total_seconds()
        else:
            latest_ts_age = 9999.9
        agebox = f'<div class="agebox" style="{latest_ts_age_style}"><span class="agebox_title">Data Age:</span> {latest_ts_age:.1f}s <span class="agebox_last_data">{latest_ts}</span></div>'

    presets = " ".join(
        f'<a href="?hours={hours}" class="{"current" if live and abs(span_hours - hours) < 0.01 else ""}">{label}</a>'
        for label, hours in PRESETS)
    earlier_url = range_url(start - span, start, now)
    later_link = "" if live else f'<a href="{range_url(end, end + span, now)}">Later &#9654;</a>'
    refresh = '<meta http-equiv="refresh" content="60">' if live else ""

    lprint("Making html...")
    html_out = f"""
    <html>
    <head>
    <title>Sump Pump 2.0</title>
    {refresh}
    <script src="https://code.jquery.com/jquery-3.3.1.js"></script>
    <script src="https://cdn.datatables.net/1.10.19/js/jquery.dataTables.min.js"></script>
    <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.10.19/css/jquery.dataTables.min.css">
    <style>
    body {{
        font-family: verdana;
    }}
    table.downtime {{
        border-collapse: collapse;
        border-color: #888888;
    }}
    table.downtime td, table.downtime th {{
        padding: 2px 10px 2px 10px;
    }}
    table.downtime th {{
        background-color: #CCCCCC;
        position: sticky;
        top: 0;
    }}
    .tablebox {{
        display: inline-block;
        max-height: 400px;
        overflow-y: auto;
    }}
    .controls {{
        margin-bottom: 8px;
    }}
    .controls a {{
        margin-right: 8px;
    }}
    .controls a.current {{
        font-weight: bold;
        color: black;
        text-decoration: none;
    }}
    .controls form {{
        display: inline-block;
        margin: 4px 0 4px 0;
    }}
    .agebox {{
        display: inline-block;
        padding: 2px 10px 2px 10px;
        border: 1px solid black;
    }}
    .agebox_title {{
        font-style: bold;
        color: #222222;
    }}

    .agebox_last_data {{
        font-style: italic;
        font-size: 8pt;
        color: #aaaaaa;
    }}
    </style>
    </head>
    <body>
    <div class="controls">
        <div>{presets}</div>
        <form method="get">
            <input type="datetime-local" name="start" value="{fmt_time(start)}">
            to <input type="datetime-local" name="end" value="{"" if live else fmt_time(end)}">
            <button type="submit">Go</button>
            <span style="font-size: 8pt; color: #888888;">(leave end blank for now)</span>
        </form>
        <div><a href="{earlier_url}">&#9664; Earlier</a> {later_link}</div>
    </div>
    <div><b>{start.strftime('%Y-%m-%d %H:%M')} &rarr; {"now" if live else end.strftime('%Y-%m-%d %H:%M')}</b></div>
    <div>{summary}</div>
    {agebox}
    <div>{img}</div>
    <div class="tablebox">{tbl}</div>
    </body>
    </html>
    """

    return html_out, (400 if error is not None else 200)
