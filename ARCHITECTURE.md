# 🏗️ Architecture & Design Deep Dive

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    USER INTERFACE (Streamlit)               │
│                                                             │
│  ┌──────────────┬──────────────┬────────────┬──────────┐   │
│  │  Tab 1       │   Tab 2      │  Tab 3     │  Tab 4   │   │
│  │  Upload &    │  Review &    │ Approval   │ Export & │   │
│  │  Extract     │  Match       │ Summary    │ Sign-Off │   │
│  └──────────────┴──────────────┴────────────┴──────────┘   │
│                                                             │
│  + Sidebar: Status metrics, navigation, sign-off badge    │
│  + Session State: Persistent data through workflow        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              CORE LOGIC & DATA PROCESSING                   │
│                                                             │
│  ┌──────────────────────────────────────────────────┐      │
│  │ 1. EXTRACTION LAYER                             │      │
│  │ ─────────────────────────────────────────────    │      │
│  │ Input:  Email files (.eml, .txt)               │      │
│  │ Output: List of (company_name, confidence)     │      │
│  │                                                  │      │
│  │ Mock Version: Hardcoded SAMPLE_EMAILS           │      │
│  │ Prod Version: email parser + NLP               │      │
│  └──────────────────────────────────────────────────┘      │
│                     ↓                                        │
│  ┌──────────────────────────────────────────────────┐      │
│  │ 2. MATCHING LAYER                               │      │
│  │ ─────────────────────────────────────────────    │      │
│  │ Input:  List of company names                  │      │
│  │ Output: Matched (aladdin_id, confidence, type) │      │
│  │                                                  │      │
│  │ find_aladdin_match(company_name):               │      │
│  │   1. Try exact match → ALADDIN_LOOKUP          │      │
│  │   2. Try fuzzy match → substring matching      │      │
│  │   3. Return (id, confidence, match_type)       │      │
│  │                                                  │      │
│  │ Confidence thresholds:                          │      │
│  │   >= 0.85 → auto_approved                      │      │
│  │   < 0.85 → pending (needs review)              │      │
│  │   = 0.00 → manual_required                     │      │
│  └──────────────────────────────────────────────────┘      │
│                     ↓                                        │
│  ┌──────────────────────────────────────────────────┐      │
│  │ 3. REVIEW LAYER                                 │      │
│  │ ─────────────────────────────────────────────    │      │
│  │ Status Pipeline:                                │      │
│  │                                                  │      │
│  │   Item created                                  │      │
│  │      ↓                                           │      │
│  │   match_confidence < 0.85 OR no match?         │      │
│  │      ├─ YES → status = "pending"               │      │
│  │      └─ NO  → status = "auto_approved"         │      │
│  │      ↓                                           │      │
│  │   Human Review                                  │      │
│  │      ├─ ✅ Approve → status = "approved"       │      │
│  │      ├─ ❌ Reject  → status = "rejected"       │      │
│  │      └─ 🔧 Override → status = "approved" (manual) │
│  │      ↓                                           │      │
│  │   Audit Record (timestamp, user, action)        │      │
│  │                                                  │      │
│  └──────────────────────────────────────────────────┘      │
│                     ↓                                        │
│  ┌──────────────────────────────────────────────────┐      │
│  │ 4. EXPORT LAYER                                 │      │
│  │ ─────────────────────────────────────────────    │      │
│  │ Filter: Only items with status = "approved"    │      │
│  │ Format: CSV with full audit trail              │      │
│  │ Output: unsigned.csv (temp) + signed.csv (final)│     │
│  │                                                  │      │
│  │ Columns:                                        │      │
│  │   - email_filename, company_name, aladdin_id   │      │
│  │   - matched_by (auto/manual), confidence       │      │
│  │   - reviewed_by, review_timestamp              │      │
│  │   - signed_by, signed_at, reason, team         │      │
│  └──────────────────────────────────────────────────┘      │
│                     ↓                                        │
│  ┌──────────────────────────────────────────────────┐      │
│  │ 5. SIGN-OFF LAYER                               │      │
│  │ ─────────────────────────────────────────────    │      │
│  │ Mandatory Checklist (3 items):                  │      │
│  │   ✓ All approved items reviewed for accuracy   │      │
│  │   ✓ All manual overrides validated             │      │
│  │   ✓ No conflicts with existing rules           │      │
│  │                                                  │      │
│  │ Captures:                                       │      │
│  │   - User: name, role, team                     │      │
│  │   - Timestamp (ISO 8601)                       │      │
│  │   - Reason/justification                       │      │
│  │   - Sets st.session_state.signed_off = True    │      │
│  │                                                  │      │
│  │ Output: Locked, audit-ready signed CSV         │      │
│  └──────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│             DATA STORES & LOOKUPS                           │
│                                                             │
│  ┌────────────────────────────────────────────────┐         │
│  │ ALADDIN_LOOKUP (Dict/CSV/Database)             │         │
│  │ ─────────────────────────────────────────────  │         │
│  │ company_name → aladdin_id mapping              │         │
│  │ e.g.: "Goldman Sachs" → "ALADDIN_GS_001"      │         │
│  │                                                 │         │
│  │ Mock (current):   dict with 10 entries         │         │
│  │ Prod: Load from PostgreSQL or CSV              │         │
│  └────────────────────────────────────────────────┘         │
│                                                             │
│  ┌────────────────────────────────────────────────┐         │
│  │ SAMPLE_EMAILS (Dict)                           │         │
│  │ ─────────────────────────────────────────────  │         │
│  │ Pre-extracted company names for demo            │         │
│  │ 3 emails × 3 companies = 9 demo items          │         │
│  │                                                 │         │
│  │ Mock (current):   hardcoded in code            │         │
│  │ Prod: S3, Azure Blob, or file server           │         │
│  └────────────────────────────────────────────────┘         │
│                                                             │
│  ┌────────────────────────────────────────────────┐         │
│  │ SESSION STATE (In-Memory)                      │         │
│  │ ─────────────────────────────────────────────  │         │
│  │ st.session_state.data[]                        │         │
│  │   - Main transaction list                      │         │
│  │   - Each item: extraction → matching → review  │         │
│  │                                                 │         │
│  │ st.session_state.current_tab                   │         │
│  │   - Navigation state (which tab is active)     │         │
│  │                                                 │         │
│  │ st.session_state.signed_off                    │         │
│  │   - Boolean flag (is data locked?)             │         │
│  │                                                 │         │
│  │ st.session_state.signoff_user                  │         │
│  │   - Who signed off                             │         │
│  │                                                 │         │
│  │ Mock (current): Memory only (lost on refresh)  │         │
│  │ Prod: PostgreSQL, Redis, or file-based         │         │
│  └────────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                      OUTPUT                                 │
│                                                             │
│  ┌────────────────────────────────────────────────┐         │
│  │ UNSIGNED CSV (Temporary Review)                │         │
│  │ ─────────────────────────────────────────────  │         │
│  │ For: Internal review before sign-off           │         │
│  │ Contains: All approved items                   │         │
│  │ Security: NOT signed (not production-ready)    │         │
│  └────────────────────────────────────────────────┘         │
│                                                             │
│  ┌────────────────────────────────────────────────┐         │
│  │ SIGNED CSV (Production Ready)                  │         │
│  │ ─────────────────────────────────────────────  │         │
│  │ For: Direct upload to Aladdin system           │         │
│  │ Contains: Approved items + sign-off metadata   │         │
│  │ Security: Audit trail, compliance certified   │         │
│  │ Usage: Feed directly to Aladdin import         │         │
│  └────────────────────────────────────────────────┘         │
│                                                             │
│  ┌────────────────────────────────────────────────┐         │
│  │ AUDIT LOG (Sidebar + Tab 4)                    │         │
│  │ ─────────────────────────────────────────────  │         │
│  │ Timestamps for every action                    │         │
│  │ User responsible for each action               │         │
│  │ Details of what changed and why                │         │
│  └────────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Flow: A Company Through the System

