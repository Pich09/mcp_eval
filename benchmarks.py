"""
Query Benchmarks
=================
Each benchmark defines the ground-truth expectations for a class of user query.
Add new entries here when expanding the evaluation test suite.

Fields
------
query_pattern       : regex matched (case-insensitive) against the user query
target_system       : which enterprise system should handle this query
expected_tools      : list of acceptable correct tools (any match → correct)
tool_type           : "static" | "dynamic"
expected_params     : {param_name: expected_value} for the first tool call
expected_sequence   : ordered list of tools expected across the episode
intent              : analytical intent for dynamic SQL evaluation
  aggregation       : expected SQL aggregation function (str) or None
  group_by          : True/False — whether GROUP BY is expected
  filtering         : True/False — whether WHERE clause is expected
  table             : canonical target table name (UPPER)
known_tables        : set of table names valid in this query context
known_columns       : set of column names valid in this query context
"""

from __future__ import annotations
import re


BENCHMARKS: list[dict] = [

    # ── Dynamic: subscriber activation count ────────────────────────────────
    {
        "query_pattern":    r"subscriber.*(activat|last.+month)",
        "target_system":    "analytics_db",
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
        "known_tables":     {"MCP_SUBSCRIBERS"},
        "known_columns":    {"DATE_ENTER_ACTIVE", "COUNT"},
    },

    # ── Static: customer call-issue diagnosis ───────────────────────────────
    {
        "query_pattern":    r"customer.*(cannot|can.t|issue|call)",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_customer", "diagnose_customer"],
        "tool_type":        "static",
        "expected_params":  {"account_no_masked": "126398141"},
        "expected_sequence":["get_customer", "diagnose_customer"],
        "intent":           None,
        "known_tables":     set(),
        "known_columns":    set(),
    },

    # ── Static: top products by subscriber count ─────────────────────────────
    {
        "query_pattern":    r"top.*product.*subscriber|subscriber.*product",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_subscribers_per_offer"],
        "tool_type":        "static",
        "expected_params":  {},
        "expected_sequence":["get_subscribers_per_offer"],
        "intent":           None,
        "known_tables":     set(),
        "known_columns":    set(),
    },

    # ── Static: revenue trend per product ────────────────────────────────────
    {
        "query_pattern":    r"revenue.*trend|trend.*revenue",
        "target_system":    "cust_billing",
        "expected_tools":   ["get_revenue_by_product_trend"],
        "tool_type":        "static",
        "expected_params":  {"months": "6"},
        "expected_sequence":["get_revenue_by_product_trend"],
        "intent":           None,
        "known_tables":     set(),
        "known_columns":    set(),
    },
]


def match_benchmark(query: str) -> dict | None:
    """Return the first matching benchmark for a user query, or None."""
    for b in BENCHMARKS:
        if re.search(b["query_pattern"], query, re.IGNORECASE):
            return b
    return None
