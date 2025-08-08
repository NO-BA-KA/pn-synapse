import os
import sqlite3
from typing import List, Dict, Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS claims (
  id TEXT PRIMARY KEY,
  text TEXT,
  topic TEXT
);
CREATE TABLE IF NOT EXISTS edges (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  subj TEXT NOT NULL,
  pred TEXT NOT NULL,
  obj TEXT NOT NULL
);
"""

def _db_path() -> str:
    # Resolve each time so tests can switch PN_DB between modules
    return os.environ.get("PN_DB", "pn.db")

def _conn():
    conn = sqlite3.connect(_db_path())
    # Always ensure schema exists (idempotent)
    conn.executescript(SCHEMA)
    return conn

def apply_patches(patches: List[Dict[str, Any]], paper: Any) -> None:
    conn = _conn()
    with conn:
        for c in paper.claims or []:
            conn.execute(
                "INSERT OR IGNORE INTO claims(id, text, topic) VALUES(?,?,?)",
                (c.id, c.text, c.topic),
            )
        for p in patches:
            if p.get("op") == "add":
                s, pred, o = p["triple"]
                if isinstance(s, str) and s.startswith("urn:pn:claim:"):
                    conn.execute(
                        "INSERT OR IGNORE INTO claims(id, text, topic) VALUES(?,?,?)",
                        (s, None, None),
                    )
                if isinstance(o, str) and o.startswith("urn:pn:claim:"):
                    conn.execute(
                        "INSERT OR IGNORE INTO claims(id, text, topic) VALUES(?,?,?)",
                        (o, None, None),
                    )
                conn.execute(
                    "INSERT INTO edges(subj, pred, obj) VALUES(?,?,?)",
                    (s, pred, o),
                )

def count_edges() -> int:
    conn = _conn()
    (n,) = conn.execute("SELECT COUNT(*) FROM edges").fetchone()
    return int(n)
