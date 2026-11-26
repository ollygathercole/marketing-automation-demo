"""Sync Veridian Engage engagement summaries into Salesforce Contacts.

Reads /leads/engagement-summary from the local Veridian Engage API and
writes data/processed/sf_engagement.csv, keyed on Veridian_Contact_ID__c
so the upload updates existing contacts without creating new ones.
All data is fictional.

The API must be running in another terminal:
    uvicorn src.engage.api:app
Run from the project root with:  python -m src.loaders.salesforce_engagement
"""

from pathlib import Path

import pandas as pd
import requests

API_URL = "http://127.0.0.1:8000/leads/engagement-summary"


def main():
    try:
        response = requests.get(API_URL, timeout=60)
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise SystemExit(
            "Could not reach the Veridian Engage API. "
            "Start it in another terminal with: uvicorn src.engage.api:app"
        )

    df = pd.DataFrame(response.json())

    sf = pd.DataFrame({
        "Veridian_Contact_ID__c": df["lead_id"],
        "Emails_Delivered__c": df["emails_delivered"],
        "Emails_Opened__c": df["emails_opened"],
        "Emails_Clicked__c": df["emails_clicked"],
        "Webinars_Registered__c": df["webinars_registered"],
        "Webinars_Attended__c": df["webinars_attended"],
        "Demo_Requested__c": df["demo_requested"].map({1: "true", 0: "false"}),
        "Demo_Request_Date__c": df["demo_request_date"],
        "Last_Engagement_Date__c": df["last_engagement_date"],
    })

    out_dir = Path("data/processed")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "sf_engagement.csv"
    sf.to_csv(out_file, index=False)

    print(f"Wrote {len(sf)} contact updates to {out_file}")
    print()
    print("Totals across all contacts (to check against Salesforce afterwards):")
    print(f"  Emails delivered:    {df['emails_delivered'].sum()}")
    print(f"  Emails opened:       {df['emails_opened'].sum()}")
    print(f"  Emails clicked:      {df['emails_clicked'].sum()}")
    print(f"  Webinars registered: {df['webinars_registered'].sum()}")
    print(f"  Webinars attended:   {df['webinars_attended'].sum()}")
    print(f"  Demo requests:       {df['demo_requested'].sum()}")


if __name__ == "__main__":
    main()