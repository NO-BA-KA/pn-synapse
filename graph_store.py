import os
import sqlite3
from typing import Any, Dict, List

DB_PATH = os.environ.get("PN_DB", "pn.db")

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS claims(
  id TEXT PRIMARY KEY,
  text TEXT,
  topic TEXT
);
CREATE TABLE IF NOT EXISTS edges(
  id   INTEGER PRIMARY KEY AUTOINCREMENT,
  subj TEXT,
  pred TEXT,
  obj  TEXT
);
"""


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    return conn


def apply_patches(patch: List[Dict[str, Any]], paper) -> None:
    """graphPatch を DB に反映（add only, MVP）"""
    conn = _conn()
    with conn:
        for op in patch or []:
            if op.get("op") != "add":
                continue
            s, pred, o = op.get("triple") or [None, None, None]
            if not (s and pred and o):
                continue

            # claims の存在保証（URNっぽいIDのみ）
            for cid in (s, o):
                if isinstance(cid, str) and cid.startswith("urn:pn:claim:"):
                    c = None
                    try:
                        c = next(
                            (cl for cl in (paper.claims or []) if getattr(cl, "id", None) == cid),
                            None,
                        )
                    except Exception:
                        c = None
                    text = getattr(c, "text", None) if c else None
                    topic = getattr(c, "topic", None) if c else None
                    conn.execute(
                        "INSERT OR IGNORE INTO claims(id, text, topic) VALUES(?,?,?)",
                        (cid, text, topic),
                    )

            conn.execute(
                "INSERT INTO edges(subj, pred, obj) VALUES(?,?,?)",
                (s, pred, o),
            )


def count_edges() -> int:
    (n,) = _conn().execute("SELECT COUNT(*) FROM edges").fetchone()
    return int(n)


def list_edges(limit: int = 1000) -> List[Dict[str, str]]:
    cur = _conn().execute("SELECT subj, pred, obj FROM edges LIMIT ?", (limit,))
    return [{"subj": s, "pred": p, "obj": o} for (s, p, o) in cur.fetchall()]


def list_claims(limit: int = 1000) -> List[Dict[str, str]]:
    cur = _conn().execute("SELECT id, text, topic FROM claims LIMIT ?", (limit,))
    return [{"id": i, "text": t, "topic": topic} for (i, t, topic) in cur.fetchall()]


def debug_info() -> Dict[str, Any]:
    exists = os.path.exists(DB_PATH)
    size = os.path.getsize(DB_PATH) if exists else 0
    return {"db_path": DB_PATH, "exists": exists, "size": size, "edges": count_edges()}
