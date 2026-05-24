"""
Query Benchmarks  —  v2
========================
Maps user query patterns to ground-truth evaluation expectations.
Derived from SOUL.md Tool Lookup Table, Multi-Step Flows, and the
telecom_eval_questions spreadsheet (Daravuth review).

Covers all 4 query categories:
  - cust_billing  (billing, revenue, CDR, customer, collections)
  - main_db       (subscribers, balance, activations, churn)
  - ctlg_db       (SIM inventory)
  - multi-step    (service diagnostic, customer 360, account audit)
  - dynamic SQL   (execute_sql flows)

v2 changes vs v1
----------------
  NEW patterns (14 missing from spreadsheet coverage):
    - total billed revenue this month          → execute_sql (Finance)
    - active subscribers currently             → get_subscriber_state_summary
    - expiry balance rate                      → get_subscriber_activations_summary
    - multiple products / multi-service SQL    → execute_sql
    - highest revenue product (top N)          → get_offer_charge_summary
    - total call volume / usage revenue        → get_cdr_summary
    - top 10 customers by usage revenue        → execute_sql
    - usage trend over N months                → get_cdr_usage_trend
    - call type distribution                   → get_cdr_summary
    - accounts in collections                  → get_collections
    - total amount due from collections        → get_collections_summary
    - frequently pay late                      → execute_sql (late payment SQL)
    - full customer 360 view                   → multi-step 360 flow
    - subscribers + CDR per account            → multi-step sub+cdr

  FIXED patterns:
    - "(revenue|product).*(trend|over time)"  was overly broad → split into
      specific patterns so product-revenue-trend doesn't shadow revenue_trend
    - "invoice|unpaid invoice" now excludes "unpaid invoices older than N days"
      (those are execute_sql queries, not get_invoices)

  ORDERING NOTE:
    Patterns are matched first-wins by match_benchmark(). More-specific
    patterns must appear BEFORE broader ones that could shadow them.
"""

from __future__ import annotations
import re


