from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from .ir import Citation


@dataclass
class EvidenceDocument:
    source_id: str
    title: str
    text: str
    url: str | None = None


def _tokenize(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9]+", value.lower())
        if len(token) > 2
    }


_NEGATION_TOKENS = {"no", "not", "never", "none", "without", "cannot", "can't", "doesnt", "doesn't"}
_CONTRADICTION_PAIRS = {
    ("increase", "decrease"),
    ("increases", "decreases"),
    ("increased", "decreased"),
    ("true", "false"),
    ("valid", "invalid"),
    ("safe", "unsafe"),
    ("legal", "illegal"),
    ("effective", "ineffective"),
    ("requires", "forbids"),
}


def _root_path() -> Path:
    return Path(__file__).resolve().parents[3]


def resolve_evidence_path(explicit_path: str | None = None) -> Path | None:
    if explicit_path:
        path = Path(explicit_path)
        return path if path.exists() else None

    env_path = os.getenv("LLM_CF_EVIDENCE_PATH")
    if env_path:
        path = Path(env_path)
        return path if path.exists() else None

    default_path = _root_path() / "benchmarks" / "evidence_corpus.jsonl"
    return default_path if default_path.exists() else None


def load_evidence_corpus(path: Path) -> list[EvidenceDocument]:
    documents: list[EvidenceDocument] = []

    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            payload = json.loads(line)
            source_id = str(payload.get("id", "")).strip()
            title = str(payload.get("title", "")).strip()
            text = str(payload.get("text", "")).strip()
            url = payload.get("url")

            if not source_id or not title or not text:
                raise ValueError(f"Invalid evidence record at line {line_number}")

            documents.append(
                EvidenceDocument(
                    source_id=source_id,
                    title=title,
                    text=text,
                    url=url,
                )
            )

    return documents


def retrieve_citations(
    query: str,
    documents: list[EvidenceDocument],
    top_k: int = 3,
    min_score: float = 0.12,
) -> list[Citation]:
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    scored: list[tuple[float, EvidenceDocument]] = []
    for doc in documents:
        doc_tokens = _tokenize(doc.title + " " + doc.text)
        if not doc_tokens:
            continue

        overlap = query_tokens.intersection(doc_tokens)
        if not overlap:
            continue

        score = len(overlap) / len(query_tokens)
        scored.append((score, doc))

    scored.sort(key=lambda item: item[0], reverse=True)

    citations: list[Citation] = []
    for score, doc in scored[:top_k]:
        if score < min_score:
            continue

        snippet = doc.text
        if len(snippet) > 240:
            snippet = snippet[:237].rstrip() + "..."

        citations.append(
            Citation(
                source_id=doc.source_id,
                title=doc.title,
                snippet=snippet,
                score=round(score, 4),
                url=doc.url,
            )
        )

    return citations


def classify_stance(claim: str, snippet: str) -> str:
    """
    Lightweight lexical stance classifier.

    Returns one of:
    - support
    - contradict
    - neutral
    """
    claim_tokens = _tokenize(claim)
    snippet_tokens = _tokenize(snippet)
    if not claim_tokens or not snippet_tokens:
        return "neutral"

    overlap = claim_tokens.intersection(snippet_tokens)
    overlap_ratio = len(overlap) / len(claim_tokens)
    if overlap_ratio < 0.2:
        return "neutral"

    claim_lower = claim.lower()
    snippet_lower = snippet.lower()

    claim_has_negation = any(token in claim_lower for token in _NEGATION_TOKENS)
    snippet_has_negation = any(token in snippet_lower for token in _NEGATION_TOKENS)
    if claim_has_negation != snippet_has_negation:
        return "contradict"

    for left, right in _CONTRADICTION_PAIRS:
        left_in_claim = left in claim_lower
        right_in_claim = right in claim_lower
        left_in_snippet = left in snippet_lower
        right_in_snippet = right in snippet_lower
        if (left_in_claim and right_in_snippet) or (right_in_claim and left_in_snippet):
            return "contradict"

    if overlap_ratio >= 0.35:
        return "support"

    return "neutral"
