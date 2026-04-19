from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..core import verify_claim

app = FastAPI(title="LLM Claim Formalization Demo")

static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


class VerifyRequest(BaseModel):
    claim: str = Field(..., min_length=1, max_length=5000)


@app.post("/api/verify")
async def verify(request: VerifyRequest) -> dict:
    return verify_claim(request.claim).to_dict()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(str(static_dir / "index.html"))
