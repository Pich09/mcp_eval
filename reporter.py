"""
Report Generator
=================
Produces three output sections per spec §11:

  1. Per-query evaluation      individual orchestration analysis
  2. Cumulative scores         aggregate evaluation metrics
  3. Retry statistics          orchestration recovery analysis
  4. Failure / weakness analysis
  5. Model comparison report   comparative LLM evaluation (multi-run)
"""

from __future__ import annotations

import textwrap
from models import EpisodeResult


# ── Layout constants ───────────────────────────────────────────────────────────
W         = 84
DOUBLE    = "═" * W
SINGLE    = "─" * W
THICK     = "━" * W


def _bar(score: float, width: int = 24) -> str:
    """
    Render a score in [−1 … +1] as a filled block bar.
    Centre point (score = 0) ≈ half-filled.
    """
    norm   = max(0.0, min(1.0, (score + 1.0) / 2.0))
    filled = round(norm * width)
    return "█" * filled + "░" * (width - filled)


def _section_header(title: str) -> str:
    return f"\n  {THICK}\n  {title}\n  {THICK}"


# ══════════════════════════════════════════════════════════════════════════════
# PER-QUERY REPORT
# ══════════════════════════════════════════════════════════════════════════════

def _format_episode(idx: int, r: EpisodeResult) -> list[str]:
    lines: list[str] = []

    # Episode header
    q_short = textwrap.shorten(r.query, W - 18)
    lines += [
        "",
        f"  ╔{'═' * (W - 4)}╗",
        f"  ║  Episode {idx}  │  {r.tool_type.upper()}  │  system: {r.target_system}".ljust(W - 1) + "║",
        f"  ║  Query: {q_short}".ljust(W - 1) + "║",
        f"  ╚{'═' * (W - 4)}╝",
    ]

    # ── Layer 1 ───────────────────────────────────────────────────────────────
    lines.append(_section_header("LAYER 1 — Initial Orchestration Quality (first call only)"))

    if r.tool_type == "dynamic":
        rows = [
            ("Tool correctness",       r.layer1.tool_correctness,
             f"[{r.layer1.tool_classification}]"),
            ("SQL execution success",  r.layer1.exec_success,      ""),
            ("Table existence",        r.layer1.table_score,       ""),
            ("Column existence",       r.layer1.column_score,      ""),
            ("Schema relationship",    r.layer1.schema_rel_score,  ""),
            ("Semantic SQL quality",   r.layer1.semantic_score,    ""),
        ]
    else:
        rows = [
            ("Tool correctness",       r.layer1.tool_correctness,
             f"[{r.layer1.tool_classification}]"),
            ("Parameter correctness",  r.layer1.param_correctness, ""),
            ("Sequence quality",       r.layer1.sequence_score,    ""),
            ("Context retention",      r.layer1.context_score,     ""),
        ]
        if r.layer1.fallback_score >= 0.0:
            rows.append(
                ("Fallback reasoning",  r.layer1.fallback_score,   "[optional]")
            )

    for label, score, annot in rows:
        bar  = _bar(score)
        sstr = f"{score:+.3f}"
        lines.append(f"    {label:<28} {sstr}   [{bar}]  {annot}")

    lines.append(
        f"    {'─' * 60}"
    )
    lines.append(
        f"    {'Layer 1 total':<28} {r.layer1.total:+.3f}   [{_bar(r.layer1.total)}]"
    )

    # ── Layer 2 ───────────────────────────────────────────────────────────────
    lines.append(_section_header("LAYER 2 — Recovery Effort"))

    if r.retry_count == 0:
        retry_line = "No retries — first-call success (ideal)"
    elif r.retry_success == 1.0:
        retry_line = f"{r.retry_count} retries → ✔ recovered"
    else:
        retry_line = f"{r.retry_count} retries → ✘ failed to recover"

    lines.append(f"    Retry count    : {r.retry_count}")
    lines.append(f"    Recovery       : {retry_line}  ({r.retry_success:+.3f})")
    if r.retry_count >= 3:
        lines.append(
            f"    ⚠  {r.retry_count} retries indicate unstable orchestration."
        )

    # ── Layer 3 ───────────────────────────────────────────────────────────────
    lines.append(_section_header("LAYER 3 — Task Completion"))
    comp_label = "✔ completed" if r.task_completion == 1.0 else "✘ failed / partial"
    lines.append(f"    Final outcome  : {comp_label}  ({r.task_completion:+.3f})")

    # ── Total ─────────────────────────────────────────────────────────────────
    lines += [
        "",
        f"    {'TOTAL SCORE':<28} {r.total_score:+.3f}   [{_bar(r.total_score)}]",
        f"    Weights: Layer 1 × 50%   Layer 2 × 20%   Layer 3 × 30%",
    ]

    # ── Evaluation notes ──────────────────────────────────────────────────────
    lines.append(_section_header("Evaluation Notes"))
    for note in r.notes:
        lines.append(f"    {note}")

    lines += ["", DOUBLE]
    return lines


