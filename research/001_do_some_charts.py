import numpy as np
import pandas as pd
from pandas import Timestamp, Timedelta
import matplotlib.pylab as plt
import seaborn as sns
import random

sns.set_style("whitegrid")


# %%

url = "https://jayflatland.com/powerhawk/logs/2023-03-01_housepower.csv"
df = pd.read_csv(url)

df.set_index(pd.to_datetime(df['ts']), inplace=True)


# %%

r, c = 2, 1
fig, axs = plt.subplots(r, c, figsize=(14, 7), sharex=True)
if r == 1 and c == 1: axs = [axs]
elif c == 1:  axs = list(axs)
else:         axs = [axs[i, j] for j in range(c) for i in range(r)]  # flatten

plt.sca(axs.pop(0))
plt.plot(df['amps1'] + df['amps2'])
#plt.plot(df['amps3'])
#plt.plot(df['amps4'])

plt.sca(axs.pop(0))
plt.plot(df['amps1'])
plt.plot(df['amps2'])

plt.show()

