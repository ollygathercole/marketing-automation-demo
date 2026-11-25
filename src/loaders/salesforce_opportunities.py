"""Prepare the Veridian platform trials as Salesforce Opportunities.

Reads data/raw/subscriptions.csv and data/raw/accounts.csv and writes
data/processed/sf_opportunities.csv. Each trial becomes one Opportunity
on its account: paid trials are Closed Won, lapsed trials Closed Lost,
and trials still running stay open. All data is fictional.

Run from the project root with:  python -m src.loaders.salesforce_opportunities
"""

from pathlib import Path

import pandas as pd

STAGE = {
    "Paid": "Closed Won",
    "Lapsed trial": "Closed Lost",
    "In trial": "Value Proposition",
}


def main():
    subs = pd.read_csv(Path("data/raw/subscriptions.csv"))
    accounts = pd.read_csv(Path("data/raw/accounts.csv"))[["account_id", "name"]]
    df = subs.merge(accounts, on="account_id", how="left")

    # Paid deals close when the subscription starts, everything else when the trial ends
    close_date = df["subscription_start"].where(df["status"] == "Paid", df["trial_end"])
    # Yearly value, only known for paid subscriptions
    amount = (df["monthly_value"] * 12).round(2)

    sf = pd.DataFrame({
        "Name": df["name"] + " - Cloud Image Platform",
        "StageName": df["status"].map(STAGE),
        "CloseDate": close_date,
        "Amount": amount,
        "Veridian_Subscription_ID__c": df["subscription_id"],
        "Plan__c": df["plan"],
        "Seats__c": df["seats"].astype("Int64"),
        "Trial_Start__c": df["trial_start"],
        "Trial_End__c": df["trial_end"],
        "Monthly_Value__c": df["monthly_value"],
        "Account.Veridian_Account_ID__c": df["account_id"],
    })

    out_dir = Path("data/processed")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "sf_opportunities.csv"
    sf.to_csv(out_file, index=False)

    print(f"Wrote {len(sf)} opportunities to {out_file}")
    print()
    print(sf["StageName"].value_counts().to_string())
    print()
    print(f"Closed Won yearly value: £{sf['Amount'].sum():,.0f}")


if __name__ == "__main__":
    main()