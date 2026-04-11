# LLM Claim Formalization

**Hybrid symbolic-neural verification for natural language claims**

A Python library that extracts, formalizes, and verifies mathematical claims from natural language using a combination of symbolic reasoning (Z3, SAT solvers) and local LLMs.

## "I found an idea." — Ainsley Merritt, age 4

As my daughter Ainsley likes to say, I found an idea.

That idea was simple: LLMs (especially small, local ones) shouldn't have to "guess" at logic. This library provides a layer of formal rigor, turning fuzzy natural language into deterministic symbolic logic.

## 5-Minute Quickstart

**Prerequisites:** Install [Ollama](https://ollama.com/download) first if you don't have it.

**For everyone (recommended):**

```bash
# 1. Clone the repository
git clone https://github.com/michaelgideonmerritt/llm-claim-formalization.git
cd llm-claim-formalization

# 2. Run the install script (handles python/python3 automatically)
./install.sh

# 3. Pull the LLM model
ollama pull lfm2.5-thinking-128k

# 4. Run the demo
./run-demo.sh
```

The demo will auto-open in your browser at `http://localhost:8000`.

**Or try the quickstart example:**
```bash
./run-example.sh
```

## Installation

### Core Library Only
```bash
pip install llm-claim-formalization
```

### With Demo Interface
```bash
pip install llm-claim-formalization[demo]
```

### With Cloud LLM Support
```bash
pip install llm-claim-formalization[cloud-llms]
```

### For Development
```bash
git clone https://github.com/michaelgideonmerritt/llm-claim-formalization.git
cd llm-claim-formalization
pip install -e ".[dev]"
```

## Usage

### As a Library

```python
from llm_claim_formalization import extract_claim

text = "$100 with 50% off then 20% off"
claim = extract_claim(text)

if claim:
    if claim.insufficient_info:
        print(f"Missing: {claim.missing_info}")
        print(f"Clarification: {claim.suggested_clarification}")
    else:
        print(f"Equation: {claim.equation}")
        print(f"Confidence: {claim.confidence:.2f}")
else:
    print("No claim detected")
```

### Example Output

```
Input: "$100 with 50% off then 20% off"
Equation: (100 * 0.5) * 0.8 == 40
Confidence: 0.92
```

### With Verification

```python
from llm_claim_formalization import extract_claim
from llm_claim_formalization.backends import verify_with_z3, verify_with_ollama

text = "$100 with 50% off is $50"
claim = extract_claim(text)

if claim and claim.equation:
    result = verify_with_z3(claim.equation)
    print(f"Verified: {result['verified']}")
```

### Running the Demo

```bash
# Start the interactive web interface
python -m llm_claim_formalization.demo

# Or with custom port
uvicorn llm_claim_formalization.demo.server:app --port 8080
```

## Architecture

### 3-Stage Pipeline

1. **Entity Extraction** - Identifies quantities with units ($100, 50%, 25 mpg)
2. **Semantic Normalization** - Maps operations to canonical forms (discount, multiplication)
3. **Equation Synthesis** - Compiles formal mathematical expressions

### 5-Route Verification

- **structured** - High-confidence extraction → Z3 symbolic verification
- **formal** - Already formal math → Direct Z3 proof
- **llm** - Fallback to LLM reasoning (LFM 2.5)
- **insufficient_info** - Missing critical information (suggests clarification)
- **no_claim** - No verifiable claim detected

### Insufficient Info Detection

When information is missing, the system provides:

- **Normalized reason code** - Machine-friendly (`missing_base_value`, `missing_operation_type`)
- **Suggested clarification** - User-friendly prompt ("What starting value should I apply the 50% discount to?")
- **Detected values** - What was found in the input

This enables a feedback loop: input → insufficient_info → clarification → corrected input → success.

### Backends

- **Z3 Backend** - Symbolic SMT solver for formal proofs
- **Ollama Backend** - Local LLM (LFM 2.5) for semantic reasoning

## Examples

See `examples/quickstart.py` for runnable examples:

```bash
python examples/quickstart.py
```

### Example Claims

| Input | Status | Result |
|-------|--------|--------|
| "$100 with 50% off is $50" | ✓ Verified | `100 * 0.5 == 50` |
| "$100 with 50% off then 20% off" | ✓ Extracted | `(100 * 0.5) * 0.8 == 40` |
| "120 miles at 25 mpg is less than 4 gallons" | ✓ Verified | `120 / 25 < 4` |
| "A price increases by 100%" | ⚠ Insufficient Info | Missing: `missing_base_value` |

## Testing

```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/unit/
pytest tests/integration/
pytest tests/regression/

# With coverage
pytest --cov=src/llm_claim_formalization
```

## Project Structure

```
llm-claim-formalization/
├── src/llm_claim_formalization/
│   ├── core/
│   │   └── extraction.py          # 3-stage extraction pipeline
│   ├── backends/
│   │   ├── z3_backend.py          # Symbolic verification
│   │   ├── sat_backend.py         # SAT solver
│   │   └── ollama_backend.py      # Local LLM
│   └── demo/
│       ├── server.py              # FastAPI demo server
│       └── static/                # HTML/CSS/JS interface
├── examples/
│   └── quickstart.py              # Example usage
├── tests/
│   ├── unit/
│   ├── integration/
│   └── regression/
└── pyproject.toml
```

## Requirements

- **Python 3.10+**
- **[Ollama](https://ollama.com/download)** - Download and install from [ollama.com/download](https://ollama.com/download)
  - macOS: `brew install ollama` or download the app
  - Linux: `curl -fsSL https://ollama.com/install.sh | sh`
  - Windows: Download from [ollama.com/download](https://ollama.com/download)
- **LFM 2.5 model**: After installing Ollama, run `ollama pull lfm2.5-thinking-128k`

## Dependencies

### Core
- `z3-solver>=4.12.0` - Symbolic verification
- `ollama>=0.6.0` - Local LLM client

### Optional
- `fastapi>=0.100.0` - Demo web server
- `uvicorn>=0.20.0` - ASGI server
- `openai>=1.0.0` - Cloud LLM support
- `anthropic>=0.20.0` - Cloud LLM support

## Framework Agnostic

The core library has zero web framework dependencies. Use it with:

- FastAPI (see demo)
- Flask
- Django
- Streamlit
- Jupyter notebooks
- CLI tools
- Any Python application

## Design Philosophy

1. **Batteries Included** - Works immediately after `pip install`
2. **Local-First** - No API keys required (uses Ollama)
3. **Zero-Friction Demo** - Clone → Install → Run → Working interface
4. **Academic Rigor** - Formal verification with symbolic solvers
5. **Practical Usability** - Clear error messages and suggested clarifications
6. **Framework Agnostic** - Use with any Python framework or standalone

## License

MIT License - Free for everyone, forever.

See [LICENSE](LICENSE) for full terms.

## Contributing

This project welcomes community contributions. However, please note:

- Bug reports are welcome via GitHub Issues
- Feature requests will be reviewed but may not receive immediate response
- Pull requests are appreciated but review times may vary
- For support, please consult documentation first

See [SUPPORT.md](SUPPORT.md) for details on community expectations.

## Repository

[https://github.com/michaelgideonmerritt/llm-claim-formalization](https://github.com/michaelgideonmerritt/llm-claim-formalization)

## Acknowledgments

This project is a bridge built upon the shoulders of giants. LLM Claim Formalization would not be possible without the groundbreaking research, engineering, and commitment to both open-source and accessible AI from the following organizations:

### LLM Technology

- **Anthropic**: For the nuanced reasoning of Claude Opus 4.5.
- **OpenAI**: For the industry-defining capabilities of GPT 5.3 and the foundational work in gpt-oss-20b.
- **Google**: For the expansive multi-modal power of Gemini and the highly efficient, accessible Gemma 4.
- **Meta**: For the incredible gift to the open-source community that is Llama 3.2.
- **Microsoft**: For proving that "small is powerful" with the Phi 4 series.
- **MIT**: For the specialized mathematical reasoning capabilities of lfm2.5-thinking.

### Open Source Tools

- **[Z3 Theorem Prover](https://github.com/Z3Prover/z3)** - Microsoft Research's SMT solver
- **[PySAT](https://pysathq.github.io/)** - Alexey Ignatiev, Antonio Morgado, and Joao Marques-Silva (Monash University)
- **[Ollama](https://ollama.ai/)** - Jeffrey Morgan and Michael Chiang for local LLM runtime
- **[FastAPI](https://fastapi.tiangolo.com/)** - Sebastián Ramírez (@tiangolo)
- **[Pydantic](https://pydantic.dev/)** - Samuel Colvin and the Pydantic team
- **[Uvicorn](https://uvicorn.dev/)** - Tom Christie and Encode
- **[pytest](https://pytest.org/)** - Holger Krekel and the pytest-dev community

To the researchers, engineers, and support staff at these institutions: thank you for your hard work. I am grateful for the privilege of building on top of the tools you have created, whether through paid APIs or open-weight models. You are the reason "found ideas" can become reality.

## Citation

If you use this library in academic work, please cite:

```bibtex
@software{llm_claim_formalization,
  title = {LLM Claim Formalization},
  author = {Merritt, Michael},
  year = {2026},
  url = {https://github.com/michaelgideonmerritt/llm-claim-formalization},
  license = {MIT}
}
```