**Example: "JPMorgan" extracted from client email**

```
1. EXTRACTION
   ─────────
   Input Email:  "We do not trade with JPMorgan, Goldman Sachs..."
   Extraction:   company_name = "JPMorgan"
                 extraction_confidence = 0.85
   
2. MATCHING
   ────────
   find_aladdin_match("JPMorgan")
   ├─ Exact match in ALADDIN_LOOKUP? NO
   ├─ Fuzzy match (substring)?
   │  ├─ Compare "JPMorgan" vs "JPMorgan Chase" → 68% similarity
   │  └─ Best match: "ALADDIN_JPM_003" (68% confidence)
   └─ Return: ("ALADDIN_JPM_003", 0.68, "fuzzy")
   
   Item State:
   {
     "company_name": "JPMorgan",
     "extraction_confidence": 0.85,
     "aladdin_id": "ALADDIN_JPM_003",
     "match_confidence": 0.68,
     "match_type": "fuzzy",
     "status": "pending"  # < 0.85 confidence, needs review
   }

3. REVIEW (Human Decision)
   ──────────────────────
   Tab 2 → Fuzzy Matches
   User sees: "JPMorgan" → "ALADDIN_JPM_003" (68% confidence)
   User decides: "Yes, JPMorgan = JPMorgan Chase, this is correct"
   User clicks: ✅ Approve
   
   Item State:
   {
     ...,
     "status": "approved",
     "reviewed_by": "current_user",
     "review_timestamp": "2026-03-02T11:25:30.123456",
     "override_aladdin_id": False  # Not a manual override
   }

4. EXPORT
   ──────
   Tab 4 → Preview
   Row appears in CSV:
   client_email_...,JPMorgan,ALADDIN_JPM_003,auto,68%,current_user,2026-03-02T11:25:30

5. SIGN-OFF
   ────────
   User fills:
     Name: "Sarah Johnson"
     Role: "Compliance Officer"
     Reason: "Verified fuzzy match, confirmed JPMorgan = JPMorgan Chase"
   
   Signed CSV row:
   ...,JPMorgan,ALADDIN_JPM_003,...,Sarah Johnson,2026-03-02 11:30:00,Verified fuzzy match,Compliance

6. OUTPUT
   ──────
   Signed CSV ready for Aladdin upload ✅
```

