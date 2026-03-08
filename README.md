# 🚀 AI-Powered Aladdin Exclusion Parser with PAUL Framework

Enterprise-grade system for parsing client exclusion lists from multiple formats (PDF, Email, CSV) using intelligent agents, human-in-the-loop review, and real-time Aladdin integration.

**Status:** Phase 2 Complete - 4 AI agents built with OpenAI GPT-4 + PAUL Constitutional Framework
- ✅ Phase 1: Extraction Agent (OCR + multi-format parsing)
- ✅ Phase 2: Entity Resolver + Aladdin Client + Confidence Aggregator + Orchestrator
- 🔄 Phase 3: FastAPI backend + Streamlit UI integration (in progress)

---

## 🎯 System Architecture

### High-Level Agent Pipeline

```
📄 Input Documents        🤖 Intelligent Agents             👥 Human Review         🔗 Aladdin API
┌─────────────────┐       ┌──────────────────────────┐      ┌──────────────┐      ┌───────────────┐
│  PDF / Email    │       │  EXTRACTION AGENT        │      │ Confidence   │      │ AladdinSDK    │
│  CSV / XLS      │  ───> │  (OCR + Layout Analysis) │──┐   │ Dashboard    │  ──> │ API Client    │
│  Raw Text       │       │  → ExtractedCompany      │  │   │              │      │               │
└─────────────────┘       │  confidence: 0.0-1.0     │  │   │ Auto-approve │      │ Returns:      │
                          └──────────────────────────┘  │   │ ≥ 0.90       │      │ - ISIN        │
                                    ↓                   │   │              │      │ - Entity ID   │
                          ┌──────────────────────────┐  │   │ Manual review│      │ - Match conf  │
                          │ ENTITY RESOLVER AGENT    │  │   │ < 0.85       │      └───────────────┘
                          │ (Fuzzy + GPT-4 NLP)     │  │   │              │
                          │ → NormalizedCompany      │──┼──→│ Approve /    │
                          │ confidence: 0.0-1.0      │  │   │ Override /   │
                          └──────────────────────────┘  │   │ Reject       │
                                    ↓                   │   │              │
                          ┌──────────────────────────┐  │   │ Track: user, │
                          │ ALADDIN CLIENT AGENT     │  │   │ reason,      │
                          │ (SDK + CSV Fallback)     │  │   │ timestamp    │
                          │ → AladdinMatch           │──┼──→└──────────────┘
                          │ ISIN + confidence        │  │
                          └──────────────────────────┘  │
                                    ↓                   │
                          ┌──────────────────────────┐  │
                          │ CONFIDENCE AGGREGATOR    │  │
                          │ Weighted Scoring:        │  │
                          │ OCR(20%) + Entity(30%)   │──┘
                          │ + Aladdin(50%)           │
                          │ → ConfidenceScore        │
                          │ overall: 0.0-1.0         │
                          └──────────────────────────┘
                                    ↓
                          ┌──────────────────────────┐
                          │ ORCHESTRATOR AGENT       │
                          │ Coordinates full         │
                          │ pipeline above           │
                          │ → ExclusionCandidate     │
                          │ ready for review         │
                          └──────────────────────────┘
```

### PAUL Framework (Constitutional AI Principles)

Each agent implements **Helpful → Harmless → Honest** principles:

