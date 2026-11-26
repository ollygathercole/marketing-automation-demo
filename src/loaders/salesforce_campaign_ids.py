from pathlib import Path
import pandas as pd

OUT = Path("data/processed")

ids = pd.read_csv(OUT / "sf_webinar_campaign_ids.csv")
id_map = dict(zip(ids["Veridian_Campaign_ID__c"], ids["Id"]))
print("Webinar campaigns found in Salesforce:", len(id_map), "(6 expected)")

statuses = []
for veridian_id, sf_id in id_map.items():
    statuses.append({"CampaignId": sf_id, "Label": "Registered", "SortOrder": 3,
                     "IsDefault": "false", "HasResponded": "false"})
    statuses.append({"CampaignId": sf_id, "Label": "Attended", "SortOrder": 4,
                     "IsDefault": "false", "HasResponded": "true"})
pd.DataFrame(statuses).to_csv(OUT / "sf_campaign_statuses.csv", index=False)

members = pd.read_csv(OUT / "sf_campaign_members.csv")
members["CampaignId"] = members["Campaign.Veridian_Campaign_ID__c"].map(id_map)
members = members.drop(columns=["Campaign.Veridian_Campaign_ID__c"])
members = members[["CampaignId", "Contact.Veridian_Contact_ID__c", "Status"]]
members.to_csv(OUT / "sf_campaign_members.csv", index=False)

print("Status rows:", len(statuses), "(12 expected)")
print("Member rows:", len(members), "(490 expected)")
print("Members with no campaign match:", int(members["CampaignId"].isna().sum()), "(0 expected)")