import numpy as np
import pandas as pd
from pandas import Timestamp, Timedelta
import matplotlib.pylab as plt
import seaborn as sns
import random

sns.set_style("whitegrid")


# %%

url = "https://jayflatland.com/powerhawk/logs/2023-02-12_housepower.csv"
df = pd.read_csv(url)

df.set_index(pd.to_datetime(df['ts']), inplace=True)


# %%

plt.figure()
plt.plot(df['amps1'] + df['amps2'])
#plt.plot(df['amps1'])
#plt.plot(df['amps2'])
#plt.plot(df['amps3'])
#plt.plot(df['amps4'])
plt.show()

