from pathlib import Path
import pandas as pd

RAW = Path("data/raw")
OUT = Path("data/processed")

camps = pd.read_csv(RAW / "campaigns.csv")
reg = pd.read_csv(RAW / "webinar_attendance.csv")

webinars = (
    reg[["webinar_name", "webinar_date"]]
    .drop_duplicates()
    .sort_values(["webinar_date", "webinar_name"])
    .reset_index(drop=True)
)
webinars["campaign_id"] = ["WEB-%02d" % (i + 1) for i in range(len(webinars))]

campaign_rows = []
for _, r in camps.iterrows():
    campaign_rows.append({
        "Veridian_Campaign_ID__c": r["campaign_id"],
        "Name": r["name"],
        "Type": "Email",
        "Status": "Completed",
        "StartDate": r["send_date"],
        "EndDate": r["send_date"],
        "IsActive": "true",
    })
for _, w in webinars.iterrows():
    campaign_rows.append({
        "Veridian_Campaign_ID__c": w["campaign_id"],
        "Name": w["webinar_name"],
        "Type": "Webinar",
        "Status": "Completed",
        "StartDate": w["webinar_date"],
        "EndDate": w["webinar_date"],
        "IsActive": "true",
    })
pd.DataFrame(campaign_rows).to_csv(OUT / "sf_campaigns.csv", index=False)

status_rows = []
for _, w in webinars.iterrows():
    status_rows.append({
        "Campaign.Veridian_Campaign_ID__c": w["campaign_id"],
        "Label": "Registered", "SortOrder": 3,
        "IsDefault": "false", "HasResponded": "false",
    })
    status_rows.append({
        "Campaign.Veridian_Campaign_ID__c": w["campaign_id"],
        "Label": "Attended", "SortOrder": 4,
        "IsDefault": "false", "HasResponded": "true",
    })
pd.DataFrame(status_rows).to_csv(OUT / "sf_campaign_statuses.csv", index=False)

merged = reg.merge(webinars[["webinar_name", "campaign_id"]], on="webinar_name")
members = pd.DataFrame({
    "Campaign.Veridian_Campaign_ID__c": merged["campaign_id"],
    "Contact.Veridian_Contact_ID__c": merged["contact_id"],
    "Status": merged["attended"].map(
        lambda a: "Attended" if str(a).lower() == "true" else "Registered"
    ),
})
members.to_csv(OUT / "sf_campaign_members.csv", index=False)

print("Campaigns:", len(campaign_rows), "(26 email + 6 webinar expected)")
print("Campaign members:", len(members), "(490 expected)")
print("Attended:", int((members["Status"] == "Attended").sum()), "(276 expected)")