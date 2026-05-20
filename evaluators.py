"""
Evaluators
===========
All layer evaluators for both static and dynamic episodes.

Each evaluator takes the relevant data + a mutable `notes` list,
appends human-readable notes, and returns a numeric score.

Score ranges per spec
---------------------
Tool correctness   : −1 … +1
Param correctness  : −1 … +1   (formula: (correct − hallucinated) / total_expected)
Sequence score     : −0.5 … +1
Context score      :  0 … +1
Fallback score     :  0 … +1   (optional)
Exec success       :  0 … +1
Table/column score : −1 … +1
Schema rel score   :  0 … +1
Semantic score     :  0 … +1
Retry success      :  0 … +1
Task completion    :  0 … +1
"""

from __future__ import annotations

import math
import re
from collections import Counter

from registry import DB_SCHEMA, find_tool, tool_in_system
from models import TraceEntry, Episode, Layer1Scores
from sql_utils import parse_sql


# ══════════════════════════════════════════════════════════════════════════════
# SIMILARITY HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _cosine(a: list[str], b: list[str]) -> float:
    vocab = set(a) | set(b)
    if not vocab:
        return 1.0
    va = {w: a.count(w) for w in vocab}
    vb = {w: b.count(w) for w in vocab}
    dot  = sum(va[w] * vb[w] for w in vocab)
    maga = math.sqrt(sum(v ** 2 for v in va.values()))
    magb = math.sqrt(sum(v ** 2 for v in vb.values()))
    return 0.0 if (maga == 0 or magb == 0) else dot / (maga * magb)


