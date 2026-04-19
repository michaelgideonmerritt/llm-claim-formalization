from __future__ import annotations

import json
from pathlib import Path

from llm_claim_formalization.eval import run_evaluation


def test_eval_harness_passes_on_baseline_dataset() -> None:
    project_root = Path(__file__).resolve().parents[2]
    dataset = project_root / "benchmarks" / "general_claims_eval.jsonl"
    thresholds = project_root / "benchmarks" / "thresholds.json"

    report = run_evaluation(dataset_path=dataset, llm_mode="mock", threshold_path=thresholds)

    assert report.passed is True
    assert report.failures == []
    assert report.total_cases >= 30
    assert report.metrics["overall_case_accuracy"] >= 0.98


def test_eval_harness_detects_threshold_failures(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[2]
    dataset = project_root / "benchmarks" / "general_claims_eval.jsonl"

    impossible_thresholds = {
        "minimums": {
            "overall_case_accuracy": 1.1,
        },
        "per_route_minimums": {},
    }
    threshold_path = tmp_path / "thresholds.json"
    threshold_path.write_text(json.dumps(impossible_thresholds), encoding="utf-8")

    report = run_evaluation(dataset_path=dataset, llm_mode="mock", threshold_path=threshold_path)

    assert report.passed is False
    assert len(report.failures) >= 1
    assert "overall_case_accuracy" in report.failures[0]
