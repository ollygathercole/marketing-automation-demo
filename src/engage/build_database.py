"""Build the Veridian Engage database, a mock marketing automation platform.

Reads the generated CSVs in data/raw and writes a SQLite database at
data/processed/engage.db with three tables, organised the way marketing
automation platforms usually organise data:

  leads       the people marketing talks to (the 900 Engage-flagged contacts)
  programs    email campaigns and webinars
  activities  one log of everything that happened: sends, opens, clicks,
              webinar registrations, attendance and demo requests

All data is fictional. Run from the project root with:
    python -m src.engage.build_database
"""

import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

SEED = 48
TODAY = date(2026, 11, 25)
RAW = Path("data/raw")
DB_PATH = Path("data/processed/engage.db")

random.seed(SEED)


def read_csv(name):
    return pd.read_csv(RAW / name)


def add_days(day_text, days):
    """Add days to an ISO date string, never going past TODAY."""
    day = date.fromisoformat(day_text) + timedelta(days=days)
    return min(day, TODAY).isoformat()


def build_leads():
    contacts = read_csv("contacts.csv")
    contacts = contacts[contacts["in_engage"]]
    return pd.DataFrame({
        "lead_id": contacts["contact_id"],
        "account_id": contacts["account_id"],
        "first_name": contacts["first_name"],
        "last_name": contacts["last_name"],
        "email": contacts["email"],
        "job_title": contacts["job_title"],
        "role_type": contacts["role_type"],
        "lead_source": contacts["lead_source"],
        "created_date": contacts["created_date"],
        "is_primary": contacts["is_primary"].astype(int),
    })


def build_programs(attendance):
    campaigns = read_csv("campaigns.csv")
    email_programs = pd.DataFrame({
        "program_id": campaigns["campaign_id"],
        "name": campaigns["name"],
        "program_type": campaigns["campaign_type"],
        "channel": "Email",
        "program_date": campaigns["send_date"],
    })

    webinars = (
        attendance[["webinar_name", "webinar_date"]]
        .drop_duplicates()
        .sort_values("webinar_date")
        .reset_index(drop=True)
    )
    webinars["program_id"] = [f"WEB-{i:02d}" for i in range(1, len(webinars) + 1)]
    webinar_programs = pd.DataFrame({
        "program_id": webinars["program_id"],
        "name": webinars["webinar_name"],
        "program_type": "Webinar",
        "channel": "Event",
        "program_date": webinars["webinar_date"],
    })

    programs = pd.concat([email_programs, webinar_programs], ignore_index=True)
    webinar_ids = dict(zip(webinars["webinar_name"], webinars["program_id"]))
    return programs, webinar_ids


def build_activities(attendance, webinar_ids):
    rows = []

    def add(lead_id, program_id, activity_type, day, detail=""):
        rows.append({
            "lead_id": lead_id,
            "program_id": program_id,
            "activity_type": activity_type,
            "activity_date": day,
            "detail": detail,
        })

    # Email activity: delivered or bounced, then opens, clicks, unsubscribes
    for r in read_csv("email_activity.csv").itertuples():
        send = r.send_date
        if not r.delivered:
            add(r.contact_id, r.campaign_id, "Email Bounced", send)
            continue
        add(r.contact_id, r.campaign_id, "Email Delivered", send)
        if r.opened:
            open_day = add_days(send, random.randint(0, 3))
            add(r.contact_id, r.campaign_id, "Email Opened", open_day)
            if r.clicked:
                click_day = add_days(open_day, random.randint(0, 1))
                add(r.contact_id, r.campaign_id, "Email Clicked", click_day)
        if r.unsubscribed:
            add(r.contact_id, r.campaign_id, "Unsubscribed", add_days(send, random.randint(0, 2)))

    # Webinar registrations and attendance
    for r in attendance.itertuples():
        program_id = webinar_ids[r.webinar_name]
        add(r.contact_id, program_id, "Webinar Registered", r.registered_date)
        if r.attended:
            add(r.contact_id, program_id, "Webinar Attended", r.webinar_date)

    # Demo requests (these come from the website, not a program)
    for r in read_csv("demo_requests.csv").itertuples():
        add(r.contact_id, None, "Demo Requested", r.request_date, r.product_interest)

    activities = pd.DataFrame(rows)
    activities = activities.sort_values("activity_date", kind="stable").reset_index(drop=True)
    activities.insert(0, "activity_id", [f"ACT-{i:06d}" for i in range(1, len(activities) + 1)])
    return activities


def main():
    attendance = read_csv("webinar_attendance.csv")

    leads = build_leads()
    programs, webinar_ids = build_programs(attendance)
    activities = build_activities(attendance, webinar_ids)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    leads.to_sql("leads", conn, index=False)
    programs.to_sql("programs", conn, index=False)
    activities.to_sql("activities", conn, index=False)

    conn.execute("CREATE INDEX idx_activities_lead ON activities(lead_id)")
    conn.execute("CREATE INDEX idx_activities_program ON activities(program_id)")
    conn.execute("CREATE INDEX idx_activities_type ON activities(activity_type)")
    conn.execute("CREATE INDEX idx_activities_date ON activities(activity_date)")
    conn.commit()
    conn.close()

    print(f"Built {DB_PATH}")
    print(f"  Leads: {len(leads)}")
    print(f"  Programs: {len(programs)}")
    print(f"  Activities: {len(activities)}")
    print()
    print("Activities by type:")
    print(activities["activity_type"].value_counts().to_string())


if __name__ == "__main__":
    main()