def _overlap(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / min(len(sa), len(sb))


# ══════════════════════════════════════════════════════════════════════════════
# STATIC  —  LAYER 1 EVALUATORS
# ══════════════════════════════════════════════════════════════════════════════

def eval_tool_correctness(
    first: TraceEntry,
    bench: dict,
    notes: list[str],
) -> tuple[float, str]:
    """
    4-level hierarchical tool correctness (§8.2).

    Returns (score, classification_label).

    Levels
    ------
    1. Correct tool                → +1
    2. Incorrect tool, same system →  0
    3. Cross-system correct tool   → −0.5
    4. Hallucinated tool           → −1
    """
    tool         = first.tool
    expected     = bench["expected_tools"]
    bench_system = bench["target_system"]

    # Level 1 — correct
    if tool in expected:
        notes.append(f"  ✔ Tool '{tool}' → CORRECT (system: {first.target_system}). Score: +1")
        return 1.0, "correct"

    # Level 2 — wrong tool but same system
    if tool_in_system(tool, bench_system):
        notes.append(
            f"  ✘ Tool '{tool}' exists in '{bench_system}' but is the wrong tool "
            f"(expected {expected}). Score: 0"
        )
        return 0.0, "incorrect"

    # Level 3 — valid tool from another system
    owner_sys, _ = find_tool(tool)
    if owner_sys is not None:
        notes.append(
            f"  ✘ Tool '{tool}' is valid but belongs to '{owner_sys}', "
            f"not target '{bench_system}'. Cross-system routing error. Score: −0.5"
        )
        return -0.5, "cross-system"

    # Level 4 — hallucinated
    notes.append(
        f"  ✘ Tool '{tool}' not found in any registered system. "
        f"HALLUCINATED. Score: −1"
    )
    return -1.0, "hallucinated"


def eval_param_correctness(
    first: TraceEntry,
    bench: dict,
    notes: list[str],
) -> tuple[float, dict]:
    """
    Parameter correctness per spec §8.3.

    Formula  (§8.3 Parameter Accuracy Formula):
        score = (correct_count − hallucinated_count) / total_expected_params

    Returns (score, breakdown_dict).
    """
    _, tool_def   = find_tool(first.tool)
    schema_params = set(tool_def["parameters"]) if tool_def else set()
    expected_vals = bench.get("expected_params", {})   # {name: value}

    breakdown: dict[str, str] = {}

    if not expected_vals and not schema_params:
        notes.append("  ℹ No parameter benchmark or schema defined. Score: 1.0 (N/A)")
        return 1.0, {}

    total_expected    = max(len(expected_vals), 1)
    correct_count     = 0
    hallucinated_count = 0

    # ── Evaluate expected parameters ─────────────────────────────────────────
    for k, exp_v in expected_vals.items():
        actual_v = first.parameters.get(k)
        if actual_v is None:
            breakdown[k] = "missing"
            notes.append(f"    Param '{k}': MISSING (+0)")
        elif str(actual_v).lower() == str(exp_v).lower():
            breakdown[k] = "correct"
            correct_count += 1
            notes.append(f"    Param '{k}': CORRECT ('{actual_v}') (+1)")
        else:
            breakdown[k] = "incorrect"
            notes.append(
                f"    Param '{k}': INCORRECT "
                f"(got '{actual_v}', expected '{exp_v}') (+0)"
            )

    # ── Check for hallucinated params (not in tool schema) ───────────────────
    for k in first.parameters:
        if schema_params and k not in schema_params:
            breakdown[k] = "hallucinated"
            hallucinated_count += 1
            notes.append(f"    Param '{k}': HALLUCINATED (not in schema) (−1)")

    # ── Apply spec formula ────────────────────────────────────────────────────
    raw_score = (correct_count - hallucinated_count) / total_expected
    score     = round(max(-1.0, min(1.0, raw_score)), 3)
    notes.append(
        f"    Formula: ({correct_count} − {hallucinated_count}) / {total_expected} = {score}"
    )
    return score, breakdown


def eval_sequence(
    episode: Episode,
    bench: dict,
    notes: list[str],
) -> float:
    """
    Orchestration sequence quality (§8.4, §8.5).

    Score = (cosine × 0.5 + overlap × 0.5) × redundancy_multiplier
    Redundancy multiplier: 1.0 (none) or 0.5 (redundant, i.e. a tool called ≥3×)
    """
    generated = [t.tool for t in episode.attempts]
    expected  = bench["expected_sequence"]

    cosine_s  = round(_cosine(generated, expected), 3)
    overlap_s = round(_overlap(generated, expected), 3)

    # Redundancy: any single tool appears 3+ times (2 is acceptable for retry)
    counts    = Counter(generated)
    redundant = any(v >= 3 for v in counts.values())
    multiplier = 0.5 if redundant else 1.0

    seq = round((cosine_s * 0.5 + overlap_s * 0.5) * multiplier, 3)

    notes.append(f"    Generated : {generated}")
    notes.append(f"    Expected  : {expected}")
    notes.append(f"    Cosine    : {cosine_s}   Overlap : {overlap_s}")
    notes.append(
        f"    Redundancy: {'YES — penalty ×0.5' if redundant else 'none'}"
        f"   Sequence score: {seq}"
    )
    return seq


def eval_context(episode: Episode, notes: list[str]) -> float:
    """
    Conversational context retention (§8.6).

    Checks whether entity-identifying parameters (e.g. account_no_masked)
    are consistently propagated across multi-call episodes.
    Returns +1 if reused, 0 if not, 1.0 if single-call (N/A).
    """
    param_sets = [t.parameters for t in episode.attempts if t.parameters]
    if len(param_sets) < 2:
        notes.append("    Single-call episode — context check N/A. Score: 1.0")
        return 1.0

    anchor_keys = set(param_sets[0].keys())
    reused      = any(anchor_keys & set(p.keys()) for p in param_sets[1:])

    if reused:
        notes.append("    ✔ Context: entity parameters propagated across calls. Score: +1")
        return 1.0
    notes.append("    ✘ Context: no shared parameters detected across calls. Score: 0")
    return 0.0


def eval_fallback(episode: Episode, notes: list[str]) -> float:
    """
    Optional fallback reasoning (§8.7).

    Detects whether the agent used alternative strategies when primary tools failed.
    Heuristic: if all tool calls failed but final episode ended with a non-error assistant
    response, the agent attempted a fallback.
    Returns +1 (success), 0 (failure / not triggered), or -1 (not applicable).
    """
    if not episode.attempts:
        return -1.0   # not applicable

    all_failed = all(t.status == "failure" for t in episode.attempts)
    if not all_failed:
        notes.append("    Fallback: not triggered (at least one tool succeeded). N/A")
        return -1.0   # flag as not applicable

    # If all failed but we still got a final_status of "success" somehow
    # (edge case: agent answered from knowledge), that's a successful fallback.
    if episode.final_status == "success":
        notes.append("    ✔ Fallback: agent succeeded despite all tool failures. Score: +1")
        return 1.0

    notes.append("    ✘ Fallback: all tools failed and no recovery detected. Score: 0")
    return 0.0


# ══════════════════════════════════════════════════════════════════════════════
# DYNAMIC  —  LAYER 1 EVALUATORS
# ══════════════════════════════════════════════════════════════════════════════

def eval_exec_success(first: TraceEntry, notes: list[str]) -> float:
    """SQL execution success on first attempt (§9.2)."""
    if first.status == "success":
        notes.append("    ✔ Execution: SUCCESS. Score: +1")
        return 1.0
    excerpt = first.raw_result[:120].replace("\n", " ")
    notes.append(f"    ✘ Execution: FAILED — {excerpt}. Score: 0")
    return 0.0


def eval_table_existence(sql: str, bench: dict, notes: list[str]) -> float:
    """
    Table existence grounding (§9.3).
    Valid tables: those in DB_SCHEMA or the benchmark's known_tables.
    Score averaged per table: +1 valid, −1 hallucinated.
    """
    comps = parse_sql(sql)
    known = set(DB_SCHEMA.keys()) | {t.upper() for t in bench.get("known_tables", set())}

    if not comps["tables"]:
        notes.append("    ℹ Table check: no tables detected in SQL.")
        return 0.0

    per_table: list[float] = []
    for t in comps["tables"]:
        if known and t not in known:
            notes.append(f"    Table '{t}': HALLUCINATED. (−1)")
            per_table.append(-1.0)
        else:
            notes.append(f"    Table '{t}': VALID. (+1)")
            per_table.append(1.0)

    return round(max(-1.0, min(1.0, sum(per_table) / len(per_table))), 3)


def eval_column_existence(sql: str, bench: dict, notes: list[str]) -> float:
    """
    Column existence grounding (§9.4).
    Valid columns: those in DB_SCHEMA or the benchmark's known_columns.
    Score averaged per scoreable column: +1 valid, −1 hallucinated.
    """
    comps = parse_sql(sql)
    known: set[str] = set()
    for cols in DB_SCHEMA.values():
        known |= cols
    known |= {c.upper() for c in bench.get("known_columns", set())}

    scoreable = [c for c in comps["columns"] if c not in ("*", "1", "COUNT")]
    if not scoreable:
        notes.append("    ℹ Column check: no scoreable columns parsed.")
        return 1.0

    per_col: list[float] = []
    for c in scoreable:
        if known and c not in known:
            notes.append(f"    Column '{c}': HALLUCINATED. (−1)")
            per_col.append(-1.0)
        else:
            notes.append(f"    Column '{c}': VALID. (+1)")
            per_col.append(1.0)

    return round(max(-1.0, min(1.0, sum(per_col) / len(per_col))), 3)


def eval_schema_relationship(sql: str, bench: dict, notes: list[str]) -> float:
    """
    Schema relationship validation (§9.5).
    Checks that referenced columns actually belong to referenced tables.
    Returns +1 if correct, 0 if violated.
    """
    comps = parse_sql(sql)
    if not comps["tables"] or not comps["columns"]:
        notes.append("    ℹ Schema relationship: insufficient SQL components to check.")
        return 1.0

    violations: list[str] = []
    for table in comps["tables"]:
        table_cols = DB_SCHEMA.get(table, set())
        if not table_cols:
            continue   # table not in local schema — skip
        bad = [
            c for c in comps["columns"]
            if c not in table_cols and c not in ("*", "1", "COUNT")
        ]
        violations.extend(bad)

    if violations:
        notes.append(
            f"    ✘ Schema relationship violated — "
            f"columns not in table: {violations}. Score: 0"
        )
        return 0.0

    notes.append("    ✔ Schema relationships valid. Score: +1")
    return 1.0


def eval_semantic_sql(sql: str, bench: dict, notes: list[str]) -> float:
    """
    Semantic SQL correctness (§9.6).
    Evaluates analytical intent, not schema grounding.

    Scoring:
        all intent components matched    → +1
        ≥ 50% matched                   → +0.5
        < 50% matched                   → 0
    """
    intent = bench.get("intent")
    if not intent:
        notes.append("    ℹ Semantic check: no intent benchmark defined. Score: 1.0")
        return 1.0

    comps   = parse_sql(sql)
    checks  = [
        ("aggregation",  intent.get("aggregation"),
         lambda v: v.upper() in sql.upper()),
        ("GROUP BY",     intent.get("group_by"),
         lambda v: comps["has_group_by"] == v),
        ("WHERE filter", intent.get("filtering"),
         lambda v: comps["has_where"] == v),
        ("target table", intent.get("table"),
         lambda v: v.upper() in comps["tables"]),
    ]

    hits  = 0
    total = 0
    for label, expected_val, check_fn in checks:
        if expected_val is None:
            continue
        total += 1
        if check_fn(expected_val):
            hits += 1
            notes.append(f"    Semantic '{label}': ✔ matched. (+1)")
        else:
            notes.append(f"    Semantic '{label}': ✘ not matched. (+0)")

    if total == 0:
        return 1.0

    ratio = hits / total
    score = 1.0 if ratio == 1.0 else (0.5 if ratio >= 0.5 else 0.0)
    notes.append(f"    Semantic: {hits}/{total} matched → score {score}")
    return score


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 2  —  RETRY / RECOVERY EVALUATOR
# ══════════════════════════════════════════════════════════════════════════════

def eval_retry(episode: Episode, notes: list[str]) -> tuple[int, float]:
    """
    Recovery effort evaluation (§8.8 / §9.7).

    retry_count = total_attempts − 1

    Returns (retry_count, retry_success_score):
        retry_success = 1.0 if any subsequent attempt succeeded
        retry_success = 0.0 if no retries, or all retries failed
    """
    retry_count = max(0, len(episode.attempts) - 1)

    if retry_count == 0:
        notes.append("    No retries — first-call success.")
        return 0, 0.0

    notes.append(f"    Retry count: {retry_count}")

    for idx, attempt in enumerate(episode.attempts[1:], start=2):
        if attempt.status == "success":
            notes.append(f"    ✔ Recovery: succeeded on attempt #{idx}. Score: +1")
            return retry_count, 1.0

    notes.append("    ✘ Recovery: all retries failed. Score: 0")
    return retry_count, 0.0


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 3  —  TASK COMPLETION EVALUATOR
# ══════════════════════════════════════════════════════════════════════════════

def eval_task_completion(
    episode: Episode,
    final_semantic_score: float,
    notes: list[str],
) -> float:
    """
    Task completion evaluation.

    Static  (§8.9):  final_status == "success"  → 1.0
    Dynamic (§9.8):  final_status == "success"
                     AND final_semantic_score == 1.0  → 1.0

    In both cases anything else → 0.0.
    """
    final_ok = episode.final_status == "success"

    if episode.tool_type == "static":
        if final_ok:
            notes.append("    ✔ Task completed successfully. Score: +1")
            return 1.0
        notes.append("    ✘ Task failed — final tool call unsuccessful. Score: 0")
        return 0.0

    # Dynamic path
    if final_ok and final_semantic_score == 1.0:
        notes.append(
            "    ✔ Task completed: SQL executed AND semantic intent satisfied. Score: +1"
        )
        return 1.0

    if final_ok and final_semantic_score < 1.0:
        notes.append(
            f"    ⚠ Task partial: SQL executed but "
            f"semantic score = {final_semantic_score} < 1.0. Score: 0"
        )
        return 0.0

    notes.append("    ✘ Task failed: final SQL execution unsuccessful. Score: 0")
    return 0.0
