"""Append-only event ledger. No UPDATE. No DELETE."""
import hashlib
import json
import os
import sqlite3
from datetime import datetime

DB = os.environ.get("GENOME_LEDGER_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "genome_ledger.db"))


def now():
    return datetime.utcnow().isoformat() + "Z"


def connect():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS events (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             ts TEXT NOT NULL,
             kind TEXT NOT NULL,
             source TEXT,
             prev_hash TEXT,
             hash TEXT NOT NULL,
             payload TEXT NOT NULL
           )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS events_kind ON events(kind)")
    conn.commit()
    return conn


def head_hash(conn):
    row = conn.execute("SELECT hash FROM events ORDER BY id DESC LIMIT 1").fetchone()
    return row["hash"] if row else "genesis"


def digest(prev_hash, ts, kind, source, payload):
    raw = (prev_hash + "|" + ts + "|" + kind + "|" + (source or "") + "|" + payload).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def append(kind, payload, source="pythonista"):
    if not isinstance(payload, str):
        payload = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    ts = now()
    conn = connect()
    try:
        prev = head_hash(conn)
        h = digest(prev, ts, kind, source, payload)
        cur = conn.execute(
            "INSERT INTO events (ts, kind, source, prev_hash, hash, payload) VALUES (?,?,?,?,?,?)",
            (ts, kind, source, prev, h, payload),
        )
        conn.commit()
        return {
            "id": cur.lastrowid,
            "ts": ts,
            "kind": kind,
            "source": source,
            "prev_hash": prev,
            "hash": h,
        }
    finally:
        conn.close()


def list_events(kind=None, limit=50):
    conn = connect()
    try:
        limit = max(1, min(int(limit), 200))
        if kind:
            rows = conn.execute(
                "SELECT id, ts, kind, source, prev_hash, hash, payload FROM events WHERE kind=? ORDER BY id DESC LIMIT ?",
                (kind, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, ts, kind, source, prev_hash, hash, payload FROM events ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        out = []
        for r in rows:
            item = dict(r)
            try:
                item["payload"] = json.loads(item["payload"])
            except Exception:
                pass
            out.append(item)
        return out
    finally:
        conn.close()


def get_event(eid):
    conn = connect()
    try:
        row = conn.execute(
            "SELECT id, ts, kind, source, prev_hash, hash, payload FROM events WHERE id=?",
            (eid,),
        ).fetchone()
        if not row:
            return None
        item = dict(row)
        try:
            item["payload"] = json.loads(item["payload"])
        except Exception:
            pass
        return item
    finally:
        conn.close()


def verify_chain():
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT id, ts, kind, source, prev_hash, hash, payload FROM events ORDER BY id ASC"
        ).fetchall()
        prev = "genesis"
        for r in rows:
            expect = digest(prev, r["ts"], r["kind"], r["source"], r["payload"])
            if r["prev_hash"] != prev or r["hash"] != expect:
                return {"ok": False, "break_at": r["id"]}
            prev = r["hash"]
        return {"ok": True, "events": len(rows), "head": prev}
    finally:
        conn.close()
