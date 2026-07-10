import numpy as np
import pandas as pd
import matplotlib.pylab as plt
import seaborn as sns

sns.set_style("whitegrid")

# %%

df = pd.read_csv("https://jayflatland.com/powerhawk/logs/2026-07-10_housepower.csv")

df = df.set_index(pd.to_datetime(df.ts))
df['ts'] = df.index



r, c = 2, 1; fig, axs = plt.subplots(r, c, figsize=(42, 25), sharex=True)
if r == 1 and c == 1: axs = [axs]
elif r == 1 or c == 1:  axs = list(axs)
else:         axs = [axs[i, j] for j in range(c) for i in range(r)]  # flatten

plt.sca(axs.pop(0))
plt.plot(df.amps4)
plt.plot(df.amps4.rolling(pd.Timedelta('5s')).mean())

df['running'] = df['amps4'] > 1.8
df['pump'] = (df.running==1) & (df.running.shift(1)==0)

df = df[df.pump]
pump_run_time = pd.Timedelta(10.0, unit='s')
df['downtime'] = (df.ts - df.ts.shift(1)) - pump_run_time
df['utilization'] = 100.0 * pump_run_time.total_seconds() / (df['downtime'].dt.total_seconds() + pump_run_time.total_seconds())


plt.sca(axs.pop(0))
plt.plot(df.utilization)


plt.show()