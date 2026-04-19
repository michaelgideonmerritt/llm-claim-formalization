# LLM Claim Formalization

Hybrid symbolic-neural verification for natural-language claims.

This project now provides a **self-contained** verification pipeline with explicit routing and status reporting:

- Formal verification where possible (Z3)
- Structured extraction for common quantitative claims
- Routed adapters for propositional/FOL/statistical/policy/factual/subjective claims
- Evidence-backed factual review with local citation retrieval
- Explicit abstention (`insufficient_info`, `cannot_formally_verify`, `no_claim`) instead of silent failure

## What It Verifies Today

### Formally verified routes
- Arithmetic/formal expressions (`2 + 2 == 4`, `120 / 25 < 4`)
- Structured quantitative claims such as:
  - discounts (`$100 with 50% off then 20% off is $40`)
  - rate comparisons (`120 miles at 25 miles per gallon is less than 4 gallons`)
  - simple budget math (`I have $200, spend $85 and $120, still have money left`)

### Routed general-use adapters
- Propositional logic (`if ... then ... therefore ...`) with theorem proving
- First-order logic (`all ... are ...`) with theorem proving
- Statistical claims (`p`, `alpha`) with formal threshold checks
- Policy/rule and subjective claims with explicit `cannot_formally_verify` guidance
- Factual claims with stance-aware citation retrieval (`support` / `contradict` / `neutral`)

### Abstention routes
- `insufficient_info`: missing critical operands (e.g., percentage with no base value)
- `cannot_formally_verify`: claim detected, but route lacks formal specification or evidence
- `no_claim`: no verifiable claim detected

## Production-Oriented Changes

- Removed hardcoded dependency on an external local project path.
- Replaced unsafe `exec` in Z3 backend with a restricted AST parser.
- Hardened Ollama parsing to avoid false positives from substring matching.
- Added deterministic routing and typed result payloads.
- Added strict typed IR per route and schema validation.
- Added pluggable domain adapters and local evidence retrieval for factual claims.
- Replaced broken tests with package-native unit/integration/regression suites.

## Installation

