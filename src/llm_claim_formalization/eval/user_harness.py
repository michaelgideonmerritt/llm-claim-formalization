from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Any, Callable, Iterator, Optional

import llm_claim_formalization.core.adapters as adapters_module
import llm_claim_formalization.core.verification as verification_module
from llm_claim_formalization.core.ir import Route, VerificationStatus


@dataclass
class UserEvalCase:
    id: str
    question: str
    category: str
    expected_route: str
    expected_status: str
    expected_reason: Optional[str] = None
    require_equation: bool = False
    require_comparison: bool = False
    require_citations: bool = False
    require_clarification: bool = False
    max_latency_ms: Optional[float] = None
    criticality: str = "medium"
    notes: Optional[str] = None


@dataclass
class UserCaseOutcome:
    id: str
    question: str
    category: str
    expected_route: str
    actual_route: str
    expected_status: str
    actual_status: str
    expected_reason: Optional[str]
    actual_reason: str
    route_match: bool
    status_match: bool
    reason_match: bool
    functionality_checks: dict[str, bool]
    functionality_pass: bool
    consistency_pass: bool
    latency_ms: float
    latency_sla_ms: Optional[float]
    latency_pass: Optional[bool]
    passed: bool
    message: Optional[str]
    criticality: str


@dataclass
class UserEvalReport:
    dataset_path: str
    total_cases: int
    llm_mode: str
    iterations: int
    metrics: dict[str, Any]
    thresholds: dict[str, Any]
    failures: list[str]
    passed: bool
    outcomes: list[UserCaseOutcome]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_path": self.dataset_path,
            "total_cases": self.total_cases,
            "llm_mode": self.llm_mode,
            "iterations": self.iterations,
            "metrics": self.metrics,
            "thresholds": self.thresholds,
            "failures": self.failures,
            "passed": self.passed,
            "outcomes": [asdict(outcome) for outcome in self.outcomes],
        }


def load_user_eval_cases(dataset_path: Path) -> list[UserEvalCase]:
    cases: list[UserEvalCase] = []
    valid_routes = {item.value for item in Route}
    valid_statuses = {item.value for item in VerificationStatus}
    valid_criticality = {"low", "medium", "high"}

    with dataset_path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            payload = json.loads(line)
            try:
                case = UserEvalCase(**payload)
            except TypeError as exc:
                raise ValueError(f"Invalid schema at line {line_number}: {exc}") from exc

            if not case.id:
                raise ValueError(f"Missing case id at line {line_number}")
            if not case.question.strip():
                raise ValueError(f"Empty question for case {case.id}")
            if case.expected_route not in valid_routes:
                raise ValueError(f"Invalid expected_route for case {case.id}: {case.expected_route}")
            if case.expected_status not in valid_statuses:
                raise ValueError(f"Invalid expected_status for case {case.id}: {case.expected_status}")
            if case.criticality not in valid_criticality:
                raise ValueError(f"Invalid criticality for case {case.id}: {case.criticality}")
            if case.max_latency_ms is not None and case.max_latency_ms <= 0:
                raise ValueError(f"max_latency_ms must be > 0 for case {case.id}")

            cases.append(case)

    if not cases:
        raise ValueError(f"No cases loaded from {dataset_path}")

    return cases


def load_user_thresholds(threshold_path: Optional[Path]) -> dict[str, Any]:
    if threshold_path is None:
        return {"minimums": {}, "maximums": {}, "per_category_minimums": {}}

    with threshold_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    minimums = payload.get("minimums", {})
    maximums = payload.get("maximums", {})
    per_category = payload.get("per_category_minimums", {})

    if not isinstance(minimums, dict) or not isinstance(maximums, dict) or not isinstance(per_category, dict):
        raise ValueError(
            "Threshold file must contain object keys: minimums, maximums, per_category_minimums"
        )

    return {
        "minimums": minimums,
        "maximums": maximums,
        "per_category_minimums": per_category,
    }


def _status_to_mock_verdict(status: str) -> str:
    if status in {"verified", "evidence_backed"}:
        return "true"
    if status in {"unverified"}:
        return "false"
    return "unknown"


def _build_mock_ollama(cases: list[UserEvalCase]) -> Callable[..., dict[str, Any]]:
    mapping = {case.question: _status_to_mock_verdict(case.expected_status) for case in cases}

    def _mock_ollama(text: str, _model: Optional[str] = None) -> dict[str, Any]:
        verdict = mapping.get(text, "unknown")
        if verdict == "true":
            verified: Optional[bool] = True
        elif verdict == "false":
            verified = False
        else:
            verified = None

        return {
            "verified": verified,
            "verdict": verdict,
            "model": "mock-user-eval",
            "raw_response": verdict,
        }

    return _mock_ollama


