import json
import os
from datetime import date, datetime, timedelta

from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()

PROJECT = os.environ.get("GCP_PROJECT_ID")
DATASET = "veridian_optics"
LOCATION = "europe-west2"
MAX_BYTES = 200 * 1024 * 1024  # safety cap per query

_client = None


def _bq():
    global _client
    if _client is None:
        _client = bigquery.Client(project=PROJECT, location=LOCATION)
    return _client


def _t(name):
    return f"`{PROJECT}.{DATASET}.{name}`"


def _clean(row):
    out = {}
    for key, value in row.items():
        out[key] = value.isoformat() if isinstance(value, (date, datetime)) else value
    return out


def _run(sql, params=None):
    config = bigquery.QueryJobConfig(
        query_parameters=params or [],
        maximum_bytes_billed=MAX_BYTES,
    )
    rows = _bq().query(sql, job_config=config).result()
    return [_clean(dict(r.items())) for r in rows]


def find_consumables_gaps(months_without_orders=6, limit=120):
    """Accounts with devices that need consumables but have not ordered them recently."""
    months = max(3, min(int(months_without_orders), 24))
    limit = max(1, min(int(limit), 300))
    sql = f"""
    WITH anchor AS (SELECT MAX(order_date) AS as_of FROM {_t('consumable_orders')}),
    asset_orders AS (
      SELECT asset_id, MAX(order_date) AS last_order
      FROM {_t('consumable_orders')} GROUP BY asset_id
    ),
    acct_orders AS (
      SELECT account_id, MAX(order_date) AS account_last_order
      FROM {_t('consumable_orders')} GROUP BY account_id
    ),
    leads AS (
      SELECT account_id, MAX(event_date) AS lead_change_date
      FROM {_t('account_events')}
      WHERE event_type LIKE '%Lead Change%' GROUP BY account_id
    ),
    trend AS (
      SELECT o.account_id,
             SUM(IF(o.order_date < ld.lead_change_date
                    AND o.order_date >= DATE_SUB(ld.lead_change_date, INTERVAL 12 MONTH),
                    o.order_value, 0)) AS value_before,
             SUM(IF(o.order_date >= ld.lead_change_date, o.order_value, 0)) AS value_since,
             DATE_DIFF(anchor.as_of, ld.lead_change_date, MONTH) AS months_since
      FROM {_t('consumable_orders')} o
      JOIN leads ld ON ld.account_id = o.account_id
      CROSS JOIN anchor
      GROUP BY o.account_id, ld.lead_change_date, anchor.as_of
    ),
    devices AS (
      SELECT b.account_id, b.asset_id, b.consumable_type,
             (b.install_date < DATE_SUB(anchor.as_of, INTERVAL @months MONTH)
              AND (ao.last_order IS NULL
                   OR ao.last_order < DATE_SUB(anchor.as_of, INTERVAL @months MONTH))) AS is_gap
      FROM {_t('installed_base')} b
      CROSS JOIN anchor
      LEFT JOIN asset_orders ao ON ao.asset_id = b.asset_id
      WHERE b.consumable_type IS NOT NULL AND b.consumable_type != ''
    )
    SELECT d.account_id, a.name, a.account_type, a.region, a.size,
           COUNT(*) AS devices_needing_consumables,
           COUNTIF(d.is_gap) AS devices_with_gap,
           STRING_AGG(DISTINCT IF(d.is_gap, d.consumable_type, NULL), ', ') AS gap_consumable_types,
           ac.account_last_order,
           ac.account_last_order >= DATE_SUB(anchor.as_of, INTERVAL @months MONTH)
             AS account_still_ordering_something,
           ld.lead_change_date,
           ROUND(tr.value_before / 12) AS avg_monthly_value_12m_before_lead_change,
           ROUND(SAFE_DIVIDE(tr.value_since, tr.months_since)) AS avg_monthly_value_since_lead_change,
           anchor.as_of AS data_as_of
    FROM devices d
    JOIN {_t('accounts')} a ON a.account_id = d.account_id
    LEFT JOIN acct_orders ac ON ac.account_id = d.account_id
    LEFT JOIN leads ld ON ld.account_id = d.account_id
    LEFT JOIN trend tr ON tr.account_id = d.account_id
    CROSS JOIN anchor
    GROUP BY d.account_id, a.name, a.account_type, a.region, a.size,
             ac.account_last_order, ld.lead_change_date,
             tr.value_before, tr.value_since, tr.months_since, anchor.as_of
    HAVING COUNTIF(d.is_gap) > 0
    ORDER BY devices_with_gap DESC, ac.account_last_order DESC
    LIMIT @limit
    """
    params = [
        bigquery.ScalarQueryParameter("months", "INT64", months),
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
    ]
    return _run(sql, params)