### Prerequisites
- Python 3.10+
- [Ollama](https://ollama.com/download)
- A local model (default: `lfm2.5-thinking-128k:latest`)

### Setup

```bash
git clone https://github.com/michaelgideonmerritt/llm-claim-formalization.git
cd llm-claim-formalization
./install.sh
```

`install.sh` now:

- creates a fresh virtualenv
- installs project dependencies
- verifies or installs Ollama (macOS/Linux)
- starts `ollama serve` if needed
- pulls the configured model (`LLM_CF_OLLAMA_MODEL`, default `lfm2.5-thinking-128k:latest`)

## Usage

### Verified Question-Answering (NEW!)

The **verified QA interface** combines LLM knowledge with formal verification in a feedback loop:

1. User asks question
2. **Verifier**: Classifies question type (routing)
3. **LLM**: Generates answer using vast training knowledge
4. **Verifier**: Checks if answer is deterministic and logical
   - ✅ YES → Send to user
   - ❌ NO → Send rejection reason back to LLM
5. **LLM**: Fixes answer and retries
6. Loop until verified or max retries

This provides **deterministic, hallucination-free answers** with the full knowledge of the LLM.

```bash
# Interactive verified QA
./run-verified-qa.sh

# Demo showing feedback loop
python3 demo_verified_qa.py
```

**Python API:**

```python
from llm_claim_formalization.verified_qa import ask_verified_question

result = ask_verified_question("What is 2 + 2?")
print(result.answer)           # "2 + 2 = 4"
print(result.verified)         # True
print(result.attempts)         # Number of LLM attempts
print(result.rejection_history)  # Shows feedback loop iterations
```

### Library API

```python
from llm_claim_formalization import verify_claim

result = verify_claim("$100 with 50% off then 20% off is $40")
print(result.status)      # verified
print(result.route)       # structured
print(result.equation)    # normalized equation used by solver
print(result.comparison)  # llm-only vs llm+verifier comparison
```

### Extraction-only API

```python
from llm_claim_formalization import extract_claim

claim = extract_claim("A price increases by 100%")
if claim and claim.insufficient_info:
    print(claim.missing_info)
    print(claim.suggested_clarification)
```

### Demo

```bash
./run-demo.sh
```

`run-demo.sh` re-checks Ollama availability and model presence before launch.

Then open `http://localhost:8000`.

Direct module run still works:

```bash
python -m llm_claim_formalization.demo
```

## Route/Status Contract

`verify_claim(...)` returns a structured result with:

- `route`: `structured | formal | propositional | fol | statistical | policy_rule | factual | subjective | insufficient_info | no_claim`
- `status`: `verified | unverified | computed | evidence_backed | llm_only | insufficient_info | no_claim | cannot_formally_verify | error`
- `message`, `confidence`, `equation`, `comparison`, `citations`, and optional clarification fields
- factual routes may return `unverified` when contradictory evidence dominates

`computed` means an arithmetic expression was computable but did not include a boolean assertion to prove/refute.

## Security Notes

- Z3 input is parsed through a restricted AST parser.
- Function calls, imports, attribute access, and arbitrary code execution payloads are rejected.
- Unsupported syntax returns structured errors.

## Testing and Quality Gates

```bash
pytest
ruff check src tests --no-cache
mypy src --cache-dir /tmp/mypy-llm-claim-formalization
llm-cf-eval --llm-mode mock --enforce-thresholds
```

The benchmark gate uses:

- `benchmarks/general_claims_eval.jsonl` (cross-domain routed cases)
- `benchmarks/evidence_corpus.jsonl` (default factual evidence corpus)
- `benchmarks/thresholds.json` (minimum metric thresholds)

### User-Centric Suite

For real-world user question testing (functionality + accuracy + speed):

```bash
# Fast deterministic run (CI-friendly)
llm-cf-user-eval --llm-mode mock --iterations 2 --output-json /tmp/user-suite-mock.json

# Live local-model run
llm-cf-user-eval \
  --llm-mode live \
  --thresholds benchmarks/user_suite_live_thresholds.json \
  --output-json /tmp/user-suite-live.json
```

Default dataset and thresholds:

- `benchmarks/user_questions_eval.jsonl`
- `benchmarks/user_suite_thresholds.json` (target)
- `benchmarks/user_suite_live_thresholds.json` (live baseline)

Reported metrics include:

- route/status/reason accuracy
- functionality accuracy (required output fields present)
- consistency accuracy across repeated runs
- latency mean/p50/p95/max/min
- SLA pass-rate (`max_latency_ms` per case)
- per-category exact-match accuracy

### Eval Harness

```bash
# Run benchmark with deterministic mock LLM labels (CI-safe)
llm-cf-eval --llm-mode mock --enforce-thresholds

# Run with live Ollama responses
llm-cf-eval --llm-mode live --output-json /tmp/eval-report.json
```

This creates a release gate for:

- overall case accuracy
- route accuracy
- status accuracy
- verified/unverified precision
- abstention quality (`insufficient_info`/`cannot_formally_verify`/`no_claim`)
- llm-only verdict accuracy

### Nightly Live Drift Tracking

A scheduled workflow runs live evaluations and uploads JSON + logs as artifacts:

- Workflow: `.github/workflows/nightly-live-eval.yml`
- Schedule: daily at `05:30 UTC`
- Manual trigger: GitHub Actions `workflow_dispatch` with optional `model` input
- Live thresholds: `benchmarks/live_thresholds.json`

Model selection order in workflow:

1. manual dispatch `model` input
2. repository variable `LLM_CF_OLLAMA_MODEL`
3. fallback `llama3.2:3b`

## Configuration

- `LLM_CF_OLLAMA_MODEL`: override default Ollama model (`lfm2.5-thinking-128k:latest`)
- `LLM_CF_FACTUAL_STANCE_MODE`: factual stance strategy (`hybrid` default, `heuristic`, or `nli`)

## Adapter Plugins

You can override route adapters at runtime:

```python
from llm_claim_formalization import Route, register_adapter, unregister_adapter
from llm_claim_formalization.core.adapters import DomainAdapter, AdapterResult
from llm_claim_formalization.core.ir import ClaimIR, VerificationStatus, ReasonCode

class MyPolicyAdapter(DomainAdapter):
    route = Route.policy_rule
    def verify(self, ir: ClaimIR) -> AdapterResult:
        return AdapterResult(
            status=VerificationStatus.verified,
            reason=ReasonCode.policy_rule_claim,
            message="Custom policy engine result",
            confidence=1.0,
        )

register_adapter(Route.policy_rule, MyPolicyAdapter(), overwrite=True)
# ... run verification ...
unregister_adapter(Route.policy_rule)  # restore default adapter
```

### Ollama Helper Script

Use the helper directly when troubleshooting setup:

```bash
# Ensure Ollama service is running and model is installed
./scripts/setup-ollama.sh --model lfm2.5-thinking-128k:latest

# Attempt automatic Ollama install if missing (macOS/Linux)
./scripts/setup-ollama.sh --install --model llama3.2:3b

# Verify model exists without pulling
./scripts/setup-ollama.sh --no-pull --model lfm2.5-thinking-128k:latest
```

## Limitations

- Not every natural-language claim is formally verifiable.
- `evidence_backed` indicates retrieved support snippets, not contradiction proofs.
- Multi-hop legal/scientific fact-checking still requires stronger retrieval/ranking and source trust policies.

## License

MIT
