from __future__ import annotations

import json
from pathlib import Path

from llm_claim_formalization.eval.user_harness import run_user_evaluation


def test_user_eval_harness_runs_and_emits_latency_metrics() -> None:
    project_root = Path(__file__).resolve().parents[2]
    dataset = project_root / "benchmarks" / "user_questions_eval.jsonl"

    report = run_user_evaluation(
        dataset_path=dataset,
        llm_mode="mock",
        threshold_path=None,
        iterations=2,
    )

    assert report.total_cases >= 20
    assert len(report.outcomes) == report.total_cases
    assert "latency_mean_ms" in report.metrics
    assert "latency_p95_ms" in report.metrics
    assert "functionality_accuracy" in report.metrics


def test_user_eval_harness_detects_threshold_failures(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    dataset = project_root / "benchmarks" / "user_questions_eval.jsonl"

    impossible_thresholds = {
        "minimums": {
            "overall_case_accuracy": 1.1,
        },
        "maximums": {
            "latency_mean_ms": 0.0,
        },
        "per_category_minimums": {},
    }
    threshold_path = tmp_path / "thresholds.json"
    threshold_path.write_text(json.dumps(impossible_thresholds), encoding="utf-8")

    report = run_user_evaluation(
        dataset_path=dataset,
        llm_mode="mock",
        threshold_path=threshold_path,
        iterations=1,
    )

    assert report.passed is False
    assert len(report.failures) >= 1
