from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..core import verify_claim
from ..verified_qa import ask_verified_question

app = FastAPI(title="LLM Claim Formalization Demo")

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


class VerifyRequest(BaseModel):
    claim: str = Field(..., min_length=1, max_length=5000)


class QuestionRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=5000)
    model: str = Field(default=os.getenv("LLM_CF_QA_MODEL", "llama3.2:3b"))
    max_retries: int = Field(default=3, ge=1, le=10)


@app.post("/api/verify")
async def verify(request: VerifyRequest) -> dict:
    return verify_claim(request.claim).to_dict()


@app.post("/api/ask")
async def ask(request: QuestionRequest) -> dict:
    """
    Verified question-answering with feedback loop.

    Takes a question, generates answer with LLM, verifies it,
    and retries with feedback if rejected.
    """
    result = ask_verified_question(
        request.question,
        model=request.model,
        max_retries=request.max_retries,
    )

    return {
        "question": result.question,
        "answer": result.answer,
        "verified": result.verified,
        "attempts": result.attempts,
        "question_type": result.question_type,
        "rejection_history": result.rejection_history,
        "final_verification": result.final_verification,
        "error": result.error,
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(str(static_dir / "index.html"))
