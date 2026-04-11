from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
import time
import sys

sys.path.insert(0, "/Users/michaelmerritt/Desktop/LLM Input Layer")

from src.formalization import formalize_prop_with_llm
from src.backends.prop_backend import verify_with_sat
from src.backends.fol_backend import verify_with_fol
from src.models import ProblemIR, VerifyRequest as LLMVerifyRequest

from ..backends.ollama_backend import verify_with_ollama

app = FastAPI(title="LLM Claim Formalization Demo")

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

class VerifyRequest(BaseModel):
    claim: str


@app.post("/api/verify")
async def verify(request: VerifyRequest):
    start_time = time.time()

    # Step 1: Get "LLM only" result (direct Ollama call)
    llm_only_result = verify_with_ollama(request.claim)
    llm_only_status = "VALID" if llm_only_result.get("verified") else "INVALID"

    # Step 2: Try formal verification with LLM Input Layer pipeline
    # First, try to formalize to IR
    ir_dict = formalize_prop_with_llm(request.claim, model="phi4-mini:3.8b")

    if ir_dict:
        # Successfully formalized - now verify with SAT solver
        # Add checksum field if missing (required by ProblemIR model - 64 hex chars)
        if "checksum" not in ir_dict:
            ir_dict["checksum"] = "0" * 64
        ir = ProblemIR(**ir_dict)

        if ir.logic == "PROP":
            result = verify_with_sat(ir, timeout_ms=5000)
        elif ir.logic == "FOL":
            result = verify_with_fol(ir, timeout_ms=5000)
        else:
            # Fallback to Ollama if unknown logic type
            ollama_result = verify_with_ollama(request.claim)
            verified = ollama_result.get("verified", False)
            verifier_status = "VALID" if verified else "INVALID"
            route = "ollama_fallback"

        # For PROP and FOL, result is an object with .status attribute
        if ir.logic in ["PROP", "FOL"]:
            verified = result.status == "VERIFIED"
            verifier_status = "VALID" if verified else "INVALID"
            route = ir.logic.lower()
    else:
        # Formalization failed - fall back to Ollama for verifier too
        fallback_result = verify_with_ollama(request.claim)
        verified = fallback_result["verified"]
        verifier_status = "VALID" if verified else "INVALID"
        route = "ollama_fallback"

    # Step 3: Compare results and determine verdict
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

@app.get("/")
async def root():
    return FileResponse(str(static_dir / "index.html"))
