# Benchmark Files

## `general_claims_eval.jsonl`
JSONL benchmark for route/status regression testing across:

- arithmetic (`structured`, `formal`)
- propositional logic
- first-order logic (`fol`)
- statistical claims
- policy/rule claims
- factual claims with evidence retrieval
- subjective claims
- abstention categories (`insufficient_info`, `no_claim`)

Each line supports:

- `id`: stable case id
- `text`: input claim text
- `domain`: domain label for analysis
- `expected_route`: one of `Route` enum values from `src/llm_claim_formalization/core/ir.py`
- `expected_status`: one of `VerificationStatus` enum values from `src/llm_claim_formalization/core/ir.py`
- `expected_llm_status` (optional): `VALID | INVALID | UNKNOWN | ERROR`
- `criticality` (optional): `low | medium | high`
- `notes` (optional)

## `evidence_corpus.jsonl`
Default local evidence corpus used for factual-route retrieval in tests and demo runs.

The factual adapter now classifies retrieved snippets as `support`, `contradict`, or `neutral`.
When `LLM_CF_FACTUAL_STANCE_MODE` is `hybrid` or `nli`, this can include local Ollama NLI signals.
Expected factual outcomes can therefore include:

- `evidence_backed` (supporting evidence found)
- `unverified` (contradictory evidence dominates)
- `cannot_formally_verify` (mixed/weak evidence)

## `live_thresholds.json`
Thresholds used by nightly live Ollama evaluation (`.github/workflows/nightly-live-eval.yml`).
These are intentionally looser than `thresholds.json` to absorb model-response variability while still catching route/status drift.

## `user_questions_eval.jsonl`
User-centric benchmark with general questions people actually ask, covering:

- shopping/math questions
- travel/rate checks
- logic and statistical reasoning
- factual verification requests
- policy/subjective claims
- insufficient-information prompts
- non-verification conversational text

Additional per-case fields include functional requirements and speed targets:

- `require_equation`
- `require_comparison`
- `require_citations`
- `require_clarification`
- `max_latency_ms`

## `user_suite_thresholds.json`
Target thresholds for the user-centric suite. Includes:

- accuracy minimums (`minimums`)
- latency ceilings (`maximums`)
- per-category minimums (`per_category_minimums`)

## `user_suite_live_thresholds.json`
Live-operation baseline thresholds for the user-centric suite.
Use this file for ongoing live tracking when model/runtime variance is expected.

Each line supports:

- `id`: source identifier
- `title`: source title
- `text`: source body used for retrieval snippets
- `url` (optional): source URL for display

## `thresholds.json`
Metric gates used by the evaluator. Build can fail when current metrics fall below these values.

Run locally:

```bash
llm-cf-eval --llm-mode mock --enforce-thresholds
```
