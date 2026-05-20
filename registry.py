"""
Enterprise MCP Tool & System Registry
======================================
Single source of truth for:
  - system definitions  (name, port, description)
  - tool definitions    (type, schema parameters)
  - known DB schema     (tables → columns)
  - port → system name  lookup

Extend SYSTEM_REGISTRY and DB_SCHEMA when onboarding new enterprise systems.
"""

from __future__ import annotations


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM & TOOL REGISTRY
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_REGISTRY: dict[str, dict] = {

    "cust_billing": {
        "port": 7861,
        "description": "Customer billing, subscription, and offer management",
        "tools": {
            "get_customer": {
                "type": "static",
                "parameters": ["account_no_masked"],
                "description": "Retrieve full customer profile by masked account number",
            },
            "get_subscribers_per_offer": {
                "type": "static",
                "parameters": [],
                "description": "Return subscriber counts grouped by offer/product",
            },
            "get_revenue_by_product_trend": {
                "type": "static",
                "parameters": ["months"],
                "description": "Return monthly revenue trend per product over N months",
            },
            "diagnose_customer": {
                "type": "static",
                "parameters": ["account_no_masked"],
                "description": "Run automated diagnostic checks on a customer account",
            },
        },
    },

    "analytics_db": {
        "port": 7862,
        "description": "Enterprise analytics SQL execution layer (SELECT / WITH only)",
        "tools": {
            "execute_sql": {
                "type": "dynamic",
                "parameters": ["role", "sql"],
                "description": "Execute a parameterised SELECT/WITH query against the analytics DB",
            },
        },
    },

    "auth_gateway": {
        "port": None,
        "description": "Authentication and RBAC — infrastructure layer, excluded from scoring",
        "tools": {
            "check_access": {
                "type": "static",
                "parameters": ["telegram_id"],
                "description": "Verify caller identity and resolve enterprise role",
            },
        },
    },
}


# ── Derived lookup structures ──────────────────────────────────────────────────

PORT_TO_SYSTEM: dict[int, str] = {
    defn["port"]: name
    for name, defn in SYSTEM_REGISTRY.items()
    if defn["port"] is not None
}

# Tools excluded from evaluation scoring (infrastructure)
INFRASTRUCTURE_TOOLS: set[str] = {"check_access"}


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE SCHEMA
# Derived from live log probe: SELECT * FROM MCP_SUBSCRIBERS LIMIT 1
# table_name (UPPER) → set of column_names (UPPER)
# ══════════════════════════════════════════════════════════════════════════════

DB_SCHEMA: dict[str, set[str]] = {
    "MCP_SUBSCRIBERS": {
        "ACCOUNT_NO_MASKED",
        "SUBSCRIBER_NO_MASKED",
        "EXTERNAL_NO_MASKED",
        "OFFER_VALUE",
        "LAST_TRANS_DATE",
        "CORE_BALANCE",
        "ACCT_EXPIRE_DATE",
        "CURRENT_STATE",
        "CREATION_DATE",
        "DATE_ENTER_ACTIVE",    # confirmed by successful query
        "PAYMENT_MODE1",
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# REGISTRY HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def find_tool(tool_name: str) -> tuple[str | None, dict | None]:
    """Return (system_name, tool_def) for the system that owns tool_name."""
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
