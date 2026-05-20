"""
Pipeline Data Models
=====================
All dataclasses used across the evaluation pipeline.
"""

from __future__ import annotations
from dataclasses import dataclass, field


# ══════════════════════════════════════════════════════════════════════════════
# RAW TRACE — one tool call + its result
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class TraceEntry:
    session_id:     str
    query:          str
    target_system:  str          # derived from port
    timestamp:      str
    tool:           str          # canonical tool name (no parens)
    tool_type:      str          # "static" | "dynamic" | "hallucinated"
    parameters:     dict[str, str]
    sql:            str          # non-empty only for dynamic tools
    status:         str          # "success" | "failure"
    sequence_index: int
    retry_detected: bool
    raw_result:     str          # first 600 chars of tool result


# ══════════════════════════════════════════════════════════════════════════════
# EPISODE — all traces for one user query
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Episode:
    session_id:    str
    query:         str
    target_system: str           # dominant non-auth system
    tool_type:     str           # "static" | "dynamic"
    attempts:      list[TraceEntry] = field(default_factory=list)
    final_status:  str = "unknown"


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 1 SCORES — initial orchestration quality (first attempt only)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Layer1Scores:
    # Static dimensions
    tool_correctness:     float = 0.0
    tool_classification:  str   = ""    # correct | incorrect | cross-system | hallucinated
    param_correctness:    float = 0.0
    param_breakdown:      dict  = field(default_factory=dict)   # per-param detail
    sequence_score:       float = 0.0
    context_score:        float = 0.0
    fallback_score:       float = 0.0   # optional; -1 = not triggered

    # Dynamic dimensions (SQL)
    exec_success:         float = 0.0
    table_score:          float = 0.0
    column_score:         float = 0.0
    schema_rel_score:     float = 0.0
    semantic_score:       float = 0.0

    # Aggregate
    total:                float = 0.0


# ══════════════════════════════════════════════════════════════════════════════
# EPISODE RESULT — full 3-layer evaluation output
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class EpisodeResult:
    session_id:       str
    query:            str
    tool_type:        str
    target_system:    str
    layer1:           Layer1Scores = field(default_factory=Layer1Scores)
    retry_count:      int   = 0
    retry_success:    float = 0.0    # 1.0 = recovered, 0.0 = did not recover / no retry
    task_completion:  float = 0.0
    total_score:      float = 0.0
    notes:            list[str] = field(default_factory=list)
