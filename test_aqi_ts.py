import sys
sys.path.append('etl')
from pathlib import Path
from transform_aqi import process_aqi_xlsx
import glob

# Files to test: January, April, December 2025, plus a 2026 file
tests = [
    "Og Data/Delhi data/Anand Vihar, Delhi - DPCC/AQI Hourly/aqi_hourly_station_level_anand_vihar,_delhi_-_dpcc_2025_January_delhi_2025.xlsx",
    "Og Data/Delhi data/Anand Vihar, Delhi - DPCC/AQI Hourly/aqi_hourly_station_level_anand_vihar,_delhi_-_dpcc_2025_April_delhi_2025.xlsx",
    "Og Data/Delhi data/Anand Vihar, Delhi - DPCC/AQI Hourly/aqi_hourly_station_level_anand_vihar,_delhi_-_dpcc_2025_December_delhi_2025.xlsx",
    "Og Data/Mumbai data/aqi_hourly_city_level__2026_May_mumbai_2026.xlsx",
]

for p in tests:
    print(f"\n--- Testing: {Path(p).name} ---")
    df, stats = process_aqi_xlsx(Path(p))
    if stats["status"] == "error":
        print("ERROR:", stats["error"])
        continue
        
    print(f"Stats: processed_rows={stats['processed_rows']}, dropped_invalid_ts={stats['dropped_invalid_ts']}")
    
    if len(df) > 0:
        print("First TS:", df['ts'].min())
        print("Middle TS:", df.iloc[len(df)//2]['ts'])
        print("Last TS:", df['ts'].max())
        print("Any 1970-01-01?", (df['ts'].dt.year == 1970).any())
