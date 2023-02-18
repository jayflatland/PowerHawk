import flask
from flask import request
# import flask_autoindex

import numpy as np
import pandas as pd
from pandas import Timestamp, Timedelta
import matplotlib
matplotlib.use('agg')
import matplotlib.pylab as plt

app = flask.Flask("server")

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



@app.route('/sumppump')
def handle_sumppump():
    import time
    # dbcxn = mysql.connector.connect(host="localhost",user="jay", passwd="jay", db="jay")

    # lookback_hours = float(request.args.get("hours", 24.0))
    # lookback_hours = min(lookback_hours, 48.0)
    # lookback_seconds = lookback_hours * 3600.0

    t1 = time.time()
    def lprint(*args):
        print(f"{time.time() - t1:.2f} :", *args)
    # lprint("DB query...")
    # df = pd.read_sql(f"""
    #     SELECT ts, running
    #     FROM sump_pump
    #     WHERE ts > TIMESTAMPADD(second, -{lookback_seconds}, NOW())
    #     ORDER BY ts;
    # """, con=dbcxn)

    now = Timestamp('now')

    nowstr = str(now)
    datestr = nowstr[:10]

    #NOTES - we read the power monitor logs.  channel 4 has sump pump.
    df = pd.read_csv(f"/opt/PowerHawk/logs/{datestr}_housepower.csv")

    lprint("Calculating...")
    latest_ts_age_style = "color: white; background-color: red;"
    df.set_index(pd.DatetimeIndex(df['ts']), inplace=True)
    df['ts'] = df.index
    df['running'] = df['amps4'] > 1.5;
    #df = df.set_index(df.ts)
    latest_ts = df.index.max()
    lprint("latest_ts=", latest_ts)

    if len(df) > 1:
        latest_ts_age = (now - latest_ts)
        if latest_ts_age < pd.Timedelta(10.0, unit='s'):
            latest_ts_age_style = "color: black; background-color: #eeeeee;"
        lprint(f"latest_ts={latest_ts} now={now} latest_ts_age={latest_ts_age}")
        latest_ts_age = latest_ts_age.total_seconds()
        df['pump'] = (df.running==1) & (df.running.shift(1)==0)
        df = df[df.pump]
        pump_run_time = pd.Timedelta(10.0, unit='s')
        df['downtime'] = (df.ts - df.ts.shift(1)) - pump_run_time
        df['utilization'] = 100.0 * pump_run_time.total_seconds() / (df['downtime'].dt.total_seconds() + pump_run_time.total_seconds())
        #lprint(df)
    else:
        latest_ts_age = 9999.9
        df['utilization'] = 0.0
        df['downtime'] = np.nan
    img = ""
    if len(df) > 1:
        lprint("Plotting...")
        #plt.figure(figsize=(6, 4))
        plt.title("Sump Pump Utilization")
        plt.plot(df.utilization)
        plt.xticks(rotation=45)
        plt.ylabel("Percent")
        plt.tight_layout()
        plt.grid()
        img = img_from_plt(plt)
        plt.close()

    if len(df) > 1:
        tbl = df[['downtime', 'utilization']][::-1].reset_index().dropna().head(10).to_html(index=False, classes="downtime")
    else:
        tbl = "<h3>NO RECENT DATA</h3>"

    lprint("Making html...")
    html = f"""
    <html>
    <head>
    <title>Sump Pump 2.0</title>
    <meta http-equiv="refresh" content="60">
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
    }}
    .agebox {{
        display: inline-block;
        padding: 2px 10px 2px 10px;
        border: 1px solid black;
        {latest_ts_age_style}
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
    <div class="agebox"><span class="agebox_title">Data Age:</span> {latest_ts_age:.1f}s <span class="agebox_last_data">{latest_ts}</span></div>
    <div>{img}</div>
    <div>{tbl}</div>
    </body>
    </html>
    """

    return html