def get_account_detail(account_id):
    """Full picture of one account: profile, devices, monthly ordering, key events."""
    p = [bigquery.ScalarQueryParameter("acc", "STRING", str(account_id))]
    profile = _run(f"SELECT * FROM {_t('accounts')} WHERE account_id = @acc", p)
    devices = _run(
        f"""SELECT asset_id, product, product_line, consumable_type, install_date,
                   warranty_end, service_contract
            FROM {_t('installed_base')} WHERE account_id = @acc ORDER BY install_date""",
        p,
    )
    orders = _run(
        f"""SELECT FORMAT_DATE('%Y-%m', order_date) AS month, consumable_type,
                   COUNT(*) AS orders, SUM(quantity) AS units, ROUND(SUM(order_value)) AS value
            FROM {_t('consumable_orders')} WHERE account_id = @acc
            GROUP BY month, consumable_type ORDER BY month DESC, consumable_type LIMIT 60""",
        p,
    )
    events = _run(
        f"""SELECT event_type, event_date FROM {_t('account_events')}
            WHERE account_id = @acc ORDER BY event_date""",
        p,
    )
    return {"profile": profile, "devices": devices,
            "recent_monthly_orders": orders, "events": events}


def _window_summary(start, end):
    p = [
        bigquery.ScalarQueryParameter("s", "DATE", start),
        bigquery.ScalarQueryParameter("e", "DATE", end),
    ]
    totals = _run(
        f"""SELECT
          (SELECT COUNT(*) FROM {_t('email_activity')} WHERE send_date BETWEEN @s AND @e) AS emails_sent,
          (SELECT COUNTIF(delivered) FROM {_t('email_activity')} WHERE send_date BETWEEN @s AND @e) AS emails_delivered,
          (SELECT COUNTIF(opened) FROM {_t('email_activity')} WHERE send_date BETWEEN @s AND @e) AS emails_opened,
          (SELECT COUNTIF(clicked) FROM {_t('email_activity')} WHERE send_date BETWEEN @s AND @e) AS emails_clicked,
          (SELECT COUNTIF(unsubscribed) FROM {_t('email_activity')} WHERE send_date BETWEEN @s AND @e) AS unsubscribes,
          (SELECT COUNT(*) FROM {_t('webinar_attendance')} WHERE registered_date BETWEEN @s AND @e) AS webinar_registrations,
          (SELECT COUNTIF(attended) FROM {_t('webinar_attendance')} WHERE webinar_date BETWEEN @s AND @e) AS webinar_attendances,
          (SELECT COUNT(*) FROM {_t('demo_requests')} WHERE request_date BETWEEN @s AND @e) AS demo_requests""",
        p,
    )[0]
    campaigns = _run(
        f"""SELECT c.name AS campaign, COUNT(*) AS sent, COUNTIF(e.opened) AS opened,
                   COUNTIF(e.clicked) AS clicked
            FROM {_t('email_activity')} e JOIN {_t('campaigns')} c ON c.campaign_id = e.campaign_id
            WHERE e.send_date BETWEEN @s AND @e GROUP BY campaign ORDER BY sent DESC LIMIT 10""",
        p,
    )
    demos = _run(
        f"""SELECT product_interest, COUNT(*) AS requests FROM {_t('demo_requests')}
            WHERE request_date BETWEEN @s AND @e GROUP BY product_interest ORDER BY requests DESC""",
        p,
    )
    return {"from": start.isoformat(), "to": end.isoformat(), "totals": totals,
            "email_campaigns_sent": campaigns, "demo_requests_by_product": demos}


def weekly_marketing_summary(period_days=7, period_end=None):
    """Marketing activity for the period ending on period_end, plus the period before it."""
    days = max(7, min(int(period_days), 90))
    if period_end:
        end = date.fromisoformat(period_end)
    else:
        end = _run(
            f"""SELECT GREATEST(
                  (SELECT MAX(send_date) FROM {_t('email_activity')}),
                  (SELECT MAX(request_date) FROM {_t('demo_requests')})) AS d"""
        )[0]["d"]
        end = date.fromisoformat(end)
    start = end - timedelta(days=days - 1)
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=days - 1)
    return {"current_period": _window_summary(start, end),
            "previous_period": _window_summary(prev_start, prev_end)}


