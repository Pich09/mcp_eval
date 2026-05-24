"""
Query Benchmarks
=================
Maps user query patterns to ground-truth evaluation expectations.
Derived from SOUL.md Tool Lookup Table and Multi-Step Flows.

Covers all 4 query categories:
  - cust_billing  (billing, revenue, CDR, customer)
  - main_db       (subscribers, balance, activations, churn)
  - ctlg_db       (SIM inventory)
  - multi-step    (service diagnostic, customer 360)
  - dynamic SQL   (execute_sql flows)
"""

from __future__ import annotations
import re


BENCHMARKS: list[dict] = [

    # ══════════════════════════════════════════════════════════════════════════
    # DYNAMIC — SQL queries via execute_sql
    # ══════════════════════════════════════════════════════════════════════════

    {
        "query_pattern":    r"subscriber.*(activat|last.+month|6 month)",
        "target_system":    "main_db",
        "expected_tools":   ["execute_sql"],
        "tool_type":        "dynamic",
        "expected_params":  {"role": "admin"},
        "expected_sequence":["execute_sql"],
        "intent": {
            "aggregation": "COUNT",
            "group_by":    False,
            "filtering":   True,
            "table":       "MCP_SUBSCRIBERS",
        },
        "known_tables":  {"MCP_SUBSCRIBERS"},
        "known_columns": {"DATE_ENTER_ACTIVE", "COUNT", "CURRENT_STATE"},
    },

    # ══════════════════════════════════════════════════════════════════════════
    # CUSTOMER / BILLING  —  cust_billing :7861
    # ══════════════════════════════════════════════════════════════════════════

    {
        "query_pattern":    r"how many customer|customer count|active account",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_customer_count"],
        "tool_type":        "static",
        "expected_params":  {"account_status": "0"},
        "expected_sequence":["get_customer_count"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"customer profile|account profile|single account",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_customer"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence":["get_customer"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"billing rollup|full billing|customer summary|customer 360 billing",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_customer_summary"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence":["get_customer_summary"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"collection.*(portfolio|overview|summary)|bad debt|cure rate",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_collections_summary"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence":["get_collections_summary"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"invoice|unpaid invoice",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_invoices"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence":["get_invoices"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"total revenue|collection rate|gross revenue|outstanding balance",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_revenue_summary"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence":["get_revenue_summary"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"overall revenue trend|revenue over time(?! per product)(?! by product)",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_revenue_trend"],
        "tool_type":        "static",
        "expected_params":  {"months": "6"},
        "expected_sequence":["get_revenue_trend"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"postpaid revenue trend|postpaid.*billing trend",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_postpaid_revenue_trend"],
        "tool_type":        "static",
        "expected_params":  {"months": "6"},
        "expected_sequence":["get_postpaid_revenue_trend"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"prepaid.*(recharge|revenue) trend",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_prepaid_revenue_trend"],
        "tool_type":        "static",
        "expected_params":  {"months": "6"},
        "expected_sequence":["get_prepaid_revenue_trend"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"\barpu\b|average revenue per user",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_arpu_by_segment"],
        "tool_type":        "static",
        "expected_params":  {"months": "6"},
        "expected_sequence":["get_arpu_by_segment"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"revenue by account type|unbilled|non.?statement prepaid",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_revenue_by_account_type"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence":["get_revenue_by_account_type"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"prepaid recharge summary|total recharged|recharge kpi",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_recharge_summary"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence":["get_recharge_summary"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"revenue by (product|offer)|offer charge summary",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_offer_charge_summary"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence":["get_offer_charge_summary"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"(top|most).*(product|offer).*subscriber|subscriber.*per.*(product|offer)|product adoption",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_subscribers_per_offer"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence":["get_subscribers_per_offer"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"cdr summary|call usage summary|usage kpi",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_cdr_summary"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence":["get_cdr_summary"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"(ltv|lifetime value|avg monthly spend)",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_customer_lifetime_value"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence":["get_customer_lifetime_value"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"payment behavi|on.?time payment|late payment|avg days to pay",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_payment_behavior"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence":["get_payment_behavior"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"health score|churn risk|dissatisfaction|upsell opportunit",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_dissatisfaction_signals"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence":["get_dissatisfaction_signals"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"product.*subscri|multi.?service|offer subscript",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_offer_subscriptions"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence":["get_offer_subscriptions"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"(revenue|product).*(trend|over time)",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_revenue_by_product_trend"],
        "tool_type":        "static",
        "expected_params":  {"months": "6"},
        "expected_sequence":["get_revenue_by_product_trend"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },

    # ══════════════════════════════════════════════════════════════════════════
    # MULTI-STEP: Service Diagnostic  (SOUL.md Multi-Step Flows)
    # ══════════════════════════════════════════════════════════════════════════

    {
        "query_pattern":    r"customer.*(cannot|can.t|issue|call|problem|service problem|diagnos)",
        "target_system":    "cust_billing",
        "expected_tools":   ["diagnose_customer", "get_subscriber_by_account",
                             "diagnose_balance", "diagnose_inventory"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence":["diagnose_customer", "get_subscriber_by_account",
                             "diagnose_balance", "diagnose_inventory"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },

    # ══════════════════════════════════════════════════════════════════════════
    # SUBSCRIBERS  —  main_db :7862
    # ══════════════════════════════════════════════════════════════════════════

    {
        "query_pattern":    r"how many subscriber|subscriber count|subscriber distribution",
        "target_system":    "main_db",
        "expected_tools":   ["get_subscriber_state_summary"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence":["get_subscriber_state_summary"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"deferred revenue|wallet total|balance summary",
        "target_system":    "main_db",
        "expected_tools":   ["get_balance_summary"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence":["get_balance_summary"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"low balance|at.?risk.*balance|top.?up campaign",
        "target_system":    "main_db",
        "expected_tools":   ["get_low_balance_subscribers"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence":["get_low_balance_subscribers"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"subscriber.*plan|subscribers by (offer|plan)|plan distribution",
        "target_system":    "main_db",
        "expected_tools":   ["get_subscribers_by_offer"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence":["get_subscribers_by_offer"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"new activation|base growth|activations? per month",
        "target_system":    "main_db",
        "expected_tools":   ["get_base_growth"],
        "tool_type":        "static",
        "expected_params":  {"months": "6"},
        "expected_sequence":["get_base_growth"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"reactivation",
        "target_system":    "main_db",
        "expected_tools":   ["get_reactivations"],
        "tool_type":        "static",
        "expected_params":  {"months": "6"},
        "expected_sequence":["get_reactivations"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"subscriber movement|churn proxy|net change.*subscriber",
        "target_system":    "main_db",
        "expected_tools":   ["get_subscriber_activations_summary"],
        "tool_type":        "static",
        "expected_params":  {"months": "6"},
        "expected_sequence":["get_subscriber_activations_summary"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"churn risk (list|subscriber)|at.?risk subscriber",
        "target_system":    "main_db",
        "expected_tools":   ["get_churn_risk_subscribers"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence":["get_churn_risk_subscribers"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },

    # ══════════════════════════════════════════════════════════════════════════
    # SIM INVENTORY  —  ctlg_db :7863
    # ══════════════════════════════════════════════════════════════════════════

    {
        "query_pattern":    r"sim (inventory|overview|summary)|inventory summary",
        "target_system":    "ctlg_db",
        "expected_tools":   ["get_inventory_summary"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence":["get_inventory_summary"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"sim status|inventory.*phone|sim.*msisdn",
        "target_system":    "ctlg_db",
        "expected_tools":   ["get_inventory_by_external_no"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence":["get_inventory_by_external_no"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"status code|inventory.*label|status catalog",
        "target_system":    "ctlg_db",
        "expected_tools":   ["get_inventory_status_catalog"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence":["get_inventory_status_catalog"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
]


def match_benchmark(query: str) -> dict | None:
    """Return the first matching benchmark for a user query, or None."""
    for b in BENCHMARKS:
        if re.search(b["query_pattern"], query, re.IGNORECASE):
            return b
    return None
