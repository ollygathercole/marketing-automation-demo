import csv
from collections import Counter

from src.agent.tools import find_consumables_gaps

with open("data/raw/answer_key.csv", newline="", encoding="utf-8") as f:
    key = {row["account_id"]: row["hidden_pattern"] for row in csv.DictReader(f)}

patterns = sorted(set(key.values()))
print("Accounts in the answer key:", dict(Counter(key.values())))

for months in (6, 9):
    rows = find_consumables_gaps(months_without_orders=months, limit=300)
    with_lead = Counter()
    no_lead = Counter()
    for r in rows:
        pattern = key.get(r["account_id"], "NOT IN KEY")
        if r.get("lead_change_date"):
            with_lead[pattern] += 1
        else:
            no_lead[pattern] += 1

    print()
    print(f"{len(rows)} accounts flagged with {months} months without orders")
    print(f"  {'Hidden pattern':<32}{'Lead change on file':>20}{'No lead change':>16}")
    for p in patterns:
        print(f"  {p:<32}{with_lead[p]:>20}{no_lead[p]:>16}")