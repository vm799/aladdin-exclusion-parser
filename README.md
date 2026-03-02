# 📧 Enterprise Aladdin Exclusion Parser

A production-ready Streamlit application for parsing client exclusion lists from emails, matching companies to Aladdin IDs, and managing human-in-the-loop review with full audit trail and sign-off.

## 🎯 Key Features

### 1. **Email Upload & Company Extraction**
   - Upload `.eml` or `.txt` files
   - Extract company names (currently mock-based for proof of concept)
   - Show extraction confidence scores
   - Preview extracted data before matching

### 2. **Intelligent Company-to-Aladdin Matching**
   - **Exact matches**: Direct database lookup (100% confidence)
   - **Fuzzy matches**: Substring/similarity matching (60-80% confidence)
   - **Manual required**: No match found, needs human intervention
   - Lookup table provided (easily swap to real Aladdin database)

### 3. **Human-in-the-Loop Review Workflow**
   - Separate tabs for different match types (fuzzy, manual, auto-approved)
   - Per-item review interface with confidence scores
   - Three actions: ✅ **Approve**, ❌ **Reject**, 🔧 **Override**
   - Bulk approval for high-confidence auto-matched items
   - Real-time status tracking in sidebar

### 4. **CSV Export & Sign-Off**
   - Preview export before committing
   - Generate CSV ready for Aladdin upload
   - **Critical:** Mandatory sign-off workflow
     - User must provide name, role, team
     - Checklist validation (3-point approval)
     - Timestamp & audit trail
   - Download both unsigned (temp) and signed (final) versions

### 5. **Complete Audit Trail**
   - Track who reviewed what, when
   - Record manual overrides
   - Log approval/rejection reasons
   - Sign-off captures full context

---

## 🏗️ Architecture

```
aladdin_exclusion_parser.py
├── CONFIG & MOCK DATA
│   ├── ALADDIN_LOOKUP - company name → Aladdin ID database
│   └── SAMPLE_EMAILS - 3 demo emails with pre-extracted companies
│
├── HELPER FUNCTIONS
│   ├── find_aladdin_match() - matches company names to IDs
│   ├── load_sample_data() - creates demo dataset with matching
│   └── get_status_color() - emoji badges for status
│
├── SESSION STATE MANAGEMENT
│   ├── data[] - main transaction list
│   ├── current_tab - workflow navigation
│   ├── signed_off - audit flag
│   └── signoff_user - who signed off
│
└── FOUR-STEP WORKFLOW (Tabs)
    ├── Tab 1: Upload & Extract
    │   └── File upload → extraction preview
    │
    ├── Tab 2: Review & Match
    │   ├── All Pending items
    │   ├── Fuzzy match suggestions
    │   ├── Manual lookup required
    │   └── Auto-approved items (bulk accept)
    │
    ├── Tab 3: Approval Summary
    │   ├── Stats (approved, rejected, pending)
    │   └── Detailed tables of each status
    │
    └── Tab 4: Export & Sign-Off
        ├── CSV preview
        ├── Download unsigned CSV
        ├── Sign-off form (name, role, reason)
        ├── 3-point checklist
        ├── Download signed CSV
        └── Audit log
```

---

## 🚀 Quick Start

### Prerequisites
```bash
pip install streamlit pandas
```

### Run Locally
```bash
streamlit run aladdin_exclusion_parser.py
```

The app will open at `http://localhost:8501` with sample data pre-loaded.

### Proof-of-Concept Flow (5 minutes)

1. **Tab 1 - Upload & Extract**
   - Click "Load Sample Data" (already loaded)
   - See 9 companies extracted from 3 mock emails
   
2. **Tab 2 - Review & Match**
   - Browse "All Pending" tab
   - Some items show exact matches (✅ auto-approved)
   - Some are fuzzy (need review)
   - Some require manual lookup (no match)
   - **Approve**: Click ✅ on high-confidence items
   - **Override**: Try changing Aladdin ID for low-confidence matches
   - **Reject**: Click ❌ on unwanted exclusions
   
3. **Tab 3 - Approval**
   - See summary metrics
   - Review all approved items before export
   
4. **Tab 4 - Export & Sign-Off**
   - Preview CSV export
   - Fill sign-off form (e.g., "John Smith", "Compliance Officer")
   - Check all 3 boxes in checklist
   - Click "Sign & Approve for Upload"
   - Download signed CSV (ready for Aladdin)

---

## 🔄 Workflow in Detail

### Step 1: Upload & Extract
```python
def load_sample_data():
    # Loads mock emails with pre-extracted companies
    # Returns list of dict with:
    # - email_file, from, company_name
    # - extraction_confidence (0-1)
    # - aladdin_id, match_confidence, match_type
    # - status (pending/auto_approved/approved/rejected)
```