```
┌─────────────────────────────────────────────────────────────────┐
│ PAUL = Projects + Auditing + Unified Logic + Lifecycle          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  HELPFUL: Actively assist with exclusion parsing               │
│  └─ Provide explanations and audit trails                      │
│  └─ Generate confidence breakdowns                             │
│                                                                 │
│  HARMLESS: Never corrupt data, fail safely                     │
│  └─ Validate all outputs (confidence 0.0-1.0)                 │
│  └─ Graceful fallback when APIs unavailable                    │
│  └─ Require human approval before Aladdin sync                │
│                                                                 │
│  HONEST: Explain confidence transparently                       │
│  └─ Document decision reasoning                                │
│  └─ Audit trail with agent versions                            │
│  └─ Admit limitations (manual_required for uncertain)          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Confidence Scoring Breakdown

```
┌─────────────────────────────────────────────────────────────────┐
│ Overall Confidence = Weighted Average of Source Signals         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  OCR Confidence (20% weight)                                   │
│  ├─ 0.95: Extracted from clear PDF text                       │
│  ├─ 0.80: Extracted from plain text email                      │
│  ├─ 0.75: Regex-based extraction from unstructured text       │
│  └─ 0.95: CSV structured data (highest confidence)            │
│                                                                 │
│  Entity Resolution Confidence (30% weight)                     │
│  ├─ 0.99: Exact alias match ("GS" → Goldman Sachs)           │
│  ├─ 0.85: Fuzzy match (>80% similarity)                       │
│  ├─ 0.70: GPT-4 semantic resolution                           │
│  └─ 0.00: Unresolved, manual_required                         │
│                                                                 │
│  Aladdin Match Confidence (50% weight)                         │
│  ├─ 1.00: Exact ISIN match from AladdinSDK                   │
│  ├─ 0.85: Fuzzy entity name match                             │
│  ├─ 0.60: Partial match (CSV fallback)                        │
│  └─ 0.00: No match found → manual_required                    │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│ FORMULA: (OCR × 0.20) + (Entity × 0.30) + (Aladdin × 0.50)   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Example: Goldman Sachs extracted from PDF email              │
│  ├─ OCR: 0.80 (from email text)                               │
│  ├─ Entity: 0.99 (exact alias "GS" match)                     │
│  ├─ Aladdin: 0.85 (fuzzy match on AladdinSDK)                │
│  └─ Overall = (0.80 × 0.20) + (0.99 × 0.30) + (0.85 × 0.50)│
│    = 0.16 + 0.297 + 0.425 = 0.882 → PENDING REVIEW            │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│ AUTO-APPROVAL THRESHOLD: ≥ 0.90 (high confidence)              │
│ MANUAL REVIEW THRESHOLD: < 0.60 (low confidence)               │
│ DEFAULT: 0.60-0.89 → PENDING (requires human judgment)         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🏗️ Project Structure

```
aladdin-exclusion-parser/
├── agents/                          # PAUL Framework Agents
│   ├── base_agent.py               # Abstract SkillAgent + SkillResult
│   ├── extraction_agent.py          # OCR + multi-format parsing
│   ├── entity_resolver.py           # Fuzzy matching + GPT-4 NLP
│   ├── aladdin_client.py            # AladdinSDK integration + CSV fallback
│   ├── confidence_aggregator.py      # Weighted scoring algorithm
│   ├── orchestrator.py              # Pipeline coordinator
│   ├── models.py                    # Pydantic: ExtractedCompany, etc
│   └── __init__.py                  # Agent exports
│
├── config/                          # Configuration & Constants
│   ├── llm.py                       # OpenAI LLM (GPT-4 Turbo)
│   ├── constants.py                 # Enums, thresholds, weights
│   ├── database.py                  # PostgreSQL config (Phase 3)
│   └── __init__.py
│
├── backend/                         # FastAPI Service (Phase 3)
│   ├── dashboard_api.py             # REST endpoints + WebSocket
│   ├── approval_service.py          # Approval workflow
│   └── __init__.py
│
├── tests/                           # TDD Test Suite
│   ├── agents/
│   │   ├── test_extraction_agent.py  # 10 tests ✓
│   │   ├── test_entity_resolver.py   # 6 tests ✓
│   │   ├── test_confidence_aggregator.py # 7 tests ✓
│   │   └── __init__.py
│   ├── integration/
│   │   ├── test_agent_pipeline.py   # E2E tests (Phase 3)
│   │   └── __init__.py
│   └── __init__.py
│
├── aladdin_exclusion_parser.py      # Streamlit UI (MVP)
├── aladdin_lookup_sample.csv        # Reference data (15 companies)
├── requirements.txt                 # Dependencies
├── pyproject.toml                   # Package config
├── pytest.ini                        # Test config
├── .env.example                     # Environment template
├── README.md                        # THIS FILE
├── ARCHITECTURE.md                  # Deep-dive design docs
└── QUICKSTART.md                    # 5-minute demo guide
```

---

## 🔧 Setup & Installation

### Prerequisites

- Python 3.9+
- OpenAI API key (GPT-4 Turbo)
- Optional: Aladdin SDK (aladdinsdk) for real API access
- Optional: PostgreSQL for persistence (Phase 3)

### Installation

