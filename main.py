"""
Enterprise MCP Evaluation Pipeline  —  v3
==========================================
Entry point. Wires all components together.

Usage
-----
  # Evaluate a single log file
  python3 main.py path/to/log.jsonl

  # Evaluate and compare multiple model runs
  python3 main.py log_modelA.jsonl log_modelB.jsonl --names ModelA ModelB
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add pipeline directory to path
sys.path.insert(0, str(Path(__file__).parent))

from parser   import parse_logs
from scorer   import evaluate_episode
from reporter import generate_report
from models   import EpisodeResult


def _run(log_path: str) -> list[EpisodeResult]:
    episodes = parse_logs(log_path)
    return [evaluate_episode(ep) for ep in episodes]


def _to_dict(r: EpisodeResult) -> dict:
    return {
        "session_id":      r.session_id,
        "query":           r.query,
        "tool_type":       r.tool_type,
        "target_system":   r.target_system,
        "layer1":          vars(r.layer1),
        "retry_count":     r.retry_count,
        "retry_success":   r.retry_success,
        "task_completion": r.task_completion,
        "total_score":     r.total_score,
        "notes":           r.notes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enterprise MCP Evaluation Pipeline v3"
    )
    parser.add_argument(
        "logs",
        nargs="+",
        help="One or more JSONL log files to evaluate",
    )
    parser.add_argument(
        "--names",
        nargs="*",
        help="Optional model names for each log (used in comparison report)",
    )
    parser.add_argument(
        "--out",
        default=".",
        help="Output directory for report and JSON files (default: current dir)",
    )
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    model_names = args.names or [Path(p).stem for p in args.logs]
    if len(model_names) < len(args.logs):
        model_names += [Path(p).stem for p in args.logs[len(model_names):]]

    model_runs: dict[str, list[EpisodeResult]] = {}
    primary_results: list[EpisodeResult] = []

    for log_path, model_name in zip(args.logs, model_names):
        print(f"Evaluating: {log_path}  [{model_name}]")
        results = _run(log_path)
        model_runs[model_name] = results
        print(f"  Episodes: {len(results)}")

        # Save per-model JSON
        json_out = out_dir / f"results_{model_name}.json"
        json_out.write_text(
            json.dumps([_to_dict(r) for r in results], indent=2),
            encoding="utf-8",
        )
        print(f"  JSON saved: {json_out}")

        if not primary_results:
            primary_results = results

    # Generate combined report
    report = generate_report(
        primary_results,
        model_runs=model_runs if len(model_runs) > 1 else None,
    )

    report_out = out_dir / "evaluation_report_v3.txt"
    report_out.write_text(report, encoding="utf-8")
    print(f"\nReport saved: {report_out}")
    print("\n" + report)


if __name__ == "__main__":
    main()