BENCHMARKS: list[dict] = [

    # ══════════════════════════════════════════════════════════════════════════
    # DYNAMIC — SQL via execute_sql
    # Order: most-specific dynamic intents first so they don't fall through
    # to static patterns.
    # ══════════════════════════════════════════════════════════════════════════

    # Finance: total billed revenue this month (execute_sql on cust_billing)
    {
        "query_pattern":    r"total billed revenue.*(this month|current month|month)",
        "target_system":    "cust_billing",
        "expected_tools":   ["execute_sql"],
        "tool_type":        "dynamic",
        "expected_params":  {"role": "admin"},
        "expected_sequence": ["execute_sql"],
        "intent": {
            "aggregation": "SUM",
            "group_by":    False,
            "filtering":   True,
            "table":       "MCP_INVOICES",
        },
        "known_tables":  {"MCP_INVOICES"},
        "known_columns": {"TOTAL_DUE", "STATEMENT_DATE"},
    },

    # Product: customers subscribed to multiple products (execute_sql)
    {
        "query_pattern":    r"subscribed to multiple (product|offer)|multi.?product|more than one (offer|product)",
        "target_system":    "cust_billing",
        "expected_tools":   ["execute_sql"],
        "tool_type":        "dynamic",
        "expected_params":  {"role": "admin"},
        "expected_sequence": ["execute_sql"],
        "intent": {
            "aggregation": "COUNT",
            "group_by":    True,
            "filtering":   True,
            "table":       "MCP_OFFER_CHARGE",
        },
        "known_tables":  {"MCP_OFFER_CHARGE"},
        "known_columns": {"ACCOUNT_NO_MASKED", "INACTIVE_DT"},
    },

    # Usage: top 10 customers by usage revenue (execute_sql)
    {
        "query_pattern":    r"top\s*\d+\s*customer.*(usage|revenue)|highest usage revenue",
        "target_system":    "cust_billing",
        "expected_tools":   ["execute_sql"],
        "tool_type":        "dynamic",
        "expected_params":  {"role": "admin"},
        "expected_sequence": ["execute_sql"],
        "intent": {
            "aggregation": "SUM",
            "group_by":    True,
            "filtering":   False,
            "table":       "MCP_CDR_DETAILS",
        },
        "known_tables":  {"MCP_CDR_DETAILS"},
        "known_columns": {"ACCOUNT_NO_MASKED", "CHARGED_AMOUNT"},
    },

    # Collections: unpaid invoices older than N days (execute_sql)
    {
        "query_pattern":    r"unpaid invoice.*(older|more than|past|exceed|over).*day",
        "target_system":    "cust_billing",
        "expected_tools":   ["execute_sql"],
        "tool_type":        "dynamic",
        "expected_params":  {"role": "admin"},
        "expected_sequence": ["execute_sql"],
        "intent": {
            "aggregation": None,
            "group_by":    False,
            "filtering":   True,
            "table":       "MCP_INVOICES",
        },
        "known_tables":  {"MCP_INVOICES"},
        "known_columns": {"ACCOUNT_NO_MASKED", "BALANCE_DUE", "STATEMENT_DATE"},
    },

    # Collections: highest outstanding balances (execute_sql)
    {
        "query_pattern":    r"highest outstanding balance|most outstanding|highest.*balance.*owed",
        "target_system":    "cust_billing",
        "expected_tools":   ["execute_sql"],
        "tool_type":        "dynamic",
        "expected_params":  {"role": "admin"},
        "expected_sequence": ["execute_sql"],
        "intent": {
            "aggregation": "SUM",
            "group_by":    True,
            "filtering":   True,
            "table":       "MCP_INVOICES",
        },
        "known_tables":  {"MCP_INVOICES"},
        "known_columns": {"ACCOUNT_NO_MASKED", "BALANCE_DUE"},
    },

    # Collections: frequently pay late (execute_sql)
    {
        "query_pattern":    r"frequently pay late|late payment|often.*late|pay.*after.*due",
        "target_system":    "cust_billing",
        "expected_tools":   ["execute_sql"],
        "tool_type":        "dynamic",
        "expected_params":  {"role": "admin"},
        "expected_sequence": ["execute_sql"],
        "intent": {
            "aggregation": "COUNT",
            "group_by":    True,
            "filtering":   False,
            "table":       "MCP_PAYMENT",
        },
        "known_tables":  {"MCP_PAYMENT"},
        "known_columns": {"ACCOUNT_NO_MASKED"},
    },

    # Advanced: offers with high revenue but low subscriber count (execute_sql)
    {
        "query_pattern":    r"high revenue.*(low|few) subscriber|revenue.*low.*adoption|offer.*revenue.*subscriber.*count",
        "target_system":    "cust_billing",
        "expected_tools":   ["execute_sql"],
        "tool_type":        "dynamic",
        "expected_params":  {"role": "admin"},
        "expected_sequence": ["execute_sql"],
        "intent": {
            "aggregation": "SUM",
            "group_by":    True,
            "filtering":   False,
            "table":       "MCP_OFFER_CHARGE",
        },
        "known_tables":  {"MCP_OFFER_CHARGE"},
        "known_columns": {"OFFER_NAME", "SUBSCRIBER_NO_MASKED"},
    },

    # SIM deactivated vs active subscriber mismatch (multi: main_db + ctlg_db)
    # IMPORTANT: must appear before the generic dynamic pattern below because
    # "Deactivated" contains "activat" which that pattern matches.
    {
        "query_pattern":    r"sim.*(deactivat|mismatch|inconsistent).*subscriber|subscriber.*active.*sim.*(deactivat|inactive)|deactivated.*inventory.*active.*subscriber|marked.*deactivated.*inventory",
        "target_system":    "main_db",
        "expected_tools":   ["get_subscriber_by_account", "diagnose_inventory"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence": ["get_subscriber_by_account", "diagnose_inventory"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },

    # NOTE: "how many subscribers have activated in last N months" → get_reactivations (static)
    # This must appear BEFORE the generic dynamic pattern below.
    {
        "query_pattern":    r"how many subscriber.*(activat|joined).*(last|past|over).*month|subscriber.*(activat).*(last|past)\s*\d+\s*month",
        "target_system":    "main_db",
        "expected_tools":   ["get_reactivations"],
        "tool_type":        "static",
        "expected_params":  {"months": "6"},
        "expected_sequence": ["get_reactivations"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },

    # Generic dynamic subscriber-activation SQL
    {
        "query_pattern":    r"subscriber.*(activat|last.+month|6 month)",
        "target_system":    "main_db",
        "expected_tools":   ["execute_sql"],
        "tool_type":        "dynamic",
        "expected_params":  {"role": "admin"},
        "expected_sequence": ["execute_sql"],
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
    # MULTI-STEP FLOWS
    # Must appear before broad single-tool patterns they might shadow.
    # ══════════════════════════════════════════════════════════════════════════

    # Customer 360 — full view (5-step flow)
    {
        "query_pattern":    r"full.*(360|view|profile).*customer|customer.*360|360.*view.*account",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_customer_summary", "get_subscriber_by_account",
                             "get_inventory_by_external_no", "get_collections",
                             "get_dissatisfaction_signals"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence": ["get_customer_summary", "get_subscriber_by_account",
                              "get_inventory_by_external_no", "get_collections",
                              "get_dissatisfaction_signals"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },

    # Service diagnostic — cannot make calls
    {
        "query_pattern":    r"customer.*(cannot|can.t|issue|call|problem|service problem|diagnos)",
        "target_system":    "cust_billing",
        "expected_tools":   ["diagnose_customer", "get_subscriber_by_account",
                             "diagnose_balance", "diagnose_inventory"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence": ["diagnose_customer", "get_subscriber_by_account",
                              "diagnose_balance", "diagnose_inventory"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },

    # Account audit — collections + balance + SIM  (3-step)
    {
        "query_pattern":    r"full audit|account.*in collection.*balance.*sim|audit.*collection.*balance",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_collections", "get_subscriber_by_account",
                             "get_inventory_by_external_no"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence": ["get_collections", "get_subscriber_by_account",
                              "get_inventory_by_external_no"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },

    # Subscribers + CDR per account (2-step)
    {
        "query_pattern":    r"subscriber.*(linked|under).*account.*cdr|find.*subscriber.*call.*(record|cdr)|cdr.*subscriber.*account",
        "target_system":    "main_db",
        "expected_tools":   ["get_subscriber_by_account", "get_cdr"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence": ["get_subscriber_by_account", "get_cdr"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },

    # Recharge vs invoices per account (2-step Finance)
    {
        "query_pattern":    r"recharge.*(vs|versus|compared|compare).*invoice|invoice.*vs.*recharge",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_recharge", "get_invoices"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence": ["get_recharge", "get_invoices"],
        "intent": None, "known_tables": set(), "known_columns": set(),
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
        "expected_sequence": ["get_customer_count"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"inactive.*subscriber|suspended.*subscriber|subscriber.*(inactive|suspended)",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_customer_count"],
        "tool_type":        "static",
        "expected_params":  {"account_status": "SUSPENDED"},
        "expected_sequence": ["get_customer_count"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"customer profile|account profile|single account",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_customer"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence": ["get_customer"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"billing rollup|full billing|customer summary|customer 360 billing",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_customer_summary"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence": ["get_customer_summary"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"collection.*(portfolio|overview|summary)|bad debt level|cure rate",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_collections_summary"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence": ["get_collections_summary"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    # Collections: accounts currently in collections  (NOT the summary)
    {
        "query_pattern":    r"(accounts?|who).*(currently|now).*(in collection)|which accounts?.*(in collection)",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_collections"],
        "tool_type":        "static",
        "expected_params":  {"active_only": "true"},
        "expected_sequence": ["get_collections"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    # Collections: total amount due (summary KPI)
    {
        "query_pattern":    r"total (amount|balance|due).*(from collection|in collection|outstanding.*collection)",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_collections_summary"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence": ["get_collections_summary"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    # Invoice list (exclude "older than N days" — that's execute_sql, handled above)
    {
        "query_pattern":    r"\binvoice\b(?!.*older than|.*more than.*day|.*past.*day)",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_invoices"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence": ["get_invoices"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"current collection rate|total revenue|gross revenue|outstanding balance",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_revenue_summary"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence": ["get_revenue_summary"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    # Postpaid revenue trend (specific — before generic revenue trend)
    {
        "query_pattern":    r"postpaid revenue trend|postpaid.*billing trend",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_postpaid_revenue_trend"],
        "tool_type":        "static",
        "expected_params":  {"months": "6"},
        "expected_sequence": ["get_postpaid_revenue_trend"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    # Prepaid recharge/revenue trend (specific — before generic revenue trend)
    {
        "query_pattern":    r"prepaid.*(recharge|revenue) trend",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_prepaid_revenue_trend"],
        "tool_type":        "static",
        "expected_params":  {"months": "6"},
        "expected_sequence": ["get_prepaid_revenue_trend"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    # Product revenue trend per product over time (specific — before generic revenue trend)
    {
        "query_pattern":    r"revenue trend per product|revenue.*(per|by) (product|offer).*(trend|over time|month)|product.*(revenue).*(trend|over time)",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_revenue_by_product_trend"],
        "tool_type":        "static",
        "expected_params":  {"months": "6"},
        "expected_sequence": ["get_revenue_by_product_trend"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    # Overall revenue trend (generic — after all specific revenue-trend patterns)
    {
        "query_pattern":    r"overall revenue trend|revenue trend$|revenue over time",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_revenue_trend"],
        "tool_type":        "static",
        "expected_params":  {"months": "6"},
        "expected_sequence": ["get_revenue_trend"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"\barpu\b|average revenue per user",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_arpu_by_segment"],
        "tool_type":        "static",
        "expected_params":  {"months": "6"},
        "expected_sequence": ["get_arpu_by_segment"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"revenue by account type|unbilled|non.?statement prepaid",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_revenue_by_account_type"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence": ["get_revenue_by_account_type"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"prepaid recharge summary|total recharged|recharge kpi",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_recharge_summary"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence": ["get_recharge_summary"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    # Revenue by product/offer (summary) — "top N products" also maps here
    {
        "query_pattern":    r"revenue by (product|offer)|offer charge summary|highest revenue.*(product|offer)|which (product|offer).*(generat|earn).*(most|highest)",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_offer_charge_summary"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence": ["get_offer_charge_summary"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    # Subscribers per offer/product (count, not revenue)
    {
        "query_pattern":    r"(how many|number of) subscriber.*per.*(product|offer)|subscriber.*(subscribed|per).*(product|offer)|product adoption",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_subscribers_per_offer"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence": ["get_subscribers_per_offer"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    # CDR summary / total call volume / usage revenue / call type distribution
    {
        "query_pattern":    r"total call volume|usage revenue|cdr summary|call usage summary|usage kpi|distribution.*call type|call type.*distribution",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_cdr_summary"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence": ["get_cdr_summary"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    # CDR usage trend over N months (specific — must precede cdr_summary)
    {
        "query_pattern":    r"usage trend.*(over|last|past).*month|cdr.*usage.*trend",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_cdr_usage_trend"],
        "tool_type":        "static",
        "expected_params":  {"months": "6"},
        "expected_sequence": ["get_cdr_usage_trend"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"(ltv|lifetime value|avg monthly spend)",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_customer_lifetime_value"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence": ["get_customer_lifetime_value"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"payment behavi|on.?time payment|avg days to pay",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_payment_behavior"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence": ["get_payment_behavior"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"health score|dissatisfaction|upsell opportunit",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_dissatisfaction_signals"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence": ["get_dissatisfaction_signals"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"product.*subscri|multi.?service|offer subscript",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_offer_subscriptions"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence": ["get_offer_subscriptions"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },

    # ══════════════════════════════════════════════════════════════════════════
    # SUBSCRIBERS  —  main_db :7862
    # ══════════════════════════════════════════════════════════════════════════

    # Active subscribers currently (get_subscriber_state_summary)
    {
        "query_pattern":    r"how many.*(active subscriber|subscriber.*active|subscriber.*currently)|active subscriber.*currently|currently.*active subscriber",
        "target_system":    "main_db",
        "expected_tools":   ["get_subscriber_state_summary"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence": ["get_subscriber_state_summary"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    # Generic subscriber count/distribution
    {
        "query_pattern":    r"how many subscriber|subscriber count|subscriber distribution|subscriber state",
        "target_system":    "main_db",
        "expected_tools":   ["get_subscriber_state_summary"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence": ["get_subscriber_state_summary"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"deferred revenue|wallet total|balance summary",
        "target_system":    "main_db",
        "expected_tools":   ["get_balance_summary"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence": ["get_balance_summary"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"total deferred revenue.*prepaid|deferred.*prepaid.*balance",
        "target_system":    "main_db",
        "expected_tools":   ["get_balance_summary"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence": ["get_balance_summary"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"low balance|at.?risk.*balance|top.?up campaign",
        "target_system":    "main_db",
        "expected_tools":   ["get_low_balance_subscribers"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence": ["get_low_balance_subscribers"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"subscriber.*plan|subscribers by (offer|plan)|plan distribution",
        "target_system":    "main_db",
        "expected_tools":   ["get_subscribers_by_offer"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence": ["get_subscribers_by_offer"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    # New activations this month (months=1) or general base growth
    {
        "query_pattern":    r"new activation|base growth(?! trend)|activations? (this month|per month|occurred)",
        "target_system":    "main_db",
        "expected_tools":   ["get_base_growth"],
        "tool_type":        "static",
        "expected_params":  {"months": "6"},
        "expected_sequence": ["get_base_growth"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"reactivation|subscriber.*(activated|activation).*(last|past|over).*6 month",
        "target_system":    "main_db",
        "expected_tools":   ["get_reactivations"],
        "tool_type":        "static",
        "expected_params":  {"months": "6"},
        "expected_sequence": ["get_reactivations"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    # Expiry balance rate + base growth trend → subscriber_activations_summary
    {
        "query_pattern":    r"expiry balance rate|subscriber movement|base growth trend|churn proxy|net change.*subscriber",
        "target_system":    "main_db",
        "expected_tools":   ["get_subscriber_activations_summary"],
        "tool_type":        "static",
        "expected_params":  {"months": "6"},
        "expected_sequence": ["get_subscriber_activations_summary"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"churn risk (list|subscriber)|at.?risk subscriber",
        "target_system":    "main_db",
        "expected_tools":   ["get_churn_risk_subscribers"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence": ["get_churn_risk_subscribers"],
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
        "expected_sequence": ["get_inventory_summary"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"sim status|inventory.*phone|sim.*msisdn",
        "target_system":    "ctlg_db",
        "expected_tools":   ["get_inventory_by_external_no"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence": ["get_inventory_by_external_no"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
    {
        "query_pattern":    r"status code|inventory.*label|status catalog",
        "target_system":    "ctlg_db",
        "expected_tools":   ["get_inventory_status_catalog"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence": ["get_inventory_status_catalog"],
        "intent": None, "known_tables": set(), "known_columns": set(),
    },
]


def match_benchmark(query: str) -> dict | None:
    """Return the first matching benchmark for a user query, or None."""
    for b in BENCHMARKS:
        if re.search(b["query_pattern"], query, re.IGNORECASE):
            return b
    return None