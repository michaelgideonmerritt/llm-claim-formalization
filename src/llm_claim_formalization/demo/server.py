from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
import time
import re

from ..core.extraction import extract_claim
from ..backends.z3_backend import verify_with_z3
from ..backends.ollama_backend import verify_with_ollama

app = FastAPI(title="LLM Claim Formalization Demo")

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

class VerifyRequest(BaseModel):
    claim: str

def is_formal_logic_claim(text: str) -> bool:
    text_lower = text.lower()
    logic_keywords = [
        "if", "then", "therefore", "thus", "hence",
        "all", "some", "every", "exists", "any",
        "implies", "entails", "follows",
        "and", "or", "not", "nor"
    ]
    logic_patterns = [
        r'\bif\s+.+,?\s+then\b',
        r'\btherefore\b',
        r'\ball\s+\w+\s+are\b',
        r'\bsome\s+\w+\s+are\b',
    ]
    has_keywords = sum(1 for kw in logic_keywords if kw in text_lower.split()) >= 2
    has_patterns = any(re.search(pattern, text_lower) for pattern in logic_patterns)
    has_numbers = bool(re.search(r'\d', text))
    return (has_keywords or has_patterns) and not has_numbers

@app.post("/api/verify")
async def verify(request: VerifyRequest):
    start_time = time.time()

    is_logic = is_formal_logic_claim(request.claim)

    if is_logic:
        llm_only_result = verify_with_ollama(request.claim)
        llm_only_status = "VALID" if llm_only_result.get("verified") else "INVALID"

        llm_with_verifier = verify_with_ollama(request.claim)
        verified = llm_with_verifier["verified"]
        verifier_status = "VALID" if verified else "INVALID"
        route = "formal_logic"

        if llm_only_status == verifier_status:
            if verified:
                verdict = "LLM_CORRECT"
                verdict_message = "LLM reasoning confirmed by formal verification"
            else:
                verdict = "BOTH_AGREE_INVALID"
                verdict_message = "Both agree claim is invalid"
        else:
            if verified and not llm_only_result.get("verified"):
                verdict = "LLM_OVERLY_CAUTIOUS"
                verdict_message = "LLM was overly cautious - claim is actually provably true"
            else:
                verdict = "LLM_ERROR_CAUGHT"
                verdict_message = "CRITICAL: Verifier caught LLM hallucination! LLM claimed valid, but it's provably false."

        return {
            "status": "verified" if verified else "unverified",
            "route": route,
            "equation": None,
            "confidence": 1.0,
            "execution_time_ms": round((time.time() - start_time) * 1000, 2),
            "comparison": {
                "llm_only": llm_only_status,
                "llm_plus_verifier": verifier_status,
                "agreement": llm_only_status == verifier_status,
                "verdict": verdict,
                "verdict_message": verdict_message
            }
        }

    claim = extract_claim(request.claim)

    if not claim:
        return {
            "status": "no_claim",
            "message": "No verifiable claim detected",
            "execution_time_ms": round((time.time() - start_time) * 1000, 2)
        }

    if claim.insufficient_info:
        return {
            "status": "insufficient_info",
            "reason_code": claim.missing_info,
            "suggested_clarification": claim.suggested_clarification,
            "detected_values": [q.span_text for q in claim.quantities],
            "execution_time_ms": round((time.time() - start_time) * 1000, 2)
        }

    llm_only_result = verify_with_ollama(request.claim)
    llm_only_status = "VALID" if llm_only_result.get("verified") else "INVALID"

    if claim.equation:
        z3_result = verify_with_z3(claim.equation)
        route = "structured"
    else:
        z3_result = {"verified": False}
        route = "llm_fallback"

    if not z3_result.get("verified"):
        llm_result = verify_with_ollama(request.claim)
        verified = llm_result["verified"]
        route = "llm"
    else:
        verified = True

    verifier_status = "VALID" if verified else "INVALID"

    if llm_only_status == verifier_status:
        if verified:
            verdict = "LLM_CORRECT"
            verdict_message = "LLM reasoning confirmed by formal verification"
        else:
            verdict = "BOTH_AGREE_INVALID"
            verdict_message = "Both agree claim is invalid"
    else:
        if verified and not llm_only_result.get("verified"):
            verdict = "LLM_OVERLY_CAUTIOUS"
            verdict_message = "LLM was overly cautious - claim is actually provably true"
        else:
            verdict = "LLM_ERROR_CAUGHT"
            verdict_message = "CRITICAL: Verifier caught LLM hallucination! LLM claimed valid, but it's provably false."

    return {
        "status": "verified" if verified else "unverified",
        "route": route,
        "equation": claim.equation if claim.equation else None,
        "confidence": claim.confidence,
        "execution_time_ms": round((time.time() - start_time) * 1000, 2),
        "comparison": {
            "llm_only": llm_only_status,
            "llm_plus_verifier": verifier_status,
            "agreement": llm_only_status == verifier_status,
            "verdict": verdict,
            "verdict_message": verdict_message
        }
    }

@app.get("/")
async def root():
    return FileResponse(str(static_dir / "index.html"))
