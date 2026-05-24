"""
Score Aggregator
=================
Orchestrates all layer evaluators into a single EpisodeResult.

Layer weights (applied to total score):
  Layer 1 — 50%   initial orchestration quality
  Layer 2 — 20%   recovery effort
  Layer 3 — 30%   final task completion

Layer-2 contribution logic:
  - If no retries (first-call success): full credit (1.0) — ideal outcome
  - If retries occurred and recovery succeeded: 1.0
  - If retries occurred but recovery failed: 0.0
"""

from __future__ import annotations

from benchmarks import match_benchmark
from evaluators import (
    eval_tool_correctness,
    eval_param_correctness,
    eval_sequence,
    eval_context,
    eval_fallback,
    eval_exec_success,
    eval_table_existence,
    eval_column_existence,
    eval_schema_relationship,
    eval_semantic_sql,
    eval_retry,
    eval_task_completion,
)
from models import Episode, EpisodeResult, Layer1Scores


# ── Layer weights ──────────────────────────────────────────────────────────────
W_LAYER1 = 0.50
W_LAYER2 = 0.20
W_LAYER3 = 0.30


def evaluate_episode(episode: Episode) -> EpisodeResult:
    """
    Run the full 3-layer evaluation for a single Episode.
    Returns an EpisodeResult with all scores and evaluation notes.
    """
    result = EpisodeResult(
        session_id    = episode.session_id,
        query         = episode.query,
        tool_type     = episode.tool_type,
        target_system = episode.target_system,
    )
    notes = result.notes
    bench = match_benchmark(episode.query)

    if not episode.attempts:
        notes.append("⚠ No tool calls found for this episode.")
        return result

    first = episode.attempts[0]

    # ══════════════════════════════════════════════════════════════════════════
    # LAYER 1 — Initial Orchestration Quality
    # ══════════════════════════════════════════════════════════════════════════
    notes.append("═══ LAYER 1 — Initial Orchestration Quality (first call only) ═══")

    l1_component_scores: list[float] = []
    final_semantic_score = 0.0        # used by dynamic Layer 3

    # ── Dynamic path ──────────────────────────────────────────────────────────
    if episode.tool_type == "dynamic":

        notes.append(f"  Tool selected: '{first.tool}'  (dynamic path)")

        # Tool correctness — pass system_hint so execute_sql routes correctly
        if bench:
            tc, tc_label = eval_tool_correctness(first, bench, notes)
        else:
            notes.append("  ⚠ No benchmark matched. Tool correctness set to 0.5 (heuristic).")
            tc, tc_label = 0.5, "unknown"

        result.layer1.tool_correctness    = tc
        result.layer1.tool_classification = tc_label

        # SQL sub-dimensions
        notes.append("  — Parameter correctness —")
        if bench:
            pc, pb = eval_param_correctness(first, bench, notes)
        else:
            notes.append("  ⚠ No benchmark matched. Param correctness set to 0.5 (heuristic).")
            pc, pb = 0.5, {}
        result.layer1.param_correctness = pc
        result.layer1.param_breakdown   = pb

        # SQL sub-dimensions
        notes.append("  — SQL quality sub-dimensions —")
        result.layer1.exec_success     = eval_exec_success(first, notes)
        result.layer1.table_score      = eval_table_existence(first.sql, bench or {}, notes)
        result.layer1.column_score     = eval_column_existence(first.sql, bench or {}, notes)
        result.layer1.schema_rel_score = eval_schema_relationship(first.sql, bench or {}, notes)
        result.layer1.semantic_score   = eval_semantic_sql(first.sql, bench or {}, notes)

        # Sequence quality (truncated to expected_sequence length)
        notes.append("  — Sequence quality —")
        if bench:
            result.layer1.sequence_score = eval_sequence(episode, bench, notes)
        else:
            result.layer1.sequence_score = 1.0
            notes.append("  ℹ No benchmark — sequence check N/A. Score: 1.0")

        # Context retention
        notes.append("  — Context retention —")
        result.layer1.context_score = eval_context(episode, notes)

        l1_component_scores = [
            result.layer1.tool_correctness,
            result.layer1.param_correctness,
            result.layer1.exec_success,
            result.layer1.table_score,
            result.layer1.column_score,
            result.layer1.schema_rel_score,
            result.layer1.semantic_score,
            result.layer1.sequence_score,
            result.layer1.context_score,
        ]

        # Semantic score of the FINAL dynamic attempt (for Layer 3)
        last_dynamic = next(
            (t for t in reversed(episode.attempts) if t.tool_type == "dynamic"),
            first,
        )
        final_semantic_score = eval_semantic_sql(last_dynamic.sql, bench or {}, [])

    # ── Static path ───────────────────────────────────────────────────────────
    else:
        notes.append(f"  Tool selected: '{first.tool}'  (static path)")

        if bench:
            tc, tc_label = eval_tool_correctness(first, bench, notes)
            result.layer1.tool_correctness    = tc
            result.layer1.tool_classification = tc_label

            notes.append("  — Parameter correctness —")
            pc, pb = eval_param_correctness(first, bench, notes)
            result.layer1.param_correctness = pc
            result.layer1.param_breakdown   = pb

            notes.append("  — Sequence quality —")
            result.layer1.sequence_score = eval_sequence(episode, bench, notes)

            notes.append("  — Context retention —")
            result.layer1.context_score = eval_context(episode, notes)

            notes.append("  — Fallback reasoning (optional) —")
            fb = eval_fallback(episode, notes)
            result.layer1.fallback_score = fb

        else:
            notes.append("  ⚠ No benchmark matched. Heuristic scoring applied (0.5).")
            result.layer1.tool_correctness    = 0.5
            result.layer1.tool_classification = "unknown"
            result.layer1.param_correctness   = 0.5
            result.layer1.sequence_score      = 0.5
            result.layer1.context_score       = 1.0
            result.layer1.fallback_score      = -1.0

        # Fallback score of −1 means "not applicable" — exclude from average
        static_scores = [
            result.layer1.tool_correctness,
            result.layer1.param_correctness,
            result.layer1.sequence_score,
            result.layer1.context_score,
        ]
        if result.layer1.fallback_score >= 0.0:
            static_scores.append(result.layer1.fallback_score)

        l1_component_scores = static_scores

    # ── Layer 1 aggregate ─────────────────────────────────────────────────────
    result.layer1.total = round(
        sum(l1_component_scores) / len(l1_component_scores), 3
    )
    notes.append(f"  → Layer 1 total: {result.layer1.total}")

    # ══════════════════════════════════════════════════════════════════════════
    # LAYER 2 — Recovery Effort
    # ══════════════════════════════════════════════════════════════════════════
    notes.append("═══ LAYER 2 — Recovery Effort ═══")
    result.retry_count, result.retry_success = eval_retry(episode, notes)

    # ══════════════════════════════════════════════════════════════════════════
    # LAYER 3 — Task Completion
    # ══════════════════════════════════════════════════════════════════════════
    notes.append("═══ LAYER 3 — Task Completion ═══")
    result.task_completion = eval_task_completion(
        episode, final_semantic_score, notes
    )

    # ══════════════════════════════════════════════════════════════════════════
    # TOTAL SCORE
    # ══════════════════════════════════════════════════════════════════════════
    # Layer 2: no retries = first-call success = full credit for stability
    l2_contrib = result.retry_success if result.retry_count > 0 else 1.0

    result.total_score = round(
        result.layer1.total    * W_LAYER1
        + l2_contrib           * W_LAYER2
        + result.task_completion * W_LAYER3,
        3,
    )
    return result