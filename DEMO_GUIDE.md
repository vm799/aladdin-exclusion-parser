# 🎬 Demo Guide - Aladdin Exclusion Parser

**Last Updated:** 2026-03-08
**Status:** ✅ Ready for Demo with Full Fallback Support

---

## 📋 Quick Start (5 minutes)

### Option 1: Demo with Mock Data (No Backend Required)
```bash
# Install dependencies
pip install -r requirements.txt

# Run Streamlit (uses mock data automatically)
streamlit run aladdin_exclusion_parser.py
```

**Result:** Fully functional UI with realistic mock data. All approval workflows work.

---

### Option 2: Demo with Real Backend (10 minutes)

#### Terminal 1: Start FastAPI Backend
```bash
# Set up database (SQLite for demo)
export DATABASE_URL="sqlite+aiosqlite:///./aladdin_demo.db"

# Start backend
python -m uvicorn backend.app:app --reload --port 8001
```

**Expected Output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8001
INFO:     Database initialized successfully
```

#### Terminal 2: Start Streamlit Frontend
```bash
# In a new terminal, from project directory
export BACKEND_URL="http://localhost:8001"
streamlit run aladdin_exclusion_parser.py
```

**Result:** Streamlit connects to backend and displays real exclusion data with live approval workflow.

---

## 🎯 Demo Scenarios

### Scenario 1: High-Confidence Auto-Approval
**What to show:** System automatically approves high-confidence matches

1. Navigate to "Review & Match" tab
2. Look for items with confidence ≥ 0.90 and status = "auto_approved"
3. Point out confidence breakdown:
   - OCR: 0.95 (company extracted cleanly)
   - Entity Resolution: 0.99 (name normalized with high confidence)
   - Aladdin Match: 1.0 (exact ID match found)
   - **Overall: 0.98** → Auto-approved

**Why it matters:** Reduces manual review burden by auto-approving high-confidence matches

### Scenario 2: Manual Review & Approval
**What to show:** Analyst can review and approve pending items

1. Look for low-confidence items (status = "pending")
2. Click "Approve" button
3. Enter analyst name and reason
4. Show updated status: "approved"
5. Show audit trail entry

**Why it matters:** Human-in-the-loop ensures questionable matches get reviewed

### Scenario 3: Rejection Workflow
**What to show:** Analyst can reject items with explanation

1. Find a pending item with low confidence
2. Click "Reject" button
3. Provide rejection reason
4. Status changes to "rejected"

**Why it matters:** Prevents false positives from being included in exclusion list

### Scenario 4: Supervisor Override with Training Feedback
**What to show:** Supervisors can override decisions and capture training data

1. Click "Override" on an approved item
2. Change status (approved → rejected or vice versa)
3. Provide override reason
4. Add training feedback (e.g., "Increase entity match threshold to 0.85")
5. Status updates and audit trail records supervisor action

**Why it matters:** Captures human feedback to improve agent accuracy over time

### Scenario 5: Complete Audit Trail
**What to show:** Full transparency into decision pipeline

1. Click "Show Audit Trail" for any exclusion
2. Displays all agent actions:
   - **Extract**: Company extracted from document (OCR confidence)
   - **Resolve**: Name normalized to canonical form (entity confidence)
   - **Match**: Matched to Aladdin ID (match confidence)
   - **Aggregate**: Confidence scores combined (overall confidence)
   - **Auto-Approve/Approve**: Decision made (by agent or human)

**Why it matters:** Full traceability for compliance and debugging

---

## 🚀 Backend API Testing (Optional)

### Test with curl (if backend is running)

```bash
# Health check
curl http://localhost:8001/health | jq

# List exclusions
curl http://localhost:8001/api/exclusions | jq

# List pending only
curl "http://localhost:8001/api/exclusions?status=pending" | jq

# Get single exclusion
curl http://localhost:8001/api/exclusions/{id} | jq

# Create exclusion
curl -X POST http://localhost:8001/api/exclusions \
  -H "Content-Type: application/json" \
  -d @candidate.json | jq

# Approve exclusion
curl -X PATCH http://localhost:8001/api/exclusions/{id}/approve \
  -H "Content-Type: application/json" \
  -d '{"user_id": "demo@company.com", "reason": "Verified"}' | jq

# View audit trail
curl http://localhost:8001/api/exclusions/{id}/audit | jq
```

---

## 📊 Demo Data Features

### Real-World Scenarios
1. **High-confidence matches** (0.95+) → Auto-approved
2. **Medium-confidence matches** (0.60-0.89) → Pending review
3. **Low-confidence matches** (< 0.60) → Needs manual resolution
4. **Ambiguous names** (e.g., "Citi" = Citigroup or Citibank?) → Shows decision logic

### Confidence Score Breakdown
Shows how each component contributes to final decision:
```
OCR Confidence (20% weight)        = 0.95 × 0.20 = 0.19
Entity Resolution (30% weight)     = 0.99 × 0.30 = 0.297
Aladdin Match (50% weight)         = 1.0  × 0.50 = 0.50
                                   ────────────────────
                        Total:                      0.98
```

---

## 🔄 Data Flow During Demo

```
User Opens Streamlit
      ↓