```bash
# Clone repository
git clone https://github.com/vm799/aladdin-exclusion-parser.git
cd aladdin-exclusion-parser

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your OpenAI API key:
# OPENAI_API_KEY=sk-your-api-key-here

# Verify installation
python -m pytest tests/ -v
```

### Optional: AladdinSDK Integration

```bash
# Install AladdinSDK (if you have access)
pip install aladdinsdk keyring

# Configure (automatically uses CSV fallback if SDK unavailable)
export ASDK_USER_CONFIG_FILE=/path/to/aladdin/config.yaml
```

---

## 📊 Core Agents (Phase 2)

### 1. ExtractionAgent
**File:** `agents/extraction_agent.py` (327 lines)

Extracts companies from documents with OCR and layout analysis.

**Input:** File path + document type (PDF, Email, CSV, XLS, Text)

**Output:** `ExtractedCompany` objects with:
- `raw_name`: "Goldman Sachs"
- `ocr_confidence`: 0.95 (extraction quality)
- `extraction_source`: "pdf_page_1" (location)
- `source_doc`: "email_20260308.eml" (origin)

**Confidence Scores:**
- CSV: 0.95 (structured data)
- OCR: 0.75 (image-based extraction)
- Regex: 0.75 (pattern matching)
- Text: 0.80 (plain text)

---

### 2. EntityResolverAgent
**File:** `agents/entity_resolver.py` (350 lines)

Normalizes company names to canonical forms via alias matching + GPT-4.

**Input:** List of `ExtractedCompany` objects

**Output:** `NormalizedCompany` objects with:
- `canonical_name`: "Goldman Sachs" (standardized)
- `normalization_confidence`: 0.99 (via exact alias match)
- `normalization_notes`: "Exact alias match for 'GS'"
- `entity_type`: "Bank" (optional)

**Two-Stage Resolution:**
1. **Alias Lookup** (Fast, no cost)
   - Load CSV with company aliases
   - "GS", "Goldman", "GS Group" → "Goldman Sachs"
   - Confidence: 0.99 (exact) or 0.85 (fuzzy)

2. **GPT-4 Fallback** (Semantic disambiguation)
   - "Citi Bank" → Citigroup vs Citibank?
   - "Morgan Stanley" → Resolve variant spellings
   - Confidence: 0.70-0.85 (contextual)

---

### 3. AladdinClientAgent
**File:** `agents/aladdin_client.py` (330 lines)

Matches companies to Aladdin IDs via AladdinSDK or CSV fallback.

**Input:** `NormalizedCompany` object

**Output:** `AladdinMatch` object with:
- `aladdin_id`: "ALADDIN_GS_001"
- `isin`: "US3696041033" (optional)
- `match_confidence`: 0.85 (match quality)
- `match_type`: "EXACT" | "FUZZY" | "PARTIAL" | "MANUAL_REQUIRED"
- `api_response_time_ms`: 245.3 (for audit)

**Dual-Mode Operation:**
1. **SDK Mode** (Production)
   - Calls AladdinSDK via `POST /counterparties:search`
   - Returns live Aladdin database matches
   - Fallback if SDK unavailable

2. **CSV Fallback** (Testing/Offline)
   - Local `aladdin_lookup_sample.csv`
   - Identical interface, no API cost
   - 15 companies with aliases

---

### 4. ConfidenceAggregatorAgent
**File:** `agents/confidence_aggregator.py` (230 lines)

Combines multi-source confidence scores into weighted overall score.

**Input:** Confidence signals from extraction, entity, and Aladdin

**Output:** `ConfidenceScore` object with:
- `overall_confidence`: 0.882 (weighted average)
- `confidence_breakdown`: Dict of components + contributions
- `requires_human_review`: True/False
- `review_reason`: "Aladdin confidence 0.50 weak"

**Weighted Formula:**
```
overall = (OCR × 0.20) + (Entity × 0.30) + (Aladdin × 0.50)
```

**Thresholds:**
- ✅ **≥ 0.90**: Auto-approved (high confidence)
- 🔄 **0.60-0.89**: Pending (requires human review)
- ⚠️ **< 0.60**: Manual required (low confidence)

---

### 5. OrchestratorAgent
**File:** `agents/orchestrator.py` (300 lines)

Coordinates all agents in sequence, producing `ExclusionCandidate` objects.

