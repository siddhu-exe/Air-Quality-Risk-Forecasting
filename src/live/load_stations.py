"""Load the 7 Delhi stations into ``aq.stations`` (idempotent upsert).

IDs and canonical names come from ``src/features/compute_cpcb_aqi.py`` so the feature code is
unchanged. Coordinates are the station coordinates published in OpenAQ's location metadata
(CPCB provider), retrieved 2026-10-11; they replace the hand-entered approximations in
``exogenous_drivers.py`` (Bawana was about 3 km off). ``feed_name`` is left NULL: it is filled
after the first real data.gov.in fetch shows how that feed spells station names.

Usage (needs migrations applied and DATABASE_URL set):
    python -m src.live.load_stations --dry-run
    python -m src.live.load_stations
"""
from __future__ import annotations

import argparse

from src.features.compute_cpcb_aqi import STATION_IDS
from src.live.db import connect

# (latitude, longitude) from OpenAQ /v3/locations, CPCB provider, retrieved 2026-10-11.
STATION_COORDS = {
    "Anand Vihar": (28.64683, 77.31603),
    "Bawana": (28.77620, 77.05107),
    "Dwarka-Sector 8": (28.57103, 77.07190),
    "ITO": (28.62862, 77.24106),
    "Jahangirpuri": (28.73282, 77.17063),
    "Punjabi Bagh": (28.67404, 77.13102),
    "R K Puram": (28.56326, 77.18694),
}

# Operator per the raw-data folder names (e.g. "ITO, Delhi - CPCB", the rest DPCC).
OPERATORS = {"ITO": "CPCB"}
DEFAULT_OPERATOR = "DPCC"

UPSERT = """
insert into aq.stations
    (station_id, station_name, city, operator, latitude, longitude, coords_approximate)
values (%(station_id)s, %(station_name)s, 'Delhi', %(operator)s, %(latitude)s, %(longitude)s, false)
on conflict (station_id) do update set
    station_name = excluded.station_name,
    operator = excluded.operator,
    latitude = excluded.latitude,
    longitude = excluded.longitude,
    coords_approximate = excluded.coords_approximate
"""


def station_rows() -> list[dict]:
    """The rows to load. Fails loudly if a station has no coordinates."""
    missing = sorted(set(STATION_IDS) - set(STATION_COORDS))
    if missing:
        raise KeyError(f"no coordinates for stations: {missing}")
    return [
        {
            "station_id": sid,
            "station_name": name,
            "operator": OPERATORS.get(name, DEFAULT_OPERATOR),
            "latitude": STATION_COORDS[name][0],
            "longitude": STATION_COORDS[name][1],
        }
        for name, sid in sorted(STATION_IDS.items(), key=lambda kv: kv[1])
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="print the rows, do not connect")
    args = parser.parse_args()

    rows = station_rows()
    if args.dry_run:
        for row in rows:
            print(row)
        return
    with connect() as conn, conn.cursor() as cur:
        cur.executemany(UPSERT, rows)
    print(f"Upserted {len(rows)} stations (coordinates from OpenAQ metadata).")


if __name__ == "__main__":
    main()
