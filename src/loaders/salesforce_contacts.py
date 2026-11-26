"""Prepare the Veridian contacts for loading into Salesforce.

Reads data/raw/contacts.csv, keeps the contacts flagged for Veridian Engage, and
writes data/processed/sf_contacts.csv with column names matching the
Salesforce Contact object and the custom fields in force-app.
The Account.Veridian_Account_ID__c column links each contact to its
account without needing Salesforce IDs. All data is fictional.

Run from the project root with:  python -m src.loaders.salesforce_contacts
"""

from pathlib import Path

import pandas as pd


def main():
    contacts = pd.read_csv(Path("data/raw/contacts.csv"))
    contacts = contacts[contacts["in_engage"]]

    sf = pd.DataFrame({
        "FirstName": contacts["first_name"],
        "LastName": contacts["last_name"],
        "Title": contacts["job_title"],
        "Email": contacts["email"],
        "Veridian_Contact_ID__c": contacts["contact_id"],
        "Role_Type__c": contacts["role_type"],
        "Lead_Source_Detail__c": contacts["lead_source"],
        "Date_Added__c": contacts["created_date"],
        "Is_Primary__c": contacts["is_primary"].astype(str).str.lower(),
        "Account.Veridian_Account_ID__c": contacts["account_id"],
    })

    out_dir = Path("data/processed")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "sf_contacts.csv"
    sf.to_csv(out_file, index=False)

    print(f"Wrote {len(sf)} contacts to {out_file}")
    print(f"Accounts with at least one contact: {sf['Account.Veridian_Account_ID__c'].nunique()}")


if __name__ == "__main__":
    main()