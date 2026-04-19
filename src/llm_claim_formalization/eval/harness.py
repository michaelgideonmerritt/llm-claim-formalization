from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

import llm_claim_formalization.core.adapters as adapters_module
import llm_claim_formalization.core.verification as verification_module
from llm_claim_formalization.core.ir import Route, VerificationStatus


@dataclass
class EvalCase:
    id: str
    text: str
    domain: str
    expected_route: str
    expected_status: str
    expected_llm_status: Optional[str] = None
    criticality: str = "medium"
    notes: Optional[str] = None


@dataclass
class CaseOutcome:
    id: str
    text: str
    domain: str
    expected_route: str
    actual_route: str
    expected_status: str
    actual_status: str
    expected_llm_status: Optional[str]
    actual_llm_status: Optional[str]
    route_match: bool
    status_match: bool
    llm_match: bool
    passed: bool
    message: Optional[str]


@dataclass
class EvalReport:
    dataset_path: str
    total_cases: int
    llm_mode: str
    metrics: dict[str, Any]
    thresholds: dict[str, Any]
    failures: list[str]
    passed: bool
    outcomes: list[CaseOutcome]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_path": self.dataset_path,
            "total_cases": self.total_cases,
            "llm_mode": self.llm_mode,
            "metrics": self.metrics,
            "thresholds": self.thresholds,
            "failures": self.failures,
            "passed": self.passed,
            "outcomes": [asdict(outcome) for outcome in self.outcomes],
        }


