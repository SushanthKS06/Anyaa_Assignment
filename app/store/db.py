"""SQLite (WAL) schema. M0: households, members, plans, cook_logs, grocery_runs."""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS households (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, budget_inr INTEGER, created_ts REAL
);
CREATE TABLE IF NOT EXISTS members (
  household_id TEXT, name TEXT, age_group TEXT, diet TEXT,
  allergies_json TEXT DEFAULT '[]', health_json TEXT DEFAULT '[]',
  dislikes_json TEXT DEFAULT '[]', fasting_json TEXT DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS plans (
  household_id TEXT, plan_json TEXT, reasons_json TEXT DEFAULT '[]', created_ts REAL
);
CREATE TABLE IF NOT EXISTS grocery_runs (
  household_id TEXT, cart_json TEXT DEFAULT '[]', total_inr REAL DEFAULT 0,
  order_id TEXT, created_ts REAL
);
CREATE TABLE IF NOT EXISTS cook_logs (
  household_id TEXT, date TEXT, event_json TEXT, created_ts REAL
);
"""


def get_conn(db_path: str) -> sqlite3.Connection:
    p = Path(db_path)
    if p.parent.as_posix() not in ("", "."):
        p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p.as_posix())
    conn.executescript(SCHEMA)
    return conn


def init_db(db_path: str) -> str:
    conn = get_conn(db_path)
    conn.close()
    return db_path
