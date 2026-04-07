"""SQLite storage in ~/.jobcraft/."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

DATA_DIR = Path.home() / ".jobcraft"
DB_PATH = DATA_DIR / "jobs.db"
PROFILE_PATH = DATA_DIR / "profile.json"
DOCS_DIR = DATA_DIR / "docs"


def init() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    DOCS_DIR.mkdir(exist_ok=True)
    conn = _conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            title TEXT,
            company TEXT,
            location TEXT,
            contract_type TEXT,
            salary TEXT,
            text TEXT,
            added_at TEXT,
            score INTEGER,
            analysis TEXT,
            documents TEXT
        )
    """)
    conn.commit()
    conn.close()


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def save_profile(data: dict[str, Any]) -> None:
    PROFILE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def load_profile() -> dict[str, Any] | None:
    if not PROFILE_PATH.exists():
        return None
    return json.loads(PROFILE_PATH.read_text())


def add_job(url: str, title: str, company: str, location: str,
            contract_type: str, salary: str, text: str) -> int:
    conn = _conn()
    cur = conn.execute(
        """INSERT INTO jobs (url, title, company, location, contract_type, salary, text, added_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (url, title, company, location, contract_type, salary, text,
         datetime.now().isoformat()),
    )
    conn.commit()
    job_id = cur.lastrowid
    conn.close()
    return job_id


def update_analysis(job_id: int, score: int, analysis: dict[str, Any]) -> None:
    conn = _conn()
    conn.execute(
        "UPDATE jobs SET score = ?, analysis = ? WHERE id = ?",
        (score, json.dumps(analysis, ensure_ascii=False), job_id),
    )
    conn.commit()
    conn.close()


def update_documents(job_id: int, documents: dict[str, str]) -> None:
    conn = _conn()
    conn.execute(
        "UPDATE jobs SET documents = ? WHERE id = ?",
        (json.dumps(documents, ensure_ascii=False), job_id),
    )
    conn.commit()
    conn.close()


def get_job(job_id: int) -> dict[str, Any] | None:
    conn = _conn()
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    d = dict(row)
    if d.get("analysis"):
        d["analysis"] = json.loads(d["analysis"])
    if d.get("documents"):
        d["documents"] = json.loads(d["documents"])
    return d


def list_jobs() -> list[dict[str, Any]]:
    conn = _conn()
    rows = conn.execute(
        "SELECT id, url, title, company, location, score, added_at FROM jobs ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_job(job_id: int) -> None:
    conn = _conn()
    conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()


def docs_path(job_id: int) -> Path:
    return DOCS_DIR / str(job_id)


def save_doc_file(job_id: int, filename: str, content: str) -> Path:
    d = docs_path(job_id)
    d.mkdir(exist_ok=True)
    p = d / filename
    p.write_text(content)
    return p
