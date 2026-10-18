import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "rfp.db"

SEED_CRITERIA = [
    ("Technical Capability", "Architecture, integrations, scalability, technical fit", 30, 10),
    ("Implementation Plan", "Timeline, milestones, staffing, risk plan", 20, 10),
    ("Commercial Value", "Pricing clarity, total cost, assumptions", 20, 10),
    ("Security & Compliance", "Controls, certifications, privacy, auditability", 20, 10),
    ("Support & Experience", "Support model, similar projects, references", 10, 10),
]


def get_conn():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if missing and seed the sample criteria once."""
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS evaluation_criteria (
            criterion_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            weight REAL NOT NULL,
            max_score REAL NOT NULL DEFAULT 10,
            is_active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS rfp_runs (
            rfp_run_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL,
            criteria_snapshot TEXT
        );
        CREATE TABLE IF NOT EXISTS supplier_results (
            rfp_run_id TEXT NOT NULL REFERENCES rfp_runs(rfp_run_id),
            supplier_name TEXT NOT NULL,
            submission_date TEXT,
            experience_rating REAL,
            absolute_score REAL,
            ppi REAL,
            final_rank INTEGER,
            result_json TEXT,
            PRIMARY KEY (rfp_run_id, supplier_name)
        );
        """)
        count = conn.execute("SELECT COUNT(*) FROM evaluation_criteria").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO evaluation_criteria (name, description, weight, max_score) VALUES (?,?,?,?)",
                SEED_CRITERIA,
            )


def get_all_criteria():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM evaluation_criteria ORDER BY criterion_id").fetchall()
    return [dict(r) for r in rows]


def get_active_criteria():
    return [c for c in get_all_criteria() if c["is_active"]]


def update_criterion(criterion_id, weight, max_score, is_active):
    with get_conn() as conn:
        conn.execute(
            "UPDATE evaluation_criteria SET weight=?, max_score=?, is_active=? WHERE criterion_id=?",
            (weight, max_score, int(is_active), criterion_id),
        )


def create_run(criteria):
    run_id = f"RFP-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:4].upper()}"
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO rfp_runs (rfp_run_id, created_at, status, criteria_snapshot) VALUES (?,?,?,?)",
            (run_id, datetime.now().isoformat(timespec="seconds"), "RUNNING", json.dumps(criteria)),
        )
    return run_id


def set_run_status(run_id, status):
    with get_conn() as conn:
        conn.execute("UPDATE rfp_runs SET status=? WHERE rfp_run_id=?", (status, run_id))


def save_supplier_result(run_id, supplier_name, submission_date, experience_rating,
                         absolute_score, ppi, final_rank, result):
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO supplier_results
               (rfp_run_id, supplier_name, submission_date, experience_rating,
                absolute_score, ppi, final_rank, result_json)
               VALUES (?,?,?,?,?,?,?,?)""",
            (run_id, supplier_name, submission_date, experience_rating,
             absolute_score, ppi, final_rank, json.dumps(result)),
        )


def list_runs():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM rfp_runs ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def load_run_results(run_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM supplier_results WHERE rfp_run_id=? ORDER BY final_rank", (run_id,)
        ).fetchall()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    init_db()
    criteria = get_active_criteria()
    for c in criteria:
        print(f"{c['criterion_id']}. {c['name']}  weight={c['weight']}  max={c['max_score']}")
    print("Total weight:", sum(c["weight"] for c in criteria))
