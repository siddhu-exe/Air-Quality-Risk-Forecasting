"""DB helper and station-loader tests. No network, no database."""

import re
from pathlib import Path

import pytest

from src.live import db
from src.live.load_stations import station_rows

MIGRATIONS = sorted((Path(__file__).resolve().parents[1] / "db" / "migrations").glob("*.sql"))


def test_missing_url_raises_without_leaking(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(db, "load_dotenv", lambda *a, **k: None, raising=False)
    with pytest.raises(db.DatabaseConfigError, match="DATABASE_URL is not set"):
        db.get_url()


def test_non_postgres_url_rejected_and_value_not_echoed(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "mysql://user:secret-pw@host/db")
    with pytest.raises(db.DatabaseConfigError) as err:
        db.get_url()
    assert "secret-pw" not in str(err.value)


def test_connection_failure_message_has_no_credentials(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:secret-pw@127.0.0.1:1/db")
    with pytest.raises(db.DatabaseConfigError) as err:
        with db.connect():
            pass
    assert "secret-pw" not in str(err.value)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://job_writer.ref:sec:ret+pw@host:5432/postgres",  # ':' in the password
        "postgresql://job_writer.ref:sec@ret+pw@host:5432/postgres",  # '@' in the password
        "postgresql://job_writer.ref:sec/ret#pw@host:5432/postgres",  # '/' and '#'
        "postgresql://job_writer.ref:s3cretpw@no-such-host.invalid:5432/postgres",
    ],
)
def test_malformed_or_unreachable_urls_never_echo_the_password(monkeypatch, url):
    monkeypatch.setenv("DATABASE_URL", url)
    with pytest.raises(db.DatabaseConfigError) as err:
        with db.connect():
            pass
    message = str(err.value)
    for fragment in ("sec:ret", "ret+pw", "+pw", "sec@", "ret#pw", "s3cretpw", "pw@"):
        assert fragment not in message
    assert "job_writer.ref" not in message and "5432" not in message


def test_describe_url_flags_reserved_characters_without_returning_the_password(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://job_writer.ref:ab:c+d@host.example:5432/postgres")
    info = db.describe_url()
    assert info["user"] == "job_writer.ref" and info["host"] == "host.example" and info["port"] == "5432"
    assert info["password_has_reserved_chars"] == ["+", ":"]
    assert "abc" not in str(info) and "ab:c" not in str(info)


def test_station_rows_cover_the_seven_stations():
    rows = station_rows()
    assert [r["station_id"] for r in rows] == [3, 4, 5, 6, 7, 8, 9]
    assert all(28.0 < r["latitude"] < 29.0 and 76.5 < r["longitude"] < 77.8 for r in rows)
    assert {r["station_name"]: r["operator"] for r in rows}["ITO"] == "CPCB"


def test_migrations_are_numbered_and_contain_no_secrets():
    assert [p.name[:3] for p in MIGRATIONS] == ["001", "002", "003", "004", "005", "006", "007", "008"]
    for path in MIGRATIONS:
        sql = path.read_text()
        # no password literal may appear in a statement (comments describing the manual step are fine)
        code = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
        assert not re.search(r"password\s+'", code, re.IGNORECASE), path.name
        assert "drop " not in code.lower() and "truncate" not in code.lower(), path.name


def test_every_table_gets_rls_in_migration_006():
    created = set()
    for path in MIGRATIONS:
        created |= set(re.findall(r"create table aq\.(\w+)", path.read_text()))
    rls = next(p for p in MIGRATIONS if p.name.startswith("006")).read_text()
    missing = [t for t in sorted(created) if f"'{t}'" not in rls]
    assert not missing, f"tables without RLS/grants in 006: {missing}"
