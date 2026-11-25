"""Generate fictional digital platform trials and subscriptions.

Reads data/raw/accounts.csv. Some accounts start a 30 day trial of the
Veridian cloud image platform, and some of those convert to paid.
Hidden story: conversion is strong at NHC sites and weak at
independent clinics. All data is invented.

Run from the project root with:  python -m src.generators.subscriptions
"""

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

SEED = 46
TODAY = date(2026, 11, 25)
TRIAL_DAYS = 30
TRIAL_WINDOW_START = date(2025, 1, 1)
TRIAL_WINDOW_END = date(2026, 11, 10)

# Share of accounts that start a trial, by account type
TRIAL_RATE = {"NHC Site": 0.55, "Private Hospital": 0.50, "Independent Clinic": 0.40}

# Share of finished trials that convert to paid, by account type
CONVERT_RATE = {"NHC Site": 0.70, "Private Hospital": 0.40, "Independent Clinic": 0.15}

# Plan details: monthly base price and price per seat (in pounds)
PLANS = {
    "Core": {"base": 250, "per_seat": 15},
    "Pro with AI Screening Assist": {"base": 450, "per_seat": 25},
}
PRO_SHARE = {"NHC Site": 0.45, "Private Hospital": 0.35, "Independent Clinic": 0.20}

SEATS_BY_SIZE = {"Small": (2, 5), "Medium": (5, 12), "Large": (10, 25)}

random.seed(SEED)


def random_day(start, end):
    """Return a random date between start and end (inclusive)."""
    return date.fromordinal(random.randint(start.toordinal(), end.toordinal()))


def build_subscriptions(accounts):
    rows = []

    for _, acc in accounts.iterrows():
        acc_type = acc["account_type"]
        if random.random() >= TRIAL_RATE[acc_type]:
            continue

        customer_since = date.fromisoformat(acc["customer_since"])
        trial_start = random_day(max(TRIAL_WINDOW_START, customer_since), TRIAL_WINDOW_END)
        trial_end = trial_start + timedelta(days=TRIAL_DAYS)

        row = {
            "account_id": acc["account_id"],
            "trial_start": trial_start.isoformat(),
            "trial_end": trial_end.isoformat(),
            "status": "In trial",
            "plan": None,
            "seats": None,
            "subscription_start": None,
            "monthly_value": None,
        }

        if trial_end <= TODAY:
            if random.random() < CONVERT_RATE[acc_type]:
                plan = "Pro with AI Screening Assist" if random.random() < PRO_SHARE[acc_type] else "Core"
                seats = random.randint(*SEATS_BY_SIZE[acc["size"]])
                start = min(trial_end + timedelta(days=random.randint(0, 7)), TODAY)
                info = PLANS[plan]
                row.update({
                    "status": "Paid",
                    "plan": plan,
                    "seats": seats,
                    "subscription_start": start.isoformat(),
                    "monthly_value": info["base"] + seats * info["per_seat"],
                })
            else:
                row["status"] = "Lapsed trial"

        rows.append(row)

    return rows


def main():
    accounts = pd.read_csv(Path("data/raw/accounts.csv"))
    rows = build_subscriptions(accounts)

    df = pd.DataFrame(rows)
    df = df.sort_values("trial_start").reset_index(drop=True)
    df.insert(0, "subscription_id", [f"SUB-{i:04d}" for i in range(1, len(df) + 1)])

    out_dir = Path("data/raw")
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "subscriptions.csv", index=False)

    # Summary (joins account type back in, just for printing)
    merged = df.merge(accounts[["account_id", "account_type"]], on="account_id")
    decided = merged[merged["status"] != "In trial"]

    print(f"Created {len(df)} trials in data/raw/subscriptions.csv")
    print()
    print("Trials by status:")
    print(df["status"].value_counts())
    print()
    print("Trial-to-paid conversion by account type (finished trials only):")
    conversion = decided.groupby("account_type")["status"].apply(
        lambda s: round((s == "Paid").mean() * 100, 1)
    )
    print(conversion.to_string())
    print()
    print(f"Total monthly recurring value: £{df['monthly_value'].sum():,.0f}")


if __name__ == "__main__":
    main()