def webinar_demo_conversion():
    """Demo request rate for emailed contacts, by webinar behaviour."""
    sql = f"""
    WITH emailed AS (SELECT DISTINCT contact_id FROM {_t('email_activity')}),
    web AS (
      SELECT contact_id, MAX(IF(attended, 1, 0)) AS attended_any
      FROM {_t('webinar_attendance')} GROUP BY contact_id
    ),
    demo AS (SELECT DISTINCT contact_id FROM {_t('demo_requests')})
    SELECT
      CASE WHEN w.attended_any = 1 THEN 'Attended a webinar'
           WHEN w.contact_id IS NOT NULL THEN 'Registered but did not attend'
           ELSE 'Never registered' END AS segment,
      COUNT(*) AS contacts,
      COUNTIF(d.contact_id IS NOT NULL) AS contacts_requesting_demo,
      ROUND(100 * COUNTIF(d.contact_id IS NOT NULL) / COUNT(*), 1) AS demo_rate_percent
    FROM emailed e
    LEFT JOIN web w ON w.contact_id = e.contact_id
    LEFT JOIN demo d ON d.contact_id = e.contact_id
    GROUP BY segment
    ORDER BY demo_rate_percent DESC
    """
    return _run(sql)


TOOL_SCHEMAS = [
    {
        "name": "find_consumables_gaps",
        "description": (
            "Finds accounts with devices that need consumables but have not ordered "
            "them recently. Returns one row per account with the number of devices "
            "affected, which consumable types are missing, the account's last order "
            "date, and whether the account is still ordering other things. An account "
            "still ordering something suggests a gap on specific devices; one that has "
            "stopped entirely suggests lapsing. lead_change_date is the date of a recorded clinical lead change at the account (empty if none), and avg_monthly_value_12m_before_lead_change versus avg_monthly_value_since_lead_change show how its ordering changed after it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "months_without_orders": {
                    "type": "integer",
                    "description": "Months without an order to count as a gap (3 to 24, default 6).",
                },
                "limit": {"type": "integer", "description": "Maximum accounts to return (default 120, max 300)."},
            },
        },
    },
    {
        "name": "get_account_detail",
        "description": (
            "Returns one account's profile, installed devices, monthly consumable "
            "ordering history and key events such as clinical lead changes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"account_id": {"type": "string", "description": "For example ACC-0023."}},
            "required": ["account_id"],
        },
    },
    {
        "name": "weekly_marketing_summary",
        "description": (
            "Summarises marketing activity (emails sent, delivered, opened, clicked, "
            "unsubscribes, webinar registrations and attendances, demo requests) for a "
            "period, with the previous period of the same length for comparison. "
            "Defaults to the 7 days ending on the latest activity in the data."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "period_days": {"type": "integer", "description": "Length of period in days (7 to 90, default 7)."},
                "period_end": {"type": "string", "description": "Optional end date as YYYY-MM-DD."},
            },
        },
    },
    {
        "name": "webinar_demo_conversion",
        "description": (
            "Compares the demo request rate of emailed contacts who attended a "
            "webinar, registered but did not attend, or never registered."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
]

_FUNCTIONS = {
    "find_consumables_gaps": find_consumables_gaps,
    "get_account_detail": get_account_detail,
    "weekly_marketing_summary": weekly_marketing_summary,
    "webinar_demo_conversion": webinar_demo_conversion,
}


MAX_CHARS = 60000


def _compact(result):
    if isinstance(result, list) and result and all(isinstance(r, dict) for r in result):
        columns = list(result[0].keys())
        return {"columns": columns, "rows": [[r.get(c) for c in columns] for r in result]}
    return result


def run_tool(name, arguments):
    func = _FUNCTIONS.get(name)
    if func is None:
        return json.dumps({"error": "Unknown tool: " + str(name)})
    try:
        text = json.dumps(_compact(func(**(arguments or {}))), default=str)
    except Exception as exc:
        return json.dumps({"error": str(exc)})
    if len(text) > MAX_CHARS:
        return json.dumps({"error": "Result too large (" + str(len(text))
                           + " characters). Call again with a smaller limit."})
    return text