@contextmanager
def _patched_ollama_mode(mode: str, cases: list[UserEvalCase]) -> Iterator[None]:
    original = adapters_module.verify_with_ollama
    original_nli = adapters_module.verify_entailment_with_ollama

    if mode == "live":
        yield
        return

    replacement: Callable[..., dict[str, Any]]
    nli_replacement: Callable[..., dict[str, Any]]

    if mode == "mock":
        replacement = _build_mock_ollama(cases)
        factual_mapping = {
            case.question: (
                "entailment"
                if case.expected_status == "evidence_backed"
                else ("contradiction" if case.expected_status == "unverified" else "neutral")
            )
            for case in cases
        }

        def nli_replacement(claim: str, _evidence: str, _model: Optional[str] = None) -> dict[str, Any]:
            label = factual_mapping.get(claim, "neutral")
            return {
                "label": label,
                "confidence": 0.9 if label != "neutral" else 0.5,
                "model": "mock-user-eval-nli",
                "raw_response": label,
            }

    elif mode == "skip":
        def replacement(_text: str, _model: Optional[str] = None) -> dict[str, Any]:
            return {
                "verified": None,
                "verdict": "unknown",
                "model": "skip-user-eval",
                "raw_response": "unknown",
            }

        def nli_replacement(_claim: str, _evidence: str, _model: Optional[str] = None) -> dict[str, Any]:
            return {
                "label": "neutral",
                "confidence": 0.5,
                "model": "skip-user-eval-nli",
                "raw_response": "neutral",
            }

    else:
        raise ValueError(f"Unsupported llm mode: {mode}")

    adapters_module.verify_with_ollama = replacement  # type: ignore[assignment]
    adapters_module.verify_entailment_with_ollama = nli_replacement  # type: ignore[assignment]
    try:
        yield
    finally:
        adapters_module.verify_with_ollama = original
        adapters_module.verify_entailment_with_ollama = original_nli


def _percentile(latencies: list[float], quantile: float) -> float:
    if not latencies:
        return 0.0
    values = sorted(latencies)
    index = int(round((len(values) - 1) * quantile))
    index = max(0, min(index, len(values) - 1))
    return round(values[index], 3)


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 1.0
    return round(numerator / denominator, 6)


def _build_functionality_checks(case: UserEvalCase, result: verification_module.VerificationResult) -> dict[str, bool]:
    checks: dict[str, bool] = {
        "no_error_status": result.status != "error",
    }
    if case.require_equation:
        checks["equation_present"] = bool(result.equation)
    if case.require_comparison:
        checks["comparison_present"] = bool(result.comparison)
    if case.require_citations:
        checks["citations_present"] = len(result.citations) > 0
    if case.require_clarification:
        checks["clarification_present"] = bool(result.suggested_clarification)
    return checks


def _compute_metrics(outcomes: list[UserCaseOutcome]) -> dict[str, Any]:
    total = len(outcomes)
    route_matches = sum(1 for outcome in outcomes if outcome.route_match)
    status_matches = sum(1 for outcome in outcomes if outcome.status_match)
    reason_comparable = [outcome for outcome in outcomes if outcome.expected_reason is not None]
    reason_matches = sum(1 for outcome in reason_comparable if outcome.reason_match)
    functionality_passes = sum(1 for outcome in outcomes if outcome.functionality_pass)
    consistency_passes = sum(1 for outcome in outcomes if outcome.consistency_pass)
    no_error = sum(1 for outcome in outcomes if outcome.functionality_checks.get("no_error_status", False))
    exact_passes = sum(1 for outcome in outcomes if outcome.passed)

    latency_values = [outcome.latency_ms for outcome in outcomes]
    sla_cases = [outcome for outcome in outcomes if outcome.latency_pass is not None]
    sla_passes = sum(1 for outcome in sla_cases if outcome.latency_pass)

    per_category_total: dict[str, int] = {}
    per_category_pass: dict[str, int] = {}
    for outcome in outcomes:
        per_category_total[outcome.category] = per_category_total.get(outcome.category, 0) + 1
        if outcome.passed:
            per_category_pass[outcome.category] = per_category_pass.get(outcome.category, 0) + 1

    per_category_exact_match = {
        category: _safe_ratio(per_category_pass.get(category, 0), total_count)
        for category, total_count in per_category_total.items()
    }

    high_criticality = [outcome for outcome in outcomes if outcome.criticality == "high"]
    high_criticality_accuracy = _safe_ratio(
        sum(1 for outcome in high_criticality if outcome.passed),
        len(high_criticality),
    )

    return {
        "overall_case_accuracy": _safe_ratio(exact_passes, total),
        "route_accuracy": _safe_ratio(route_matches, total),
        "status_accuracy": _safe_ratio(status_matches, total),
        "reason_accuracy": _safe_ratio(reason_matches, len(reason_comparable)),
        "functionality_accuracy": _safe_ratio(functionality_passes, total),
        "consistency_accuracy": _safe_ratio(consistency_passes, total),
        "user_success_rate": _safe_ratio(no_error, total),
        "sla_pass_rate": _safe_ratio(sla_passes, len(sla_cases)),
        "latency_mean_ms": round(mean(latency_values), 3) if latency_values else 0.0,
        "latency_p50_ms": _percentile(latency_values, 0.50),
        "latency_p95_ms": _percentile(latency_values, 0.95),
        "latency_max_ms": round(max(latency_values), 3) if latency_values else 0.0,
        "latency_min_ms": round(min(latency_values), 3) if latency_values else 0.0,
        "total_cases": total,
        "passed_cases": exact_passes,
        "per_category_exact_match": per_category_exact_match,
        "high_criticality_accuracy": high_criticality_accuracy,
    }