# ══════════════════════════════════════════════════════════════════════════════
# CUMULATIVE SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

def _format_cumulative(results: list[EpisodeResult]) -> list[str]:
    lines: list[str] = []
    n = len(results)
    if n == 0:
        return ["  No results to summarise."]

    static_ep   = [r for r in results if r.tool_type == "static"]
    dynamic_ep  = [r for r in results if r.tool_type == "dynamic"]

    avg = lambda seq: sum(seq) / len(seq) if seq else 0.0

    avg_l1    = avg([r.layer1.total       for r in results])
    avg_l2    = avg([r.retry_success      for r in results])
    avg_l3    = avg([r.task_completion    for r in results])
    avg_total = avg([r.total_score        for r in results])
    total_retries = sum(r.retry_count for r in results)
    perfect   = sum(1 for r in results if r.total_score >= 0.99)

    lines += [
        "",
        "  CUMULATIVE SUMMARY".center(W),
        SINGLE,
        f"  Episodes evaluated        : {n}",
        f"  Static episodes           : {len(static_ep)}",
        f"  Dynamic episodes          : {len(dynamic_ep)}",
        f"  Perfect scores (≥ 0.99)   : {perfect}/{n}",
        f"  Total retries observed    : {total_retries}",
        "",
        f"  Avg Layer 1 (init. orch.) : {avg_l1:+.3f}   [{_bar(avg_l1)}]",
        f"  Avg Layer 2 (recovery)    : {avg_l2:+.3f}   [{_bar(avg_l2)}]",
        f"  Avg Layer 3 (completion)  : {avg_l3:+.3f}   [{_bar(avg_l3)}]",
        f"  Avg OVERALL score         : {avg_total:+.3f}   [{_bar(avg_total)}]",
    ]
    return lines


# ══════════════════════════════════════════════════════════════════════════════
# RETRY STATISTICS
# ══════════════════════════════════════════════════════════════════════════════

def _format_retry_stats(results: list[EpisodeResult]) -> list[str]:
    lines: list[str] = [
        "",
        "  RETRY STATISTICS".center(W),
        SINGLE,
    ]
    for r in results:
        q = textwrap.shorten(r.query, 50)
        if r.retry_count == 0:
            status = "✔ first-call success"
        elif r.retry_success == 1.0:
            status = f"✔ recovered after {r.retry_count} retries"
        else:
            status = f"✘ {r.retry_count} retries, all failed"

        stability = ""
        if r.retry_count >= 3:
            stability = "  ⚠ UNSTABLE"

        lines.append(f"  {q:<52} {status}{stability}")
    return lines


# ══════════════════════════════════════════════════════════════════════════════
# FAILURE & WEAKNESS ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

_WEAKNESS_THRESHOLDS = {
    "Tool routing errors":           lambda r: r.layer1.tool_classification
                                                in ("hallucinated", "cross-system", "incorrect"),
    "Parameter grounding failures":  lambda r: r.layer1.param_correctness < 0.5
                                                and r.tool_type == "static",
    "Sequence / workflow errors":    lambda r: 0.0 <= r.layer1.sequence_score < 0.7,
    "High retry instability (≥3)":   lambda r: r.retry_count >= 3,
    "Schema hallucinations (SQL)":   lambda r: r.layer1.table_score < 0
                                                or r.layer1.column_score < 0,
    "Semantic SQL failures":         lambda r: r.tool_type == "dynamic" and 0.0 <= r.layer1.semantic_score < 0.5,
    "Task completion failures":      lambda r: r.task_completion == 0.0,
}


