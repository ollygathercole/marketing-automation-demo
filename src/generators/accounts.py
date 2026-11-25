"""Generate the fictional Veridian Optics account list.

Reads the fictional NHC sites and adds fictional private hospital groups
and independent clinics. All organisations and details are invented.

Run from the project root with:  python -m src.generators.accounts
"""

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from faker import Faker

from src.generators.nhc_sites import NHC_REGIONS, NHC_ACRONYM

SEED = 42
N_PRIVATE_HOSPITALS = 60
N_CLINICS = 220

random.seed(SEED)
Faker.seed(SEED)
fake = Faker("en_GB")

PRIVATE_GROUPS = [
    "Meridian Eye Hospitals",
    "Harbourview Healthcare",
    "Sovereign Private Hospitals",
    "Oakleaf Health Group",
    "Northgate Surgical Partners",
    "Linden Vision Group",
]

CLINIC_SUFFIXES = [
    "Eye Clinic",
    "Eye Care",
    "Vision Centre",
    "Ophthalmic Practice",
    "Eye Specialists",
    "Optical and Eye Clinic",
]

REGION_TOWNS = {
    "East of England": ["Cambridge", "Norwich", "Ipswich", "Peterborough", "Colchester", "Bedford"],
    "London North": ["Camden", "Islington", "Barnet", "Enfield", "Hackney", "Harrow"],
    "London South": ["Southwark", "Lewisham", "Croydon", "Greenwich", "Kingston", "Bromley"],
    "South East": ["Brighton", "Maidstone", "Canterbury", "Oxford", "Reading", "Guildford"],
    "South West": ["Bristol", "Exeter", "Plymouth", "Bath", "Truro", "Taunton"],
    "West Midlands": ["Birmingham", "Coventry", "Wolverhampton", "Worcester", "Walsall", "Solihull"],
    "East Midlands": ["Nottingham", "Leicester", "Derby", "Lincoln", "Northampton", "Kettering"],
    "North West": ["Manchester", "Liverpool", "Preston", "Chester", "Blackpool", "Lancaster"],
    "North East": ["Newcastle", "Sunderland", "Durham", "Gateshead", "Darlington", "Hexham"],
    "Yorkshire and Humber": ["Leeds", "Sheffield", "Hull", "York", "Harrogate", "Doncaster"],
    "Wales": ["Cardiff", "Swansea", "Newport", "Wrexham", "Bangor", "Carmarthen"],
    "Scotland and Northern Ireland": ["Edinburgh", "Glasgow", "Aberdeen", "Dundee", "Belfast", "Inverness"],
}


def random_date(start, end):
    """Return a random date between start and end."""
    return start + timedelta(days=random.randint(0, (end - start).days))


def unique_name(make_name, used):
    """Keep generating names until one has not been used yet."""
    name = make_name()
    while name in used:
        name = make_name()
    used.add(name)
    return name


def make_clinic_name(region):
    suffix = random.choice(CLINIC_SUFFIXES)
    if random.random() < 0.5:
        return f"{fake.last_name()} {suffix}"
    return f"{random.choice(REGION_TOWNS[region])} {suffix}"


def build_accounts():
    rows = []
    used = set()
    regions = list(NHC_REGIONS)
    start, end = date(2012, 1, 1), date(2026, 6, 30)

    # 1. Fictional NHC sites (from nhc_sites.py)
    for region, sites in NHC_REGIONS.items():
        for site in sites:
            used.add(site)
            rows.append({
                "name": site,
                "account_type": "NHC Site",
                "parent_group": NHC_ACRONYM,
                "region": region,
                "size": random.choices(["Medium", "Large"], weights=[40, 60])[0],
                "customer_since": random_date(start, end).isoformat(),
            })

    # 2. Fictional private hospitals
    for _ in range(N_PRIVATE_HOSPITALS):
        region = random.choice(regions)
        group = random.choice(PRIVATE_GROUPS)
        name = unique_name(
            lambda: f"{group} {random.choice(REGION_TOWNS[region])}", used
        )
        rows.append({
            "name": name,
            "account_type": "Private Hospital",
            "parent_group": group,
            "region": region,
            "size": random.choices(["Small", "Medium", "Large"], weights=[10, 50, 40])[0],
            "customer_since": random_date(start, end).isoformat(),
        })

    # 3. Fictional independent clinics
    for _ in range(N_CLINICS):
        region = random.choice(regions)
        name = unique_name(lambda: make_clinic_name(region), used)
        rows.append({
            "name": name,
            "account_type": "Independent Clinic",
            "parent_group": "Independent",
            "region": region,
            "size": random.choices(["Small", "Medium"], weights=[75, 25])[0],
            "customer_since": random_date(start, end).isoformat(),
        })

    return rows


def main():
    rows = build_accounts()
    random.shuffle(rows)

    df = pd.DataFrame(rows)
    df.insert(0, "account_id", [f"ACC-{i:04d}" for i in range(1, len(df) + 1)])

    out_dir = Path("data/raw")
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / "accounts.csv", index=False)

    print(f"Created {len(df)} accounts in data/raw/accounts.csv")
    print()
    print(df["account_type"].value_counts())
    print()
    print(df["size"].value_counts())


if __name__ == "__main__":
    main()