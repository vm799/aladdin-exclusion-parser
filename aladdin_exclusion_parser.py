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
import hashlib
import os

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


def get_risk_badge_html(confidence: float) -> str:
    """Return risk badge HTML based on confidence (low confidence = high risk)."""
    if confidence >= 0.85:
        return '<span class="risk-badge risk-low"><span class="risk-badge-dot"></span>Low Risk</span>'
    elif confidence >= 0.60:
        return '<span class="risk-badge risk-medium"><span class="risk-badge-dot"></span>Med Risk</span>'
    else:
        return '<span class="risk-badge risk-high"><span class="risk-badge-dot"></span>High Risk</span>'


def get_confidence_gauge_html(confidence: float) -> str:
    """Return enhanced confidence gauge HTML with color zones and threshold markers."""
    pct = confidence * 100
    conf_color = get_confidence_bar_color(confidence)
    return (
        f'<div class="confidence-gauge">'
        f'<div class="confidence-gauge-track">'
        f'<div class="confidence-gauge-threshold" style="left:60%;"></div>'
        f'<div class="confidence-gauge-threshold" style="left:85%;"></div>'
        f'<div class="confidence-gauge-fill-marker" style="left:calc({pct}% - 2px);"></div>'
        f'</div>'
        f'<div class="confidence-gauge-zone-labels">'
        f'<span class="zone-red">High Risk (0-60%)</span>'
        f'<span class="zone-amber">Medium (60-85%)</span>'
        f'<span class="zone-green">Low (85%+)</span>'
        f'</div>'
        f'<div class="confidence-gauge-pct" style="color:{conf_color};">{pct:.0f}%</div>'
        f'</div>'
    )

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
        --glass-border: rgba(0, 0, 0, 0.12);
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
        margin: 0 -1rem 1rem -1rem;
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

    /* ===== STAT CARD TREND INDICATORS ===== */
    .stat-trend {
        display: block;
        font-size: 0.65rem;
        font-weight: 500;
        margin-top: 0.3rem;
        letter-spacing: 0.01em;
    }
    .stat-trend-up { color: #059669; }
    .stat-trend-down { color: #DC2626; }
    .stat-trend-neutral { color: #6B7280; }

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

    /* ===== CONFIDENCE GAUGE (enhanced) ===== */
    .confidence-gauge { position: relative; width: 100%; margin-top: 0.5rem; }
    .confidence-gauge-track {
        position: relative; width: 100%; height: 10px; border-radius: 5px; overflow: visible;
        background: linear-gradient(to right, #DC2626 0%, #DC2626 60%, #D97706 60%, #D97706 85%, #059669 85%, #059669 100%);
    }
    .confidence-gauge-fill-marker {
        position: absolute; top: -3px; width: 4px; height: 16px;
        background: #1A1A2E; border-radius: 2px; border: 1px solid #FFFFFF;
        box-shadow: 0 1px 3px rgba(0,0,0,0.3);
    }
    .confidence-gauge-zone-labels {
        display: flex; width: 100%; font-size: 0.6rem; font-weight: 500;
        letter-spacing: 0.02em; margin-top: 0.3rem;
    }
    .confidence-gauge-zone-labels span { text-align: center; line-height: 1; }
    .confidence-gauge-zone-labels .zone-red { width: 60%; color: #DC2626; }
    .confidence-gauge-zone-labels .zone-amber { width: 25%; color: #D97706; }
    .confidence-gauge-zone-labels .zone-green { width: 15%; color: #059669; }
    .confidence-gauge-threshold {
        position: absolute; top: -1px; width: 1px; height: 12px;
        border-left: 1.5px dashed rgba(0,0,0,0.4);
    }
    .confidence-gauge-pct { font-size: 0.8rem; font-weight: 700; text-align: right; margin-top: 0.15rem; }

    /* ===== RISK SCORE BADGE ===== */
    .risk-badge {
        display: inline-flex; align-items: center; gap: 0.3rem;
        font-size: 0.65rem; font-weight: 600; text-transform: uppercase;
        letter-spacing: 0.04em; padding: 0.15rem 0.5rem; border-radius: 10px;
        margin-left: 0.5rem; vertical-align: middle;
    }
    .risk-badge-dot {
        width: 7px; height: 7px; border-radius: 50%; display: inline-block; flex-shrink: 0;
    }
    .risk-low { background: rgba(209,250,229,0.7); color: #064E3B; }
    .risk-low .risk-badge-dot { background: #059669; box-shadow: 0 0 4px rgba(5,150,105,0.5); }
    .risk-medium { background: rgba(254,243,199,0.7); color: #78350F; }
    .risk-medium .risk-badge-dot { background: #D97706; box-shadow: 0 0 4px rgba(217,119,6,0.5); }
    .risk-high { background: rgba(254,226,226,0.7); color: #991B1B; }
    .risk-high .risk-badge-dot { background: #DC2626; box-shadow: 0 0 4px rgba(220,38,38,0.5); }

    /* ===== SIDEBAR DONUT / RING CHART ===== */
    .progress-donut {
        width: 110px; height: 110px; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        margin: 0 auto 0.5rem auto; position: relative;
    }
    .progress-donut-inner {
        width: 74px; height: 74px; border-radius: 50%;
        background: var(--blk-dark); display: flex; align-items: center;
        justify-content: center; flex-direction: column;
    }
    .progress-donut-pct { font-size: 1.2rem; font-weight: 700; color: #FFFFFF; line-height: 1; }
    .progress-donut-sublabel {
        font-size: 0.55rem; color: #9CA3AF; text-transform: uppercase;
        letter-spacing: 0.05em; margin-top: 0.15rem;
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
        border: 1px solid rgba(0, 0, 0, 0.12);
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

    /* ===== EMPTY STATE PANELS ===== */
    .empty-state {
        background: rgba(255, 255, 255, 0.45);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1.5px dashed rgba(107, 114, 128, 0.5);
        border-radius: 12px;
        padding: 2rem;
        text-align: center;
        color: #6B7280;
        margin: 1rem 0;
    }
    .empty-state .empty-state-icon {
        font-size: 1.6rem;
        margin-bottom: 0.5rem;
        opacity: 0.6;
    }
    .empty-state .empty-state-message {
        font-size: 0.95rem;
        font-weight: 500;
        color: #374151;
        margin-bottom: 0.35rem;
    }
    .empty-state .empty-state-hint {
        font-size: 0.8rem;
        color: #9CA3AF;
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
    .app-footer .footer-meta {
        display: flex;
        justify-content: center;
        gap: 1.5rem;
        margin-top: 0.25rem;
        font-size: 0.65rem;
        color: #9CA3AF;
    }
    .app-footer .footer-meta span {
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
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
        border: 1px solid rgba(0, 0, 0, 0.12);
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow: 0 4px 24px rgba(0, 0, 0, 0.10);
    }

    /* ===== DISABLED SIGN-OFF HINT ===== */
    .signoff-hint {
        background: rgba(243, 244, 246, 0.7);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(0, 0, 0, 0.12);
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

    /* ===== STEP NAV CAROUSEL ===== */
    .step-nav-bar {
        display: flex;
        gap: 0;
        border-bottom: 2px solid #E5E7EB;
        margin-bottom: 0.25rem;
        background: rgba(255, 255, 255, 0.7);
        backdrop-filter: blur(8px);
        border-radius: 8px 8px 0 0;
        padding: 0 0.25rem;
    }
    .step-nav-item {
        flex: 1;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.5rem;
        padding: 0.75rem 0.5rem 0.65rem;
        font-size: 0.82rem;
        font-weight: 500;
        color: #6B7280;
        border-bottom: 3px solid transparent;
        margin-bottom: -2px;
        transition: all 0.15s ease;
        white-space: nowrap;
    }
    .step-nav-item.active {
        color: #1A4332;
        font-weight: 600;
        border-bottom-color: #1A4332;
    }
    .step-nav-item .step-num {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 22px;
        height: 22px;
        border-radius: 50%;
        font-size: 0.72rem;
        font-weight: 700;
        background: #E5E7EB;
        color: #6B7280;
        flex-shrink: 0;
    }
    .step-nav-item.active .step-num {
        background: #1A4332;
        color: #FFFFFF;
    }
    .step-nav-item.completed .step-num {
        background: #059669;
        color: #FFFFFF;
    }
    .step-nav-item .step-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 20px;
        height: 20px;
        border-radius: 10px;
        font-size: 0.68rem;
        font-weight: 700;
        padding: 0 5px;
        background: #E5E7EB;
        color: #6B7280;
        margin-left: 2px;
    }
    .step-nav-item.active .step-badge {
        background: rgba(26, 67, 50, 0.12);
        color: #1A4332;
    }
    .step-nav-item.completed .step-badge {
        background: rgba(5, 150, 105, 0.12);
        color: #059669;
    }
    .step-nav-item .step-check {
        color: #059669;
        font-size: 0.9rem;
        margin-right: -2px;
    }
    /* Hide real Streamlit buttons behind the HTML nav bar */
    .step-nav-buttons .stButton > button {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        color: transparent !important;
        height: 0px !important;
        min-height: 0px !important;
        padding: 0 !important;
        margin: -0.5rem 0 0 0 !important;
        overflow: hidden !important;
        line-height: 0 !important;
        font-size: 0 !important;
    }

    /* ===== SIDEBAR ACTIVITY PANEL ===== */
    .sidebar-activity {
        background: rgba(243, 244, 246, 0.6);
        border: 1px solid rgba(0, 0, 0, 0.12);
        border-radius: 8px;
        padding: 0.6rem 0.75rem;
        font-size: 0.78rem;
        color: #374151;
        margin-top: 0.25rem;
    }
    .sidebar-activity .activity-label {
        font-weight: 600;
        color: #6B7280;
        font-size: 0.68rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 0.2rem;
    }
    .sidebar-activity .activity-action {
        color: #1A4332;
        font-weight: 500;
    }
    .sidebar-activity .activity-time {
        color: #9CA3AF;
        font-size: 0.72rem;
        margin-top: 0.15rem;
    }
    .sidebar-duration {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        font-size: 0.72rem;
        color: #9CA3AF;
        margin-top: 0.35rem;
    }

    /* ===== TIGHTER SPACING ===== */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 0.5rem !important;
    }

    /* Push content below Streamlit toolbar so header is not hidden */
    header[data-testid="stHeader"] {
        background: transparent !important;
        pointer-events: none;
    }
    header[data-testid="stHeader"] > * {
        pointer-events: auto;
    }
    [data-testid="stToolbar"] {
        z-index: 999 !important;
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

    /* ===== BUTTON STATE MACHINE (5-state Aladdin standard) ===== */
    .stButton > button[kind="primary"]:active {
        background-color: #0F2D1F !important;
        transform: translateY(0) !important;
        box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.3) !important;
    }
    .stButton > button[kind="primary"]:focus-visible {
        outline: 3px solid #1E40AF !important;
        outline-offset: 3px !important;
        box-shadow: 0 0 0 1px #FFFFFF, 0 4px 12px rgba(26, 67, 50, 0.3) !important;
    }
    .stButton > button[kind="primary"]:disabled,
    .stButton > button[kind="primary"][disabled] {
        background-color: var(--blk-green) !important;
        opacity: 0.5 !important;
        cursor: not-allowed !important;
        transform: none !important;
        box-shadow: none !important;
        pointer-events: auto !important;
    }
    .stButton > button[kind="primary"]:disabled:hover,
    .stButton > button[kind="primary"][disabled]:hover {
        background-color: var(--blk-green) !important;
        transform: none !important;
        box-shadow: none !important;
    }

    .stButton > button[kind="secondary"]:active {
        background-color: #E5E7EB !important;
        transform: translateY(0) !important;
        box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.15) !important;
    }
    .stButton > button[kind="secondary"]:focus-visible {
        outline: 3px solid #1E40AF !important;
        outline-offset: 3px !important;
        box-shadow: 0 0 0 1px #FFFFFF !important;
    }
    .stButton > button[kind="secondary"]:disabled,
    .stButton > button[kind="secondary"][disabled] {
        background-color: var(--blk-white) !important;
        color: var(--blk-dark) !important;
        opacity: 0.5 !important;
        cursor: not-allowed !important;
        transform: none !important;
        box-shadow: none !important;
        pointer-events: auto !important;
    }
    .stButton > button[kind="secondary"]:disabled:hover,
    .stButton > button[kind="secondary"][disabled]:hover {
        background-color: var(--blk-white) !important;
        transform: none !important;
        box-shadow: none !important;
    }

    .stButton > button:focus-visible {
        outline: 3px solid #1E40AF !important;
        outline-offset: 3px !important;
    }

    .step-nav-row .stButton > button:active {
        box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.2) !important;
    }
    .step-nav-row .stButton > button:focus-visible {
        outline: 3px solid #1E40AF !important;
        outline-offset: 3px !important;
    }
    .step-nav-row .stButton > button:disabled {
        opacity: 0.5 !important;
        cursor: not-allowed !important;
    }

    .stDownloadButton > button:active {
        box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.2) !important;
    }
    .stDownloadButton > button:focus-visible {
        outline: 3px solid #1E40AF !important;
        outline-offset: 3px !important;
    }
    .stDownloadButton > button:disabled {
        opacity: 0.5 !important;
        cursor: not-allowed !important;
    }

    /* ===== DATA TABLE REFINEMENT ===== */
    .stDataFrame [data-testid="stDataFrameResizable"] table thead tr th {
        position: sticky !important;
        top: 0 !important;
        z-index: 2 !important;
        background-color: #1A1A2E !important;
        color: #FFFFFF !important;
        padding: 0.5rem 0.75rem !important;
        font-weight: 600 !important;
        font-size: 0.78rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.04em !important;
    }
    .stDataFrame table tbody tr td {
        padding: 0.5rem 0.75rem !important;
    }
    .stDataFrame table tbody tr:nth-child(even) {
        background-color: #F8F9FB !important;
    }
    .stDataFrame table tbody tr:nth-child(odd) {
        background-color: #FFFFFF !important;
    }
    .stDataFrame table tbody tr:hover {
        background-color: #EEF2FF !important;
    }
    /* Glide Data Grid (Streamlit >=1.22) alternating rows */
    [data-testid="glideDataEditor"] [role="row"]:nth-child(even) {
        background-color: #F8F9FB !important;
    }
    [data-testid="glideDataEditor"] [role="row"]:hover {
        background-color: #EEF2FF !important;
    }

    /* ===== REDUCED MOTION ===== */
    @media (prefers-reduced-motion: reduce) {
        .review-card,
        .stat-card,
        .confidence-bar-fill,
        .stButton > button,
        .stDownloadButton > button,
        .step-nav-row .stButton > button {
            transition: none !important;
            animation: none !important;
        }
        .review-card:hover,
        .stButton > button:hover,
        .stButton > button[kind="primary"]:hover {
            transform: none !important;
        }
    }

    /* ===== FOCUS STYLES FOR FORM INPUTS ===== */
    .stTextInput input:focus,
    .stTextArea textarea:focus,
    .stSelectbox [data-baseweb="select"]:focus-within,
    .stMultiSelect [data-baseweb="select"]:focus-within,
    .stNumberInput input:focus,
    .stDateInput input:focus {
        outline: 2px solid #1E40AF !important;
        outline-offset: 0px !important;
        border-color: #1E40AF !important;
        box-shadow: 0 0 0 1px #1E40AF !important;
    }
    .stTextInput input:focus,
    .stTextArea textarea:focus,
    .stNumberInput input:focus,
    .stDateInput input:focus {
        outline: 2px solid #1E40AF !important;
    }
    /* Remove default browser outline in favor of custom */
    .stTextInput input,
    .stTextArea textarea,
    .stNumberInput input,
    .stDateInput input {
        outline: none !important;
    }

    /* ===== DESKTOP RESPONSIVENESS ===== */

    /* Large desktops (1440px+): wider content, larger type */
    @media (min-width: 1440px) {
        .block-container {
            max-width: 1280px !important;
            padding-left: 2rem !important;
            padding-right: 2rem !important;
        }
        .aladdin-header {
            padding: 1.4rem 2.5rem;
        }
        .stat-card .stat-value {
            font-size: 2rem;
        }
        .review-card {
            padding: 1.25rem 1.5rem;
        }
    }

    /* Standard desktops (1024px–1439px): balanced layout */
    @media (min-width: 1024px) and (max-width: 1439px) {
        .block-container {
            max-width: 1100px !important;
            padding-left: 1.5rem !important;
            padding-right: 1.5rem !important;
        }
    }

    /* Small desktops / large tablets (768px–1023px) */
    @media (min-width: 768px) and (max-width: 1023px) {
        .block-container {
            max-width: 100% !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
        .aladdin-header {
            padding: 1rem 1.25rem;
        }
        .aladdin-header h1 {
            font-size: 1.1rem;
        }
        .stat-card .stat-value {
            font-size: 1.5rem;
        }
        .stat-card {
            padding: 0.85rem 0.75rem;
        }
        .step-nav-item {
            font-size: 0.75rem;
            padding: 0.6rem 0.35rem 0.55rem;
        }
        .review-card-meta {
            gap: 0.75rem;
            flex-wrap: wrap;
        }
    }

    /* Compact / small screens (<768px) */
    @media (max-width: 767px) {
        .block-container {
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
        }
        .aladdin-header {
            padding: 0.85rem 1rem;
            flex-direction: column;
            gap: 0.5rem;
            align-items: flex-start;
        }
        .aladdin-header h1 {
            font-size: 1rem;
        }
        .step-nav-bar {
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }
        .step-nav-item {
            font-size: 0.72rem;
            min-width: max-content;
            padding: 0.55rem 0.4rem 0.5rem;
        }
        .stat-card .stat-value {
            font-size: 1.4rem;
        }
        .review-card {
            padding: 0.85rem 0.75rem;
        }
        .review-card-header {
            flex-direction: column;
            align-items: flex-start;
            gap: 0.35rem;
        }
        .review-card-meta {
            flex-wrap: wrap;
            gap: 0.5rem;
        }
        .confidence-gauge-zone-labels {
            font-size: 0.5rem;
        }
    }

    /* ===== PRINT STYLES ===== */
    @media print {
        /* Hide non-essential UI */
        section[data-testid="stSidebar"],
        .aladdin-header,
        .step-nav-row,
        .stButton,
        .stDownloadButton,
        .app-footer,
        #MainMenu,
        footer,
        header,
        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        [data-testid="stStatusWidget"] {
            display: none !important;
        }
        /* Full-width content */
        .main .block-container {
            max-width: 100% !important;
            padding: 0 !important;
            margin: 0 !important;
        }
        /* Remove glassmorphism, solid white backgrounds */
        .stat-card,
        .review-card,
        .override-panel,
        .signoff-panel,
        .upload-zone {
            background: #FFFFFF !important;
            backdrop-filter: none !important;
            -webkit-backdrop-filter: none !important;
            box-shadow: none !important;
            border: 1px solid #D1D5DB !important;
        }
        /* Black text on white */
        body, body * {
            color: #000000 !important;
            background-color: transparent !important;
        }
        .stApp {
            background-color: #FFFFFF !important;
        }
        /* Data tables full-width */
        .stDataFrame {
            width: 100% !important;
            box-shadow: none !important;
            border: 1px solid #000000 !important;
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

if "session_start" not in st.session_state:
    st.session_state.session_start = datetime.now()

if "session_id" not in st.session_state:
    st.session_state.session_id = hashlib.sha256(
        datetime.now().isoformat().encode()
    ).hexdigest()[:8].upper()

if "last_data_load" not in st.session_state:
    st.session_state.last_data_load = datetime.now()


if "last_action" not in st.session_state:
    st.session_state.last_action = None

if "last_action_time" not in st.session_state:
    st.session_state.last_action_time = None
# ==================== HEADER ====================

st.markdown("""
<div class="aladdin-header" role="banner" aria-label="Aladdin Exclusion Parser">
    <div class="aladdin-header-left">
        <div class="aladdin-logo-mark">A</div>
        <div>
            <h1>Aladdin Exclusion Parser</h1>
            <p class="subtitle">Counterparty exclusion management &middot; Human-in-the-loop review</p>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Breadcrumb navigation context
_step_labels = {s["key"]: s["label"] for s in WORKFLOW_STEPS}
_current_label = _step_labels.get(st.session_state.current_step, "Upload & Extract")
st.markdown(
    f'<div style="font-size:0.75rem;color:#9CA3AF;padding:0 0 0.5rem 0.25rem;letter-spacing:0.02em;">'
    f'Exclusion Management &rsaquo; Email Parser &rsaquo; <span style="color:#6B7280;font-weight:600;">{_current_label}</span>'
    f'</div>',
    unsafe_allow_html=True
)

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

    # Session timer
    _elapsed = datetime.now() - st.session_state.session_start
    _hours, _remainder = divmod(int(_elapsed.total_seconds()), 3600)
    _minutes, _seconds = divmod(_remainder, 60)
    st.markdown(
        f'<div style="text-align:center;color:#6B7280;font-size:0.78rem;font-weight:500;'
        f'letter-spacing:0.03em;padding:0.25rem 0;">'
        f'Session: {_hours:02d}:{_minutes:02d}:{_seconds:02d}'
        f'</div>',
        unsafe_allow_html=True
    )

    st.divider()

    # Progress donut chart + progress bar
    review_progress = (approved + rejected) / total if total > 0 else 0
    progress_deg = review_progress * 360
    approved_deg = (approved / total * 360) if total > 0 else 0
    rejected_deg = (rejected / total * 360) if total > 0 else 0
    st.markdown(f"**Review Progress** &mdash; {review_progress:.0%}")
    st.markdown(
        f'<div class="progress-donut" style="background: conic-gradient('
        f'#059669 0deg {approved_deg}deg, '
        f'#DC2626 {approved_deg}deg {approved_deg + rejected_deg}deg, '
        f'#374151 {approved_deg + rejected_deg}deg 360deg'
        f');">'
        f'<div class="progress-donut-inner">'
        f'<span class="progress-donut-pct">{review_progress:.0%}</span>'
        f'<span class="progress-donut-sublabel">Complete</span>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True
    )
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

    # --- Last Activity & Audit Summary ---
    st.divider()
    st.markdown("#### Last Activity")

    _last_action = st.session_state.last_action
    _last_action_time = st.session_state.last_action_time

    if _last_action and _last_action_time:
        _action_ago = datetime.now() - _last_action_time
        _ago_seconds = int(_action_ago.total_seconds())
        if _ago_seconds < 60:
            _ago_str = f"{_ago_seconds}s ago"
        elif _ago_seconds < 3600:
            _ago_str = f"{_ago_seconds // 60}m ago"
        else:
            _ago_str = f"{_ago_seconds // 3600}h {(_ago_seconds % 3600) // 60}m ago"

        st.markdown(
            f'<div class="sidebar-activity">'
            f'<div class="activity-label">Last Action</div>'
            f'<div class="activity-action">{_last_action}</div>'
            f'<div class="activity-time">{_last_action_time.strftime("%H:%M:%S")} ({_ago_str})</div>'
            f'</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<div class="sidebar-activity">'
            '<div class="activity-label">Last Action</div>'
            '<div style="color:#9CA3AF;">No actions taken yet</div>'
            '</div>',
            unsafe_allow_html=True
        )

    # Session duration
    _elapsed = datetime.now() - st.session_state.session_start
    _dur_h, _dur_rem = divmod(int(_elapsed.total_seconds()), 3600)
    _dur_m, _dur_s = divmod(_dur_rem, 60)
    st.markdown(
        f'<div class="sidebar-duration">'
        f'&#9201; Session duration: {_dur_h:02d}:{_dur_m:02d}:{_dur_s:02d}'
        f'</div>',
        unsafe_allow_html=True
    )

    # Mini audit summary
    _actions_taken = approved + rejected
    st.markdown(
        f'<div class="sidebar-activity" style="margin-top:0.5rem;">'
        f'<div class="activity-label">Audit Summary</div>'
        f'<div>{approved} approved &middot; {rejected} rejected &middot; {pending} pending</div>'
        f'</div>',
        unsafe_allow_html=True
    )

# ==================== STEP NAVIGATION ====================

# Compute per-step counts and completion status
_nav_data = st.session_state.data
_nav_total = len(_nav_data)
_nav_pending = len([d for d in _nav_data if d["status"] in ["pending", "manual_required", "auto_approved"]])
_nav_approved = len([d for d in _nav_data if d["status"] == "approved"])
_nav_rejected = len([d for d in _nav_data if d["status"] == "rejected"])
_nav_reviewed = _nav_approved + _nav_rejected

# Step completion logic
_step_counts = {
    "upload": _nav_total,
    "review": _nav_pending,
    "approval": _nav_reviewed,
    "export": _nav_approved,
}
_step_complete = {
    "upload": _nav_total > 0,
    "review": _nav_total > 0 and _nav_pending == 0,
    "approval": _nav_total > 0 and _nav_pending == 0 and _nav_reviewed > 0,
    "export": st.session_state.signed_off,
}

# Build the HTML nav bar
_nav_items_html = ""
for step in WORKFLOW_STEPS:
    _is_active = step["key"] == st.session_state.current_step
    _is_done = _step_complete[step["key"]]
    _count = _step_counts[step["key"]]

    _classes = "step-nav-item"
    if _is_active:
        _classes += " active"
    if _is_done and not _is_active:
        _classes += " completed"

    _check_html = '<span class="step-check">&#10003;</span>' if _is_done else ""
    _num_html = f'<span class="step-num">{step["num"]}</span>'
    _badge_html = f'<span class="step-badge">{_count}</span>'

    _nav_items_html += (
        f'<div class="{_classes}">'
        f'{_check_html}{_num_html} {step["label"]} {_badge_html}'
        f'</div>'
    )

st.markdown(
    f'<nav role="navigation" aria-label="Workflow steps">'
    f'<div class="step-nav-bar">{_nav_items_html}</div>'
    f'</nav>',
    unsafe_allow_html=True,
)

# Hidden Streamlit buttons for actual click handling
st.markdown('<div class="step-nav-buttons">', unsafe_allow_html=True)
nav_container = st.container()
with nav_container:
    nav_cols = st.columns(4, gap="small")
    for i, step in enumerate(WORKFLOW_STEPS):
        with nav_cols[i]:
            if st.button(
                step["label"],
                key=f"nav_{step['key']}",
                use_container_width=True,
            ):
                st.session_state.current_step = step["key"]
                st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

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
            st.session_state.last_action = "Loaded sample data"
            st.session_state.last_action_time = datetime.now()
            st.rerun()

    st.markdown('<div class="section-header">Extraction Results</div>', unsafe_allow_html=True)

    # Summary stats
    data = st.session_state.data
    exact = len([d for d in data if d["match_type"] == "exact"])
    fuzzy = len([d for d in data if d["match_type"] == "fuzzy"])
    manual = len([d for d in data if d["match_type"] == "manual_required"])

    # Simulated previous-batch deltas for trend indicators
    prev_batch = {"total": max(len(data) - 2, 0), "exact": max(exact - 1, 0), "fuzzy": max(fuzzy - 1, 0), "manual": max(manual, 0)}

    def _trend_html(current, previous, invert=False):
        delta = current - previous
        if delta == 0:
            return '<span class="stat-trend stat-trend-neutral">&mdash; same as previous</span>'
        arrow = "&uarr;" if delta > 0 else "&darr;"
        css_class = "stat-trend-down" if (delta > 0 and invert) or (delta < 0 and not invert) else "stat-trend-up"
        return f'<span class="stat-trend {css_class}">{arrow} {abs(delta)} from previous</span>'

    scol1, scol2, scol3, scol4 = st.columns(4)
    with scol1:
        st.markdown(
            f'<div class="stat-card accent-blue" role="figure" aria-label="{len(data)} Total Extracted">'
            f'<div class="stat-value">{len(data)}</div>'
            '<div class="stat-label">Total Extracted</div>'
            f'{_trend_html(len(data), prev_batch["total"])}'
            '</div>', unsafe_allow_html=True
        )
    with scol2:
        st.markdown(
            f'<div class="stat-card accent-green" role="figure" aria-label="{exact} Exact Matches">'
            f'<div class="stat-value">{exact}</div>'
            '<div class="stat-label">Exact Matches</div>'
            f'{_trend_html(exact, prev_batch["exact"])}'
            '</div>', unsafe_allow_html=True
        )
    with scol3:
        st.markdown(
            f'<div class="stat-card accent-amber" role="figure" aria-label="{fuzzy} Fuzzy Matches">'
            f'<div class="stat-value">{fuzzy}</div>'
            '<div class="stat-label">Fuzzy Matches</div>'
            f'{_trend_html(fuzzy, prev_batch["fuzzy"], invert=True)}'
            '</div>', unsafe_allow_html=True
        )
    with scol4:
        st.markdown(
            f'<div class="stat-card accent-red" role="figure" aria-label="{manual} Manual Required">'
            f'<div class="stat-value">{manual}</div>'
            '<div class="stat-label">Manual Required</div>'
            f'{_trend_html(manual, prev_batch["manual"], invert=True)}'
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
            f'<div class="stat-card accent-amber" role="figure" aria-label="{len(needs_review)} Awaiting Review">'
            f'<div class="stat-value">{len(needs_review)}</div>'
            '<div class="stat-label">Awaiting Review</div>'
            '</div>', unsafe_allow_html=True
        )
    with scol2:
        st.markdown(
            f'<div class="stat-card accent-green" role="figure" aria-label="{len(already_reviewed)} Reviewed">'
            f'<div class="stat-value">{len(already_reviewed)}</div>'
            '<div class="stat-label">Reviewed</div>'
            '</div>', unsafe_allow_html=True
        )
    with scol3:
        st.markdown(
            f'<div class="stat-card accent-blue" role="figure" aria-label="{len(data)} Total Items">'
            f'<div class="stat-value">{len(data)}</div>'
            '<div class="stat-label">Total Items</div>'
            '</div>', unsafe_allow_html=True
        )

    st.markdown("")

    if not needs_review:
        st.markdown(
            '<div class="empty-state">'
            '<div class="empty-state-icon">[All Clear]</div>'
            '<div class="empty-state-message">All items have been reviewed</div>'
            '<div class="empty-state-hint">Proceed to Approval to view summary and finalize</div>'
            '</div>',
            unsafe_allow_html=True
        )
    else:
        # Batch actions
        auto_approved = [d for d in needs_review if d["status"] == "auto_approved"]
        if auto_approved:
            st.markdown(
                f'<div class="review-card" style="border-left: 3px solid #059669;" role="article" aria-label="Batch approval for {len(auto_approved)} high-confidence matches">'
                f'<div class="review-card-header">'
                f'<span class="review-card-company">{len(auto_approved)} high-confidence matches ready for batch approval</span>'
                f'<span class="status-badge badge-auto" role="status" aria-label="Status: Auto-matched">AUTO-MATCHED</span>'
                f'</div>'
                f'<div class="review-card-meta">'
                f'<span>All items have confidence &ge; 85%</span>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True
            )
            if st.button("Approve All High-Confidence Matches", use_container_width=True, type="primary"):
                with st.spinner("Processing batch approval..."):
                    for item in auto_approved:
                        idx = data.index(item)
                        st.session_state.data[idx]["status"] = "approved"
                        st.session_state.data[idx]["reviewed_by"] = "batch_auto"
                        st.session_state.data[idx]["review_timestamp"] = datetime.now().isoformat()
                    st.session_state.last_action = f"Batch approved {len(auto_approved)} items"
                    st.session_state.last_action_time = datetime.now()
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

                risk_badge = get_risk_badge_html(item["match_confidence"])
                st.markdown(
                    f'<div class="review-card" role="article" aria-label="{item["company_name"]}">'
                    f'<div class="review-card-header">'
                    f'<div>'
                    f'<span class="review-card-company">{item["company_name"]}</span>'
                    f'<span class="review-card-arrow">&rarr;</span>'
                    f'{aladdin_display}'
                    f'{risk_badge}'
                    f'</div>'
                    f'<span class="status-badge {status_class}" role="status" aria-label="Status: {get_status_label(item["status"])}">{get_status_label(item["status"])}</span>'
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
                        st.session_state.last_action = f"Approved {item['company_name']}"
                        st.session_state.last_action_time = datetime.now()
                        st.rerun()

                with act_cols[2]:
                    if st.button("Reject", key=f"rej_{global_idx}", use_container_width=True):
                        st.session_state.data[global_idx]["status"] = "rejected"
                        st.session_state.data[global_idx]["reviewed_by"] = "analyst"
                        st.session_state.data[global_idx]["review_timestamp"] = datetime.now().isoformat()
                        st.session_state.last_action = f"Rejected {item['company_name']}"
                        st.session_state.last_action_time = datetime.now()
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
                                st.session_state.last_action = f"Override approved {item['company_name']}"
                                st.session_state.last_action_time = datetime.now()
                                st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)

        with review_tabs[1]:
            fuzzy_items = [d for d in needs_review if d["match_type"] == "fuzzy"]
            if fuzzy_items:
                st.markdown(f"**{len(fuzzy_items)}** fuzzy matches found. These have partial name matches and need verification.")
                for item in fuzzy_items:
                    risk_badge = get_risk_badge_html(item["match_confidence"])
                    gauge_html = get_confidence_gauge_html(item["match_confidence"])
                    st.markdown(
                        f'<div class="review-card" role="article" aria-label="{item["company_name"]}">'
                        f'<div class="review-card-header">'
                        f'<span class="review-card-company">{item["company_name"]}</span>'
                        f'<div>'
                        f'<span class="review-card-id">{item["aladdin_id"]}</span>'
                        f'{risk_badge}'
                        f'</div>'
                        f'</div>'
                        f'{gauge_html}'
                        f'</div>',
                        unsafe_allow_html=True
                    )
            else:
                st.markdown(
                    '<div class="empty-state">'
                    '<div class="empty-state-icon">[--]</div>'
                    '<div class="empty-state-message">No fuzzy matches to review</div>'
                    '<div class="empty-state-hint">All extractions were either exact matches or require manual lookup</div>'
                    '</div>',
                    unsafe_allow_html=True
                )

        with review_tabs[2]:
            manual_items = [d for d in needs_review if d["match_type"] == "manual_required"]
            if manual_items:
                st.markdown(
                    f'<div style="background:#FEF3C7;border:1px solid #FDE68A;border-left:4px solid #D97706;'
                    f'border-radius:8px;padding:0.75rem 1rem;color:#78350F;font-size:0.85rem;font-weight:500;" role="alert">'
                    f'<strong>{len(manual_items)}</strong> items could not be automatically matched and require manual Aladdin ID lookup.'
                    f'</div>',
                    unsafe_allow_html=True
                )
                for m_idx, item in enumerate(manual_items):
                    st.markdown(
                        f'<div class="review-card" style="border-left: 3px solid #DC2626;" role="article" aria-label="{item["company_name"]}">'
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

                    with st.expander(f"Similar Entities for {item['company_name']}", expanded=False):
                        # Other entities from the same email source
                        same_source = [
                            d for d in st.session_state.data
                            if d["email_file"] == item["email_file"] and d["company_name"] != item["company_name"]
                        ]
                        if same_source:
                            st.markdown("**Other entities from same email source:**")
                            for s in same_source:
                                id_display = s["aladdin_id"] if s["aladdin_id"] else "No ID"
                                st.markdown(
                                    f'<div style="padding:0.3rem 0.6rem;margin:0.15rem 0;background:#F9FAFB;'
                                    f'border-radius:4px;font-size:0.82rem;border:1px solid #E5E7EB;">'
                                    f'{s["company_name"]} &mdash; {id_display} ({s["match_confidence"]:.0%})'
                                    f'</div>',
                                    unsafe_allow_html=True
                                )
                        else:
                            st.markdown("*No other entities from this email source.*")

                        st.markdown("")

                        # Suggested Aladdin IDs based on partial name matching
                        st.markdown("**Suggested Aladdin IDs (partial name match):**")
                        company_lower = item["company_name"].lower()
                        suggestions = [
                            (name, aid) for name, aid in ALADDIN_LOOKUP.items()
                            if any(tok in name.lower() for tok in company_lower.split() if len(tok) > 2)
                        ]
                        if suggestions:
                            for name, aid in suggestions:
                                st.markdown(
                                    f'<div style="padding:0.3rem 0.6rem;margin:0.15rem 0;background:#FEF3C7;'
                                    f'border-radius:4px;font-size:0.82rem;border:1px solid #FDE68A;">'
                                    f'{name} &rarr; {aid}'
                                    f'</div>',
                                    unsafe_allow_html=True
                                )
                        else:
                            st.markdown("*No partial matches found in database.*")

                        st.markdown("")

                        # Manual lookup input
                        st.markdown("**Search Aladdin Database:**")
                        search_query = st.text_input(
                            "Enter company name or ID fragment",
                            key=f"manual_search_{m_idx}",
                            placeholder="e.g., Goldman, ALADDIN_GS",
                            label_visibility="collapsed"
                        )
                        if search_query:
                            query_lower = search_query.lower()
                            results = [
                                (name, aid) for name, aid in ALADDIN_LOOKUP.items()
                                if query_lower in name.lower() or query_lower in aid.lower()
                            ]
                            if results:
                                for name, aid in results:
                                    st.markdown(
                                        f'<div style="padding:0.3rem 0.6rem;margin:0.15rem 0;background:#D1FAE5;'
                                        f'border-radius:4px;font-size:0.82rem;border:1px solid #6EE7B7;">'
                                        f'{name} &rarr; {aid}'
                                        f'</div>',
                                        unsafe_allow_html=True
                                    )
                            else:
                                st.markdown("*No results found.*")
            else:
                st.markdown(
                    '<div class="empty-state">'
                    '<div class="empty-state-icon">[OK]</div>'
                    '<div class="empty-state-message">No items require manual lookup</div>'
                    '<div class="empty-state-hint">All companies were matched automatically. Return to Review & Match to process items.</div>'
                    '</div>',
                    unsafe_allow_html=True
                )

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
            f'<div class="stat-card accent-blue" role="figure" aria-label="{len(data)} Total Items">'
            f'<div class="stat-value">{len(data)}</div>'
            '<div class="stat-label">Total Items</div>'
            '</div>', unsafe_allow_html=True
        )
    with scol2:
        st.markdown(
            f'<div class="stat-card accent-green" role="figure" aria-label="{len(approved_items)} Approved">'
            f'<div class="stat-value">{len(approved_items)}</div>'
            '<div class="stat-label">Approved</div>'
            '</div>', unsafe_allow_html=True
        )
    with scol3:
        st.markdown(
            f'<div class="stat-card accent-red" role="figure" aria-label="{len(rejected_items)} Rejected">'
            f'<div class="stat-value">{len(rejected_items)}</div>'
            '<div class="stat-label">Rejected</div>'
            '</div>', unsafe_allow_html=True
        )
    with scol4:
        st.markdown(
            f'<div class="stat-card accent-amber" role="figure" aria-label="{len(pending_items)} Pending">'
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
        st.markdown(
            '<div class="empty-state">'
            '<div class="empty-state-icon">[Pending]</div>'
            '<div class="empty-state-message">No approved items yet</div>'
            '<div class="empty-state-hint">Return to Review & Match to process items</div>'
            '</div>',
            unsafe_allow_html=True
        )

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
            f'border-radius:8px;padding:0.75rem 1rem;color:#78350F;font-size:0.85rem;font-weight:500;" role="alert">'
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
        st.markdown('<div class="signoff-panel" role="form" aria-label="Final sign-off form">', unsafe_allow_html=True)
        st.markdown(
            '<div style="color:#6B7280;font-size:0.82rem;margin-bottom:0.5rem;">'
            'This export must be reviewed and signed off by an authorized user before upload to Aladdin.</div>',
            unsafe_allow_html=True
        )
        st.markdown(
            '<div style="background:#EFF6FF;border:1px solid #BFDBFE;border-radius:6px;padding:0.6rem 0.85rem;'
            'margin-bottom:0.75rem;font-size:0.78rem;color:#1E40AF;line-height:1.5;">'
            '<strong>[INFO] Compliance Sign-Off:</strong> By signing below, you attest under the firm\'s '
            'compliance policy (Section 4.2 - Counterparty Exclusion Controls) that all exclusion entries '
            'have been reviewed for accuracy, duplicate entries have been reconciled, and the resulting '
            'Aladdin rule set will not conflict with existing portfolio constraints. This sign-off '
            'constitutes an auditable record under MiFID II / Dodd-Frank operational risk requirements.'
            '</div>',
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
                st.session_state.last_action = f"Signed off by {signoff_name}"
                st.session_state.last_action_time = datetime.now()

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

            # Gather actual timestamps from reviewed items
            _review_timestamps = [
                d["review_timestamp"] for d in data
                if d.get("review_timestamp")
            ]
            _first_review = min(_review_timestamps) if _review_timestamps else "N/A"
            _last_review = max(_review_timestamps) if _review_timestamps else "N/A"
            _approved_count = len([d for d in data if d["status"] == "approved"])
            _rejected_count = len([d for d in data if d["status"] == "rejected"])

            _audit_entries = [
                {
                    "icon": "[LOAD]",
                    "action": "Data Loaded & Extracted",
                    "timestamp": _first_review if _first_review != "N/A" else datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "user": "System (Auto)",
                    "summary": f"{len(data)} entities extracted from {len(set(d['email_file'] for d in data))} email(s)",
                    "details": "Email files were parsed using NLP extraction. "
                               "Entities were matched against the Aladdin ID database using exact and fuzzy matching.",
                },
                {
                    "icon": "[REVIEW]",
                    "action": "Items Reviewed",
                    "timestamp": _last_review if _last_review != "N/A" else datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "user": "analyst",
                    "summary": f"{_approved_count} approved, {_rejected_count} rejected",
                    "details": f"Review window: {_first_review} to {_last_review}. "
                               f"Each item was individually assessed for Aladdin ID accuracy. "
                               f"Manual overrides applied where system confidence was below threshold.",
                },
                {
                    "icon": "[APPROVE]",
                    "action": "Items Approved for Export",
                    "timestamp": _last_review if _last_review != "N/A" else datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "user": "analyst",
                    "summary": f"{len(approved_items)} items cleared for Aladdin upload",
                    "details": "Approved items passed all validation checks: "
                               "Aladdin ID exists, no duplicate exclusion entries, "
                               "confidence threshold met or manual override provided.",
                },
                {
                    "icon": "[SIGN]",
                    "action": "Data Signed Off",
                    "timestamp": st.session_state.signoff_timestamp,
                    "user": st.session_state.signoff_user,
                    "summary": "Compliance sign-off completed",
                    "details": "Authorized user attested that all entries have been reviewed, "
                               "overrides validated, and no conflicts with existing Aladdin rules. "
                               "Signed CSV generated for upload.",
                },
            ]

            for _entry in _audit_entries:
                st.markdown(
                    f'<div class="review-card" style="border-left:3px solid #1E40AF;margin-bottom:0.5rem;">'
                    f'<div class="review-card-header">'
                    f'<span style="font-family:monospace;font-weight:700;color:#1E40AF;font-size:0.8rem;margin-right:0.4rem;">'
                    f'{_entry["icon"]}</span>'
                    f'<span class="review-card-company">{_entry["action"]}</span>'
                    f'<span style="font-size:0.75rem;color:#6B7280;">{_entry["timestamp"]}</span>'
                    f'</div>'
                    f'<div class="review-card-meta">'
                    f'<span>User: {_entry["user"]}</span>'
                    f'<span>{_entry["summary"]}</span>'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
                with st.expander(f'Details: {_entry["action"]}', expanded=False):
                    st.markdown(
                        f'<div style="font-size:0.8rem;color:#374151;line-height:1.6;padding:0.25rem 0;">'
                        f'{_entry["details"]}'
                        f'</div>',
                        unsafe_allow_html=True
                    )

# ==================== FOOTER ====================

_env_label = os.environ.get("APP_ENV", "DEV").upper()
_last_load_str = st.session_state.last_data_load.strftime("%Y-%m-%d %H:%M:%S")

st.markdown(
    f'<div class="app-footer" role="contentinfo">'
    f'Aladdin Exclusion Parser &middot; Enterprise Counterparty Management &middot; v2.1.0'
    f'<div class="footer-meta">'
    f'<span>Env: {_env_label}</span>'
    f'<span>Session: {st.session_state.session_id}</span>'
    f'<span>Last Load: {_last_load_str}</span>'
    f'</div>'
    f'</div>',
    unsafe_allow_html=True
)
