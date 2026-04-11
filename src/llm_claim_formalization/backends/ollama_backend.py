import ollama
from typing import Optional

DEFAULT_MODEL = "lfm2.5-thinking-128k:latest"

def verify_with_ollama(claim: str, model: str = DEFAULT_MODEL) -> dict:
    prompt = f"""Verify this mathematical claim. Respond with ONLY 'true' or 'false'.

Claim: {claim}

Verification:"""

    response = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.1}
    )

    answer = response['message']['content'].strip().lower()
    verified = "true" in answer

    return {
        "verified": verified,
        "model": model,
        "raw_response": response['message']['content']
    }
