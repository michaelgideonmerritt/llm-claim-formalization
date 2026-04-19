from __future__ import annotations

import argparse
import json
from pathlib import Path

from .user_harness import UserEvalReport, run_user_evaluation


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="User-centric functionality/accuracy/speed benchmark for claim verification."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("benchmarks/user_questions_eval.jsonl"),
        help="Path to user-question benchmark JSONL file.",
    )
    parser.add_argument(
        "--thresholds",
        type=Path,
        default=Path("benchmarks/user_suite_thresholds.json"),
        help="Path to threshold JSON file.",
    )
    parser.add_argument(
        "--llm-mode",
        choices=["mock", "live", "skip"],
        default="mock",
        help="Use mock labels, live Ollama calls, or skip LLM signals.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Run each question multiple times to measure consistency and average latency.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Number of parallel workers for concurrent test execution (default: 1 = sequential).",
    )
    parser.add_argument(
        "--enforce-thresholds",
        action="store_true",
        help="Exit non-zero if metrics fall below configured thresholds.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Optional path to write full JSON report.",
    )
    parser.add_argument(
        "--show-failures",
        type=int,
        default=20,
        help="Number of failing cases to print.",
    )
    return parser


def _print_summary(report: UserEvalReport, show_failures: int) -> None:
    metrics = report.metrics
    print("=== LLM Claim Formalization User Suite ===")
    print(f"Dataset: {report.dataset_path}")
    print(f"LLM mode: {report.llm_mode}")
    print(f"Iterations per case: {report.iterations}")
    print(f"Cases: {report.total_cases}")
    print()

    ordered_metrics = [
        "overall_case_accuracy",
        "route_accuracy",
        "status_accuracy",
        "reason_accuracy",
        "functionality_accuracy",
        "consistency_accuracy",
        "user_success_rate",
        "sla_pass_rate",
        "high_criticality_accuracy",
    ]

    print("Quality Metrics:")
    for key in ordered_metrics:
        value = metrics.get(key)
        if value is not None:
            print(f"  - {key}: {value:.3f}")

    print("Latency Metrics:")
    for key in ["latency_mean_ms", "latency_p50_ms", "latency_p95_ms", "latency_max_ms", "latency_min_ms"]:
        value = metrics.get(key)
        if value is not None:
            print(f"  - {key}: {value:.3f}")

    print("  - passed_cases: {}/{}".format(metrics.get("passed_cases"), metrics.get("total_cases")))

    per_category = metrics.get("per_category_exact_match", {})
    if per_category:
        print("Per-category exact match:")
        for category in sorted(per_category.keys()):
            print(f"  - {category}: {per_category[category]:.3f}")

    if report.failures:
        print()
        print("Threshold failures:")
        for failure in report.failures:
            print(f"  - {failure}")

    mismatches = [outcome for outcome in report.outcomes if not outcome.passed]
    if mismatches:
        print()
        print(f"Top {min(show_failures, len(mismatches))} case mismatches:")
        for outcome in mismatches[:show_failures]:
            print(
                "  - {id}: expected({eroute}/{estatus}) actual({aroute}/{astatus}) "
                "latency={lat:.1f}ms function={fpass} consistency={cpass} sla={slapass}".format(
                    id=outcome.id,
                    eroute=outcome.expected_route,
                    estatus=outcome.expected_status,
                    aroute=outcome.actual_route,
                    astatus=outcome.actual_status,
                    lat=outcome.latency_ms,
                    fpass=outcome.functionality_pass,
                    cpass=outcome.consistency_pass,
                    slapass=outcome.latency_pass,
                )
            )


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    report = run_user_evaluation(
        dataset_path=args.dataset,
        llm_mode=args.llm_mode,
        threshold_path=args.thresholds,
        iterations=args.iterations,
        concurrency=args.concurrency,
    )
    _print_summary(report, show_failures=args.show_failures)

    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        with args.output_json.open("w", encoding="utf-8") as handle:
            json.dump(report.to_dict(), handle, indent=2)
            handle.write("\n")

    if args.enforce_thresholds and not report.passed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