**Pipeline:**
```
Extract → Normalize → Match → Aggregate → ExclusionCandidate
  ↓        ↓           ↓       ↓            ↓
 10x      10x         10x     10x         ExclusionCandidate
companies companies   companies candidates objects
```

**Error Handling:**
- If extraction fails: entire document fails
- If entity resolution fails: use raw name, low confidence
- If Aladdin lookup fails: flag manual_required
- If aggregation fails: return zero confidence

**Output:** `ExclusionCandidate` with complete pipeline results:
- Company identity (raw + normalized + matched)
- Confidence breakdown
- Auto-approval status
- Processing time
- Agent version tracking

---

## 📝 Data Models (Pydantic)

All models validate input automatically with Pydantic v2:

```python
# ExtractedCompany - from OCR/parsing
{
  "raw_name": "Goldman Sachs",
  "aliases": ["GS", "Goldman"],
  "ocr_confidence": 0.95,  # 0.0-1.0
  "extraction_source": "pdf_page_1",
  "source_doc": "email_20260308.eml"
}

# NormalizedCompany - standardized form
{
  "canonical_name": "Goldman Sachs",
  "extracted_from": {...},  # ExtractedCompany
  "normalization_confidence": 0.99,
  "normalization_notes": "Exact alias match"
}

# AladdinMatch - Aladdin API result
{
  "aladdin_id": "ALADDIN_GS_001",
  "isin": "US3696041033",
  "entity_name": "Goldman Sachs Inc",
  "match_confidence": 0.85,
  "match_type": "FUZZY",
  "asset_classes": ["Equities", "Fixed Income"]
}

# ConfidenceScore - aggregated scoring
{
  "overall_confidence": 0.882,
  "ocr_confidence": 0.80,
  "entity_resolution_confidence": 0.99,
  "aladdin_match_confidence": 0.85,
  "requires_human_review": true,
  "review_reason": "overall confidence 0.882 not meeting auto-approval threshold 0.90",
  "confidence_breakdown": {
    "ocr_weight": 0.20,
    "entity_weight": 0.30,
    "aladdin_weight": 0.50,
    "ocr_contribution": 0.16,
    "entity_contribution": 0.297,
    "aladdin_contribution": 0.425
  }
}

# ExclusionCandidate - ready for review
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "source_doc": "email_20260308.eml",
  "company_name": "Goldman Sachs",
  "extracted_company": {...},
  "normalized_company": {...},
  "aladdin_match": {...},
  "confidence_score": {...},
  "status": "pending",  # PENDING | AUTO_APPROVED | APPROVED | REJECTED | SYNCED
  "agent_version": "v1-orchestrator",
  "processing_time_ms": 2347.5
}
```

---

## 🧪 Testing (TDD)

### Test Coverage

```
Phase 1: 10 tests (all passing ✓)
├─ test_extraction_agent.py (10 tests)
│  ├─ PDF/CSV/text extraction
│  ├─ Validation skill
│  ├─ Deduplication
│  └─ Explanation skill

Phase 2: 13 tests (all passing ✓)
├─ test_entity_resolver.py (6 tests)
│  ├─ Exact alias matching
│  ├─ Fuzzy matching
│  ├─ Unknown name handling
│  └─ Batch processing
├─ test_confidence_aggregator.py (7 tests)
│  ├─ Auto-approval threshold
│  ├─ Manual review threshold
│  ├─ Weighted calculation
│  ├─ Breakdown validation
│  └─ Explanation generation

Total: 23/23 passing ✓
```

### Run Tests

```bash
# All tests
python -m pytest tests/ -v

# Specific test file
python -m pytest tests/agents/test_entity_resolver.py -v

# Single test
python -m pytest tests/agents/test_extraction_agent.py::TestExtractionAgentRed::test_failing_extract_from_text -v

# With coverage
python -m pytest tests/ --cov=agents --cov-report=html
```

---

## 🔗 Configuration

### Environment Variables

```bash
# .env file
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL=gpt-4-turbo
OPENAI_TEMPERATURE=0.3
OPENAI_MAX_TOKENS=4096

# Aladdin SDK (optional)
ASDK_USER_CONFIG_FILE=/path/to/aladdin/config.yaml
ALADDIN_ENVIRONMENT=test

# Database (Phase 3)
DATABASE_URL=postgresql://user:password@localhost:5432/aladdin_parser
DATABASE_ECHO=false
```

