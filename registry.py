"""
Enterprise MCP Tool & System Registry
======================================
Source of truth derived directly from SOUL.md.

4 servers  ·  53 scoreable tools  ·  3 databases
  cust_billing  :7861  — cust_billing_dbt   (30 tools)
  main_db       :7862  — main_dbt           (16 tools)
  ctlg_db       :7863  — ctlg_dbt           ( 7 tools)
  auth_gateway  :7870  — auth_db            ( 9 tools, all infrastructure)

Primary join keys (SOUL.md Cross-DB section):
  account_no_masked    cust_billing_dbt  <-> main_dbt
  external_no_masked   main_dbt          <-> ctlg_dbt
  subscriber_no_masked main_dbt          <-> cust_billing_dbt (MCP_RCHG, MCP_OFFER_CHARGE, mcp_cdr_details)
"""

from __future__ import annotations


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM & TOOL REGISTRY
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_REGISTRY: dict[str, dict] = {

    # ── auth_gateway ──────────────────────────────────────────────────────────
    "auth_gateway": {
        "port": 7870,
        "database": "auth_db",
        "description": "Access control only — no data served here",
        "tools": {
            "check_access":                  {"type": "static", "parameters": ["telegram_id"]},
            "get_registration_instructions": {"type": "static", "parameters": []},
            "get_role_permissions":          {"type": "static", "parameters": ["telegram_id"]},
            "notify_user":                   {"type": "static", "parameters": ["telegram_id", "message"]},
            "get_pending_registrations":     {"type": "static", "parameters": []},
            "approve_user":                  {"type": "static", "parameters": ["request_id", "role", "notify"]},
            "reject_user":                   {"type": "static", "parameters": ["request_id", "reason", "notify"]},
            "change_user_role":              {"type": "static", "parameters": ["telegram_id", "new_role", "reason", "notify"]},
            "call_tool":                     {"type": "static", "parameters": ["telegram_id", "server", "tool", "arguments"]},
        },
    },

    # ── cust_billing  :7861 ───────────────────────────────────────────────────
    "cust_billing": {
        "port": 7861,
        "database": "cust_billing_dbt",
        "description": "Customer billing, invoices, payments, recharge, offers, CDR",
        "primary_key": "account_no_masked",
        "tools": {
            "get_customer":                  {"type": "static",  "parameters": ["account_no_masked"]},
            "get_customer_count":            {"type": "static",  "parameters": ["account_type", "account_status", "collection_indicator"]},
            "get_customers":                 {"type": "static",  "parameters": ["account_type", "account_status", "collection_indicator", "limit"]},
            "get_customer_summary":          {"type": "static",  "parameters": ["account_no_masked"]},
            "get_collections":               {"type": "static",  "parameters": ["account_no_masked", "active_only"]},
            "get_collections_summary":       {"type": "static",  "parameters": []},
            "get_invoices":                  {"type": "static",  "parameters": ["account_no_masked", "unpaid_only", "limit"]},
            "get_revenue_summary":           {"type": "static",  "parameters": []},
            "get_revenue_trend":             {"type": "static",  "parameters": ["months"]},
            "get_postpaid_revenue_trend":    {"type": "static",  "parameters": ["months"]},
            "get_prepaid_revenue_trend":     {"type": "static",  "parameters": ["months"]},
            "get_arpu_by_segment":           {"type": "static",  "parameters": ["months"]},
            "get_revenue_by_account_type":   {"type": "static",  "parameters": []},
            "get_payments":                  {"type": "static",  "parameters": ["account_no_masked", "limit"]},
            "get_recharge":                  {"type": "static",  "parameters": ["account_no_masked", "subscriber_no_masked", "limit"]},
            "get_recharge_summary":          {"type": "static",  "parameters": []},
            "get_offer_charges":             {"type": "static",  "parameters": ["account_no_masked", "subscriber_no_masked", "active_only", "limit"]},
            "get_offer_charge_summary":      {"type": "static",  "parameters": []},
            "get_subscribers_per_offer":     {"type": "static",  "parameters": []},
            "get_cdr":                       {"type": "static",  "parameters": ["account_no_masked", "subscriber_no_masked", "limit"]},
            "get_cdr_summary":               {"type": "static",  "parameters": []},
            "diagnose_customer":             {"type": "static",  "parameters": ["account_no_masked"]},
            "get_customer_lifetime_value":   {"type": "static",  "parameters": ["account_no_masked"]},
            "get_payment_behavior":          {"type": "static",  "parameters": ["account_no_masked"]},
            "get_customer_revenue_trend":    {"type": "static",  "parameters": ["account_no_masked", "months"]},
            "get_dissatisfaction_signals":   {"type": "static",  "parameters": ["account_no_masked"]},
            "get_offer_subscriptions":       {"type": "static",  "parameters": ["account_no_masked"]},
            "get_cdr_usage_trend":           {"type": "static",  "parameters": ["account_no_masked", "subscriber_no_masked", "months"]},
            "get_revenue_by_product_trend":  {"type": "static",  "parameters": ["months"]},
            "execute_sql":                   {"type": "dynamic", "parameters": ["sql", "role"]},
        },
    },

    # ── main_db  :7862 ────────────────────────────────────────────────────────
    "main_db": {
        "port": 7862,
        "database": "main_dbt",
        "description": "Subscriber profiles, balances, activations, churn risk",
        "primary_key": "subscriber_no_masked",
        "tools": {
            "get_subscriber":                    {"type": "static",  "parameters": ["subscriber_no_masked"]},
            "get_subscriber_by_account":         {"type": "static",  "parameters": ["account_no_masked"]},
            "get_subscriber_by_external_no":     {"type": "static",  "parameters": ["external_no_masked"]},
            "get_subscribers":                   {"type": "static",  "parameters": ["payment_mode1", "current_state", "low_balance_threshold", "limit"]},
            "get_balance":                       {"type": "static",  "parameters": ["subscriber_no_masked"]},
            "get_balance_by_account":            {"type": "static",  "parameters": ["account_no_masked"]},
            "get_balance_summary":               {"type": "static",  "parameters": []},
            "get_low_balance_subscribers":       {"type": "static",  "parameters": ["threshold", "limit"]},
            "get_subscribers_by_offer":          {"type": "static",  "parameters": []},
            "get_subscriber_state_summary":      {"type": "static",  "parameters": []},
            "get_base_growth":                   {"type": "static",  "parameters": ["months"]},
            "get_reactivations":                 {"type": "static",  "parameters": ["months"]},
            "get_subscriber_activations_summary":{"type": "static",  "parameters": ["months"]},
            "get_churn_risk_subscribers":        {"type": "static",  "parameters": ["balance_threshold", "days_inactive_recharge", "limit"]},
            "diagnose_balance":                  {"type": "static",  "parameters": ["subscriber_no_masked"]},
            "execute_sql":                       {"type": "dynamic", "parameters": ["sql", "role"]},
        },
    },

    # ── ctlg_db  :7863 ────────────────────────────────────────────────────────
    "ctlg_db": {
        "port": 7863,
        "database": "ctlg_dbt",
        "description": "SIM inventory and provisioning status",
        "primary_key": "inventory_id",
        "tools": {
            "get_inventory_by_external_no":  {"type": "static",  "parameters": ["external_no_masked"]},
            "get_inventory_by_id":           {"type": "static",  "parameters": ["inventory_id", "inventory_id_resets"]},
            "get_inventory_summary":         {"type": "static",  "parameters": []},
            "get_inventory_status_catalog":  {"type": "static",  "parameters": []},
            "get_inventory":                 {"type": "static",  "parameters": ["state", "status_id", "external_id_type", "limit"]},
            "diagnose_inventory":            {"type": "static",  "parameters": ["external_no_masked"]},
            "execute_sql":                   {"type": "dynamic", "parameters": ["sql", "role"]},
        },
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# DERIVED LOOKUPS
# ══════════════════════════════════════════════════════════════════════════════

PORT_TO_SYSTEM: dict[int, str] = {
    defn["port"]: name
    for name, defn in SYSTEM_REGISTRY.items()
    if defn["port"] is not None
}

# Tools that are infrastructure — excluded from evaluation scoring
INFRASTRUCTURE_TOOLS: set[str] = set(
    SYSTEM_REGISTRY["auth_gateway"]["tools"].keys()
)


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE SCHEMA  (from SOUL.md table/column references)
# ══════════════════════════════════════════════════════════════════════════════

DB_SCHEMA: dict[str, set[str]] = {

    # cust_billing_dbt
    "MCP_CUSTOMER": {
        "ACCOUNT_NO_MASKED", "ACCOUNT_TYPE", "ACCOUNT_STATUS", "COLLECTION_INDICATOR",
    },
    "MCP_CUST_COLL": {
        "ACCOUNT_NO_MASKED", "ACTIVE_ONLY",
    },
    "MCP_INVOICES": {
        "ACCOUNT_NO_MASKED", "BALANCE_DUE", "ACCOUNT_TYPE",
    },
    "MCP_PAYMENT": {
        "ACCOUNT_NO_MASKED",
    },
    "MCP_RCHG": {
        "ACCOUNT_NO_MASKED", "SUBSCRIBER_NO_MASKED", "RECHARGE_DATE_TIME", "FACE_VALUE",
    },
    "MCP_OFFER_CHARGE": {
        "ACCOUNT_NO_MASKED", "SUBSCRIBER_NO_MASKED", "OFFER_NAME", "ACTIVE_ONLY",
    },
    "MCP_CDR_DETAILS": {
        "ACCOUNT_NO_MASKED", "SUBSCRIBER_NO_MASKED", "CALLTYPE", "RATED_UNITS", "CHARGED_AMOUNT",
    },

    # main_dbt
    "MCP_SUBSCRIBERS": {
        "ACCOUNT_NO_MASKED", "SUBSCRIBER_NO_MASKED", "EXTERNAL_NO_MASKED",
        "OFFER_VALUE", "LAST_TRANS_DATE", "CORE_BALANCE", "ACCT_EXPIRE_DATE",
        "CURRENT_STATE", "CREATION_DATE", "DATE_ENTER_ACTIVE", "PAYMENT_MODE1",
    },

    # ctlg_dbt
    "MCP_INVENTORY": {
        "INVENTORY_ID", "INVENTORY_ID_RESETS", "EXTERNAL_NO_MASKED", "STATUS_ID", "STATE",
    },
    "MCP_INVENTORY_STATUS": {
        "STATUS_ID", "DISPLAY_VALUE", "LANGUAGE_CODE",
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# ROLE -> execute_sql PERMISSIONS  (SOUL.md §Execute_SQL Rules)
# ══════════════════════════════════════════════════════════════════════════════

EXECUTE_SQL_PERMISSIONS: dict[str, set[str]] = {
    "admin":    {"cust_billing", "main_db", "ctlg_db"},
    "internal": {"cust_billing", "main_db", "ctlg_db"},
    "finance":  {"cust_billing", "main_db"},   # aggregate only, no ctlg_db
    "sales":    set(),
    "customer": set(),
}


# ══════════════════════════════════════════════════════════════════════════════
# REGISTRY HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def find_tool(tool_name: str) -> tuple[str | None, dict | None]:
    """Return (system_name, tool_def) for the first system that owns tool_name."""
    for sys_name, sys_def in SYSTEM_REGISTRY.items():
        if tool_name in sys_def["tools"]:
            return sys_name, sys_def["tools"][tool_name]
    return None, None


def tool_in_system(tool_name: str, system_name: str) -> bool:
    return tool_name in SYSTEM_REGISTRY.get(system_name, {}).get("tools", {})


def all_registered_tools() -> set[str]:
    names: set[str] = set()
    for sys_def in SYSTEM_REGISTRY.values():
        names |= set(sys_def["tools"].keys())
    return names


def system_of_port(port: int) -> str:
    return PORT_TO_SYSTEM.get(port, "unknown_system")
