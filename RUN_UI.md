# Running the Verified QA Web UI

## Quick Start

```bash
# Start the demo server
./run-demo.sh

# Or manually:
source venv/bin/activate
python3 -m llm_claim_formalization.demo
```

Then open your browser to:
- **http://localhost:8000** - Main page (claim verification)
- **http://localhost:8000/static/qa.html** - Verified Question-Answering UI ✨

## The Verified QA UI

### What It Does

The verified QA interface provides an interactive web UI for the feedback loop system:

1. **User asks question** in the text box
2. **System processes**:
   - Verifier classifies question type
   - LLM generates answer
   - Verifier checks answer
   - If rejected → LLM retries with feedback
3. **User sees results**:
   - ✅ Verified answer (if passed)
   - 🔄 Feedback loop history (if retries happened)
   - ❌ Error details (if failed after max retries)

### Features

✅ **Live feedback loop visualization**
- See each attempt and rejection reason
- Watch the LLM self-correct

✅ **Question type routing**
- Arithmetic → Z3 formal verification
- Logic → Theorem proving
- Factual → Evidence-backed verification

✅ **Verification details**
- Status, route, confidence
- Complete transparency

✅ **Example questions**
- Click examples to try different question types
- Math, percentages, factual questions

## API Endpoints

### POST /api/ask

Ask a verified question:

```bash
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is 2 + 2?",
    "model": "llama3.2:3b",
    "max_retries": 3
  }'
```

Response:

```json
{
  "question": "What is 2 + 2?",
  "answer": "The answer to 2 + 2 is 4.",
  "verified": true,
  "attempts": 1,
  "question_type": "formal",
  "rejection_history": [],
  "final_verification": {
    "status": "verified",
    "route": "formal",
    "confidence": 1.0,
    "message": "Claim verified by formal solver."
  },
  "error": null
}
```

### POST /api/verify

Verify a claim (original functionality):

```bash
curl -X POST http://localhost:8000/api/verify \
  -H "Content-Type: application/json" \
  -d '{"claim": "2 + 2 = 4"}'
```

## Testing the Feedback Loop

To see the feedback loop in action, you can test with questions that might cause initial rejections:

**Example: Complex percentage**
```
Question: "If I have $100 and spend 50%, how much is left?"

Expected flow:
1. LLM generates: "You would have $50 left"
2. Verifier extracts and verifies claim
3. If verified → done
4. If rejected → LLM retries with feedback
```

## Configuration

### Environment Variables

```bash
# Model for question answering
export LLM_CF_QA_MODEL=llama3.2:3b

# Max retry attempts
export LLM_CF_MAX_RETRIES=3

# Demo server port
export PORT=8000
```

### Recommended Models

- **llama3.2:3b** - Fast, accurate (recommended)
- **gemma4:26b** - Slower, very accurate
- **devstral-small-2:24b** - Good balance

## Troubleshooting

### "Failed to generate verified answer after 3 attempts"

This means the LLM couldn't generate a verifiable answer even after retries.

**Solutions:**
1. Try a different model (larger models may be better at following feedback)
2. Increase max_retries
3. Simplify the question
4. Check Ollama is running: `ollama list`

### Port already in use

If port 8000 is taken:

```bash
export PORT=8001
python3 -m llm_claim_formalization.demo
```

### Slow responses

- LLM inference takes 1-10 seconds per attempt
- Multiple retries will take longer
- Use a faster model like llama3.2:3b

## Architecture

The UI communicates with the backend like this:

```
User Browser
    ↓
    POST /api/ask {"question": "..."}
    ↓
FastAPI Server
    ↓
Verified QA Module
    ↓
    1. Classify question (verifier)
    2. Generate answer (LLM)
    3. Verify answer (verifier)
    4. If rejected → feedback to LLM → retry
    5. Return result
    ↓
JSON Response
    ↓
User Browser (displays result with feedback history)
```

## What's Next

**Try these examples in the UI:**

1. **Simple math**: "What is 10 * 5?"
2. **Percentage**: "If I have $100 and spend 50%, how much is left?"
3. **Factual**: "At what temperature does water boil at sea level?"

Watch the verification process and feedback loop in action!

## Screenshots

The UI shows:
- Question input box
- "Ask" button
- Loading spinner during processing
- Results with ✅/❌ verification status
- Feedback loop history (if retries happened)
- Verification details (status, route, confidence)

All in a clean, responsive interface!