def load_eval_cases(dataset_path: Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    valid_routes = {item.value for item in Route}
    valid_statuses = {item.value for item in VerificationStatus}

    with dataset_path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            payload = json.loads(line)
            try:
                case = EvalCase(**payload)
            except TypeError as exc:
                raise ValueError(f"Invalid schema at line {line_number}: {exc}") from exc

            if not case.id:
                raise ValueError(f"Missing case id at line {line_number}")
            if case.expected_route not in valid_routes:
                raise ValueError(f"Invalid expected_route for case {case.id}: {case.expected_route}")
            if case.expected_status not in valid_statuses:
                raise ValueError(f"Invalid expected_status for case {case.id}: {case.expected_status}")
            if case.expected_llm_status and case.expected_llm_status not in {"VALID", "INVALID", "UNKNOWN", "ERROR"}:
                raise ValueError(f"Invalid expected_llm_status for case {case.id}: {case.expected_llm_status}")

            cases.append(case)

    if not cases:
        raise ValueError(f"No cases loaded from {dataset_path}")

    return cases


def load_thresholds(threshold_path: Optional[Path]) -> dict[str, Any]:
    if threshold_path is None:
        return {"minimums": {}, "per_route_minimums": {}}

    with threshold_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    minimums = payload.get("minimums", {})
    per_route = payload.get("per_route_minimums", {})

    if not isinstance(minimums, dict) or not isinstance(per_route, dict):
        raise ValueError("Threshold file must contain object keys: minimums, per_route_minimums")

    return {
        "minimums": minimums,
        "per_route_minimums": per_route,
    }


def _status_to_mock_verdict(case: EvalCase) -> str:
    if case.expected_llm_status == "VALID":
        return "true"
    if case.expected_llm_status == "INVALID":
        return "false"
    if case.expected_llm_status == "UNKNOWN":
        return "unknown"

    if case.expected_status in {"verified"}:
        return "true"
    if case.expected_status in {"unverified"}:
        return "false"
    return "unknown"


def _build_mock_ollama(cases: list[EvalCase]) -> Callable[..., dict[str, Any]]:
    mapping = {
        case.text: _status_to_mock_verdict(case)
        for case in cases
    }

    def _mock_ollama(text: str, _model: Optional[str] = None) -> dict[str, Any]:
        verdict = mapping.get(text, "unknown")

        if verdict == "true":
            verified: Optional[bool] = True
            llm_status = "VALID"
        elif verdict == "false":
            verified = False
            llm_status = "INVALID"
        else:
            verified = None
            llm_status = "UNKNOWN"

        return {
            "verified": verified,
            "verdict": verdict,
            "model": "mock-eval",
            "raw_response": verdict,
            "llm_status": llm_status,
        }

    return _mock_ollama


@contextmanager
def _patched_ollama_mode(mode: str, cases: list[EvalCase]) -> Iterator[None]:
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
            case.text: (
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
                "model": "mock-eval-nli",
                "raw_response": label,
            }
    elif mode == "skip":
        def replacement(_text: str, _model: Optional[str] = None) -> dict[str, Any]:
            return {
                "verified": None,
                "verdict": "unknown",
                "model": "skip-eval",
                "raw_response": "unknown",
                "llm_status": "UNKNOWN",
            }

        def nli_replacement(_claim: str, _evidence: str, _model: Optional[str] = None) -> dict[str, Any]:
            return {
                "label": "neutral",
                "confidence": 0.5,
                "model": "skip-eval-nli",
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


def _extract_llm_status(result: verification_module.VerificationResult) -> Optional[str]:
    if result.llm_only:
        return result.llm_only.get("status")
    if result.comparison:
        return result.comparison.get("llm_only")
    return None


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 1.0
    return round(numerator / denominator, 6)


def _compute_metrics(outcomes: list[CaseOutcome]) -> dict[str, Any]:
    total = len(outcomes)

    route_matches = sum(1 for outcome in outcomes if outcome.route_match)
    status_matches = sum(1 for outcome in outcomes if outcome.status_match)
    exact_matches = sum(1 for outcome in outcomes if outcome.passed)

    predicted_verified = [outcome for outcome in outcomes if outcome.actual_status == "verified"]
    predicted_unverified = [outcome for outcome in outcomes if outcome.actual_status == "unverified"]

    verified_precision = _safe_ratio(
        sum(1 for outcome in predicted_verified if outcome.expected_status == "verified"),
        len(predicted_verified),
    )
    unverified_precision = _safe_ratio(
        sum(1 for outcome in predicted_unverified if outcome.expected_status == "unverified"),
        len(predicted_unverified),
    )

    expected_abstentions = [
        outcome
        for outcome in outcomes
        if outcome.expected_status in {"insufficient_info", "no_claim", "cannot_formally_verify"}
    ]
    abstention_accuracy = _safe_ratio(
        sum(1 for outcome in expected_abstentions if outcome.status_match and outcome.route_match),
        len(expected_abstentions),
    )

    llm_labeled = [
        outcome
        for outcome in outcomes
        if outcome.expected_status == "llm_only" and outcome.expected_llm_status is not None
    ]
    llm_only_accuracy = _safe_ratio(
        sum(1 for outcome in llm_labeled if outcome.llm_match and outcome.status_match),
        len(llm_labeled),
    )

    per_route_total: dict[str, int] = {}
    per_route_correct: dict[str, int] = {}
    for outcome in outcomes:
        per_route_total[outcome.expected_route] = per_route_total.get(outcome.expected_route, 0) + 1
        if outcome.passed:
            per_route_correct[outcome.expected_route] = per_route_correct.get(outcome.expected_route, 0) + 1

    per_route_exact_match = {
        route: _safe_ratio(per_route_correct.get(route, 0), count)
        for route, count in per_route_total.items()
    }

    return {
        "overall_case_accuracy": _safe_ratio(exact_matches, total),
        "route_accuracy": _safe_ratio(route_matches, total),
        "status_accuracy": _safe_ratio(status_matches, total),
        "verified_precision": verified_precision,
        "unverified_precision": unverified_precision,
        "abstention_accuracy": abstention_accuracy,
        "llm_only_accuracy": llm_only_accuracy,
        "total_cases": total,
        "passed_cases": exact_matches,
        "per_route_exact_match": per_route_exact_match,
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

    per_route_minimums = thresholds.get("per_route_minimums", {})
    per_route_actual = metrics.get("per_route_exact_match", {})
    for route, minimum in per_route_minimums.items():
        actual = per_route_actual.get(route)
        if actual is None:
            failures.append(f"Route metric not found for '{route}'")
            continue
        if actual < minimum:
            failures.append(
                f"Route '{route}' below threshold: actual={actual:.3f}, required={minimum:.3f}"
            )

    return failures


def run_evaluation(
    dataset_path: Path,
    llm_mode: str = "mock",
    threshold_path: Optional[Path] = None,
) -> EvalReport:
    cases = load_eval_cases(dataset_path)
    thresholds = load_thresholds(threshold_path)

    outcomes: list[CaseOutcome] = []

    with _patched_ollama_mode(llm_mode, cases):
        for case in cases:
            result = verification_module.verify_claim(case.text)
            actual_llm_status = _extract_llm_status(result)

            route_match = result.route == case.expected_route
            status_match = result.status == case.expected_status
            llm_match = case.expected_llm_status is None or actual_llm_status == case.expected_llm_status

            outcomes.append(
                CaseOutcome(
                    id=case.id,
                    text=case.text,
                    domain=case.domain,
                    expected_route=case.expected_route,
                    actual_route=result.route,
                    expected_status=case.expected_status,
                    actual_status=result.status,
                    expected_llm_status=case.expected_llm_status,
                    actual_llm_status=actual_llm_status,
                    route_match=route_match,
                    status_match=status_match,
                    llm_match=llm_match,
                    passed=route_match and status_match and llm_match,
                    message=result.message,
                )
            )

    metrics = _compute_metrics(outcomes)
    failures = _evaluate_thresholds(metrics, thresholds)

    return EvalReport(
        dataset_path=str(dataset_path),
        total_cases=len(cases),
        llm_mode=llm_mode,
        metrics=metrics,
        thresholds=thresholds,
        failures=failures,
        passed=len(failures) == 0,
        outcomes=outcomes,
    )
