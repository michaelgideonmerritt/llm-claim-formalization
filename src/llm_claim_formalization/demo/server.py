from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
import time

from ..core.extraction import extract_claim
from ..backends.z3_backend import verify_with_z3
from ..backends.ollama_backend import verify_with_ollama

app = FastAPI(title="LLM Claim Formalization Demo")

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

class VerifyRequest(BaseModel):
    claim: str

@app.post("/api/verify")
async def verify(request: VerifyRequest):
    start_time = time.time()

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

    return {
        "status": "verified" if verified else "unverified",
        "route": route,
        "equation": claim.equation if claim.equation else None,
        "confidence": claim.confidence,
        "execution_time_ms": round((time.time() - start_time) * 1000, 2)
    }

@app.get("/")
async def root():
    return FileResponse(str(static_dir / "index.html"))
