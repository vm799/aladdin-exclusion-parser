"""
Enterprise Email Exclusion Parser with Human Review Workflow
A Streamlit app for parsing client exclusion lists and mapping to Aladdin IDs
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Dict, List, Tuple
import json
import io

# ==================== CONFIG & MOCK DATA ====================

# Mock Aladdin ID lookup database
ALADDIN_LOOKUP = {
    "Goldman Sachs": "ALADDIN_GS_001",
    "Morgan Stanley": "ALADDIN_MS_002",
    "JPMorgan Chase": "ALADDIN_JPM_003",
    "Bank of America": "ALADDIN_BOA_004",
    "Citigroup": "ALADDIN_CITI_005",
    "Wells Fargo": "ALADDIN_WF_006",
    "BlackRock": "ALADDIN_BLK_007",
    "Vanguard": "ALADDIN_VG_008",
    "Fidelity": "ALADDIN_FIDO_009",
    "Schwab": "ALADDIN_SCHW_010",
}

# Mock sample emails for proof of concept
SAMPLE_EMAILS = {
    "client_email_20260302_001.eml": {
        "from": "john.smith@investmentcorp.com",
        "subject": "Updated Exclusion List - Vendor Review",
        "extracted_companies": [
            {"name": "Goldman Sachs", "confidence": 0.95},
            {"name": "GS Bank", "confidence": 0.60},
            {"name": "Morgan Stanley", "confidence": 0.90},
        ]
    },
    "client_email_20260302_002.eml": {
        "from": "alice.brown@hedgefund.io",
        "subject": "Compliance: Counterparty Restrictions",
        "extracted_companies": [
            {"name": "JPMorgan", "confidence": 0.85},
            {"name": "Citibank", "confidence": 0.75},
            {"name": "Unknown Vendor XYZ", "confidence": 0.40},
        ]
    },
    "client_email_20260302_003.eml": {
        "from": "bob.williams@pension.org",
        "subject": "RE: Approved Trading Partners",
        "extracted_companies": [
            {"name": "BlackRock", "confidence": 0.98},
            {"name": "Vanguard", "confidence": 0.97},
            {"name": "Fidelity Investments", "confidence": 0.88},
        ]
    }
}

WORKFLOW_STEPS = [
    {"key": "upload", "label": "Upload & Extract", "num": 1},
    {"key": "review", "label": "Review & Match", "num": 2},
    {"key": "approval", "label": "Approval", "num": 3},
    {"key": "export", "label": "Export & Sign-Off", "num": 4},
]

# ==================== HELPER FUNCTIONS ====================

def find_aladdin_match(company_name: str) -> Tuple[str, float, str]:
    """
    Find Aladdin ID match for a company name.
    Returns: (aladdin_id, confidence, match_type)
    """
    if company_name in ALADDIN_LOOKUP:
        return ALADDIN_LOOKUP[company_name], 1.0, "exact"

    matches = []
    for db_name, aladdin_id in ALADDIN_LOOKUP.items():
        if company_name.lower() in db_name.lower() or db_name.lower() in company_name.lower():
            similarity = len(set(company_name.lower()) & set(db_name.lower())) / max(len(company_name), len(db_name))
            matches.append((aladdin_id, similarity, db_name))

    if matches:
        matches.sort(key=lambda x: x[1], reverse=True)
        best_match, confidence, _ = matches[0]
        return best_match, confidence * 0.8, "fuzzy"

    return "", 0.0, "manual_required"

def load_sample_data():
    """Load mock email data for demo."""
    data = []
    for email_file, content in SAMPLE_EMAILS.items():
        for company in content["extracted_companies"]:
            aladdin_id, match_confidence, match_type = find_aladdin_match(company["name"])

            data.append({
                "email_file": email_file,
                "from": content["from"],
                "company_name": company["name"],
                "extraction_confidence": company["confidence"],
                "aladdin_id": aladdin_id,
                "match_confidence": match_confidence,
                "match_type": match_type,
                "status": "pending" if match_confidence < 0.85 or not aladdin_id else "auto_approved",
                "reviewed_by": None,
                "review_timestamp": None,
                "override_aladdin_id": None,
            })
    return data

def get_status_label(status: str) -> str:
    """Return formatted status label."""
    labels = {
        "pending": "PENDING",
        "manual_required": "MANUAL",
        "auto_approved": "AUTO",
        "approved": "APPROVED",
        "rejected": "REJECTED",
    }
    return labels.get(status, "UNKNOWN")

def get_confidence_bar_color(confidence: float) -> str:
    """Return color based on confidence level."""
    if confidence >= 0.85:
        return "#1A4332"
    elif confidence >= 0.60:
        return "#C68A00"
    else:
        return "#B22222"

# ==================== STREAMLIT CONFIG ====================

st.set_page_config(
    page_title="Aladdin Exclusion Parser",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# BlackRock Aladdin Enterprise Design System CSS
st.markdown("""
<style>
    /* ===== BLACKROCK ALADDIN DESIGN TOKENS ===== */
    :root {
        --blk-black: #000000;
        --blk-dark: #1A1A2E;
        --blk-charcoal: #2C2D3C;
        --blk-slate: #404258;
        --blk-mid-gray: #6B7280;
        --blk-light-gray: #D1D5DB;
        --blk-border: #E5E7EB;
        --blk-bg-warm: #EFF1F5;
        --blk-bg-cool: #F3F4F6;
        --blk-white: #FFFFFF;
        --blk-green: #1A4332;
        --blk-green-light: #D1FAE5;
        --blk-green-accent: #059669;
        --blk-vermilion: #DC2626;
        --blk-amber: #D97706;
        --blk-amber-light: #FEF3C7;
        --blk-blue: #1E40AF;
        --blk-blue-light: #DBEAFE;
        --glass-bg: rgba(255, 255, 255, 0.85);
        --glass-border: rgba(0, 0, 0, 0.06);
        --glass-shadow: 0 2px 16px rgba(0, 0, 0, 0.10);
    }

    /* ===== GLOBAL OVERRIDES ===== */
    .stApp {
        background-color: var(--blk-bg-warm) !important;
    }

    section[data-testid="stSidebar"] {
        background-color: var(--blk-dark) !important;
        border-right: 1px solid var(--blk-charcoal) !important;
    }

    section[data-testid="stSidebar"] * {
        color: #E5E7EB !important;
    }

    section[data-testid="stSidebar"] .stMetric label {
        color: #9CA3AF !important;
        font-size: 0.7rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.08em !important;
    }

    section[data-testid="stSidebar"] [data-testid="stMetricValue"] {
        color: #FFFFFF !important;
        font-weight: 600 !important;
    }

    section[data-testid="stSidebar"] hr {
        border-color: #374151 !important;
    }

    /* ===== TOP HEADER BAR ===== */
    .aladdin-header {
        background: linear-gradient(135deg, #000000 0%, #1A1A2E 100%);
        padding: 1.2rem 2rem;
        border-radius: 0;
        margin: -1rem -1rem 1rem -1rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .aladdin-header-left {
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }
    .aladdin-logo-mark {
        width: 32px;
        height: 32px;
        background: #1A4332;
        border-radius: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        color: white;
        font-size: 0.9rem;
        letter-spacing: -0.02em;
    }
    .aladdin-header h1 {
        color: #FFFFFF;
        font-size: 1.25rem;
        font-weight: 600;
        margin: 0;
        letter-spacing: -0.01em;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }
    .aladdin-header .subtitle {
        color: #9CA3AF;
        font-size: 0.75rem;
        margin: 0;
        font-weight: 400;
        letter-spacing: 0.02em;
    }

    /* ===== SECTION HEADERS ===== */
    .section-header {
        font-size: 1rem;
        font-weight: 600;
        color: var(--blk-dark);
        margin: 1rem 0 0.75rem 0;
        padding-bottom: 0.4rem;
        border-bottom: 2px solid var(--blk-dark);
        letter-spacing: -0.01em;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }

    /* ===== STATUS BADGES ===== */
    .status-badge {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 10px;
        font-size: 0.65rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .badge-pending {
        background: var(--blk-amber-light);
        color: #78350F;
        border: 1px solid #FDE68A;
    }
    .badge-manual {
        background: #FEE2E2;
        color: #991B1B;
        border: 1px solid #FECACA;
    }
    .badge-auto {
        background: var(--blk-blue-light);
        color: #1E3A8A;
        border: 1px solid #BFDBFE;
    }
    .badge-approved {
        background: var(--blk-green-light);
        color: #064E3B;
        border: 1px solid #A7F3D0;
    }
    .badge-rejected {
        background: #FEE2E2;
        color: #991B1B;
        border: 1px solid #FECACA;
    }

    /* ===== GLASSMORPHISM STAT CARDS ===== */
    .stat-card {
        background: var(--glass-bg);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid var(--glass-border);
        border-radius: 14px;
        padding: 1.1rem 1rem;
        text-align: center;
        box-shadow: var(--glass-shadow);
    }
    .stat-card .stat-value {
        font-size: 1.75rem;
        font-weight: 700;
        color: var(--blk-dark);
        line-height: 1;
        margin-bottom: 0.2rem;
    }
    .stat-card .stat-label {
        font-size: 0.7rem;
        color: var(--blk-mid-gray);
        text-transform: uppercase;
        letter-spacing: 0.06em;
        font-weight: 500;
    }
    .stat-card.accent-green {
        border-left: 3px solid var(--blk-green-accent);
    }
    .stat-card.accent-amber {
        border-left: 3px solid var(--blk-amber);
    }
    .stat-card.accent-red {
        border-left: 3px solid var(--blk-vermilion);
    }
    .stat-card.accent-blue {
        border-left: 3px solid var(--blk-blue);
    }

    /* ===== CONFIDENCE BAR ===== */
    .confidence-bar-bg {
        width: 100%;
        height: 5px;
        background: var(--blk-bg-cool);
        border-radius: 3px;
        overflow: hidden;
    }
    .confidence-bar-fill {
        height: 100%;
        border-radius: 3px;
        transition: width 0.3s ease;
    }

    /* ===== GLASSMORPHISM REVIEW CARD ===== */
    .review-card {
        background: var(--glass-bg);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid var(--glass-border);
        border-radius: 14px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.5rem;
        box-shadow: var(--glass-shadow);
        transition: transform 0.18s ease, box-shadow 0.18s ease;
    }
    .review-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 36px rgba(0, 0, 0, 0.1);
    }
    .review-card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 0.5rem;
    }
    .review-card-company {
        font-size: 0.95rem;
        font-weight: 600;
        color: var(--blk-dark);
    }
    .review-card-arrow {
        color: var(--blk-mid-gray);
        font-size: 0.85rem;
        margin: 0 0.4rem;
    }
    .review-card-id {
        font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
        font-size: 0.8rem;
        color: var(--blk-green);
        font-weight: 500;
        background: rgba(209, 250, 229, 0.7);
        padding: 0.15rem 0.5rem;
        border-radius: 6px;
    }
    .review-card-noid {
        font-size: 0.8rem;
        color: var(--blk-vermilion);
        font-weight: 500;
        background: rgba(254, 226, 226, 0.7);
        padding: 0.15rem 0.5rem;
        border-radius: 6px;
    }
    .review-card-meta {
        display: flex;
        gap: 1.25rem;
        font-size: 0.75rem;
        color: var(--blk-mid-gray);
    }
    .review-card-meta span {
        display: flex;
        align-items: center;
        gap: 0.25rem;
    }

    /* ===== GLASSMORPHISM OVERRIDE PANEL ===== */
    .override-panel {
        background: rgba(255, 255, 255, 0.88);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(0, 0, 0, 0.06);
        border-radius: 12px;
        padding: 0.85rem 1rem;
        margin-top: 0.35rem;
        margin-bottom: 0.5rem;
        box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
    }

    /* ===== SIDEBAR STATUS BANNER ===== */
    .sidebar-status {
        padding: 0.6rem 0.75rem;
        border-radius: 8px;
        font-size: 0.78rem;
        font-weight: 500;
    }
    .sidebar-status-signed {
        background: rgba(5, 150, 105, 0.15);
        border: 1px solid rgba(5, 150, 105, 0.3);
        color: #6EE7B7 !important;
    }
    .sidebar-status-awaiting {
        background: rgba(217, 119, 6, 0.15);
        border: 1px solid rgba(217, 119, 6, 0.3);
        color: #FCD34D !important;
    }

    /* ===== DATA TABLE STYLING ===== */
    .stDataFrame {
        border: 1px solid rgba(255, 255, 255, 0.5) !important;
        border-radius: 12px !important;
        overflow: hidden !important;
        box-shadow: 0 2px 16px rgba(0, 0, 0, 0.05) !important;
    }

    /* ===== BUTTON OVERRIDES ===== */
    .stButton > button {
        border-radius: 8px !important;
        font-weight: 500 !important;
        font-size: 0.82rem !important;
        letter-spacing: 0 !important;
        transition: all 0.15s ease !important;
        cursor: pointer !important;
        padding: 0.4rem 1rem !important;
    }

    .stButton > button[kind="primary"] {
        background-color: var(--blk-green) !important;
        border-color: var(--blk-green) !important;
        color: #FFFFFF !important;
    }

    .stButton > button[kind="primary"]:hover {
        background-color: #143728 !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(26, 67, 50, 0.3);
    }

    .stButton > button[kind="secondary"] {
        background-color: var(--blk-white) !important;
        border: 1px solid var(--blk-border) !important;
        color: var(--blk-dark) !important;
    }

    .stButton > button[kind="secondary"]:hover {
        background-color: var(--blk-bg-cool) !important;
        border-color: var(--blk-light-gray) !important;
    }

    /* ===== STEP NAV BUTTONS ===== */
    .step-nav-row .stButton > button {
        border-radius: 0 !important;
        border: none !important;
        border-right: 1px solid var(--blk-border) !important;
        font-size: 0.8rem !important;
        padding: 0.65rem 0.5rem !important;
    }
    .step-nav-row .stButton > button[kind="primary"] {
        background-color: var(--blk-green) !important;
        color: #FFFFFF !important;
    }
    .step-nav-row .stButton > button[kind="secondary"] {
        background-color: var(--blk-white) !important;
        color: var(--blk-slate) !important;
    }
    .step-nav-row .stButton > button[kind="secondary"]:hover {
        background-color: var(--blk-bg-cool) !important;
    }

    /* ===== DOWNLOAD BUTTON ===== */
    .stDownloadButton > button {
        border-radius: 8px !important;
        font-weight: 500 !important;
        cursor: pointer !important;
    }

    /* ===== EXPANDER OVERRIDES ===== */
    .streamlit-expanderHeader {
        font-weight: 500 !important;
        font-size: 0.85rem !important;
        color: var(--blk-dark) !important;
    }

    /* ===== HIDE STREAMLIT BRANDING ===== */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* ===== UPLOAD AREA ===== */
    .upload-zone {
        background: var(--glass-bg);
        backdrop-filter: blur(12px);
        border: 2px dashed var(--blk-light-gray);
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
        margin-bottom: 0.75rem;
    }

    /* ===== FOOTER ===== */
    .app-footer {
        text-align: center;
        padding: 0.75rem 0;
        color: var(--blk-mid-gray);
        font-size: 0.7rem;
        border-top: 1px solid var(--blk-border);
        margin-top: 1.5rem;
        letter-spacing: 0.02em;
    }

    /* ===== CHECKLIST STYLING ===== */
    .stCheckbox label {
        font-size: 0.85rem !important;
    }

    /* ===== METRIC DELTA OVERRIDE ===== */
    [data-testid="stMetricDelta"] {
        font-size: 0.7rem !important;
    }

    /* ===== TAB STYLING ===== */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        border-bottom: 2px solid var(--blk-border);
    }
    .stTabs [data-baseweb="tab"] {
        font-weight: 500;
        font-size: 0.82rem;
        color: var(--blk-mid-gray);
        border-bottom: 2px solid transparent;
        padding: 0.6rem 1rem;
    }
    .stTabs [aria-selected="true"] {
        color: var(--blk-dark) !important;
        border-bottom-color: var(--blk-green) !important;
    }

    /* ===== GLASSMORPHISM SIGN-OFF PANEL ===== */
    .signoff-panel {
        background: rgba(255, 255, 255, 0.88);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(0, 0, 0, 0.06);
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow: 0 4px 24px rgba(0, 0, 0, 0.10);
    }

    /* ===== DISABLED SIGN-OFF HINT ===== */
    .signoff-hint {
        background: rgba(243, 244, 246, 0.7);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(0, 0, 0, 0.06);
        border-radius: 8px;
        padding: 0.6rem 0.85rem;
        color: #4B5563;
        font-size: 0.8rem;
    }

    /* ===== STREAMLIT ALERT OVERRIDES (fix white-on-yellow) ===== */
    .stAlert > div {
        color: #1A1A2E !important;
    }
    .stAlert > div p,
    .stAlert > div span,
    .stAlert > div strong,
    .stAlert > div a {
        color: #1A1A2E !important;
    }
    /* Warning: dark brown text on amber */
    .stAlert [data-testid="stNotificationContentWarning"],
    .stAlert [data-testid="stNotificationContentWarning"] p,
    .stAlert [data-testid="stNotificationContentWarning"] span,
    .stAlert [data-testid="stNotificationContentWarning"] strong {
        color: #78350F !important;
    }
    /* Info: dark blue text */
    .stAlert [data-testid="stNotificationContentInfo"],
    .stAlert [data-testid="stNotificationContentInfo"] p,
    .stAlert [data-testid="stNotificationContentInfo"] span {
        color: #1E3A5F !important;
    }
    /* Success: dark green text */
    .stAlert [data-testid="stNotificationContentSuccess"],
    .stAlert [data-testid="stNotificationContentSuccess"] p,
    .stAlert [data-testid="stNotificationContentSuccess"] span {
        color: #064E3B !important;
    }
    /* Error: dark red text */
    .stAlert [data-testid="stNotificationContentError"],
    .stAlert [data-testid="stNotificationContentError"] p,
    .stAlert [data-testid="stNotificationContentError"] span {
        color: #7F1D1D !important;
    }
    /* Broader fallback for all notification types */
    div[data-baseweb="notification"] * {
        color: #1A1A2E !important;
    }
    div[data-baseweb="notification"][kind="warning"] * {
        color: #78350F !important;
    }
    div[data-baseweb="notification"][kind="info"] * {
        color: #1E3A5F !important;
    }
    div[data-baseweb="notification"][kind="positive"] * {
        color: #064E3B !important;
    }
    div[data-baseweb="notification"][kind="negative"] * {
        color: #7F1D1D !important;
    }

    /* ===== TIGHTER SPACING ===== */
    .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 0.5rem !important;
    }

    /* ===== ACCESSIBILITY FALLBACKS ===== */
    @media (prefers-reduced-transparency) {
        .stat-card, .review-card, .override-panel, .signoff-panel {
            background: #FFFFFF !important;
            backdrop-filter: none !important;
            -webkit-backdrop-filter: none !important;
        }
    }
    @supports not (backdrop-filter: blur(1px)) {
        .stat-card, .review-card, .override-panel, .signoff-panel {
            background: rgba(255, 255, 255, 0.96) !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# ==================== SESSION STATE INIT ====================

if "data" not in st.session_state:
    st.session_state.data = load_sample_data()

if "current_step" not in st.session_state:
    st.session_state.current_step = "upload"

if "signed_off" not in st.session_state:
    st.session_state.signed_off = False

if "signoff_user" not in st.session_state:
    st.session_state.signoff_user = None

# ==================== HEADER ====================

st.markdown("""
<div class="aladdin-header">
    <div class="aladdin-header-left">
        <div class="aladdin-logo-mark">A</div>
        <div>
            <h1>Aladdin Exclusion Parser</h1>
            <p class="subtitle">Counterparty exclusion management &middot; Human-in-the-loop review</p>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ==================== SIDEBAR ====================

with st.sidebar:
    st.markdown("#### Workflow Status")

    data = st.session_state.data
    total = len(data)
    approved = len([d for d in data if d["status"] == "approved"])
    rejected = len([d for d in data if d["status"] == "rejected"])
    pending = len([d for d in data if d["status"] in ["pending", "manual_required", "auto_approved"]])

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total", total)
        st.metric("Pending", pending)
    with col2:
        st.metric("Approved", approved)
        st.metric("Rejected", rejected)

    st.divider()

    # Progress bar
    review_progress = (approved + rejected) / total if total > 0 else 0
    st.markdown(f"**Review Progress** &mdash; {review_progress:.0%}")
    st.progress(review_progress)

    st.divider()

    if st.session_state.signed_off:
        st.markdown(
            '<div class="sidebar-status sidebar-status-signed">'
            'SIGNED OFF &mdash; Ready for Aladdin upload'
            '</div>',
            unsafe_allow_html=True
        )
        st.markdown(f"**Signed by:** {st.session_state.signoff_user}")
        st.markdown(f"**Time:** {st.session_state.signoff_timestamp}")
    elif approved > 0 or rejected > 0:
        awaiting_count = approved + rejected
        st.markdown(
            f'<div class="sidebar-status sidebar-status-awaiting">'
            f'{awaiting_count} item{"s" if awaiting_count != 1 else ""} reviewed &mdash; Awaiting sign-off'
            f'</div>',
            unsafe_allow_html=True
        )

# ==================== STEP NAVIGATION ====================

nav_container = st.container()
with nav_container:
    nav_cols = st.columns(4, gap="small")
    for i, step in enumerate(WORKFLOW_STEPS):
        with nav_cols[i]:
            if st.button(
                f"{step['num']}. {step['label']}",
                key=f"nav_{step['key']}",
                use_container_width=True,
                type="primary" if step["key"] == st.session_state.current_step else "secondary",
            ):
                st.session_state.current_step = step["key"]
                st.rerun()

# ==================== TAB 1: UPLOAD & EXTRACT ====================

if st.session_state.current_step == "upload":
    st.markdown('<div class="section-header">Upload & Extract Companies</div>', unsafe_allow_html=True)

    col1, col2 = st.columns([2.5, 1])

    with col1:
        st.markdown("Upload email files (.eml or .txt) containing counterparty exclusion lists.")
        uploaded_files = st.file_uploader(
            "Choose files",
            type=["eml", "txt"],
            accept_multiple_files=True,
            label_visibility="collapsed"
        )

        if uploaded_files:
            st.success(f"Uploaded {len(uploaded_files)} file(s). Processing...")

    with col2:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        if st.button("Load Sample Data", use_container_width=True, type="primary"):
            st.session_state.data = load_sample_data()
            st.rerun()

    st.markdown('<div class="section-header">Extraction Results</div>', unsafe_allow_html=True)

    # Summary stats
    data = st.session_state.data
    scol1, scol2, scol3, scol4 = st.columns(4)
    with scol1:
        st.markdown(
            '<div class="stat-card accent-blue">'
            f'<div class="stat-value">{len(data)}</div>'
            '<div class="stat-label">Total Extracted</div>'
            '</div>', unsafe_allow_html=True
        )
    with scol2:
        exact = len([d for d in data if d["match_type"] == "exact"])
        st.markdown(
            '<div class="stat-card accent-green">'
            f'<div class="stat-value">{exact}</div>'
            '<div class="stat-label">Exact Matches</div>'
            '</div>', unsafe_allow_html=True
        )
    with scol3:
        fuzzy = len([d for d in data if d["match_type"] == "fuzzy"])
        st.markdown(
            '<div class="stat-card accent-amber">'
            f'<div class="stat-value">{fuzzy}</div>'
            '<div class="stat-label">Fuzzy Matches</div>'
            '</div>', unsafe_allow_html=True
        )
    with scol4:
        manual = len([d for d in data if d["match_type"] == "manual_required"])
        st.markdown(
            '<div class="stat-card accent-red">'
            f'<div class="stat-value">{manual}</div>'
            '<div class="stat-label">Manual Required</div>'
            '</div>', unsafe_allow_html=True
        )

    st.markdown("")

    # Extraction results table
    extraction_df = pd.DataFrame([
        {
            "Email Source": d["email_file"].replace("client_email_", "").replace(".eml", ""),
            "Sender": d["from"],
            "Company": d["company_name"],
            "Confidence": d["extraction_confidence"],
            "Match Type": d["match_type"].replace("_", " ").title(),
            "Aladdin ID": d["aladdin_id"] if d["aladdin_id"] else "—",
        }
        for d in st.session_state.data
    ])

    st.dataframe(
        extraction_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Confidence": st.column_config.ProgressColumn(
                "Confidence",
                min_value=0,
                max_value=1,
                format="%.0f%%",
            ),
        }
    )

    st.info("Companies extracted from emails. Proceed to **Review & Match** to validate mappings.")

# ==================== TAB 2: REVIEW & MATCH ====================

elif st.session_state.current_step == "review":
    st.markdown('<div class="section-header">Review & Match to Aladdin IDs</div>', unsafe_allow_html=True)

    data = st.session_state.data
    needs_review = [d for d in data if d["status"] in ["pending", "manual_required", "auto_approved"]]
    already_reviewed = [d for d in data if d["status"] in ["approved", "rejected"]]

    # Summary bar
    scol1, scol2, scol3 = st.columns(3)
    with scol1:
        st.markdown(
            '<div class="stat-card accent-amber">'
            f'<div class="stat-value">{len(needs_review)}</div>'
            '<div class="stat-label">Awaiting Review</div>'
            '</div>', unsafe_allow_html=True
        )
    with scol2:
        st.markdown(
            '<div class="stat-card accent-green">'
            f'<div class="stat-value">{len(already_reviewed)}</div>'
            '<div class="stat-label">Reviewed</div>'
            '</div>', unsafe_allow_html=True
        )
    with scol3:
        st.markdown(
            '<div class="stat-card accent-blue">'
            f'<div class="stat-value">{len(data)}</div>'
            '<div class="stat-label">Total Items</div>'
            '</div>', unsafe_allow_html=True
        )

    st.markdown("")

    if not needs_review:
        st.success("All items have been reviewed. Proceed to **Approval** for summary.")
    else:
        # Batch actions
        auto_approved = [d for d in needs_review if d["status"] == "auto_approved"]
        if auto_approved:
            st.markdown(
                f'<div class="review-card" style="border-left: 3px solid #059669;">'
                f'<div class="review-card-header">'
                f'<span class="review-card-company">{len(auto_approved)} high-confidence matches ready for batch approval</span>'
                f'<span class="status-badge badge-auto">AUTO-MATCHED</span>'
                f'</div>'
                f'<div class="review-card-meta">'
                f'<span>All items have confidence &ge; 85%</span>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True
            )
            if st.button("Approve All High-Confidence Matches", use_container_width=True, type="primary"):
                for item in auto_approved:
                    idx = data.index(item)
                    st.session_state.data[idx]["status"] = "approved"
                    st.session_state.data[idx]["reviewed_by"] = "batch_auto"
                    st.session_state.data[idx]["review_timestamp"] = datetime.now().isoformat()
                st.rerun()

            st.markdown("")

        # Individual review items
        st.markdown('<div class="section-header">Individual Review</div>', unsafe_allow_html=True)

        review_tabs = st.tabs(["All Pending", "Fuzzy Matches", "Manual Required"])

        with review_tabs[0]:
            for idx, item in enumerate(needs_review):
                global_idx = data.index(item)
                status_class = {
                    "pending": "badge-pending",
                    "manual_required": "badge-manual",
                    "auto_approved": "badge-auto",
                }.get(item["status"], "badge-pending")

                aladdin_display = (
                    f'<span class="review-card-id">{item["aladdin_id"]}</span>'
                    if item["aladdin_id"]
                    else '<span class="review-card-noid">No Match</span>'
                )

                st.markdown(
                    f'<div class="review-card">'
                    f'<div class="review-card-header">'
                    f'<div>'
                    f'<span class="review-card-company">{item["company_name"]}</span>'
                    f'<span class="review-card-arrow">&rarr;</span>'
                    f'{aladdin_display}'
                    f'</div>'
                    f'<span class="status-badge {status_class}">{get_status_label(item["status"])}</span>'
                    f'</div>'
                    f'<div class="review-card-meta">'
                    f'<span>Source: {item["email_file"].replace("client_email_", "").replace(".eml", "")}</span>'
                    f'<span>Extraction: {item["extraction_confidence"]:.0%}</span>'
                    f'<span>Match: {item["match_confidence"]:.0%}</span>'
                    f'<span>Type: {item["match_type"].replace("_", " ").title()}</span>'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # Inline action row — no expander needed
                act_cols = st.columns([2, 1, 1, 1])

                with act_cols[0]:
                    available_ids = []
                    if item["aladdin_id"]:
                        available_ids.append(item["aladdin_id"])
                    available_ids += [aid for aid in ALADDIN_LOOKUP.values() if aid not in available_ids]

                    selected_id = st.selectbox(
                        "Aladdin ID",
                        available_ids,
                        key=f"sel_{global_idx}",
                        label_visibility="collapsed"
                    )

                with act_cols[1]:
                    if st.button("Approve", key=f"apr_{global_idx}", use_container_width=True, type="primary"):
                        st.session_state.data[global_idx]["status"] = "approved"
                        st.session_state.data[global_idx]["aladdin_id"] = selected_id
                        st.session_state.data[global_idx]["reviewed_by"] = "analyst"
                        st.session_state.data[global_idx]["review_timestamp"] = datetime.now().isoformat()
                        st.rerun()

                with act_cols[2]:
                    if st.button("Reject", key=f"rej_{global_idx}", use_container_width=True):
                        st.session_state.data[global_idx]["status"] = "rejected"
                        st.session_state.data[global_idx]["reviewed_by"] = "analyst"
                        st.session_state.data[global_idx]["review_timestamp"] = datetime.now().isoformat()
                        st.rerun()

                with act_cols[3]:
                    if st.button("Override", key=f"ovr_{global_idx}", use_container_width=True):
                        st.session_state[f"show_override_{global_idx}"] = True

                # Override input (shown only when requested)
                if st.session_state.get(f"show_override_{global_idx}", False):
                    st.markdown('<div class="override-panel">', unsafe_allow_html=True)
                    ovr_cols = st.columns([3, 1])
                    with ovr_cols[0]:
                        custom_id = st.text_input(
                            "Custom Aladdin ID",
                            key=f"cust_{global_idx}",
                            placeholder="Enter custom Aladdin ID...",
                            label_visibility="collapsed"
                        )
                    with ovr_cols[1]:
                        if st.button("Submit Override", key=f"sub_ovr_{global_idx}", use_container_width=True, type="primary"):
                            if custom_id:
                                st.session_state.data[global_idx]["aladdin_id"] = custom_id
                                st.session_state.data[global_idx]["status"] = "approved"
                                st.session_state.data[global_idx]["override_aladdin_id"] = True
                                st.session_state.data[global_idx]["reviewed_by"] = "analyst (override)"
                                st.session_state.data[global_idx]["review_timestamp"] = datetime.now().isoformat()
                                st.session_state[f"show_override_{global_idx}"] = False
                                st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)

        with review_tabs[1]:
            fuzzy_items = [d for d in needs_review if d["match_type"] == "fuzzy"]
            if fuzzy_items:
                st.markdown(f"**{len(fuzzy_items)}** fuzzy matches found. These have partial name matches and need verification.")
                for item in fuzzy_items:
                    conf_color = get_confidence_bar_color(item["match_confidence"])
                    st.markdown(
                        f'<div class="review-card">'
                        f'<div class="review-card-header">'
                        f'<span class="review-card-company">{item["company_name"]}</span>'
                        f'<span class="review-card-id">{item["aladdin_id"]}</span>'
                        f'</div>'
                        f'<div style="margin-top:0.5rem;">'
                        f'<div class="confidence-bar-bg">'
                        f'<div class="confidence-bar-fill" style="width:{item["match_confidence"]*100}%;background:{conf_color};"></div>'
                        f'</div>'
                        f'<div style="font-size:0.75rem;color:#6B7280;margin-top:0.25rem;">Match confidence: {item["match_confidence"]:.0%}</div>'
                        f'</div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
            else:
                st.info("No fuzzy matches to review.")

        with review_tabs[2]:
            manual_items = [d for d in needs_review if d["match_type"] == "manual_required"]
            if manual_items:
                st.markdown(
                    f'<div style="background:#FEF3C7;border:1px solid #FDE68A;border-left:4px solid #D97706;'
                    f'border-radius:8px;padding:0.75rem 1rem;color:#78350F;font-size:0.85rem;font-weight:500;">'
                    f'<strong>{len(manual_items)}</strong> items could not be automatically matched and require manual Aladdin ID lookup.'
                    f'</div>',
                    unsafe_allow_html=True
                )
                for item in manual_items:
                    st.markdown(
                        f'<div class="review-card" style="border-left: 3px solid #DC2626;">'
                        f'<div class="review-card-header">'
                        f'<span class="review-card-company">{item["company_name"]}</span>'
                        f'<span class="review-card-noid">No Match Found</span>'
                        f'</div>'
                        f'<div class="review-card-meta">'
                        f'<span>Source: {item["email_file"]}</span>'
                        f'<span>Extraction confidence: {item["extraction_confidence"]:.0%}</span>'
                        f'</div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
            else:
                st.success("No items require manual lookup.")

# ==================== TAB 3: APPROVAL ====================

elif st.session_state.current_step == "approval":
    st.markdown('<div class="section-header">Approval Summary</div>', unsafe_allow_html=True)

    data = st.session_state.data
    approved_items = [d for d in data if d["status"] == "approved"]
    rejected_items = [d for d in data if d["status"] == "rejected"]
    pending_items = [d for d in data if d["status"] in ["pending", "manual_required", "auto_approved"]]

    scol1, scol2, scol3, scol4 = st.columns(4)
    with scol1:
        st.markdown(
            '<div class="stat-card accent-blue">'
            f'<div class="stat-value">{len(data)}</div>'
            '<div class="stat-label">Total Items</div>'
            '</div>', unsafe_allow_html=True
        )
    with scol2:
        st.markdown(
            '<div class="stat-card accent-green">'
            f'<div class="stat-value">{len(approved_items)}</div>'
            '<div class="stat-label">Approved</div>'
            '</div>', unsafe_allow_html=True
        )
    with scol3:
        st.markdown(
            '<div class="stat-card accent-red">'
            f'<div class="stat-value">{len(rejected_items)}</div>'
            '<div class="stat-label">Rejected</div>'
            '</div>', unsafe_allow_html=True
        )
    with scol4:
        st.markdown(
            '<div class="stat-card accent-amber">'
            f'<div class="stat-value">{len(pending_items)}</div>'
            '<div class="stat-label">Pending</div>'
            '</div>', unsafe_allow_html=True
        )

    st.markdown("")

    if approved_items:
        st.markdown('<div class="section-header">Approved Items</div>', unsafe_allow_html=True)
        approval_df = pd.DataFrame([
            {
                "Company": d["company_name"],
                "Aladdin ID": d["aladdin_id"],
                "Match Type": d["match_type"].replace("_", " ").title(),
                "Override": "Yes" if d["override_aladdin_id"] else "No",
                "Reviewed By": d["reviewed_by"] or "—",
                "Timestamp": d["review_timestamp"][:16].replace("T", " ") if d["review_timestamp"] else "—"
            }
            for d in approved_items
        ])
        st.dataframe(approval_df, use_container_width=True, hide_index=True)
    else:
        st.info("No approved items yet. Complete the review process first.")

    if rejected_items:
        st.markdown('<div class="section-header">Rejected Items</div>', unsafe_allow_html=True)
        reject_df = pd.DataFrame([
            {
                "Company": d["company_name"],
                "Email Source": d["email_file"],
                "Rejected By": d["reviewed_by"] or "—",
            }
            for d in rejected_items
        ])
        st.dataframe(reject_df, use_container_width=True, hide_index=True)

    if pending_items:
        st.markdown(
            f'<div style="background:#FEF3C7;border:1px solid #FDE68A;border-left:4px solid #D97706;'
            f'border-radius:8px;padding:0.75rem 1rem;color:#78350F;font-size:0.85rem;font-weight:500;">'
            f'{len(pending_items)} items still pending review. Return to <strong>Review &amp; Match</strong> to complete.'
            f'</div>',
            unsafe_allow_html=True
        )

# ==================== TAB 4: EXPORT & SIGN-OFF ====================

elif st.session_state.current_step == "export":
    st.markdown('<div class="section-header">Export & Final Sign-Off</div>', unsafe_allow_html=True)

    data = st.session_state.data
    approved_items = [d for d in data if d["status"] == "approved"]

    if not approved_items:
        st.error("No approved items to export. Complete the review process first.")
    else:
        st.markdown('<div class="section-header">Export Preview</div>', unsafe_allow_html=True)

        export_data = pd.DataFrame([
            {
                "email_filename": d["email_file"],
                "company_name": d["company_name"],
                "aladdin_id": d["aladdin_id"],
                "matched_by": "manual" if d["override_aladdin_id"] else "auto",
                "match_confidence": f"{d['match_confidence']:.0%}",
                "reviewed_by": d["reviewed_by"],
                "review_timestamp": d["review_timestamp"]
            }
            for d in approved_items
        ])

        st.dataframe(export_data, use_container_width=True, hide_index=True)

        st.divider()

        # Export download
        csv_buffer = io.StringIO()
        export_data.to_csv(csv_buffer, index=False)
        csv_bytes = csv_buffer.getvalue().encode()

        st.download_button(
            label="Download CSV (Unsigned)",
            data=csv_bytes,
            file_name=f"aladdin_exclusions_unsigned_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )

        st.divider()

        # Sign-off section
        st.markdown('<div class="section-header">Final Sign-Off</div>', unsafe_allow_html=True)
        st.markdown('<div class="signoff-panel">', unsafe_allow_html=True)
        st.markdown(
            '<div style="color:#6B7280;font-size:0.82rem;margin-bottom:0.5rem;">'
            'This export must be reviewed and signed off by an authorized user before upload to Aladdin.</div>',
            unsafe_allow_html=True
        )

        col1, col2 = st.columns(2)

        with col1:
            signoff_name = st.text_input("Your Name", placeholder="John Smith")
            signoff_role = st.selectbox("Role", ["Compliance Officer", "Trading Manager", "Risk Officer", "Operations"])

        with col2:
            signoff_team = st.text_input("Team", placeholder="Compliance / Trading")
            signoff_reason = st.text_area("Sign-Off Notes", placeholder="e.g., Reviewed for accuracy, all matches verified", height=80)

        st.markdown("**Compliance Checklist**")
        check1 = st.checkbox("I have reviewed all approved items and confirmed accuracy")
        check2 = st.checkbox("All manual overrides have been validated")
        check3 = st.checkbox("No conflicts with existing Aladdin rules")

        all_checks = signoff_name and signoff_role and signoff_team and check1 and check2 and check3

        if all_checks:
            if st.button("Sign & Approve for Aladdin Upload", use_container_width=True, type="primary"):
                st.session_state.signed_off = True
                st.session_state.signoff_user = f"{signoff_name} ({signoff_role})"
                st.session_state.signoff_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                signed_export = export_data.copy()
                signed_export["signed_by"] = signoff_name
                signed_export["signed_at"] = st.session_state.signoff_timestamp
                signed_export["sign_off_reason"] = signoff_reason
                signed_export["team"] = signoff_team

                st.session_state.signed_export = signed_export
                st.rerun()
        else:
            st.markdown(
                '<div class="signoff-hint">Complete all fields and checklist items to enable sign-off.</div>',
                unsafe_allow_html=True
            )
        st.markdown('</div>', unsafe_allow_html=True)

        if st.session_state.signed_off:
            st.divider()
            st.markdown('<div class="section-header">Signed & Approved</div>', unsafe_allow_html=True)
            st.success(f"Signed by {st.session_state.signoff_user} at {st.session_state.signoff_timestamp}")

            csv_buffer_signed = io.StringIO()
            st.session_state.signed_export.to_csv(csv_buffer_signed, index=False)
            csv_signed = csv_buffer_signed.getvalue().encode()

            st.download_button(
                label="Download Signed CSV (Ready for Aladdin Upload)",
                data=csv_signed,
                file_name=f"aladdin_exclusions_SIGNED_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True,
                type="primary"
            )

            # Audit log
            st.markdown('<div class="section-header">Audit Trail</div>', unsafe_allow_html=True)
            audit_log = {
                "Action": ["Data Loaded", "Items Reviewed", "Items Approved", "Data Signed Off"],
                "Timestamp": [
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    st.session_state.signoff_timestamp
                ],
                "User": ["System", "analyst", "analyst", st.session_state.signoff_user],
                "Details": [
                    f"{len(data)} items processed",
                    f"{len([d for d in data if d['status'] == 'approved'])} approved, {len([d for d in data if d['status'] == 'rejected'])} rejected",
                    f"{len(approved_items)} items ready for upload",
                    "Sign-off approved"
                ]
            }
            st.dataframe(pd.DataFrame(audit_log), use_container_width=True, hide_index=True)

# ==================== FOOTER ====================

st.markdown(
    '<div class="app-footer">Aladdin Exclusion Parser &middot; Enterprise Counterparty Management &middot; v2.0</div>',
    unsafe_allow_html=True
)
