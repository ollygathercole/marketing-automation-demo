"""Generate fictional contacts for each Veridian Optics account.

Reads data/raw/accounts.csv and creates people at each account.
All names and email addresses are invented. Emails use example.com,
a domain reserved for examples, so they can never reach a real person.

Run from the project root with:  python -m src.generators.contacts
"""

import random
import re
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from faker import Faker

SEED = 43
HUBSPOT_CONTACTS = 900
TODAY = date(2026, 11, 25)

random.seed(SEED)
Faker.seed(SEED)
fake = Faker("en_GB")

# How many contacts each account gets, by size (min, max)
CONTACTS_PER_SIZE = {"Small": (2, 3), "Medium": (3, 5), "Large": (5, 7)}

# (job title, role type, weight) for each kind of account
ROLES = {
    "NHC Site": [
        ("Consultant Ophthalmologist", "Clinical", 30),
        ("Head of Ophthalmology", "Management", 10),
        ("Clinical Lead", "Clinical", 10),
        ("Theatre Manager", "Management", 12),
        ("Procurement Manager", "Procurement", 18),
        ("Finance Business Partner", "Finance", 10),
        ("Medical Engineering Lead", "Technical", 10),
    ],
    "Private Hospital": [
        ("Hospital Director", "Management", 10),
        ("Consultant Ophthalmologist", "Clinical", 30),
        ("Theatre Manager", "Management", 15),
        ("Procurement Lead", "Procurement", 20),
        ("Finance Manager", "Finance", 10),
        ("Clinical Engineer", "Technical", 15),
    ],
    "Independent Clinic": [
        ("Practice Manager", "Management", 35),
        ("Optometrist", "Clinical", 30),
        ("Clinic Owner", "Management", 15),
        ("Consultant Ophthalmologist", "Clinical", 15),
        ("Clinic Administrator", "Management", 5),
    ],
}

LEAD_SOURCES = [
    ("Trade Show", 25),
    ("Webinar", 20),
    ("Website", 20),
    ("Referral", 15),
    ("Email Campaign", 10),
    ("LinkedIn", 10),
]


def clean(text):
    """Lowercase and strip everything except a-z, for email addresses."""
    return re.sub(r"[^a-z]", "", text.lower())


def pick_role(account_type):
    roles = ROLES[account_type]
    title, role_type, _ = random.choices(roles, weights=[r[2] for r in roles])[0]
    return title, role_type


def pick_lead_source():
    sources = [s[0] for s in LEAD_SOURCES]
    weights = [s[1] for s in LEAD_SOURCES]
    return random.choices(sources, weights=weights)[0]


def build_contacts(accounts):
    rows = []
    used_emails = set()

    for _, acc in accounts.iterrows():
        low, high = CONTACTS_PER_SIZE[acc["size"]]
        n_contacts = random.randint(low, high)

        slug = re.sub(r"[^a-z0-9]+", "-", acc["name"].lower()).strip("-")
        domain = f"{slug}.example.com"

        customer_since = date.fromisoformat(acc["customer_since"])
        span_days = (TODAY - customer_since).days

        for i in range(n_contacts):
            first, last = fake.first_name(), fake.last_name()
            title, role_type = pick_role(acc["account_type"])

            local = f"{clean(first)}.{clean(last)}"
            email = f"{local}@{domain}"
            suffix = 2
            while email in used_emails:
                email = f"{local}{suffix}@{domain}"
                suffix += 1
            used_emails.add(email)

            created = customer_since + timedelta(days=random.randint(0, span_days))

            rows.append({
                "account_id": acc["account_id"],
                "first_name": first,
                "last_name": last,
                "job_title": title,
                "role_type": role_type,
                "email": email,
                "lead_source": pick_lead_source(),
                "created_date": created.isoformat(),
                "is_primary": i == 0,
            })

    return rows


def main():
    accounts = pd.read_csv(Path("data/raw/accounts.csv"))
    rows = build_contacts(accounts)

    df = pd.DataFrame(rows)
    df.insert(0, "contact_id", [f"CON-{i:05d}" for i in range(1, len(df) + 1)])

    # Choose exactly 900 contacts to load into HubSpot (free cap is 1,000)
    hubspot_rows = random.sample(range(len(df)), min(HUBSPOT_CONTACTS, len(df)))
    df["in_hubspot"] = False
    df.loc[hubspot_rows, "in_hubspot"] = True

    out_dir = Path("data/raw")
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "contacts.csv", index=False)

    print(f"Created {len(df)} contacts in data/raw/contacts.csv")
    print()
    print("Contacts by role type:")
    print(df["role_type"].value_counts())
    print()
    print("Contacts by lead source:")
    print(df["lead_source"].value_counts())
    print()
    print(f"Contacts marked for HubSpot: {df['in_hubspot'].sum()}")


if __name__ == "__main__":
    main()