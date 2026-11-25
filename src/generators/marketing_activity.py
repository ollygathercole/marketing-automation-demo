"""Generate fictional marketing activity for Veridian Optics.

Reads data/raw/contacts.csv and creates:
  campaigns.csv           email campaigns (newsletters, product emails, webinar invites)
  email_activity.csv      sends, opens and clicks for the HubSpot contacts
  webinar_attendance.csv  webinar registrations and attendance
  demo_requests.csv       demo requests from HubSpot contacts
  web_sessions.csv        website sessions (for the BigQuery analytics layer)

Hidden story: contacts who attend a webinar request a demo at about three
times the rate of contacts who never attend one. All data is invented.

Run from the project root with:  python -m src.generators.marketing_activity
"""

import random
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

SEED = 47
TODAY = date(2026, 11, 25)
WINDOW_START = date(2025, 12, 1)

DEMO_RATE_ATTENDEE = 0.24
DEMO_RATE_OTHER = 0.08

random.seed(SEED)

# (open rate, click rate among people who opened) for each kind of email
EMAIL_RATES = {
    "Newsletter": (0.34, 0.10),
    "Product Email": (0.28, 0.16),
    "Webinar Invite": (0.36, 0.22),
}

PRODUCT_EMAILS = [
    ("Retinal Camera Launch Update", date(2026, 1, 20)),
    ("OCT Scanner Upgrade Offer", date(2026, 2, 24)),
    ("Consumables Reorder Made Easy", date(2026, 3, 17)),
    ("Introducing AI Screening Assist", date(2026, 4, 21)),
    ("Phaco System Service Plans", date(2026, 5, 19)),
    ("Cloud Image Platform Free Trial", date(2026, 6, 16)),
    ("Consumables Bundle Savings", date(2026, 9, 15)),
    ("Year-End Planning Guide", date(2026, 10, 20)),
]

# All webinars finish at least 45 days before TODAY, so every
# follow-up demo request has time to happen.
WEBINARS = [
    ("Retinal Imaging in Primary Care", date(2026, 2, 5)),
    ("Reducing Theatre Waste with Single-Use Packs", date(2026, 3, 26)),
    ("AI Screening Assist: What the Evidence Shows", date(2026, 5, 7)),
    ("Getting More from OCT", date(2026, 6, 25)),
    ("Managing Image Data in the Cloud", date(2026, 7, 23)),
    ("Consumables Planning for the Year Ahead", date(2026, 9, 10)),
]

PRODUCT_INTEREST = ["Retinal Imaging Camera", "OCT Scanner", "Phaco Surgical System", "Cloud Image Platform"]
PRODUCT_INTEREST_WEIGHTS = [25, 25, 20, 30]

SOURCES = ["Organic Search", "Direct", "Paid Search", "LinkedIn", "Referral", "Email"]

LANDING_PAGES = [
    "/", "/products/retinal-imaging-camera", "/products/oct-scanner",
    "/products/phaco-system", "/consumables", "/platform",
    "/platform/ai-screening-assist", "/resources/webinars", "/about", "/contact",
]
LANDING_WEIGHTS = [28, 10, 10, 7, 12, 12, 8, 5, 4, 4]

# Busiest during UK working hours
HOUR_WEIGHTS = [1, 1, 1, 1, 1, 2, 4, 8, 12, 14, 14, 13,
                11, 12, 13, 12, 10, 7, 5, 4, 3, 2, 2, 1]

DEVICES = ["Desktop", "Mobile", "Tablet"]
DEVICE_WEIGHTS = [62, 32, 6]

COUNTRIES = ["United Kingdom", "Ireland", "Germany", "France", "Netherlands", "Other"]
COUNTRY_WEIGHTS = [82, 4, 3, 3, 2, 6]


def random_day(start, end):
    """Return a random date between start and end (inclusive)."""
    return date.fromordinal(random.randint(start.toordinal(), end.toordinal()))


def load_hubspot_contacts():
    contacts = pd.read_csv(Path("data/raw/contacts.csv"))
    hub = contacts[contacts["in_hubspot"]]
    return [
        {
            "contact_id": r.contact_id,
            "account_id": r.account_id,
            "role_type": r.role_type,
            "created": date.fromisoformat(r.created_date),
        }
        for r in hub.itertuples()
    ]


