"""Veridian Engage API: a read-only API over the mock marketing platform.

Reads data/processed/engage.db, which is built by
src/engage/build_database.py. All data is fictional.

Run from the project root with:
    uvicorn src.engage.api:app --reload
Then open http://127.0.0.1:8000/docs in your browser.
"""

import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query

DB_PATH = Path("data/processed/engage.db")

app = FastAPI(
    title="Veridian Engage API",
    description=(
        "A mock marketing automation platform for the fictional company "
        "Veridian Optics. Leads, programs and an activity log. All data is fictional."
    ),
    version="0.1.0",
)


def run_query(sql, params=()):
    """Run a read-only query and return the rows as a list of dictionaries."""
    try:
        conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        raise HTTPException(
            status_code=503,
            detail="Database not found. Run: python -m src.engage.build_database",
        )
    conn.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


@app.get("/health")
def health():
    """Check the API is running and see how much data it holds."""
    counts = {}
    for table in ("leads", "programs", "activities"):
        counts[table] = run_query(f"SELECT COUNT(*) AS n FROM {table}")[0]["n"]
    return {"status": "ok", "records": counts}


@app.get("/leads")
def list_leads(
    account_id: Optional[str] = None,
    role_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """List leads, optionally filtered by account or role type."""
    sql = "SELECT * FROM leads WHERE 1=1"
    params = []
    if account_id:
        sql += " AND account_id = ?"
        params.append(account_id)
    if role_type:
        sql += " AND role_type = ?"
        params.append(role_type)
    sql += " ORDER BY lead_id LIMIT ? OFFSET ?"
    params += [limit, offset]
    return run_query(sql, params)


@app.get("/leads/engagement-summary")
def engagement_summary():
    """One row per lead summarising their marketing engagement.

    This is what a CRM sync would write back onto each contact.
    """
    return run_query(
        """
        SELECT
            l.lead_id,
            l.account_id,
            COALESCE(SUM(a.activity_type = 'Email Delivered'), 0) AS emails_delivered,
            COALESCE(SUM(a.activity_type = 'Email Opened'), 0) AS emails_opened,
            COALESCE(SUM(a.activity_type = 'Email Clicked'), 0) AS emails_clicked,
            COALESCE(SUM(a.activity_type = 'Webinar Registered'), 0) AS webinars_registered,
            COALESCE(SUM(a.activity_type = 'Webinar Attended'), 0) AS webinars_attended,
            COALESCE(MAX(a.activity_type = 'Demo Requested'), 0) AS demo_requested,
            MAX(CASE WHEN a.activity_type = 'Demo Requested'
                     THEN a.activity_date END) AS demo_request_date,
            MAX(CASE WHEN a.activity_type IN
                     ('Email Opened', 'Email Clicked', 'Webinar Attended', 'Demo Requested')
                     THEN a.activity_date END) AS last_engagement_date
        FROM leads l
        LEFT JOIN activities a ON a.lead_id = l.lead_id
        GROUP BY l.lead_id, l.account_id
        ORDER BY l.lead_id
        """
    )


@app.get("/leads/{lead_id}")
def get_lead(lead_id: str):
    """Get one lead by ID, for example CON-00002."""
    rows = run_query("SELECT * FROM leads WHERE lead_id = ?", (lead_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Lead not found")
    return rows[0]


@app.get("/leads/{lead_id}/activities")
def lead_activities(lead_id: str):
    """Everything one lead has done, oldest first."""
    if not run_query("SELECT 1 FROM leads WHERE lead_id = ?", (lead_id,)):
        raise HTTPException(status_code=404, detail="Lead not found")
    return run_query(
        "SELECT * FROM activities WHERE lead_id = ? ORDER BY activity_date, activity_id",
        (lead_id,),
    )


@app.get("/programs")
def list_programs(program_type: Optional[str] = None):
    """List email campaigns and webinars. Types: Newsletter, Product Email, Webinar Invite, Webinar."""
    sql = "SELECT * FROM programs WHERE 1=1"
    params = []
    if program_type:
        sql += " AND program_type = ?"
        params.append(program_type)
    sql += " ORDER BY program_date"
    return run_query(sql, params)


@app.get("/programs/{program_id}/summary")
def program_summary(program_id: str):
    """Counts of each activity type for one program."""
    programs = run_query("SELECT * FROM programs WHERE program_id = ?", (program_id,))
    if not programs:
        raise HTTPException(status_code=404, detail="Program not found")
    counts = run_query(
        """
        SELECT activity_type, COUNT(*) AS n
        FROM activities WHERE program_id = ?
        GROUP BY activity_type ORDER BY n DESC
        """,
        (program_id,),
    )
    return {"program": programs[0], "activity_counts": {c["activity_type"]: c["n"] for c in counts}}


@app.get("/activities")
def list_activities(
    activity_type: Optional[str] = None,
    lead_id: Optional[str] = None,
    program_id: Optional[str] = None,
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Search the activity log."""
    sql = "SELECT * FROM activities WHERE 1=1"
    params = []
    if activity_type:
        sql += " AND activity_type = ?"
        params.append(activity_type)
    if lead_id:
        sql += " AND lead_id = ?"
        params.append(lead_id)
    if program_id:
        sql += " AND program_id = ?"
        params.append(program_id)
    if start_date:
        sql += " AND activity_date >= ?"
        params.append(start_date)
    if end_date:
        sql += " AND activity_date <= ?"
        params.append(end_date)
    sql += " ORDER BY activity_date, activity_id LIMIT ? OFFSET ?"
    params += [limit, offset]
    return run_query(sql, params)