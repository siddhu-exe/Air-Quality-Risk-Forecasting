# etl/generate_mapping_report.py
from pathlib import Path
import pandas as pd
from schemas import CSV_COLUMN_MAPPING

def generate_report():
    script_dir = Path(__file__).resolve().parent
    schema_report_path = script_dir.parent / "profiling" / "schema_report.csv"
    output_path = script_dir.parent / "reports" / "column_mapping_report.md"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not schema_report_path.exists():
        print("schema_report.csv not found. Did you run the profiler first?")
        return

    df = pd.read_csv(schema_report_path)

    # All unique raw columns
    unique_raw_cols = df["col_name"].dropna().unique()

    # Time specific wide columns in XLSX
    time_cols = [c for c in unique_raw_cols if isinstance(c, str) and ":" in c and len(c) >= 5]
    other_raw_cols = [c for c in unique_raw_cols if c not in time_cols]

    report = []
    report.append("# Column Mapping Report")
    report.append(f"\nGenerated from empirical data in `{schema_report_path.name}`.\n")

    report.append("## Mapped Columns (CAAQMS)")
    report.append("| Raw Column Name | Canonical Target Column | Target Mapping Status |")
    report.append("| --- | --- | --- |")

    mapped_count = 0
    unmapped_count = 0

    for col in sorted(other_raw_cols):
        if col in CSV_COLUMN_MAPPING:
            report.append(f"| `{col}` | `{CSV_COLUMN_MAPPING[col]}` | Mapped |")
            mapped_count += 1
        elif col in ["Date", "station_id", "source_file_id"]:
            # Special case for Dates
            report.append(f"| `{col}` | `ts` (base) | Handled specifically in pipeline |")
            mapped_count += 1
        else:
            report.append(f"| `{col}` | None | **UNMAPPED** (Flagged to drop) |")
            unmapped_count += 1

    report.append("\n## AQI Wide-Format Hours (XLSX files)\n")
    report.append(f"{len(time_cols)} distinct hour columns found (e.g. `00:00:00`, `01:00:00`).")
    report.append("They are automatically unpivoted in staging to the canonical `ts` and `aqi` columns.\n")

    report.append("## Summary")
    report.append(f"- **Total Non-Time Raw Columns Found:** {len(other_raw_cols)}")
    report.append(f"- **Mapped / Handled:** {mapped_count}")
    report.append(f"- **Unmapped (Discarded):** {unmapped_count}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    print(f"Mapping report generated at {output_path}")

if __name__ == "__main__":
    generate_report()
