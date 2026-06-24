import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "briefs.db"))


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS briefs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            org_name    TEXT NOT NULL,
            cause       TEXT NOT NULL,
            audience    TEXT NOT NULL,
            tone        TEXT NOT NULL,
            platforms   TEXT NOT NULL,
            goal        TEXT NOT NULL,
            brief_text  TEXT NOT NULL,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS orgs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT    NOT NULL,
            mission         TEXT    DEFAULT '',
            brand_voice     TEXT    DEFAULT '',
            target_audience TEXT    DEFAULT '',
            past_campaigns  TEXT    DEFAULT '[]',
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()
    db.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialised at {DB_PATH}")
