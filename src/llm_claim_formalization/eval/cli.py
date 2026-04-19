from __future__ import annotations

import argparse
import json
from pathlib import Path

from .harness import EvalReport, run_evaluation


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate claim verification behavior on a benchmark dataset.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("benchmarks/general_claims_eval.jsonl"),
        help="Path to JSONL benchmark file.",
    )
    parser.add_argument(
        "--thresholds",
        type=Path,
        default=Path("benchmarks/thresholds.json"),
        help="Path to threshold JSON file.",
    )
    parser.add_argument(
        "--llm-mode",
        choices=["mock", "live", "skip"],
        default="mock",
        help="Use mock labels, live Ollama calls, or skip LLM signals.",
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
        default=10,
        help="Number of failing cases to print.",
    )
    return parser


def _print_summary(report: EvalReport, show_failures: int) -> None:
    metrics = report.metrics
    print("=== LLM Claim Formalization Eval ===")
    print(f"Dataset: {report.dataset_path}")
    print(f"LLM mode: {report.llm_mode}")
    print(f"Cases: {report.total_cases}")
    print()

    ordered_metrics = [
        "overall_case_accuracy",
        "route_accuracy",
        "status_accuracy",
        "verified_precision",
        "unverified_precision",
        "abstention_accuracy",
        "llm_only_accuracy",
    ]

    print("Metrics:")
    for key in ordered_metrics:
        value = metrics.get(key)
        if value is not None:
            print(f"  - {key}: {value:.3f}")

    print("  - passed_cases: {}/{}".format(metrics.get("passed_cases"), metrics.get("total_cases")))

    per_route = metrics.get("per_route_exact_match", {})
    if per_route:
        print("Per-route exact match:")
        for route in sorted(per_route.keys()):
            print(f"  - {route}: {per_route[route]:.3f}")

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
                "  - {id}: expected({eroute}/{estatus}{ellm}) actual({aroute}/{astatus}{allm})".format(
                    id=outcome.id,
                    eroute=outcome.expected_route,
                    estatus=outcome.expected_status,
                    ellm=f", llm={outcome.expected_llm_status}" if outcome.expected_llm_status else "",
                    aroute=outcome.actual_route,
                    astatus=outcome.actual_status,
                    allm=f", llm={outcome.actual_llm_status}" if outcome.actual_llm_status else "",
                )
            )


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    report = run_evaluation(
        dataset_path=args.dataset,
        llm_mode=args.llm_mode,
        threshold_path=args.thresholds,
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
