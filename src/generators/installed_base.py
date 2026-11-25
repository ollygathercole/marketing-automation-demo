"""Generate the fictional installed base for Veridian Optics.

Reads data/raw/accounts.csv and assigns each account a number of
Veridian devices. All devices, serial numbers and dates are invented.

Run from the project root with:  python -m src.generators.installed_base
"""

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

SEED = 44
TODAY = date(2026, 11, 25)
WARRANTY_DAYS = 730  # two years

random.seed(SEED)

# Product details: the consumable each device uses, and a serial prefix
PRODUCTS = {
    "Retinal Imaging Camera": {"consumable": "Probe Tips", "prefix": "RC"},
    "OCT Scanner": {"consumable": "Calibration Kits", "prefix": "OC"},
    "Phaco Surgical System": {"consumable": "Surgical Packs", "prefix": "PH"},
}

# Which products each account type tends to own (weights)
PRODUCT_WEIGHTS = {
    "NHC Site": {"Retinal Imaging Camera": 30, "OCT Scanner": 35, "Phaco Surgical System": 35},
    "Private Hospital": {"Retinal Imaging Camera": 25, "OCT Scanner": 35, "Phaco Surgical System": 40},
    "Independent Clinic": {"Retinal Imaging Camera": 55, "OCT Scanner": 45},
}

# How many devices each account owns, by size (min, max)
DEVICES_PER_SIZE = {"Small": (1, 2), "Medium": (2, 3), "Large": (3, 5)}


def make_serial(prefix, used):
    """Create a fictional serial number that has not been used yet."""
    serial = f"VO-{prefix}-{random.randint(10000, 99999)}"
    while serial in used:
        serial = f"VO-{prefix}-{random.randint(10000, 99999)}"
    used.add(serial)
    return serial


def build_installed_base(accounts):
    rows = []
    used_serials = set()

    for _, acc in accounts.iterrows():
        low, high = DEVICES_PER_SIZE[acc["size"]]
        n_devices = random.randint(low, high)

        weights = PRODUCT_WEIGHTS[acc["account_type"]]
        products = list(weights)
        product_weights = list(weights.values())

        customer_since = date.fromisoformat(acc["customer_since"])
        span_days = (TODAY - customer_since).days

        for _ in range(n_devices):
            product = random.choices(products, weights=product_weights)[0]
            info = PRODUCTS[product]

            install_date = customer_since + timedelta(days=random.randint(0, span_days))
            warranty_end = install_date + timedelta(days=WARRANTY_DAYS)
            under_warranty = warranty_end >= TODAY

            # Devices under warranty are covered; older ones often have a paid contract
            service_contract = True if under_warranty else random.random() < 0.6

            rows.append({
                "account_id": acc["account_id"],
                "product": product,
                "product_line": "Hardware",
                "serial_number": make_serial(info["prefix"], used_serials),
                "consumable_type": info["consumable"],
                "install_date": install_date.isoformat(),
                "warranty_end": warranty_end.isoformat(),
                "service_contract": service_contract,
            })

    return rows


def main():
    accounts = pd.read_csv(Path("data/raw/accounts.csv"))
    rows = build_installed_base(accounts)

    df = pd.DataFrame(rows)
    df.insert(0, "asset_id", [f"AST-{i:05d}" for i in range(1, len(df) + 1)])

    out_dir = Path("data/raw")
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "installed_base.csv", index=False)

    print(f"Created {len(df)} devices in data/raw/installed_base.csv")
    print()
    print("Devices by product:")
    print(df["product"].value_counts())
    print()
    print(f"Accounts with at least one device: {df['account_id'].nunique()} of {len(accounts)}")
    print(f"Devices with a service contract: {df['service_contract'].sum()}")


if __name__ == "__main__":
    main()