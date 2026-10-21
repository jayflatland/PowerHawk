import flask
from flask import request
# import flask_autoindex

import functools
import html
import json
from urllib.parse import urlencode

import numpy as np
import pandas as pd
from pandas import Timestamp, Timedelta

app = flask.Flask("server")

LOG_DIR = "/opt/PowerHawk/logs"
MAX_RANGE = pd.Timedelta(days=90)
PRESETS = [("6h", 6), ("24h", 24), ("3d", 72), ("7d", 168), ("30d", 720), ("90d", 2160)]
PUMP_RUN_TIME = pd.Timedelta(10.0, unit='s')


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
        try:
            hours = float(args.get('hours', 24.0))
        except ValueError:
            raise ValueError("Hours must be a number")
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


def fmt_iso(t):
    return t.strftime('%Y-%m-%dT%H:%M:%S')


def fmt_ts(t):
    return t.strftime('%b %-d, %-I:%M:%S %p')


def fmt_short(t):
    return t.strftime('%b %-d, %-I:%M %p')


def fmt_duration(td):
    if pd.isna(td):
        return "&mdash;"
    s = int(td.total_seconds())
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    if d:
        return f"{d}d {h}h"
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def fmt_pct(v):
    if pd.isna(v):
        return "&mdash;"
    # Dry spells run well under 1%, so keep enough digits to tell them apart
    return f"{v:.2f}%" if v < 1 else f"{v:.1f}%"


def range_url(start, end, now):
    hours = (end - start).total_seconds() / 3600
    if end >= now:
        return "?" + urlencode({'hours': f"{hours:g}"})
    return "?" + urlencode({'start': fmt_time(start), 'end': fmt_time(end)})


PAGE_CSS = """
:root {
    --bg: #f4f5f7;
    --card: #ffffff;
    --border: #e3e5e8;
    --text: #1d2228;
    --muted: #6b7380;
    --accent: #2f6fde;
    --accent-soft: rgba(47, 111, 222, 0.12);
    --good: #1f9d55;
    --bad: #d64545;
    --grid: #eceef1;
    --stripe: #f8f9fb;
    color-scheme: light;
}
@media (prefers-color-scheme: dark) {
    :root {
        --bg: #111418;
        --card: #1a1e24;
        --border: #2a2f37;
        --text: #e6e8eb;
        --muted: #9aa3ae;
        --accent: #5b93f0;
        --accent-soft: rgba(91, 147, 240, 0.18);
        --good: #3ecf7a;
        --bad: #f06464;
        --grid: #262b32;
        --stripe: #1f242b;
        color-scheme: dark;
    }
}
* { box-sizing: border-box; }
body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font: 14px/1.4 system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
.topbar {
    position: sticky;
    top: 0;
    z-index: 10;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 12px 20px;
    background: var(--card);
    border-bottom: 1px solid var(--border);
}
.topbar h1 { margin: 0; font-size: 18px; font-weight: 650; }
.pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 999px;
    font-size: 12px;
    background: var(--stripe);
    border: 1px solid var(--border);
    color: var(--muted);
}
.pill::before {
    content: "";
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--muted);
}
.pill.live { color: var(--good); }
.pill.live::before { background: var(--good); }
.pill.stale { color: var(--bad); }
.pill.stale::before { background: var(--bad); }
main {
    max-width: 1100px;
    margin: 0 auto;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 16px;
}
.card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px;
}
.card h2 { margin: 0 0 4px 0; font-size: 15px; font-weight: 600; }
.hint { margin: 0 0 12px 0; font-size: 12px; color: var(--muted); }
.toolbar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px 20px;
}
.seg {
    display: inline-flex;
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
}
.seg a {
    padding: 6px 12px;
    color: var(--text);
    text-decoration: none;
    border-right: 1px solid var(--border);
}
.seg a:last-child { border-right: none; }
.seg a:hover { background: var(--stripe); }
.seg a.current { background: var(--accent); color: #fff; }
.rangenav { display: inline-flex; align-items: center; gap: 8px; }
.range-label { font-weight: 600; white-space: nowrap; }
.btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 32px;
    height: 32px;
    padding: 0 10px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--card);
    color: var(--text);
    text-decoration: none;
    font: inherit;
    cursor: pointer;
}
.btn:hover { background: var(--stripe); }
.btn.disabled { opacity: 0.35; pointer-events: none; }
.btn.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
.rangeform { display: inline-flex; flex-wrap: wrap; align-items: center; gap: 8px; color: var(--muted); }
.rangeform input {
    height: 32px;
    padding: 0 8px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--card);
    color: var(--text);
    font: inherit;
}
.error { border-color: var(--bad); color: var(--bad); }
.empty { color: var(--muted); text-align: center; padding: 32px 16px; }
.tiles {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 16px;
}
.tile .label { font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }
.tile .value { font-size: 26px; font-weight: 650; margin-top: 4px; font-variant-numeric: tabular-nums; }
.chart-box { position: relative; height: 280px; }
.chart-box canvas { touch-action: pan-y; }
.drag-box {
    position: absolute;
    background: var(--accent-soft);
    border-left: 1px solid var(--accent);
    border-right: 1px solid var(--accent);
    pointer-events: none;
}
.tablebox { max-height: 420px; overflow: auto; }
table.runs { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }
table.runs th, table.runs td { padding: 7px 12px; text-align: left; white-space: nowrap; }
table.runs th {
    position: sticky;
    top: 0;
    background: var(--card);
    border-bottom: 1px solid var(--border);
    color: var(--muted);
    font-weight: 600;
    font-size: 12px;
}
table.runs .num { text-align: right; }
table.runs tbody tr:nth-child(even) { background: var(--stripe); }
@media (max-width: 480px) {
    main { padding: 12px; gap: 12px; }
    .card { padding: 12px; }
    table.runs th, table.runs td { padding: 6px; }
    .tile .value { font-size: 22px; }
}
"""

