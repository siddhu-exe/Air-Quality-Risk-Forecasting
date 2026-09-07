import pandas as pd
df = pd.read_csv("Og Data/Delhi data/Bawana, Delhi - DPCC/Raw Data/2024_raw_data_hourly_bawana,_delhi_-_dpcc_1H.csv", na_values=["NA", "na"])
print("BP stats:")
print(df["BP (mmHg)"].describe())
