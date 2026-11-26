"""Generate fictional consumable orders for Veridian Optics.

Reads accounts.csv and installed_base.csv and creates about two years of
monthly consumable orders. Three hidden patterns are built in for the
Claude layer to find later:

1. Consumables gap: accounts that own devices but almost never reorder.
2. Lapsed after lead change: accounts that order normally, then drop off
   sharply after their clinical lead changes.
3. Decoys: accounts with a lead change that carry on ordering normally.

All data is invented. Run from the project root with:
    python -m src.generators.consumable_orders
"""

import random
from datetime import date
from pathlib import Path

import pandas as pd

SEED = 45
TODAY = date(2026, 11, 25)
WINDOW_START = date(2024, 12, 1)

GAP_SHARE = 0.15
LAPSE_SHARE = 0.12
DECOY_SHARE = 0.08

# Chance of an order per device per month
P_NORMAL = 0.50
P_GAP = 0.03
P_LAPSED = 0.06

# Lead changes happen between these dates
LEAD_CHANGE_START = date(2025, 4, 1)
LEAD_CHANGE_END = date(2026, 4, 30)

random.seed(SEED)

CONSUMABLES = {
    "Probe Tips": {"unit_price": 45.00, "qty": (2, 6)},
    "Calibration Kits": {"unit_price": 180.00, "qty": (1, 2)},
    "Surgical Packs": {"unit_price": 95.00, "qty": (5, 15)},
}

# Quieter months (August holidays, December)
SEASON = {8: 0.7, 12: 0.8}


def month_starts(start, end):
    """Return the first day of every month from start up to end."""
    months = []
    current = date(start.year, start.month, 1)
    while current <= end:
        months.append(current)
        year = current.year + (current.month // 12)
        month = current.month % 12 + 1
        current = date(year, month, 1)
    return months


def random_day(start, end):
    """Return a random date between start and end (inclusive)."""
    return date.fromordinal(random.randint(start.toordinal(), end.toordinal()))


def assign_patterns(account_ids):
    """Split accounts into the hidden groups."""
    ids = list(account_ids)
    random.shuffle(ids)
    n = len(ids)
    n_gap = int(n * GAP_SHARE)
    n_lapse = int(n * LAPSE_SHARE)
    n_decoy = int(n * DECOY_SHARE)

    pattern = {}
    for i, acc_id in enumerate(ids):
        if i < n_gap:
            pattern[acc_id] = "Consumables gap"
        elif i < n_gap + n_lapse:
            pattern[acc_id] = "Lapsed after lead change"
        elif i < n_gap + n_lapse + n_decoy:
            pattern[acc_id] = "Lead change, still ordering"
        else:
            pattern[acc_id] = "Healthy"
    return pattern


def main():
    accounts = pd.read_csv(Path("data/raw/accounts.csv"))
    devices = pd.read_csv(Path("data/raw/installed_base.csv"))

    pattern = assign_patterns(accounts["account_id"])

    # Lead change events for the lapsed and decoy accounts
    events = []
    lead_change = {}
    for acc_id, p in pattern.items():
        if p in ("Lapsed after lead change", "Lead change, still ordering"):
            change_date = random_day(LEAD_CHANGE_START, LEAD_CHANGE_END)
            lead_change[acc_id] = change_date
            events.append({
                "account_id": acc_id,
                "event_type": "Clinical Lead Change",
                "event_date": change_date.isoformat(),
            })

    rows = []
    months = month_starts(WINDOW_START, TODAY)

    for _, dev in devices.iterrows():
        acc_id = dev["account_id"]
        p = pattern[acc_id]
        install = date.fromisoformat(dev["install_date"])
        info = CONSUMABLES[dev["consumable_type"]]

        for month in months:
            if install > month:
                continue

            # Work out the order chance for this device this month
            if p == "Consumables gap":
                chance = P_GAP
            elif p == "Lapsed after lead change" and month >= lead_change[acc_id]:
                chance = P_LAPSED
            else:
                chance = P_NORMAL
            chance *= SEASON.get(month.month, 1.0)

            if random.random() >= chance:
                continue

            # Pick an order date inside the month, but never in the future
            last_day = date(month.year, month.month, 28)
            order_date = random_day(month, min(last_day, TODAY))

            qty = random.randint(*info["qty"])
            rows.append({
                "account_id": acc_id,
                "asset_id": dev["asset_id"],
                "consumable_type": dev["consumable_type"],
                "order_date": order_date.isoformat(),
                "quantity": qty,
                "unit_price": info["unit_price"],
                "order_value": round(qty * info["unit_price"], 2),
            })

    orders = pd.DataFrame(rows).sort_values("order_date").reset_index(drop=True)
    orders.insert(0, "order_id", [f"ORD-{i:05d}" for i in range(1, len(orders) + 1)])

    out_dir = Path("data/raw")
    out_dir.mkdir(parents=True, exist_ok=True)
    orders.to_csv(out_dir / "consumable_orders.csv", index=False)

    events_df = pd.DataFrame(events).sort_values("event_date").reset_index(drop=True)
    events_df.insert(0, "event_id", [f"EVT-{i:04d}" for i in range(1, len(events_df) + 1)])
    events_df.to_csv(out_dir / "account_events.csv", index=False)

    # Private answer key for checking Claude's findings later.
    # Never load this file into Salesforce, Veridian Engage or BigQuery.
    key = pd.DataFrame(
        {"account_id": list(pattern), "hidden_pattern": list(pattern.values())}
    )
    order_counts = orders.groupby("account_id").size()
    key["orders_in_window"] = key["account_id"].map(order_counts).fillna(0).astype(int)
    key.to_csv(out_dir / "answer_key.csv", index=False)

    print(f"Created {len(orders)} orders in data/raw/consumable_orders.csv")
    print(f"Total order value: £{orders['order_value'].sum():,.2f}")
    print(f"Created {len(events_df)} lead change events in data/raw/account_events.csv")
    print()
    print("Orders by consumable:")
    print(orders["consumable_type"].value_counts())
    print()
    print("Accounts and average orders per account, by hidden pattern:")
    summary = key.groupby("hidden_pattern")["orders_in_window"].agg(["count", "mean"])
    print(summary.round(1))


if __name__ == "__main__":
    main()