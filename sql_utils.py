"""
SQL Parsing Utilities
======================
Extracts structural components from SQL strings using sqlparse (§10).

Extracted components used across dynamic evaluators:
  tables        → schema grounding (table existence, schema relationship)
  columns       → schema grounding (column existence, schema relationship)
  aggregations  → semantic correctness (SUM / COUNT / AVG / MAX / MIN)
  has_group_by  → semantic correctness
  has_where     → semantic correctness
"""

from __future__ import annotations

import re

import sqlparse
from sqlparse.sql import Identifier, IdentifierList


def parse_sql(sql: str) -> dict:
    """
    Parse a SQL string and return a dict with:
      tables        : list[str]   (UPPER-cased)
      columns       : list[str]   (UPPER-cased, deduplicated)
      aggregations  : list[str]   (function names, UPPER-cased)
      has_group_by  : bool
      has_where     : bool
    """
    tables:       list[str] = []
    columns:      list[str] = []
    aggregations: list[str] = []
    has_group_by             = False
    has_where                = False

    for stmt in sqlparse.parse(sql):
        flat_upper = " ".join(t.value.upper() for t in stmt.flatten())
        has_group_by = has_group_by or "GROUP BY" in flat_upper
        has_where    = has_where    or "WHERE"    in flat_upper

        # ── aggregation functions ─────────────────────────────────────────────
        for m in re.finditer(r"\b(SUM|COUNT|AVG|MAX|MIN)\s*\(", sql, re.IGNORECASE):
            agg = m.group(1).upper()
            if agg not in aggregations:
                aggregations.append(agg)

        # ── table names (after FROM / JOIN keywords) ──────────────────────────
        from_active = False
        for tok in stmt.tokens:
            tv = tok.ttype
            ts = tok.value.upper().strip()

            if tv is not None:
                if ts in ("FROM", "JOIN", "INNER JOIN", "LEFT JOIN", "RIGHT JOIN",
                          "CROSS JOIN", "FULL JOIN"):
                    from_active = True
                elif ts in ("WHERE", "SET", "GROUP", "ORDER", "HAVING",
                            "LIMIT", "SELECT", "WITH"):
                    from_active = False
                continue

            if from_active:
                if isinstance(tok, Identifier):
                    name = tok.get_real_name()
                    if name:
                        tables.append(name.upper())
                elif isinstance(tok, IdentifierList):
                    for ident in tok.get_identifiers():
                        if isinstance(ident, Identifier):
                            name = ident.get_real_name()
                            if name:
                                tables.append(name.upper())
                from_active = False

        # ── column names (from SELECT … FROM clause) ──────────────────────────
        sel_m = re.search(r"SELECT\s+(.*?)\s+FROM", sql, re.IGNORECASE | re.DOTALL)
        if sel_m:
            raw = sel_m.group(1)
            for part in raw.split(","):
                part  = part.strip()
                inner = re.sub(r"\w+\s*\(([^)]+)\)", r"\1", part)
                for col in inner.split(","):
                    col = re.sub(r".*\.", "", col.strip())
                    col = col.split()[0].strip().upper()
                    if col and col not in ("*", "AS", "DISTINCT") and col not in columns:
                        columns.append(col)

    # Deduplicate tables preserving order
    seen:   set[str] = set()
    unique_tables:   list[str] = []
    for t in tables:
        if t not in seen:
            seen.add(t)
            unique_tables.append(t)

    return {
        "tables":       unique_tables,
        "columns":      columns,
        "aggregations": aggregations,
        "has_group_by": has_group_by,
        "has_where":    has_where,
    }
