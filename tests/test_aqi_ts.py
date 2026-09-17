import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT / "etl"))
from transform_aqi import process_aqi_xlsx

# Files to test: January, April, December 2025, plus a 2026 file
tests = [
    PROJECT_ROOT / "Og Data/Delhi data/Anand Vihar, Delhi - DPCC/AQI Hourly/aqi_hourly_station_level_anand_vihar,_delhi_-_dpcc_2025_January_delhi_2025.xlsx",
    PROJECT_ROOT / "Og Data/Delhi data/Anand Vihar, Delhi - DPCC/AQI Hourly/aqi_hourly_station_level_anand_vihar,_delhi_-_dpcc_2025_April_delhi_2025.xlsx",
    PROJECT_ROOT / "Og Data/Delhi data/Anand Vihar, Delhi - DPCC/AQI Hourly/aqi_hourly_station_level_anand_vihar,_delhi_-_dpcc_2025_December_delhi_2025.xlsx",
    PROJECT_ROOT / "Og Data/Mumbai data/aqi_hourly_city_level__2026_May_mumbai_2026.xlsx",
]

for p in tests:
    print(f"\n--- Testing: {p.name} ---")
    df, stats = process_aqi_xlsx(p)
    if stats["status"] == "error":
        print("ERROR:", stats["error"])
        continue
        
    print(f"Stats: processed_rows={stats['processed_rows']}, dropped_invalid_ts={stats['dropped_invalid_ts']}")
    
    if len(df) > 0:
        print("First TS:", df['ts'].min())
        print("Middle TS:", df.iloc[len(df)//2]['ts'])
        print("Last TS:", df['ts'].max())
        print("Any 1970-01-01?", (df['ts'].dt.year == 1970).any())