def build_campaigns():
    items = []
    for i in range(12):
        year = 2025 + (11 + i) // 12
        month = (11 + i) % 12 + 1
        send = date(year, month, 8)
        items.append({
            "name": f"Veridian Insights newsletter {send:%b %Y}",
            "campaign_type": "Newsletter",
            "send_date": send,
        })
    for name, send in PRODUCT_EMAILS:
        items.append({"name": name, "campaign_type": "Product Email", "send_date": send})
    for name, webinar_date in WEBINARS:
        items.append({
            "name": f"Webinar invite: {name}",
            "campaign_type": "Webinar Invite",
            "send_date": webinar_date - timedelta(days=14),
        })
    items.sort(key=lambda c: c["send_date"])
    for i, c in enumerate(items, start=1):
        c["campaign_id"] = f"CMP-{i:03d}"
    return items


def build_email_activity(campaigns, hub):
    rows = []
    unsubscribed = set()

    for camp in campaigns:
        open_rate, click_rate = EMAIL_RATES[camp["campaign_type"]]
        send = camp["send_date"]

        for c in hub:
            if c["created"] > send or c["contact_id"] in unsubscribed:
                continue

            delivered = random.random() > 0.03
            opened = clicked = unsub = False
            if delivered:
                opened = random.random() < open_rate
                clicked = opened and random.random() < click_rate
                unsub = random.random() < 0.003
                if unsub:
                    unsubscribed.add(c["contact_id"])

            rows.append({
                "campaign_id": camp["campaign_id"],
                "contact_id": c["contact_id"],
                "send_date": send.isoformat(),
                "delivered": delivered,
                "opened": opened,
                "clicked": clicked,
                "unsubscribed": unsub,
            })

    return rows


def build_attendance(hub):
    rows = []
    for name, webinar_date in WEBINARS:
        invite = webinar_date - timedelta(days=14)
        for c in hub:
            if c["created"] > invite:
                continue
            chance = 0.14 if c["role_type"] == "Clinical" else 0.08
            if random.random() >= chance:
                continue
            registered = invite + timedelta(days=random.randint(1, 10))
            rows.append({
                "webinar_name": name,
                "webinar_date": webinar_date.isoformat(),
                "contact_id": c["contact_id"],
                "account_id": c["account_id"],
                "registered_date": registered.isoformat(),
                "attended": random.random() < 0.55,
            })
    return rows


def build_demo_requests(hub, attendance):
    # Earliest webinar each contact actually attended
    first_attended = {}
    for r in attendance:
        if not r["attended"]:
            continue
        d = date.fromisoformat(r["webinar_date"])
        cid = r["contact_id"]
        if cid not in first_attended or d < first_attended[cid]:
            first_attended[cid] = d

    rows = []
    for c in hub:
        cid = c["contact_id"]
        if cid in first_attended:
            if random.random() >= DEMO_RATE_ATTENDEE:
                continue
            request_date = first_attended[cid] + timedelta(days=random.randint(1, 45))
        else:
            if random.random() >= DEMO_RATE_OTHER:
                continue
            earliest = max(c["created"], WINDOW_START)
            request_date = random_day(earliest, TODAY)

        rows.append({
            "contact_id": cid,
            "account_id": c["account_id"],
            "request_date": request_date.isoformat(),
            "product_interest": random.choices(PRODUCT_INTEREST, weights=PRODUCT_INTEREST_WEIGHTS)[0],
            "request_source": "Website Form",
        })

    return rows, first_attended


def make_session(day, source, landing):
    if landing is None:
        landing = random.choices(LANDING_PAGES, weights=LANDING_WEIGHTS)[0]
    hour = random.choices(range(24), weights=HOUR_WEIGHTS)[0]
    started = datetime(day.year, day.month, day.day, hour,
                       random.randint(0, 59), random.randint(0, 59))
    pages = random.choices(range(1, 9), weights=[30, 22, 16, 11, 8, 6, 4, 3])[0]
    return {
        "session_start": started.strftime("%Y-%m-%d %H:%M:%S"),
        "source": source,
        "landing_page": landing,
        "pages_viewed": pages,
        "duration_seconds": pages * random.randint(20, 70),
        "device": random.choices(DEVICES, weights=DEVICE_WEIGHTS)[0],
        "country": random.choices(COUNTRIES, weights=COUNTRY_WEIGHTS)[0],
    }


