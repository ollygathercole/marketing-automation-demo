# Marketing automation demo: Veridian Optics

An end-to-end demonstration of how marketing operations data can flow from a marketing automation platform, through a CRM and a data warehouse, to an AI assistant that answers questions and writes a weekly briefing.

**Everything here is fictional.** Veridian Optics, the National Health Collective (NHC), every hospital, group, person and number are synthetic. Any resemblance to a real organisation is coincidental. It was built in my own time, with personal accounts and generated data only.

## What it shows

A fictional ophthalmology company sells devices (OCT scanners, phaco systems, retinal cameras) and the consumables they need (calibration kits, surgical packs, probe tips), mainly to a fictional national health service and to private hospital groups. The data contains hidden stories, and the project tests whether a set of tools and Claude can find them honestly:

1. **Consumables gaps.** Accounts that own devices but have stopped ordering the matching consumables. Some follow a clinical lead change, some never ordered at all, and some are deliberately healthy decoys.
2. **Webinars and demo requests.** Contacts who attend webinars request demos at roughly three times the rate of other contacts. This is an association, not proof of cause, and the report says so.

## Architecture

```
Synthetic data generators (Python)
        |
        v
   data/raw/*.csv
        |
        +--> Veridian Engage (mock marketing automation platform: SQLite + FastAPI)
        |
        +--> Salesforce Developer Edition (accounts, contacts, opportunities, campaigns)
        |
        +--> BigQuery (warehouse, nine tables)
                    |
                    v
          Fixed, read-only tools  -->  Claude  -->  answers and a weekly briefing
```

| Layer | What it is | Where |
|---|---|---|
| Data | Python generators write accounts, devices, orders, contacts, subscriptions, campaigns and email, webinar and demo activity | `src/generators/` |
| Marketing platform | "Veridian Engage", a mock platform modelled on generic marketing automation concepts (campaigns, email activity, webinars, demo requests), with a small read-only API | `src/engage/` |
| CRM | Salesforce Developer Edition: custom fields, a permission set, Campaigns with members and statuses, loaded with the Salesforce CLI | `force-app/`, `src/loaders/salesforce_*.py` |
| Warehouse | BigQuery dataset in the sandbox, loaded by one script | `src/loaders/bigquery_load.py` |
| AI layer | Claude with four fixed, read-only tools and a Monday briefing generator | `src/agent/` |

## How Claude is used, and how it is kept honest

Claude does not write SQL. It can only call four fixed tools, which I wrote and tested:

- `find_consumables_gaps` finds accounts with devices that need consumables but have not ordered them, and returns before and after order values where a lead change is on record.
- `get_account_detail` returns one account's profile, devices, orders and events.
- `weekly_marketing_summary` compares the latest period with the one before.
- `webinar_demo_conversion` compares demo rates for attendees, no-shows and contacts who never registered.

Safeguards:

- Tools are read-only, and each query is capped at 200 MB billed.
- The API key lives only in a git-ignored `.env` file.
- The system prompt tells Claude to use only numbers from the tools, to label inferences, and to state the data date.
- If a tool result is too large, the tool says so instead of silently truncating it. Early versions truncated silently, and Claude quietly changed its own threshold, which is why this rule exists.
- The answer key used for scoring stays on my machine. It is never loaded into BigQuery, never shown to Claude and never committed.

A sample output is in [`reports/`](reports/). Generating one costs a few cents.

## Evaluation

Because the data is synthetic, I know which accounts are really in trouble, so the tools can be scored against a private answer key (`python -m src.agent.score_tools`).

At the 6 month threshold the consumables tool flags 96 accounts:

- 34 are accounts that lapsed after a clinical lead change.
- 50 are accounts with a consumables gap and no lead change.
- 12 are healthy accounts flagged wrongly.

That is about 88% precision and about 78% recall. The lead change date separates the "lapsed after lead change" story from the other gap accounts cleanly. The decoys (an account with a lead change that kept ordering, and accounts still ordering) are not flagged at 6 months.

## Limitations

- Precision and recall depend on the threshold. Twelve healthy accounts are flagged at 6 months.
- The webinar tool cannot tell whether a demo request came before or after the webinar, so the 25.9% against 8% comparison is an association only.
- "Still ordering" depends on the threshold chosen.
- Some accounts stopped ordering before their recorded lead change, so the lead change does not explain every lapse.
- Salesforce Developer Edition has a 5 MB data limit, which is why the CRM holds a subset of the activity data.
- BigQuery sandbox tables expire after 60 days. To rebuild them, run `python -m src.loaders.bigquery_load`.

## Run it yourself

You need Python 3, and for the optional parts a Google Cloud project, a Salesforce Developer Edition org with the Salesforce CLI, and an Anthropic API key.

1. Set up:

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

2. Generate the data (this also writes a private answer key to `data/raw/`):

```
python -m src.generators.accounts
python -m src.generators.contacts
python -m src.generators.installed_base
python -m src.generators.consumable_orders
python -m src.generators.subscriptions
python -m src.generators.marketing_activity
```

3. Build the mock marketing platform, and optionally browse its API:

```
python -m src.engage.build_database
uvicorn src.engage.api:app --reload
```

Then open http://127.0.0.1:8000/docs.

4. Load BigQuery. Put `GCP_PROJECT_ID` in `.env`, sign in with `gcloud auth application-default login`, then:

```
python -m src.loaders.bigquery_load
```

5. Ask Claude a question or generate the briefing. Put `ANTHROPIC_API_KEY` in `.env`, then:

```
python -m src.agent.ask_claude "Which accounts have stopped ordering consumables?"
python -m src.agent.monday_report
```

The Salesforce loaders in `src/loaders/salesforce_*.py` prepare CSV files in `data/processed/` for the Salesforce CLI bulk import. Salesforce is optional: the AI layer reads from BigQuery.

## Layout

```
src/generators/   synthetic data
src/engage/       mock marketing platform and API
src/loaders/      Salesforce and BigQuery loaders
src/agent/        tools, Claude loop, scorer, weekly briefing
force-app/        Salesforce metadata (custom fields, permission set)
reports/          sample generated briefing
```

## About

Built by Olly Gathercole as a portfolio project for marketing automation and marketing engineering roles. More at [ollygathercole.com](https://ollygathercole.com).

Licence: see `LICENSE`.