### Constants (config/constants.py)

Configured thresholds and weights:

```python
class ConfidenceThresholds:
    CSV_STRUCTURED = 0.95
    OCR_DEFAULT = 0.75
    ENTITY_EXACT_MATCH = 0.99
    ALADDIN_FUZZY = 0.85
    AUTO_APPROVAL_THRESHOLD = 0.90
    MANUAL_REVIEW_THRESHOLD = 0.60
```

---

## 🚀 Usage Example

### Basic Pipeline (Async)

```python
from agents import OrchestratorAgent
from config.llm import LLMConfig

# Initialize
llm = LLMConfig(api_key="sk-...")
orchestrator = OrchestratorAgent(llm)

# Process document
result = await orchestrator.execute({
    "file_path": "email_with_exclusions.pdf",
    "doc_type": "pdf",
    "source_doc": "client_email_20260308.eml"
})

# Results
candidates = result.data["candidates"]  # List of ExclusionCandidate

for candidate in candidates:
    print(f"Company: {candidate['company_name']}")
    print(f"Confidence: {candidate['confidence_score']['overall_confidence']:.2f}")
    print(f"Status: {candidate['status']}")
    print(f"Requires review: {candidate['confidence_score']['requires_human_review']}")
```

---

## 📈 Performance Targets (GSD Principle)

| Operation | Target | Notes |
|-----------|--------|-------|
| PDF extraction per page | < 5s | Tesseract OCR |
| Entity resolution per company | < 2s | Alias lookup or GPT-4 |
| Aladdin lookup per company | < 1s | SDK or CSV |
| Full pipeline (5 companies) | < 15s | All agents serial |
| Dashboard load | < 2s | HTTP polling |

**Note:** MVP optimizes for correctness over speed. Performance tuning in Phase 3.

---

## 🔐 Security & Compliance

### Phase 1-2 (Current MVP)
- ⚠️ No authentication (local-only)
- ⚠️ No encryption (in-memory session state)
- ⚠️ No persistence (data lost on refresh)
- ✅ Full audit trail (who, what, when)
- ✅ Graceful API fallback (works offline)

### Phase 3+ (Production)
- 🔄 Okta/Azure AD authentication
- 🔄 HTTPS/TLS encryption
- 🔄 PostgreSQL persistence
- 🔄 Role-based access control (RBAC)
- 🔄 Append-only audit logs
- 🔄 Aladdin API signing

---

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| README.md (this file) | System overview, setup, architecture |
| ARCHITECTURE.md | Deep-dive design decisions, scaling path |
| QUICKSTART.md | 5-minute demo walkthrough |
| Code Docstrings | Inline API documentation |

---

## 🤝 Contributing

### Development Workflow

1. Create feature branch: `git checkout -b feature/my-feature`
2. Write TDD tests (RED phase first)
3. Implement code (GREEN phase)
4. Refactor while tests pass (REFACTOR phase)
5. Commit with descriptive message
6. Push and create PR

### Code Style

- Python 3.9+ type hints required
- Pydantic models for all data structures
- Async/await for concurrency
- PAUL principles in agents (helpful/harmless/honest)

---

## 📞 Support

### Issues & Questions

- GitHub Issues: [vm799/aladdin-exclusion-parser/issues](https://github.com/vm799/aladdin-exclusion-parser/issues)
- Documentation: See ARCHITECTURE.md for detailed design

### Roadmap

- **Phase 3 (In Progress):** FastAPI backend + Streamlit UI integration
- **Phase 4 (Q2 2026):** Real Aladdin API + database persistence
- **Phase 5 (Q3 2026):** Advanced matching + user authentication

---

## 📄 License

[LICENSE FILE - TBD]

---

## 🙏 Acknowledgments

- **PAUL Framework:** Constitutional AI principles (Helpful + Harmless + Honest)
- **GSD Methodology:** Pragmatic, results-driven delivery
- **Aladdin SDK:** Official Counterparty API integration
- **OpenAI:** GPT-4 Turbo for semantic understanding

---

**Last Updated:** March 8, 2026
**Version:** v0.2.0 (Phase 2 - Agents Built)
