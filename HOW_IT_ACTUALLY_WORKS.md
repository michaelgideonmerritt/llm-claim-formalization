# How the System Actually Works - The Truth

## Your Critical Question
**"How does it give responses? How does it know anything? The LLM does, right?"**

## The Answer: NO - It Doesn't "Know" Anything

The system is **NOT a question-answering system**. It's a **claim verification system**.

---

## What It Actually Does

### Input
```
User: "Is Paris the capital of France?"
```

### Output
```json
{
  "route": "factual",
  "status": "evidence_backed",
  "message": "Retrieved supporting evidence snippets for factual review.",
  "confidence": 1.0,
  "citations": [
    {
      "source_id": "E003",
      "title": "France Country Profile",
      "snippet": "Paris is the capital and largest city of France.",
      "score": 1.0,
      "stance": "support",
      "url": "https://www.britannica.com/place/France"
    }
  ]
}
```

### What the System Says
**"I found evidence that supports this claim."**

### What the System DOES NOT Say
**"Yes, Paris is the capital of France."**

---

## The Evidence Corpus - Where the "Knowledge" Really Lives

### The Corpus File
`benchmarks/evidence_corpus.jsonl` contains **4 documents written by humans:**

```json
{"id": "E001", "title": "CDC Heart Disease Risk Factors",
 "text": "Smoking damages blood vessels and increases the risk of heart disease and heart attack.",
 "url": "https://www.cdc.gov/heartdisease/risk_factors.htm"}

{"id": "E002", "title": "Water Boiling Point",
 "text": "At sea level, pure water boils at 100 degrees Celsius under standard atmospheric pressure.",
 "url": "https://www.nist.gov/"}

{"id": "E003", "title": "France Country Profile",
 "text": "Paris is the capital and largest city of France.",
 "url": "https://www.britannica.com/place/France"}

{"id": "E004", "title": "General Climate Notes",
 "text": "Atmospheric pressure affects boiling temperature and can shift the boiling point of liquids.",
 "url": "https://www.noaa.gov/"}
```

### Key Point
**A HUMAN wrote "Paris is the capital and largest city of France."**

The system did NOT:
- ❌ Learn this from training data
- ❌ Generate this text
- ❌ "Know" this fact
- ❌ Use an LLM to produce this answer

The system DID:
- ✅ Search for keywords: ['paris', 'capital', 'france']
- ✅ Find document E003 that contains those keywords
- ✅ Return that document to the user
- ✅ Let the USER read the evidence

---

## The Complete Process (Zero Knowledge, Zero LLM)

### Step 1: Route the Claim (Pattern Matching)
```python
text = "Is Paris the capital of France?"

# Regex check: contains "is" and "capital" (factual words)
if has_factual_words(text):
    route = "factual"  # ← No knowledge needed, just pattern matching
```

### Step 2: Load Evidence Corpus (Read from Disk)
```python
corpus = load_jsonl("evidence_corpus.jsonl")
# Returns: [Document1, Document2, Document3, Document4]
# ← No knowledge needed, just file I/O
```

### Step 3: BM25 Retrieval (Keyword Search)
```python
claim_tokens = tokenize("Paris is the capital of France")
# → ['paris', 'capital', 'france']

for doc in corpus:
    doc_tokens = tokenize(doc.text)
    overlap = claim_tokens ∩ doc_tokens
    score = len(overlap) / len(claim_tokens)

# Document E003:
#   doc_tokens = ['paris', 'capital', 'largest', 'city', 'france']
#   overlap = ['paris', 'capital', 'france']
#   score = 3/3 = 1.0 ← PERFECT MATCH
```

**No knowledge needed** - just set intersection math!

### Step 4: Lexical Stance (Pattern Matching)
```python
claim = "Paris is the capital of France"
snippet = "Paris is the capital and largest city of France."

claim_tokens = ['paris', 'capital', 'france']
snippet_tokens = ['paris', 'capital', 'largest', 'city', 'france']

overlap = ['paris', 'capital', 'france']
overlap_ratio = 3/3 = 1.0

# Check negation
has_negation_in_claim = False    # No "not", "never", etc.
has_negation_in_snippet = False  # No "not", "never", etc.

# Verdict
if overlap_ratio >= 0.35 and no_negation_mismatch:
    stance = "support"  # ← No knowledge needed, just counting tokens
```

### Step 5: Return Evidence
```python
return {
    "status": "evidence_backed",
    "citations": [snippet_from_E003],
    "message": "Retrieved supporting evidence snippets..."
}
# ← No knowledge needed, just returning what was found
```

---

## The Critical Difference

### Question-Answering System (LLM-based)
```
User: "What is the capital of France?"
  ↓
LLM (GPT-4, Claude, etc.):
  - Has learned from billions of documents
  - Generates new text from patterns
  - "Knows" that Paris is the capital
  - Outputs: "The capital of France is Paris."
  ↓
System: "The capital of France is Paris."
```

**The LLM GENERATES the answer.**

### Claim Verification System (Deterministic)
```
User: "Is Paris the capital of France?"
  ↓
System:
  - Searches evidence corpus (4 documents written by humans)
  - Finds: "Paris is the capital and largest city of France."
  - Returns: "Here's evidence that supports your claim"
  ↓
System: "status=evidence_backed, citations=[...]"
User: *Reads citation E003 to verify the claim themselves*
```

**The HUMAN AUTHOR of E003 provided the answer.**

---

## Where Is the LLM?

### In Deterministic Mode (Your Production Config)
```bash
export LLM_CF_FAST_PATH=true
export LLM_CF_FACTUAL_STANCE_MODE=heuristic
```