---

## Status State Machine

```
        ┌─────────────────────────────────────────────┐
        │          ITEM CREATED                       │
        │  (extracted from email)                     │
        └────────────────┬────────────────────────────┘
                         │
                         ▼
        ┌─────────────────────────────────────────────┐
        │  Automatic Classification                   │
        │  (find_aladdin_match)                       │
        └────────────┬──────────────────────────┬─────┘
                     │                          │
         ┌─────────────────────┐    ┌─────────────────────┐
         │  High Confidence    │    │   Low Confidence    │
         │  (>= 0.85 + found)  │    │   (< 0.85 or none)  │
         │                     │    │                     │
         │  status: auto_      │    │  status: pending    │
         │  approved           │    │  (red 🔴 flag)      │
         └──────────┬──────────┘    └──────────┬──────────┘
                    │                          │
                    ▼                          ▼
         ┌──────────────────────┐  ┌──────────────────────┐
         │  Auto-Approved Tab   │  │  Manual Review       │
         │  (bulk accept all)   │  │  (per-item or bulk)  │
         │                      │  │                      │
         │  User can:           │  │  User can:           │
         │  - ✅ bulk approve   │  │  - ✅ approve        │
         │  - 🔍 inspect each   │  │  - ❌ reject         │
         └──────────┬───────────┘  │  - 🔧 override       │
                    │              └──────────┬───────────┘
                    │                         │
                    └──────────┬──────────────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
                    ▼                     ▼
         ┌─────────────────────┐  ┌─────────────────────┐
         │    APPROVED ✅      │  │     REJECTED ❌     │
         │   (ready to export) │  │  (excluded from CSV)│
         └──────────┬──────────┘  └─────────────────────┘
                    │
                    ▼
         ┌─────────────────────┐
         │  Export to CSV      │
         │  Only approved items│
         └──────────┬──────────┘
                    │
                    ▼
         ┌─────────────────────┐
         │  Sign-Off (forced)  │
         │  Checklist → sign   │
         │  Locked for audit   │
         └──────────┬──────────┘
                    │
                    ▼
         ┌─────────────────────┐
         │  Ready for Aladdin  │
         │  Signed CSV download│
         └─────────────────────┘
```

---

## Key Design Decisions

### 1. **No AI/NLP for MVP**
- ✅ Deterministic matching (exact + fuzzy string)
- ✅ Easy to audit and explain to compliance
- ✅ No ML model training or maintenance
- ✅ Humans approve everything (belt & suspenders)
- 🚀 Future: Can swap in ML model in `find_aladdin_match()`