def build_web_sessions(campaigns):
    # Extra sessions on days when an email goes out or a webinar runs
    extra = defaultdict(list)
    for camp in campaigns:
        landing = "/resources/webinars" if camp["campaign_type"] == "Webinar Invite" else None
        send = camp["send_date"]
        extra[send].append(("Email", 25, landing))
        extra[send + timedelta(days=1)].append(("Email", 15, landing))
        extra[send + timedelta(days=2)].append(("Email", 5, landing))
    for _, webinar_date in WEBINARS:
        extra[webinar_date].append(("Email", 20, "/resources/webinars"))
        extra[webinar_date].append(("LinkedIn", 10, "/resources/webinars"))

    rows = []
    total_days = (TODAY - WINDOW_START).days
    day = WINDOW_START
    while day <= TODAY:
        progress = (day - WINDOW_START).days / total_days
        base = 110 if day.weekday() < 5 else 45
        if (day.month == 12 and day.day >= 24) or (day.month == 1 and day.day <= 2):
            base = int(base * 0.5)
        n = int(base * random.uniform(0.8, 1.2))

        # LinkedIn traffic grows steadily through the year
        weights = [38, 22, 10, 8 + 8 * progress, 12, 8]
        for _ in range(n):
            source = random.choices(SOURCES, weights=weights)[0]
            rows.append(make_session(day, source, None))

        for source, count, landing in extra.get(day, []):
            for _ in range(count):
                rows.append(make_session(day, source, landing))

        day += timedelta(days=1)

    return rows


def main():
    hub = load_hubspot_contacts()
    campaigns = build_campaigns()
    email_rows = build_email_activity(campaigns, hub)
    attendance = build_attendance(hub)
    demo_rows, first_attended = build_demo_requests(hub, attendance)
    session_rows = build_web_sessions(campaigns)

    out_dir = Path("data/raw")
    out_dir.mkdir(parents=True, exist_ok=True)

    campaigns_df = pd.DataFrame(campaigns)[["campaign_id", "name", "campaign_type", "send_date"]]
    campaigns_df.to_csv(out_dir / "campaigns.csv", index=False)

    email_df = pd.DataFrame(email_rows)
    email_df.insert(0, "email_id", [f"EML-{i:06d}" for i in range(1, len(email_df) + 1)])
    email_df.to_csv(out_dir / "email_activity.csv", index=False)

    attendance_df = pd.DataFrame(attendance)
    attendance_df.insert(0, "registration_id", [f"REG-{i:04d}" for i in range(1, len(attendance_df) + 1)])
    attendance_df.to_csv(out_dir / "webinar_attendance.csv", index=False)

    demo_df = pd.DataFrame(demo_rows).sort_values("request_date").reset_index(drop=True)
    demo_df.insert(0, "demo_id", [f"DEM-{i:04d}" for i in range(1, len(demo_df) + 1)])
    demo_df.to_csv(out_dir / "demo_requests.csv", index=False)

    sessions_df = pd.DataFrame(session_rows).sort_values("session_start").reset_index(drop=True)
    sessions_df.insert(0, "session_id", [f"S-{i:06d}" for i in range(1, len(sessions_df) + 1)])
    sessions_df.to_csv(out_dir / "web_sessions.csv", index=False)

    delivered = email_df[email_df["delivered"]]
    print(f"Created {len(campaigns_df)} email campaigns in data/raw/campaigns.csv")
    print(f"Created {len(email_df)} email records in data/raw/email_activity.csv")
    print(f"  Open rate: {delivered['opened'].mean() * 100:.1f}%   "
          f"Click rate: {delivered['clicked'].mean() * 100:.1f}%")
    print(f"Created {len(attendance_df)} webinar registrations in data/raw/webinar_attendance.csv")
    print(f"  Attended: {int(attendance_df['attended'].sum())}")
    print(f"Created {len(demo_df)} demo requests in data/raw/demo_requests.csv")

    attendees = set(first_attended)
    others = {c["contact_id"] for c in hub} - attendees
    demo_ids = set(demo_df["contact_id"])
    rate_att = len(attendees & demo_ids) / len(attendees) * 100
    rate_oth = len(others & demo_ids) / len(others) * 100
    print(f"  Demo request rate, webinar attendees: {rate_att:.1f}%")
    print(f"  Demo request rate, never attended a webinar: {rate_oth:.1f}%")
    print(f"Created {len(sessions_df)} website sessions in data/raw/web_sessions.csv")


if __name__ == "__main__":
    main()