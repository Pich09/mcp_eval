"""
Log Parser
===========
Converts raw OpenClaw JSONL orchestration logs into structured Episode objects.

Parsing capabilities (per spec §5.3):
  - tool extraction       detect invoked MCP tools
  - parameter extraction  parse parameter names and values
  - status extraction     detect success/failure states
  - retry detection       detect repeated orchestration attempts
  - sequence indexing     preserve orchestration ordering
  - session grouping      associate logs with user queries
  - system detection      identify target enterprise system via port
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from registry import INFRASTRUCTURE_TOOLS, system_of_port, find_tool
from models import TraceEntry, Episode


# ── Error signal keywords ──────────────────────────────────────────────────────
_ERROR_SIGNALS = (
    '"error"',
    "syntax error",
    "does not exist",
    "unknown tool",
    "only select",
    "command exited with code",
)


def _is_error(text: str) -> bool:
    lower = text.lower()
    return any(sig in lower for sig in _ERROR_SIGNALS)


def _get_text(content: Any) -> str:
    """Flatten content block(s) to a single string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "")
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


def _extract_query(raw_text: str) -> str:
    """Strip OpenClaw metadata wrapper; return the real user question."""
    # Remove JSON code fences (conversation metadata)
    clean = re.sub(r"```json.*?```", "", raw_text, flags=re.DOTALL)
    lines = [l.strip() for l in clean.splitlines() if l.strip()]
    drop  = {
        "conversation info (untrusted metadata):",
        "sender (untrusted metadata):",
    }
    return " ".join(l for l in lines if l.lower() not in drop).strip()


def _parse_command(cmd: str) -> tuple[str, str, dict[str, str], str]:
    """
    Parse an mcporter CLI invocation.

    Returns
    -------
    system_name : str
    tool_name   : str   (clean, no paren artifacts)
    parameters  : dict[str, str]
    sql         : str   (empty if not a dynamic call)
    """
    # ── system from port ──────────────────────────────────────────────────────
    port_m = re.search(r":(\d+)/", cmd)
    port   = int(port_m.group(1)) if port_m else 0
    system = system_of_port(port)

    # ── tool name (strip shell-quoting artifact: tool(arg=...) → tool) ───────
    tool_m = re.search(r"--allow-http\s+([^\s(]+)", cmd)
    tool   = tool_m.group(1).strip() if tool_m else "unknown"

    # ── SQL value ─────────────────────────────────────────────────────────────
    sql_m = re.search(r'\bsql="(.+?)"(?:\s|$)', cmd, re.DOTALL | re.IGNORECASE)
    if not sql_m:
        sql_m = re.search(r"\bsql='(.+?)'(?:\s|$)", cmd, re.DOTALL | re.IGNORECASE)
    sql = sql_m.group(1).strip() if sql_m else ""

    # ── parameters (key=value, excluding infrastructure keys) ─────────────────
    _SKIP = {"http", "allow", "sql", "command", "timeout"}
    params: dict[str, str] = {}
    for m in re.finditer(r"\b(\w+)=(?:\"([^\"]*)\"|'([^']*)'|(\S+))", cmd):
        k = m.group(1)
        if k in _SKIP:
            continue
        v = next(x for x in (m.group(2), m.group(3), m.group(4)) if x is not None)
        params[k] = v

    return system, tool, params, sql


def _classify_tool_type(tool: str) -> str:
    """Return 'static', 'dynamic', or 'hallucinated'."""
    _, tool_def = find_tool(tool)
    if tool_def is None:
        return "hallucinated"
    return tool_def["type"]


def _flush_episode(traces: list[TraceEntry], query: str) -> Episode | None:
    if not traces or not query:
        return None
    dom_type = (
        "dynamic" if any(t.tool_type == "dynamic" for t in traces) else "static"
    )
    # target system = first non-auth trace
    sys_name = next(
        (
            t.target_system
            for t in traces
            if t.target_system not in ("auth_gateway", "unknown_system")
        ),
        traces[0].target_system,
    )
    return Episode(
        session_id    = traces[0].session_id,
        query         = query,
        target_system = sys_name,
        tool_type     = dom_type,
        attempts      = list(traces),
        final_status  = traces[-1].status,
    )


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

def parse_logs(path: str | Path) -> list[Episode]:
    """
    Parse a JSONL OpenClaw conversation log.

    Each line is one message object:
      { "id": "...", "timestamp": "...", "message": { "role": "...", "content": [...] } }

    Returns one Episode per user query found in the log.
    """
    raw  = Path(path).read_text(encoding="utf-8").strip().splitlines()
    msgs = [json.loads(l) for l in raw if l.strip()]

    episodes:      list[Episode]    = []
    traces:        list[TraceEntry] = []
    pending_calls: list[tuple]      = []   # (system, tool, params, sql, ts, session_id)
    current_query  = ""
    seq_index      = 0

    for obj in msgs:
        msg     = obj.get("message", {})
        role    = msg.get("role", "")
        ts      = obj.get("timestamp", "")
        sid     = obj.get("id", "")
        content = msg.get("content", [])

        # ── New user message → flush current episode ──────────────────────────
        if role == "user":
            ep = _flush_episode(traces, current_query)
            if ep:
                episodes.append(ep)
            traces        = []
            pending_calls = []
            seq_index     = 0

            for block in content:
                if block.get("type") == "text":
                    current_query = _extract_query(block["text"])
                    break

        # ── Assistant message → collect tool calls ────────────────────────────
        elif role == "assistant":
            for block in content:
                if block.get("type") == "toolCall":
                    cmd = block.get("arguments", {}).get("command", "")
                    system, tool, params, sql = _parse_command(cmd)
                    pending_calls.append((system, tool, params, sql, ts, sid))

        # ── Tool result → pair with pending call, build TraceEntry ────────────
        elif role == "toolResult":
            result_text = _get_text(content)

            if pending_calls:
                system, tool, params, sql, call_ts, call_sid = pending_calls.pop(0)

                # Skip infrastructure tools from scoring
                if tool in INFRASTRUCTURE_TOOLS:
                    continue

                status    = "failure" if _is_error(result_text) else "success"
                tool_type = _classify_tool_type(tool)

                # Retry detected if same tool was already attempted and failed
                retry = any(
                    t.tool == tool and t.status == "failure"
                    for t in traces
                )

                traces.append(TraceEntry(
                    session_id     = call_sid,
                    query          = current_query,
                    target_system  = system,
                    timestamp      = call_ts,
                    tool           = tool,
                    tool_type      = tool_type,
                    parameters     = params,
                    sql            = sql,
                    status         = status,
                    sequence_index = seq_index,
                    retry_detected = retry,
                    raw_result     = result_text[:600],
                ))
                seq_index += 1

    # Flush final episode
    ep = _flush_episode(traces, current_query)
    if ep:
        episodes.append(ep)

    return episodes
