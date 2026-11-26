from pathlib import Path
import pandas as pd

RAW = Path("data/raw")
OUT = Path("data/processed")

emails = pd.read_csv(RAW / "email_activity.csv")
for col in ["delivered", "opened", "clicked", "unsubscribed"]:
    emails[col] = emails[col].astype(str).str.lower().eq("true")

stats = emails.groupby("campaign_id").agg(
    NumberSent=("email_id", "count"),
    Emails_Delivered__c=("delivered", "sum"),
    Emails_Opened__c=("opened", "sum"),
    Emails_Clicked__c=("clicked", "sum"),
    Emails_Unsubscribed__c=("unsubscribed", "sum"),
).reset_index().rename(columns={"campaign_id": "Veridian_Campaign_ID__c"})

stats.to_csv(OUT / "sf_campaign_stats.csv", index=False)

print("Campaigns:", len(stats), "(26 expected)")
print("Sent:", int(stats["NumberSent"].sum()), "(19613 expected)")
print("Delivered:", int(stats["Emails_Delivered__c"].sum()), "(19018 expected)")
print("Opened:", int(stats["Emails_Opened__c"].sum()), "(6074 expected)")
print("Clicked:", int(stats["Emails_Clicked__c"].sum()), "(913 expected)")
print("Unsubscribed:", int(stats["Emails_Unsubscribed__c"].sum()), "(54 expected)") 