"""Prepare the Veridian accounts for loading into Salesforce.

Reads data/raw/accounts.csv and writes data/processed/sf_accounts.csv,
with column names matching the Salesforce Account object and the custom
fields in force-app. All data is fictional.

Run from the project root with:  python -m src.loaders.salesforce_accounts
"""

from pathlib import Path

import pandas as pd


def main():
    accounts = pd.read_csv(Path("data/raw/accounts.csv"))

    sf = pd.DataFrame({
        "Name": accounts["name"],
        "Veridian_Account_ID__c": accounts["account_id"],
        "Account_Category__c": accounts["account_type"],
        "Parent_Group__c": accounts["parent_group"],
        "Region__c": accounts["region"],
        "Account_Size__c": accounts["size"],
        "Customer_Since__c": accounts["customer_since"],
    })

    out_dir = Path("data/processed")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "sf_accounts.csv"
    sf.to_csv(out_file, index=False)

    print(f"Wrote {len(sf)} accounts to {out_file}")


if __name__ == "__main__":
    main()