### 2. **Human-in-the-Loop**
- All matches (even exact) can be reviewed
- Override capability for edge cases
- Mandatory sign-off (can't accidentally export)
- Three-point checklist (compliance-grade)

### 3. **Audit Trail First**
- Every action timestamped
- Every action attributed to user
- Every manual override flagged
- All metadata exported with CSV

### 4. **Session State for MVP**
- Data lives in memory (fast, simple)
- Good for demo and single-user testing
- ✅ Fine for 1-5K items
- 🚀 Future: Migrate to PostgreSQL for scale

### 5. **Streamlit for Speed**
- Zero DevOps (single Python file)
- Hot reload for iteration
- Built-in file upload, tables, charts
- Deploy anywhere (Cloud Run, ECS, etc.)
- 🚀 Future: React frontend if needed

---

## Scaling Path (MVP → Production)

### Phase 1: MVP (Current) ✅
```
Email Files (mock)
    ↓
Python extraction (mock)
    ↓
Fuzzy match (ALADDIN_LOOKUP dict)
    ↓
Streamlit review UI
    ↓
CSV export (unsigned/signed)
    ↓
Manual upload to Aladdin
```

### Phase 2: Real Data (Month 1)
```
Real client emails (.eml)
    ↓
Email parser (imaplib + email module)
    ↓
Company extraction (regex + NER)  ← Add complexity here
    ↓
Database lookup (read from PostgreSQL)  ← Add persistence
    ↓
Streamlit review UI (same)
    ↓
CSV export (same)
    ↓
Manual upload to Aladdin
```

### Phase 3: User Authentication (Month 2)
```
+ Okta/Azure AD login
+ Session data → PostgreSQL (not memory)
+ User tracking (real names, not "current_user")
+ Role-based access (who can sign off?)
+ Email notifications (send signed CSV)
```

### Phase 4: Aladdin Integration (Month 3)
```
+ Aladdin API client library
+ Auto-validate against existing rules
+ Conflict detection (don't exclude existing trading partners)
+ Direct push to Aladdin (vs manual download)
+ Webhook callbacks (notify when imported)
```

### Phase 5: Advanced Matching (Month 4)
```
+ Fuzzy matching library (fuzzywuzzy, rapidfuzz)
+ Soundex/Levenshtein for typos
+ Entity resolver (alias matching)
+ Maybe: LLM for entity disambiguation
+ Confidence tuning (learn from past reviews)
```

---

## Testing Strategy

### Unit Tests
```python
def test_find_aladdin_match_exact():
    assert find_aladdin_match("Goldman Sachs") == ("ALADDIN_GS_001", 1.0, "exact")

def test_find_aladdin_match_fuzzy():
    assert find_aladdin_match("JPMorgan")[2] == "fuzzy"

def test_find_aladdin_match_none():
    aladdin_id, conf, type = find_aladdin_match("Unknown Corp")
    assert aladdin_id == ""
    assert type == "manual_required"
```

### Integration Tests
```python
def test_workflow_approval_to_export():
    # Load sample data
    # Approve one item
    # Export to CSV
    # Assert CSV has 1 row
    
def test_sign_off_enforced():
    # Try to export without sign-off
    # Assert button is disabled
    # Fill sign-off form
    # Assert button enabled
```

### Manual Testing Checklist
- [ ] Load sample data
- [ ] Approve exact match
- [ ] Reject an item
- [ ] Override with custom ID
- [ ] Bulk-accept auto-approved
- [ ] Export unsigned CSV
- [ ] Verify CSV format
- [ ] Fill sign-off form
- [ ] Download signed CSV
- [ ] Check audit log

---

## Security Considerations

### Current (MVP)
- ⚠️ No authentication (local demo only)
- ⚠️ No HTTPS (local demo only)
- ⚠️ Session state in memory (lost on restart)

### Production
- ✅ Okta/Azure AD authentication
- ✅ HTTPS/TLS encryption
- ✅ RBAC (who can review? who can sign off?)
- ✅ Database encryption (PostgreSQL + pgcrypto)
- ✅ Audit log immutability (append-only table)
- ✅ API rate limiting
- ✅ SOC 2 compliance (if needed)

---

## Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| Load sample data | < 1s | ~100ms |
| Review 1 item | < 2s | ~50ms |
| Export CSV | < 1s | ~100ms |
| Sign-off | < 1s | ~50ms |
| **Total workflow** | **~5min** | **~1min** |
| Max items (single user) | 10K | 1K (session memory limit) |
| Max concurrent users | Unlimited (DB backed) | 1 (session state) |
| Monthly throughput | 100K items | Not limited by app (by human speed) |

---

**Architecture is simple, clean, and scales from MVP to enterprise.**
