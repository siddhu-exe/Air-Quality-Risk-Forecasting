"""
Root entrypoint for Streamlit Community Cloud deployment.
Delegates directly to dashboard/app.py.
"""

import sys
from pathlib import Path

# Resolve root directory defensively
try:
    ROOT_DIR = Path(__file__).resolve().parent
except NameError:
    ROOT_DIR = Path.cwd()

DASHBOARD_PATH = ROOT_DIR / "dashboard"
if str(DASHBOARD_PATH) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_PATH))

# Execute dashboard/app.py in this namespace
app_file = DASHBOARD_PATH / "app.py"
with open(app_file, "r", encoding="utf-8") as f:
    code = compile(f.read(), str(app_file), "exec")
    exec(code, globals())
