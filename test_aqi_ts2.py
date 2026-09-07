import sys
sys.path.append('etl')
from pathlib import Path
from transform_aqi import process_aqi_xlsx

p = Path("Og Data/Delhi data/Anand Vihar, Delhi - DPCC/AQI Hourly/aqi_hourly_station_level_anand_vihar,_delhi_-_dpcc_2025_April_delhi_2025.xlsx")
df, stats = process_aqi_xlsx(p)

# Day 1, all its hours
day1 = df[df['ts'].dt.day == 1].sort_values('ts')
print("=== Day 1 hours (all should be 2025-04-01) ===")
print(day1['ts'].to_list())

# Multiple hours in same day
day15 = df[df['ts'].dt.day == 15].sort_values('ts')
print("\n=== Day 15 hours (all should be 2025-04-15) ===")
print(day15['ts'].to_list())

# Last day
day30 = df[df['ts'].dt.day == 30].sort_values('ts')
print("\n=== Last day (30th) hours ===")
print(day30['ts'].to_list())

# Confirm month boundaries - no May dates
print("\n=== Month boundary check: any ts outside April 2025? ===")
outside = df[(df['ts'].dt.month != 4) | (df['ts'].dt.year != 2025)]
print(f"Out-of-month records: {len(outside)}")
if len(outside) > 0:
    print(outside['ts'].to_list())
