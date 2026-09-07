import pandas as pd
from pathlib import Path
from discover import discover_files

DATA_ROOT = Path(__file__).resolve().parent.parent / "Og Data" / "Delhi data"
files = discover_files(DATA_ROOT)

for meta in files:
    if meta["ext"] != ".xlsx": continue
    path = meta["path"]
    xl = pd.ExcelFile(path, engine="openpyxl")
    for sheet in xl.sheet_names:
        df = xl.parse(sheet, na_values=["NA", "na", "N/A", "n/a", "--", ""], keep_default_na=True)
        if "Date" not in df.columns: continue
        print("File:", path.name)
        print("Date col head:", df["Date"].head(5).to_list())
        print("Date col dtype:", df["Date"].dtype)
        break
    break