**Status after Step 1:**
- `auto_approved` if match_confidence >= 0.85 + has Aladdin ID
- `pending` if match_confidence < 0.85
- `manual_required` if no match found

### Step 2: Review & Match
Three review categories:

#### a) **Fuzzy Matches** (Yellow 🟡)
- Substring match found (e.g., "JPMorgan" → "JPMorgan Chase")
- Confidence 60-80%
- User can: ✅ Approve suggested ID, 🔧 Override, or ❌ Reject

#### b) **Manual Required** (Red 🔴)
- No match in database (e.g., "Unknown Vendor XYZ")
- User must manually search database or confirm exclusion is invalid
- Options: ✅ Select from dropdown, 🔧 Custom ID, ❌ Reject

#### c) **Auto-Approved** (Green 🟢)
- Exact match or high-confidence fuzzy (80%+)
- User can bulk-accept all or spot-check individually

**After approval, status changes to `approved` and record is timestamped.**

### Step 3: Approval Summary
- Metrics: Total, Approved, Rejected, Pending
- Table view of all approved items for final review
- Shows: company name, Aladdin ID, match type, override flag, reviewed_by, timestamp

### Step 4: Export & Sign-Off
**Two exports generated:**

1. **Unsigned CSV** (temporary, for review)
   ```csv
   email_filename,company_name,aladdin_id,matched_by,match_confidence,reviewed_by,review_timestamp
   client_email_20260302_001.eml,Goldman Sachs,ALADDIN_GS_001,auto,95%,current_user,2026-03-02T...
   ```

2. **Signed CSV** (final, for upload)
   - Same as above, plus:
   ```csv
   ...,signed_by,signed_at,sign_off_reason,team
   ...,John Smith,2026-03-02 11:15:30,Reviewed for accuracy,Compliance
   ```

**Sign-Off Checklist:**
- ✅ Reviewed all approved items for accuracy
- ✅ All manual overrides validated against source emails
- ✅ No conflicts with existing Aladdin trading rules

**Sign-off captures:**
- User name, role, team
- Timestamp (ISO 8601)
- Reason/justification
- Audit log showing action history

---

## 📊 Data Structure

### Main Transaction Item
```python
{
    # Source
    "email_file": "client_email_20260302_001.eml",
    "from": "john.smith@investmentcorp.com",
    
    # Extraction
    "company_name": "Goldman Sachs",
    "extraction_confidence": 0.95,  # 0-1 scale
    
    # Matching
    "aladdin_id": "ALADDIN_GS_001",
    "match_confidence": 0.95,
    "match_type": "exact",  # exact | fuzzy | manual_required
    
    # Review
    "status": "approved",  # pending | auto_approved | approved | rejected
    "override_aladdin_id": False,  # True if manually changed
    
    # Audit
    "reviewed_by": "current_user",
    "review_timestamp": "2026-03-02T11:15:30.123456"
}
```

---

## 🛠️ Customization

### 1. Replace Mock Data with Real Emails
Currently uses `SAMPLE_EMAILS` dict. To integrate real email parsing:

```python
import email
from email.parser import BytesParser

def parse_eml_file(filepath: str) -> Tuple[str, List[str]]:
    """Parse .eml file and extract company names."""
    with open(filepath, 'rb') as f:
        msg = BytesParser().parsebytes(f.read())
    
    body = msg.get_payload()
    # Extract company names from body (use regex, NLP, or manual parsing)
    companies = extract_companies_from_text(body)  # Your function
    return msg.get('From'), companies

# Then in upload handler:
for uploaded_file in uploaded_files:
    sender, companies = parse_eml_file(uploaded_file.name)
    # Add to st.session_state.data
```

### 2. Connect to Real Aladdin Database
Replace `ALADDIN_LOOKUP` dict:

```python
# Load from CSV/database
import sqlite3

def load_aladdin_ids():
    conn = sqlite3.connect('aladdin_prod.db')
    df = pd.read_sql("SELECT company_name, aladdin_id FROM counterparties", conn)
    return dict(zip(df['company_name'], df['aladdin_id']))

ALADDIN_LOOKUP = load_aladdin_ids()
```

### 3. Advanced Matching Algorithm
Replace `find_aladdin_match()` with fuzzy string matching:

```python
from fuzzywuzzy import fuzz

def find_aladdin_match_fuzzy(company_name: str) -> Tuple[str, float, str]:
    best_match = None
    best_score = 0
    
    for db_name, aladdin_id in ALADDIN_LOOKUP.items():
        score = fuzz.token_set_ratio(company_name, db_name) / 100
        if score > best_score:
            best_score = score
            best_match = aladdin_id
    
    if best_score >= 0.85:
        return best_match, best_score, "fuzzy" if best_score < 1.0 else "exact"
    return "", 0.0, "manual_required"
```

### 4. Add Authentication
Connect to your SSO (Okta, Azure AD, etc.):