def _evaluate_thresholds(metrics: dict[str, Any], thresholds: dict[str, Any]) -> list[str]:
    failures: list[str] = []

    minimums = thresholds.get("minimums", {})
    for key, minimum in minimums.items():
        actual = metrics.get(key)
        if actual is None:
            failures.append(f"Metric not found for threshold '{key}'")
            continue
        if actual < minimum:
            failures.append(f"Metric '{key}' below threshold: actual={actual:.3f}, required={minimum:.3f}")

    maximums = thresholds.get("maximums", {})
    for key, maximum in maximums.items():
        actual = metrics.get(key)
        if actual is None:
            failures.append(f"Metric not found for max-threshold '{key}'")
            continue
        if actual > maximum:
            failures.append(
                f"Metric '{key}' above max threshold: actual={actual:.3f}, allowed={maximum:.3f}"
            )

    per_category_minimums = thresholds.get("per_category_minimums", {})
    per_category_actual = metrics.get("per_category_exact_match", {})
    for category, minimum in per_category_minimums.items():
        actual = per_category_actual.get(category)
        if actual is None:
            failures.append(f"Category metric not found for '{category}'")
            continue
        if actual < minimum:
            failures.append(
                f"Category '{category}' below threshold: actual={actual:.3f}, required={minimum:.3f}"
            )

    return failures


def run_user_evaluation(
    dataset_path: Path,
    llm_mode: str = "mock",
    threshold_path: Optional[Path] = None,
    iterations: int = 1,
    concurrency: int = 1,
) -> UserEvalReport:
    if iterations <= 0:
        raise ValueError("iterations must be >= 1")
    if concurrency < 1:
        raise ValueError("concurrency must be >= 1")

    cases = load_user_eval_cases(dataset_path)
    thresholds = load_user_thresholds(threshold_path)
    outcomes: list[UserCaseOutcome] = []

    def _run_case(case: UserEvalCase) -> UserCaseOutcome:
        """Run a single test case with iterations."""
        run_results: list[verification_module.VerificationResult] = []
        run_latencies: list[float] = []

        for _ in range(iterations):
            started = perf_counter()
            result = verification_module.verify_claim(case.question)
            elapsed_ms = (perf_counter() - started) * 1000
            run_results.append(result)
            run_latencies.append(elapsed_ms)

        final_result = run_results[-1]
        first = run_results[0]
        consistency_pass = all(
            candidate.route == first.route
            and candidate.status == first.status
            and candidate.reason == first.reason
            for candidate in run_results[1:]
        )

        route_match = final_result.route == case.expected_route
        status_match = final_result.status == case.expected_status
        reason_match = case.expected_reason is None or final_result.reason == case.expected_reason

        checks = _build_functionality_checks(case, final_result)
        functionality_pass = all(checks.values())

        latency_ms = round(mean(run_latencies), 3)
        latency_pass = None
        if case.max_latency_ms is not None:
            latency_pass = latency_ms <= case.max_latency_ms

        passed = (
            route_match
            and status_match
            and reason_match
            and functionality_pass
            and consistency_pass
            and (latency_pass is not False)
        )

        return UserCaseOutcome(
            id=case.id,
            question=case.question,
            category=case.category,
            expected_route=case.expected_route,
            actual_route=final_result.route,
            expected_status=case.expected_status,
            actual_status=final_result.status,
            expected_reason=case.expected_reason,
            actual_reason=final_result.reason,
            route_match=route_match,
            status_match=status_match,
            reason_match=reason_match,
            functionality_checks=checks,
            functionality_pass=functionality_pass,
            consistency_pass=consistency_pass,
            latency_ms=latency_ms,
            latency_sla_ms=case.max_latency_ms,
            latency_pass=latency_pass,
            passed=passed,
            message=final_result.message,
            criticality=case.criticality,
        )

    with _patched_ollama_mode(llm_mode, cases):
        if concurrency == 1:
            # Sequential execution
            for case in cases:
                outcomes.append(_run_case(case))
        else:
            # Parallel execution
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = {executor.submit(_run_case, case): case for case in cases}
                for future in as_completed(futures):
                    outcomes.append(future.result())

    metrics = _compute_metrics(outcomes)
    failures = _evaluate_thresholds(metrics, thresholds)

    return UserEvalReport(
        dataset_path=str(dataset_path),
        total_cases=len(cases),
        llm_mode=llm_mode,
        iterations=iterations,
        metrics=metrics,
        thresholds=thresholds,
        failures=failures,
        passed=len(failures) == 0,
        outcomes=outcomes,
    )