App tries to connect to http://localhost:8001/health
      ↓
   ┌─────────────────────────┐
   │ Backend Available?      │
   └─────────────────────────┘
    /                          \
  YES                          NO
   ↓                            ↓
Fetch real data         Use mock data
from backend            (automatic fallback)
   ↓                            ↓
Display exclusions      Display sample
from database           exclusions
   ↓                            ↓
All actions use         All actions work
backend API             with mock data
   ↓                            ↓
Live approval           Demo approval
workflow                workflow
   └─────────────────┬──────────────┘
                     ↓
              Streamlit UI
          (same experience
           either way!)
```

---

## 📱 UI Tour

### Tab 1: Upload & Extract
- **Demo:** Shows extracted companies with OCR confidence
- **Features:** File upload, sample data loader
- **During Demo:** Point out OCR confidence scores

### Tab 2: Review & Match
- **Demo:** Shows extracted companies matched to Aladdin IDs
- **Features:** Filter by status, sort by confidence
- **During Demo:** Show high vs low confidence items

### Tab 3: Approval
- **Demo:** Review pending items and make approval decisions
- **Features:** Approve, reject, override buttons
- **During Demo:**
  1. Approve a high-confidence item
  2. Reject a low-confidence item
  3. Override a decision with training feedback

### Tab 4: Export & Sign-Off
- **Demo:** Final sign-off before pushing to Aladdin
- **Features:** Sign-off confirmation
- **During Demo:** Point out audit trail and metrics

---

## 🎓 Key Talking Points

### 1. Intelligence Pipeline
"Each company goes through an intelligent pipeline:
- **OCR Agent** extracts text from documents
- **Entity Agent** normalizes names (e.g., 'GS' → 'Goldman Sachs')
- **Aladdin Agent** finds the ISIN and ID
- **Confidence Agent** combines all signals"

### 2. Transparent Scoring
"No black boxes. You can see exactly why a company was approved or flagged:
- High OCR confidence + exact entity match + found ISIN = Auto-approve
- Low OCR confidence = Needs human review
- All decisions logged in audit trail"

### 3. Human-in-the-Loop
"AI doesn't decide alone. Analysts review:
- Questionable matches
- Edge cases
- Can override with feedback to improve the AI"

### 4. Compliance & Audit
"Every decision is tracked:
- Who made it (AI or human)
- When it was made
- Why it was made (reasoning from agents)
- Can prove compliance for regulators"

---

## ⚙️ Configuration

### Environment Variables
```bash
# Backend (if running)
DATABASE_URL=sqlite+aiosqlite:///./aladdin_demo.db
BACKEND_URL=http://localhost:8001
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8001

# Streamlit
STREAMLIT_LOGGER_LEVEL=info
```

### Streamlit Config (`.streamlit/config.toml`)
```toml
[client]
showErrorDetails = true

[logger]
level = "info"

[theme]
primaryColor = "#1B3A7D"
backgroundColor = "#F8F9FA"
```

---

## 🧪 What to Show vs What's Coming

### ✅ Demo Ready Now
- ✅ Company extraction with confidence scores
- ✅ Entity resolution and normalization
- ✅ Aladdin ID matching
- ✅ Confidence aggregation and breakdown
- ✅ Auto-approval at 90% threshold
- ✅ Manual approval/rejection workflow
- ✅ Supervisor override with training feedback
- ✅ Complete audit trail
- ✅ Dashboard metrics and filtering

### ⏳ Coming Next
- ⏳ Real document upload (PDF, email, CSV)
- ⏳ Live agent processing with real-time status
- ⏳ WebSocket updates for processing progress
- ⏳ Integration with real Aladdin API
- ⏳ Production PostgreSQL database
- ⏳ User authentication (OAuth)
- ⏳ Bulk export to Aladdin

---

## 🐛 Troubleshooting

### Issue: Backend connection refused
**Solution:**
```bash
# Backend is optional! Streamlit automatically falls back to mock data
# Just run Streamlit without backend:
streamlit run aladdin_exclusion_parser.py
```

### Issue: Port 8001 already in use
**Solution:**
```bash
# Use a different port
python -m uvicorn backend.app:app --port 8002
export BACKEND_URL=http://localhost:8002
```

### Issue: Streamlit not loading
**Solution:**
```bash
# Clear cache
rm -rf ~/.streamlit
streamlit run aladdin_exclusion_parser.py --logger.level=debug
```

---

## ⏱️ Demo Timing

| Component | Time |
|-----------|------|
| Setup & Start | 2 min |
| Scenario 1: Auto-approval explanation | 2 min |
| Scenario 2: Manual approval demo | 2 min |
| Scenario 3: Rejection workflow | 1 min |
| Scenario 4: Override + training | 2 min |
| Scenario 5: Audit trail | 2 min |
| Q&A | 5 min |
| **Total** | **~15 min** |

---

## 📞 Demo Support

**API Docs:** http://localhost:8001/docs (if backend running)
**Test Backend:** `python -m pytest tests/ -v` (all 37 tests should pass)
**Check Imports:** `python -c "from backend.app import app; print('✅ Backend ready')"`

---

**Ready to Demo! 🚀**