```python
from streamlit_authenticator import Authenticate

authenticator = Authenticate(...)
name, authentication_status, username = authenticator.login()

if authentication_status:
    current_user = name  # Use in review workflow
```

### 5. Database Persistence
Save data to PostgreSQL instead of session state:

```python
import psycopg2

def save_review(item: dict):
    with psycopg2.connect(...) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO exclusions_review 
            (company_name, aladdin_id, status, reviewed_by, timestamp)
            VALUES (%s, %s, %s, %s, %s)
        """, (item['company_name'], item['aladdin_id'], ...))
        conn.commit()
```

---

## 🎨 UI/UX Highlights

- **Color-coded status**: 🟢 approved, 🟡 pending, 🔴 manual, ❌ rejected
- **Sidebar metrics**: Real-time progress tracking
- **Tab-based workflow**: Linear but non-blocking (skip around as needed)
- **Expanders for details**: Clean, non-cluttered interface
- **Responsive columns**: Works on desktop and tablets
- **Progress indicators**: "X of Y" items processed
- **Custom CSS**: Professional enterprise look
- **Emoji badges**: Quick visual scanning

---

## 🔒 Security & Compliance

### Audit Trail
- Every action timestamped and logged
- Who reviewed what item, when
- Manual overrides flagged with reason
- Sign-off captures full context

### Access Control (future)
```python
# Add role-based permissions
ALLOWED_REVIEWERS = ["compliance_officer", "trading_manager"]
ALLOWED_SIGNERS = ["compliance_officer", "director"]

if st.session_state.user_role not in ALLOWED_REVIEWERS:
    st.error("Unauthorized")
```

### Sign-Off Enforcement
- Cannot export without review
- Cannot sign-off without checklist completion
- Checklist enforces 3-point validation

---

## 📈 Performance Notes

- **Current**: Session-based (data lives in memory)
- **Scale**: ~1000 items → OK on single instance
- **Production**: Use database backend for persistence & scale
- **Concurrency**: Multiple users → use sessions_id for isolation

---

## 🧪 Testing the Proof of Concept

### Scenario 1: High-Confidence Matches
1. Go to Tab 2
2. See "BlackRock", "Vanguard", "Fidelity" in Auto-Approved
3. Click "Accept All Auto-Approved"
4. Go to Tab 3, see them listed as approved
5. Go to Tab 4, sign off and download

### Scenario 2: Fuzzy Matching
1. Tab 2 → "Fuzzy Matches"
2. "JPMorgan" fuzzy-matched to "JPMorgan Chase"
3. Click ✅ Approve (with suggested Aladdin ID)
4. Or 🔧 Override if you want a different ID
5. Tab 3 shows override flag if you changed it

### Scenario 3: Manual Lookup Required
1. Tab 2 → "Manual Required"
2. "Unknown Vendor XYZ" - no match found
3. You can either:
   - Select from dropdown (if similar IDs exist)
   - Enter custom Aladdin ID
   - Reject (don't include in export)
4. All options timestamped & logged

### Scenario 4: Complete Workflow
1. Load sample data (Tab 1)
2. Approve/review all items (Tab 2)
3. Check summary (Tab 3)
4. Export & sign-off (Tab 4)
5. Download signed CSV

---

## 📝 Deployment

### Local Development
```bash
streamlit run aladdin_exclusion_parser.py
```

### Docker (production)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY aladdin_exclusion_parser.py .
RUN pip install streamlit pandas
EXPOSE 8501
CMD ["streamlit", "run", "aladdin_exclusion_parser.py", "--server.port=8501"]
```

### Kubernetes / Cloud Run
```bash
gcloud run deploy aladdin-parser \
  --source . \
  --platform managed \
  --region us-central1
```

---

## 🐛 Known Limitations (v1.0)

1. **Email parsing is mocked** - currently uses hardcoded extraction. Integrate real email parser.
2. **Aladdin lookup is hardcoded** - should load from database.
3. **Single-user session** - no multi-user concurrency. Add DB backend.
4. **No persistence** - data lost on refresh. Add SQLite/PostgreSQL.
5. **Authentication not included** - add via `streamlit-authenticator`.

---

## 🚀 Next Steps

1. **Week 1**: Integrate real email parsing (use `email` + `regex` or `spaCy` NER)
2. **Week 2**: Connect to real Aladdin database
3. **Week 3**: Add user authentication & role-based access
4. **Week 4**: Migrate to production database backend
5. **Week 5**: Deploy to cloud (Cloud Run, ECS, or K8s)
6. **Week 6**: Add monitoring, logging, alerting

---

## 📞 Support

For questions or customization:
- Check the inline comments in `aladdin_exclusion_parser.py`
- Modify `ALADDIN_LOOKUP` to test matching logic
- Add email parsing in `uploaded_files` handler
- Extend session state for additional fields

---

**Built with ❤️ for enterprise compliance teams**