**LLM is used: NOWHERE**

All operations:
1. Routing → Regex pattern matching
2. Retrieval → Token set intersection (BM25)
3. Stance → Lexical pattern matching
4. Aggregation → Counting support/contradict

**Zero LLM calls. Zero learned knowledge. Zero generation.**

### In Hybrid Mode (Research Config)
```bash
export LLM_CF_FAST_PATH=false
export LLM_CF_FACTUAL_STANCE_MODE=hybrid
```

**LLM is used: For stance classification**

```python
# After BM25 retrieval, for each citation:
lexical_stance = classify_stance_with_patterns(claim, snippet)  # Deterministic

# THEN call LLM:
nli_result = verify_entailment_with_ollama(claim, snippet)
# LLM determines: entailment/contradiction/neutral

# Combine:
final_stance = select_stance(lexical_stance, nli_result, mode="hybrid")
```

**The LLM helps classify if the snippet supports the claim.**

**The LLM does NOT generate the answer - the snippet still comes from the corpus.**

---

## The Corpus Problem

Your evidence corpus has **4 documents**.

### What It Can Verify
✅ "Is Paris the capital of France?" → Yes (E003 says so)
✅ "Does smoking increase heart disease risk?" → Yes (E001 says so)
✅ "Does water boil at 100°C at sea level?" → Yes (E002 says so)

### What It CANNOT Verify
❌ "Is London the capital of England?" → No document mentions London
❌ "Is Berlin the capital of Germany?" → No document mentions Berlin
❌ "Does exercise reduce heart disease risk?" → No document mentions exercise

**The system can only verify claims that are explicitly addressed in the corpus.**

### Scaling the Corpus

To make this useful, you'd need:

**Small corpus (100 documents):**
- Manually curated facts
- High precision, low recall
- Good for narrow domains (company policies, product specs)

**Medium corpus (10,000 documents):**
- Wikipedia articles, textbooks
- Moderate precision, moderate recall
- Good for general knowledge

**Large corpus (1M+ documents):**
- Web scraping, news archives
- Lower precision, high recall
- Good for broad fact-checking

**Example:**
```bash
# Download Wikipedia dumps
wget https://dumps.wikimedia.org/enwiki/latest/enwiki-latest-pages-articles.xml.bz2

# Process to JSONL
python process_wikipedia.py > evidence_corpus.jsonl

# Now you have millions of facts
```

---

## Real-World Use Case

### Scenario: Corporate Policy Verification

**Evidence Corpus:**
```json
{"id": "P001", "title": "Access Control Policy",
 "text": "All administrative accounts must use two-factor authentication."}

{"id": "P002", "title": "Data Retention Policy",
 "text": "Customer data must be retained for a minimum of 7 years."}

{"id": "P003", "title": "Password Policy",
 "text": "Passwords must be at least 12 characters long and contain uppercase, lowercase, numbers, and symbols."}
```

**User queries:**
1. "Does policy require 2FA for admin accounts?"
   → Route: factual
   → Retrieval: P001 (keyword match: 'policy', 'admin', '2fa'/'two-factor')
   → Stance: support
   → Result: "Evidence backed" + citation to P001

2. "Can we delete customer data after 5 years?"
   → Route: factual
   → Retrieval: P002 (keyword match: 'customer', 'data', 'years')
   → Stance: contradict (claim says 5 years, policy says 7 years)
   → Result: "Unverified" + citation to P002 showing the conflict

**No LLM needed. Just search + pattern matching.**

---

## Why This Matters

### Advantages of No LLM
1. **Zero hallucinations** - System never generates false information
2. **100% traceable** - Every answer cites the source document
3. **Deterministic** - Same query always returns same result
4. **Fast** - No GPU inference, just keyword search (~20ms)
5. **Cheap** - No API costs, no GPU rental
6. **Auditable** - Can review corpus quality, update facts

### Disadvantages of No LLM
1. **Limited to corpus** - Can only verify what's in the documents
2. **No reasoning** - Can't infer "Paris is in Europe" from "Paris is in France"
3. **No paraphrasing** - "capital city" vs "capital" might miss
4. **Manual corpus** - Someone has to write/curate the evidence
5. **No synthesis** - Can't combine multiple facts

---

## The Bottom Line

### Your Question: "How does it know anything? The LLM does, right?"

**Answer: NO.**

The system doesn't "know" anything.

**The evidence corpus (written by humans) contains the knowledge.**

The system:
1. **Searches** the corpus (keyword matching)
2. **Returns** relevant documents (what humans wrote)
3. **Classifies** stance (pattern matching)
4. **Lets you** read the evidence and verify yourself

**In deterministic mode:**
- Zero LLM calls
- Zero learned knowledge
- Zero generation
- Just search, match, and cite

**The "knowledge" is in the corpus, not in the system.**

To improve it:
- ✅ Add more documents to the corpus
- ✅ Improve search (better BM25, semantic embeddings)
- ✅ Add domain-specific patterns
- ❌ Don't need an LLM (unless you want semantic understanding)

---

## Analogy

**Your system is like a librarian, not a professor:**

**Librarian (Your System):**
- User: "Is Paris the capital of France?"
- Librarian: "Let me check the encyclopedia..."
- Librarian: *Finds book, opens to France page*
- Librarian: "Here, this encyclopedia says 'Paris is the capital of France.'"
- User: *Reads the encyclopedia themselves*

**Professor (LLM):**
- User: "What is the capital of France?"
- Professor: "The capital of France is Paris."
- Professor: *Generated this from memory/knowledge*

**Your system retrieves and cites. It doesn't answer or generate.**