PAGE_JS = """
(function () {
    const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    const pad = n => String(n).padStart(2, '0');
    const fmtLocal = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
    const go = (a, b) => { location.search = new URLSearchParams({start: fmtLocal(a), end: fmtLocal(b)}).toString(); };
    const charts = [];

    Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
    Chart.defaults.animation = false;
    Chart.defaults.maintainAspectRatio = false;
    Chart.defaults.plugins.legend.display = false;

    function applyTheme(chart) {
        const accent = css('--accent'), muted = css('--muted'), grid = css('--grid');
        for (const scale of Object.values(chart.options.scales)) {
            scale.ticks.color = muted;
            scale.grid.color = grid;
            scale.border = {display: false};
        }
        for (const ds of chart.data.datasets) {
            ds.borderColor = accent;
            ds.pointBackgroundColor = accent;
            ds.backgroundColor = chart.$isBar ? accent : css('--accent-soft');
        }
        // Full update (animation is off anyway) so cached bar colors are re-resolved
        chart.update();
    }

    function makeChart(id, config) {
        const canvas = document.getElementById(id);
        if (!canvas) return null;
        const chart = new Chart(canvas, config);
        chart.$isBar = config.type === 'bar';
        applyTheme(chart);
        charts.push(chart);
        return chart;
    }

    // Drag across the chart to view that time range
    function enableDragZoom(chart) {
        const canvas = chart.canvas;
        const box = document.createElement('div');
        box.className = 'drag-box';
        box.hidden = true;
        canvas.parentNode.appendChild(box);
        let x0 = null;
        const px = e => {
            const r = canvas.getBoundingClientRect(), a = chart.chartArea;
            return Math.min(Math.max(e.clientX - r.left, a.left), a.right);
        };
        canvas.addEventListener('pointerdown', e => {
            if (e.button !== 0) return;
            x0 = px(e);
            canvas.setPointerCapture(e.pointerId);
        });
        canvas.addEventListener('pointermove', e => {
            if (x0 === null) return;
            const x1 = px(e), a = chart.chartArea;
            Object.assign(box.style, {
                left: Math.min(x0, x1) + 'px', width: Math.abs(x1 - x0) + 'px',
                top: a.top + 'px', height: (a.bottom - a.top) + 'px',
            });
            box.hidden = false;
        });
        const finish = e => {
            if (x0 === null) return;
            const x1 = px(e), lo = Math.min(x0, x1), hi = Math.max(x0, x1);
            x0 = null;
            box.hidden = true;
            if (hi - lo < 8) return;
            const a = new Date(chart.scales.x.getValueForPixel(lo));
            const b = new Date(chart.scales.x.getValueForPixel(hi));
            if (b - a >= 2 * 60 * 1000) go(a, b);
        };
        canvas.addEventListener('pointerup', finish);
        canvas.addEventListener('pointercancel', () => { x0 = null; box.hidden = true; });
    }

    const util = makeChart('util-chart', {
        type: 'line',
        data: {
            datasets: [{
                data: DATA.util.map(r => ({x: new Date(r.t).getTime(), y: r.u, d: r.d})),
                borderWidth: 1.5,
                pointRadius: DATA.util.length > 150 ? 0 : 2.5,
                pointHoverRadius: 4,
                fill: true,
            }],
        },
        options: {
            interaction: {mode: 'nearest', axis: 'x', intersect: false},
            plugins: {
                tooltip: {
                    callbacks: {
                        label: item => item.parsed.y === null
                            ? 'Utilization unknown'
                            : [`Utilization ${item.parsed.y.toFixed(item.parsed.y < 1 ? 2 : 1)}%`, `Downtime before ${item.raw.d}`],
                    },
                },
            },
            scales: {
                x: {
                    type: 'time',
                    min: new Date(DATA.start).getTime(),
                    max: new Date(DATA.end).getTime(),
                    time: {tooltipFormat: 'MMM d, h:mm:ss a'},
                    ticks: {maxRotation: 0, autoSkipPadding: 20},
                    grid: {},
                },
                y: {beginAtZero: true, ticks: {callback: v => v + '%'}, grid: {}},
            },
        },
    });
    if (util) enableDragZoom(util);

    // Click a day to view it
    makeChart('perday-chart', {
        type: 'bar',
        data: {
            datasets: [{
                data: DATA.per_day.map(r => ({x: new Date(r.t + 'T00:00').getTime(), y: r.n})),
                borderRadius: 3,
                maxBarThickness: 28,
            }],
        },
        options: {
            onClick: (e, elements, chart) => {
                if (!elements.length) return;
                const day = new Date(chart.data.datasets[0].data[elements[0].index].x);
                go(day, new Date(day.getFullYear(), day.getMonth(), day.getDate() + 1));
            },
            onHover: (e, elements) => { e.native.target.style.cursor = elements.length ? 'pointer' : 'default'; },
            plugins: {tooltip: {callbacks: {label: item => `${item.parsed.y} runs`}}},
            scales: {
                x: {type: 'time', offset: true, time: {unit: 'day', tooltipFormat: 'EEE, MMM d'}, ticks: {maxRotation: 0, autoSkipPadding: 20}, grid: {}},
                y: {beginAtZero: true, ticks: {precision: 0}, grid: {}},
            },
        },
    });

    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => charts.forEach(applyTheme));
})();
"""


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

    runs = None
    latest_ts = None
    if error is None:
        lprint(f"Loading {start} to {end}...")
        runs, latest_ts = load_pump_runs(start, end)
        lprint(f"{len(runs)} runs, latest_ts={latest_ts}")

    # Status pill
    if error is not None:
        status_class, status_text = "past", "Invalid range"
    elif not live:
        status_class, status_text = "past", "Past range"
    elif latest_ts is None or pd.isna(latest_ts):
        status_class, status_text = "stale", "No data"
    else:
        # Logger may have written newer rows while we were loading
        age = max(Timestamp('now') - latest_ts, pd.Timedelta(0))
        if age < pd.Timedelta(10.0, unit='s'):
            status_class, status_text = "live", f"Live &middot; updated {fmt_duration(age)} ago"
        else:
            status_class, status_text = "stale", f"Stale &middot; last data {fmt_duration(age)} ago"

    # Range controls
    presets = "".join(
        f'<a href="?hours={hours}"{" class=current" if live and abs(span_hours - hours) < 0.01 else ""}>{label}</a>'
        for label, hours in PRESETS)
    earlier_url = range_url(start - span, start, now)
    if live:
        later_link = '<span class="btn disabled">&#9654;</span>'
    else:
        later_link = f'<a class="btn" href="{range_url(end, end + span, now)}" title="Later">&#9654;</a>'
    range_label = f'{fmt_short(start)} &rarr; {"now" if live else fmt_short(end)}'

    # Content
    chart_data = {'start': fmt_iso(start), 'end': fmt_iso(min(end, now) if live else end), 'util': [], 'per_day': []}
    content = ""
    if error is not None:
        content = f'<section class="card error">{html.escape(error)}</section>'
    elif len(runs) == 0:
        msg = "No data for this range" if latest_ts is None else "No pump runs in this range"
        content = f'<section class="card empty">{msg}</section>'
    else:
        valid = runs.dropna()
        avg_util = fmt_pct(valid.utilization.mean())
        peak_util = fmt_pct(valid.utilization.max())
        longest_gap = fmt_duration(valid.downtime.max()) if len(valid) else "&mdash;"
        tiles = "".join(
            f'<div class="card tile"><div class="label">{label}</div><div class="value">{value}</div></div>'
            for label, value in [("Runs", len(runs)), ("Avg utilization", avg_util),
                                 ("Peak utilization", peak_util), ("Longest gap", longest_gap)])

        chart_data['util'] = [
            {'t': fmt_iso(r.ts), 'u': None if pd.isna(r.utilization) else round(r.utilization, 3), 'd': fmt_duration(r.downtime).replace("&mdash;", "unknown")}
            for r in runs.itertuples()]
        perday_card = ""
        if span >= pd.Timedelta(days=7):
            days = pd.date_range(start.normalize(), end.normalize(), freq='D')
            per_day = runs.groupby(runs.ts.dt.normalize()).size().reindex(days, fill_value=0)
            chart_data['per_day'] = [{'t': str(d)[:10], 'n': int(n)} for d, n in per_day.items()]
            perday_card = """
            <section class="card">
                <h2>Runs per day</h2>
                <p class="hint">Click a day to view it</p>
                <div class="chart-box"><canvas id="perday-chart"></canvas></div>
            </section>"""

        # Every run for short ranges, just the latest 10 for long ones
        tbl_runs = runs[::-1] if span <= pd.Timedelta(days=3) else runs[::-1].head(10)
        rows = "".join(
            f'<tr><td>{fmt_ts(r.ts)}</td><td class="num">{fmt_duration(r.downtime)}</td>'
            f'<td class="num">{fmt_pct(r.utilization)}</td></tr>'
            for r in tbl_runs.itertuples())
        tbl_hint = f"Most recent {len(tbl_runs)} of {len(runs)}" if len(tbl_runs) < len(runs) else f"All {len(runs)} runs, newest first"

        content = f"""
            <section class="tiles">{tiles}</section>
            <section class="card">
                <h2>Utilization</h2>
                <p class="hint">Drag across the chart to zoom in</p>
                <div class="chart-box"><canvas id="util-chart"></canvas></div>
            </section>
            {perday_card}
            <section class="card">
                <h2>Pump runs</h2>
                <p class="hint">{tbl_hint}</p>
                <div class="tablebox">
                    <table class="runs">
                        <thead><tr><th>Started</th><th class="num">Downtime before</th><th class="num">Utilization</th></tr></thead>
                        <tbody>{rows}</tbody>
                    </table>
                </div>
            </section>"""

    refresh = '<meta http-equiv="refresh" content="60">' if live else ""

    lprint("Making html...")
    html_out = f"""<!doctype html>
    <html>
    <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Sump Pump</title>
    {refresh}
    <style>{PAGE_CSS}</style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
    </head>
    <body>
    <header class="topbar">
        <h1>Sump Pump</h1>
        <span class="pill {status_class}">{status_text}</span>
    </header>
    <main>
        <section class="card toolbar">
            <nav class="seg">{presets}</nav>
            <div class="rangenav">
                <a class="btn" href="{earlier_url}" title="Earlier">&#9664;</a>
                <span class="range-label">{range_label}</span>
                {later_link}
            </div>
            <form class="rangeform" method="get">
                <input type="datetime-local" name="start" value="{fmt_time(start)}" aria-label="Start">
                to
                <input type="datetime-local" name="end" value="{"" if live else fmt_time(end)}" aria-label="End" title="Leave blank for now">
                <button class="btn primary" type="submit">Go</button>
            </form>
        </section>
        {content}
    </main>
    <script>const DATA = {json.dumps(chart_data)};</script>
    <script>{PAGE_JS}</script>
    </body>
    </html>
    """

    return html_out, (400 if error is not None else 200)