def _format_failure_analysis(results: list[EpisodeResult]) -> list[str]:
    lines: list[str] = [
        "",
        "  FAILURE & WEAKNESS ANALYSIS".center(W),
        SINGLE,
    ]

    weakness_map: dict[str, list[str]] = {}
    for r in results:
        q = textwrap.shorten(r.query, 48)
        for dim, condition in _WEAKNESS_THRESHOLDS.items():
            try:
                if condition(r):
                    detail = ""
                    if "retry" in dim.lower():
                        detail = f" [{r.retry_count} retries]"
                    elif "tool" in dim.lower():
                        detail = f" [{r.layer1.tool_classification}]"
                    weakness_map.setdefault(dim, []).append(f"'{q}'{detail}")
            except Exception:
                pass

    if weakness_map:
        for dim, cases in weakness_map.items():
            lines.append(f"  ▸ {dim}:")
            for c in cases:
                lines.append(f"      — {c}")
    else:
        lines.append(
            "  ✔ No significant weaknesses detected across evaluated episodes."
        )

    return lines


# ══════════════════════════════════════════════════════════════════════════════
# MODEL COMPARISON REPORT (§11)
# ══════════════════════════════════════════════════════════════════════════════

def _format_model_comparison(
    runs: dict[str, list[EpisodeResult]],
) -> list[str]:
    """
    Format a comparative table across multiple model runs.
    `runs` maps model_name → list[EpisodeResult] for the same query set.
    """
    if not runs:
        return []

    lines: list[str] = [
        "",
        "  MODEL COMPARISON REPORT".center(W),
        SINGLE,
        f"  {'Model':<25} {'Avg L1':>8} {'Avg L2':>8} {'Avg L3':>8} "
        f"{'Retries':>8} {'Total':>8}",
        f"  {'─' * 25} {'─' * 8} {'─' * 8} {'─' * 8} {'─' * 8} {'─' * 8}",
    ]

    avg = lambda seq: sum(seq) / len(seq) if seq else 0.0

    ranked: list[tuple[str, float]] = []
    for model_name, results in runs.items():
        n = len(results)
        if n == 0:
            continue
        al1      = avg([r.layer1.total    for r in results])
        al2      = avg([r.retry_success   for r in results])
        al3      = avg([r.task_completion for r in results])
        tot_ret  = sum(r.retry_count      for r in results)
        avg_tot  = avg([r.total_score     for r in results])

        lines.append(
            f"  {model_name:<25} {al1:>+8.3f} {al2:>+8.3f} {al3:>+8.3f} "
            f"{tot_ret:>8} {avg_tot:>+8.3f}"
        )
        ranked.append((model_name, avg_tot))

    if ranked:
        best = max(ranked, key=lambda x: x[1])
        lines += [
            "",
            f"  Best overall: {best[0]}  (avg score {best[1]:+.3f})",
        ]

    return lines


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

def generate_report(
    results: list[EpisodeResult],
    model_runs: dict[str, list[EpisodeResult]] | None = None,
) -> str:
    """
    Generate the full evaluation report.

    Parameters
    ----------
    results     : evaluation results for the primary (or only) model run
    model_runs  : optional dict of {model_name → results} for comparison table.
                  If supplied, results should also appear under its model name here.
    """
    lines: list[str] = [
        DOUBLE,
        "  ENTERPRISE MCP ORCHESTRATION EVALUATION REPORT".center(W),
        "  OpenClaw  ·  Multi-System Enterprise  ·  3-Layer Framework".center(W),
        DOUBLE,
    ]

    # Per-query episodes
    for idx, r in enumerate(results, 1):
        lines.extend(_format_episode(idx, r))

    # Cumulative summary
    lines.extend(_format_cumulative(results))

    # Retry statistics
    lines.extend(_format_retry_stats(results))

    # Failure analysis
    lines.extend(_format_failure_analysis(results))

    # Model comparison (only if multi-model data provided)
    if model_runs:
        lines.extend(_format_model_comparison(model_runs))

    lines += ["", DOUBLE]
    return "\n".join(lines)
