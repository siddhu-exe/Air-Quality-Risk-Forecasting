# etl/discover.py
from pathlib import Path

def discover_files(data_root: Path) -> list[dict]:
    """
    Recursively scans data_root for .csv and .xlsx files.
    Returns a list of dicts with file metadata.
    """
    files = []
    for path in sorted(data_root.rglob("*")):
        if path.is_file() and path.suffix.lower() in (".csv", ".xlsx"):
            parts = path.relative_to(data_root).parts
            station_folder = parts[0] if len(parts) >= 1 else "Unknown"
            files.append({
                "path": path,
                "ext": path.suffix.lower(),
                "station_folder": station_folder
            })
    return files
