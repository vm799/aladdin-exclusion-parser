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
            {"name": "GS Bank", "confidence": 0.60},  # Needs review
            {"name": "Morgan Stanley", "confidence": 0.90},
        ]
    },
    "client_email_20260302_002.eml": {
        "from": "alice.brown@hedgefund.io",
        "subject": "Compliance: Counterparty Restrictions",
        "extracted_companies": [
            {"name": "JPMorgan", "confidence": 0.85},  # Might be JPMorgan Chase
            {"name": "Citibank", "confidence": 0.75},  # Might be Citigroup
            {"name": "Unknown Vendor XYZ", "confidence": 0.40},  # Will need manual lookup
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

# ==================== HELPER FUNCTIONS ====================

def find_aladdin_match(company_name: str) -> Tuple[str, float, str]:
    """
    Find Aladdin ID match for a company name.
    Returns: (aladdin_id, confidence, match_type)
    match_type: 'exact', 'fuzzy', 'manual_required'
    """
    # Exact match
    if company_name in ALADDIN_LOOKUP:
        return ALADDIN_LOOKUP[company_name], 1.0, "exact"
    
    # Fuzzy match (simple substring matching)
    matches = []
    for db_name, aladdin_id in ALADDIN_LOOKUP.items():
        if company_name.lower() in db_name.lower() or db_name.lower() in company_name.lower():
            # Calculate simple similarity
            similarity = len(set(company_name.lower()) & set(db_name.lower())) / max(len(company_name), len(db_name))
            matches.append((aladdin_id, similarity, db_name))
    
    if matches:
        matches.sort(key=lambda x: x[1], reverse=True)
        best_match, confidence, _ = matches[0]
        return best_match, confidence * 0.8, "fuzzy"  # Lower confidence for fuzzy
    
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

def get_status_color(status: str) -> str:
    """Return color for status badge."""
    colors = {
        "pending": "🟡",
        "manual_required": "🔴",
        "auto_approved": "🟢",
        "approved": "✅",
        "rejected": "❌",
    }
    return colors.get(status, "⚪")

# ==================== STREAMLIT CONFIG ====================

st.set_page_config(
    page_title="Aladdin Exclusion Parser",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        color: #1f77b4;
    }
    .step-header {
        font-size: 1.3rem;
        font-weight: 600;
        margin-top: 1.5rem;
        margin-bottom: 0.8rem;
        border-bottom: 2px solid #1f77b4;
        padding-bottom: 0.5rem;
    }
    .stat-box {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .warning-box {
        background-color: #fff3cd;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #ffc107;
    }
    .success-box {
        background-color: #d4edda;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #28a745;
    }
</style>
""", unsafe_allow_html=True)

# ==================== SESSION STATE INIT ====================

if "data" not in st.session_state:
    st.session_state.data = load_sample_data()

if "current_tab" not in st.session_state:
    st.session_state.current_tab = "Upload"

if "signed_off" not in st.session_state:
    st.session_state.signed_off = False

if "signoff_user" not in st.session_state:
    st.session_state.signoff_user = None

# ==================== SIDEBAR ====================

with st.sidebar:
    st.markdown("### 📋 Workflow Status")
    
    data = st.session_state.data
    total = len(data)
    approved = len([d for d in data if d["status"] == "approved"])
    rejected = len([d for d in data if d["status"] == "rejected"])
    pending = len([d for d in data if d["status"] in ["pending", "manual_required", "auto_approved"]])
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Items", total)
        st.metric("Pending Review", pending)
    with col2:
        st.metric("Approved", approved)
        st.metric("Rejected", rejected)
    
    st.divider()
    
    st.markdown("### 🗂️ Navigation")
    tabs = ["1. Upload & Extract", "2. Review & Match", "3. Approval", "4. Export & Sign-Off"]
    selected_tab = st.selectbox("Go to step:", tabs, index=tabs.index(st.session_state.current_tab) if st.session_state.current_tab in tabs else 0)
    st.session_state.current_tab = selected_tab
    
    st.divider()
    
    if st.session_state.signed_off:
        st.markdown('<div class="success-box">✅ <b>Signed Off</b><br>Ready for Aladdin upload</div>', unsafe_allow_html=True)
        st.markdown(f"**Signed by:** {st.session_state.signoff_user}")
        st.markdown(f"**Time:** {st.session_state.signoff_timestamp}")
    else:
        if approved > 0:
            st.markdown('<div class="warning-box">⚠️ Awaiting final sign-off</div>', unsafe_allow_html=True)

# ==================== MAIN CONTENT ====================

st.markdown('<div class="main-header">📧 Aladdin Exclusion Parser</div>', unsafe_allow_html=True)
st.markdown("Enterprise-grade email parsing with human-in-the-loop review for counterparty exclusions")

st.divider()

# ==================== TAB 1: UPLOAD & EXTRACT ====================

if st.session_state.current_tab == "1. Upload & Extract":
    st.markdown('<div class="step-header">Step 1: Upload & Extract Companies</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("**Upload email files** (.eml or .txt) containing counterparty exclusion lists:")
        uploaded_files = st.file_uploader("Choose files", type=["eml", "txt"], accept_multiple_files=True)
        
        if uploaded_files:
            st.success(f"✅ Uploaded {len(uploaded_files)} file(s). Processing...")
            # In production, would parse actual emails here
            # For demo, we show sample data is ready
    
    with col2:
        if st.button("📊 Load Sample Data", use_container_width=True):
            st.session_state.data = load_sample_data()
            st.rerun()
    
    st.markdown('<div class="step-header">Extraction Preview</div>', unsafe_allow_html=True)
    
    # Show extraction results
    extraction_df = pd.DataFrame([
        {
            "Email": d["email_file"],
            "From": d["from"],
            "Company Name": d["company_name"],
            "Confidence": f"{d['extraction_confidence']:.0%}",
        }
        for d in st.session_state.data
    ])
    
    st.dataframe(extraction_df, use_container_width=True, hide_index=True)
    
    st.info("💡 Companies extracted from emails. Next: Match to Aladdin IDs and review flagged items.")

# ==================== TAB 2: REVIEW & MATCH ====================

elif st.session_state.current_tab == "2. Review & Match":
    st.markdown('<div class="step-header">Step 2: Review & Match to Aladdin IDs</div>', unsafe_allow_html=True)
    
    data = st.session_state.data
    
    # Filter for items needing review
    needs_review = [d for d in data if d["status"] in ["pending", "manual_required", "auto_approved"]]
    
    st.markdown(f"**Items needing review:** {len(needs_review)} of {len(data)}")
    
    if not needs_review:
        st.success("✅ All items reviewed!")
    else:
        # Tabs for different match types
        match_tabs = st.tabs(["All Pending", "Fuzzy Matches", "Manual Required", "Auto-Approved"])
        
        with match_tabs[0]:  # All Pending
            for idx, item in enumerate(needs_review):
                with st.expander(f"{get_status_color(item['status'])} {item['company_name']} → {item['aladdin_id'] or 'NO MATCH'}"):
                    col1, col2 = st.columns([1.5, 1])
                    
                    with col1:
                        st.markdown(f"**Email:** {item['email_file']}")
                        st.markdown(f"**Extracted Company:** {item['company_name']}")
                        st.markdown(f"**Extraction Confidence:** {item['extraction_confidence']:.0%}")
                        st.markdown(f"**Match Type:** {item['match_type']}")
                        st.markdown(f"**Match Confidence:** {item['match_confidence']:.0%}")
                    
                    with col2:
                        st.markdown("**Actions:**")
                        
                        # Manual override if needed
                        if item["aladdin_id"]:
                            st.markdown(f"**Suggested ID:** `{item['aladdin_id']}`")
                        
                        # Dropdown for all available IDs or custom input
                        available_ids = [item["aladdin_id"]] if item["aladdin_id"] else []
                        available_ids += [id for id in ALADDIN_LOOKUP.values() if id not in available_ids]
                        
                        selected_id = st.selectbox(
                            "Select Aladdin ID:",
                            available_ids,
                            key=f"select_{idx}",
                            label_visibility="collapsed"
                        )
                        
                        col_a, col_b, col_c = st.columns(3)
                        
                        with col_a:
                            if st.button("✅ Approve", key=f"approve_{idx}", use_container_width=True):
                                st.session_state.data[data.index(item)]["status"] = "approved"
                                st.session_state.data[data.index(item)]["aladdin_id"] = selected_id
                                st.session_state.data[data.index(item)]["reviewed_by"] = "current_user"
                                st.session_state.data[data.index(item)]["review_timestamp"] = datetime.now().isoformat()
                                st.rerun()
                        
                        with col_b:
                            if st.button("❌ Reject", key=f"reject_{idx}", use_container_width=True):
                                st.session_state.data[data.index(item)]["status"] = "rejected"
                                st.session_state.data[data.index(item)]["reviewed_by"] = "current_user"
                                st.session_state.data[data.index(item)]["review_timestamp"] = datetime.now().isoformat()
                                st.rerun()
                        
                        with col_c:
                            if st.button("🔧 Override", key=f"override_{idx}", use_container_width=True):
                                custom_id = st.text_input("Enter custom Aladdin ID:", key=f"custom_{idx}")
                                if custom_id:
                                    st.session_state.data[data.index(item)]["aladdin_id"] = custom_id
                                    st.session_state.data[data.index(item)]["status"] = "approved"
                                    st.session_state.data[data.index(item)]["override_aladdin_id"] = True
                                    st.rerun()
        
        with match_tabs[1]:  # Fuzzy
            fuzzy = [d for d in needs_review if d["match_type"] == "fuzzy"]
            if fuzzy:
                st.markdown(f"Fuzzy matches found: {len(fuzzy)}")
                for item in fuzzy:
                    st.write(f"- {item['company_name']} → {item['aladdin_id']}")
            else:
                st.info("No fuzzy matches")
        
        with match_tabs[2]:  # Manual Required
            manual = [d for d in needs_review if d["match_type"] == "manual_required"]
            if manual:
                st.warning(f"⚠️ {len(manual)} items require manual lookup:")
                for item in manual:
                    st.write(f"- {item['company_name']} (No Aladdin ID found)")
            else:
                st.success("No items require manual lookup")
        
        with match_tabs[3]:  # Auto-Approved
            auto = [d for d in needs_review if d["status"] == "auto_approved"]
            if auto:
                st.success(f"✅ {len(auto)} items auto-approved with high confidence:")
                auto_df = pd.DataFrame([
                    {"Company": d["company_name"], "Aladdin ID": d["aladdin_id"], "Confidence": f"{d['match_confidence']:.0%}"}
                    for d in auto
                ])
                st.dataframe(auto_df, use_container_width=True, hide_index=True)
                
                if st.button("✅ Accept All Auto-Approved", use_container_width=True):
                    for item in auto:
                        item["status"] = "approved"
                        item["reviewed_by"] = "auto"
                        item["review_timestamp"] = datetime.now().isoformat()
                    st.rerun()
            else:
                st.info("No auto-approved items")

# ==================== TAB 3: APPROVAL ====================

elif st.session_state.current_tab == "3. Approval":
    st.markdown('<div class="step-header">Step 3: Approval Summary</div>', unsafe_allow_html=True)
    
    data = st.session_state.data
    approved_items = [d for d in data if d["status"] == "approved"]
    rejected_items = [d for d in data if d["status"] == "rejected"]
    pending_items = [d for d in data if d["status"] in ["pending", "manual_required", "auto_approved"]]
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Items", len(data))
    with col2:
        st.metric("Approved", len(approved_items), delta=f"Ready for export")
    with col3:
        st.metric("Rejected", len(rejected_items))
    with col4:
        st.metric("Pending", len(pending_items), delta=f"Still in review" if pending_items else "All done!")
    
    st.divider()
    
    if approved_items:
        st.markdown("### ✅ Approved Items (Ready for Export)")
        approval_df = pd.DataFrame([
            {
                "Company": d["company_name"],
                "Aladdin ID": d["aladdin_id"],
                "Match Type": d["match_type"],
                "Override": "Yes" if d["override_aladdin_id"] else "No",
                "Reviewed By": d["reviewed_by"],
                "Timestamp": d["review_timestamp"][:10] if d["review_timestamp"] else "-"
            }
            for d in approved_items
        ])
        st.dataframe(approval_df, use_container_width=True, hide_index=True)
    else:
        st.info("No approved items yet. Complete the review process first.")
    
    if rejected_items:
        st.markdown("### ❌ Rejected Items")
        reject_df = pd.DataFrame([
            {
                "Company": d["company_name"],
                "Email File": d["email_file"],
                "Rejected By": d["reviewed_by"],
            }
            for d in rejected_items
        ])
        st.dataframe(reject_df, use_container_width=True, hide_index=True)

# ==================== TAB 4: EXPORT & SIGN-OFF ====================

elif st.session_state.current_tab == "4. Export & Sign-Off":
    st.markdown('<div class="step-header">Step 4: Export & Final Sign-Off</div>', unsafe_allow_html=True)
    
    data = st.session_state.data
    approved_items = [d for d in data if d["status"] == "approved"]
    
    if not approved_items:
        st.error("❌ No approved items to export. Please complete the review process first.")
    else:
        # Export preview
        st.markdown("### 📥 Export Preview")
        
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
        
        # Export options
        col1, col2 = st.columns([1, 1])
        
        with col1:
            # CSV download
            csv_buffer = io.StringIO()
            export_data.to_csv(csv_buffer, index=False)
            csv_bytes = csv_buffer.getvalue().encode()
            
            st.download_button(
                label="📥 Download CSV (Unsigned)",
                data=csv_bytes,
                file_name=f"aladdin_exclusions_unsigned_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col2:
            st.markdown("")  # Spacer
        
        st.divider()
        
        # Sign-off
        st.markdown("### 🔏 Final Sign-Off")
        st.markdown("Before uploading to Aladdin, this export must be reviewed and signed off by an authorized user.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            signoff_name = st.text_input("Your Name:", placeholder="John Smith")
            signoff_role = st.selectbox("Your Role:", ["Compliance Officer", "Trading Manager", "Risk Officer", "Operations"])
        
        with col2:
            signoff_team = st.text_input("Team:", placeholder="Compliance / Trading")
            signoff_reason = st.text_area("Sign-Off Reason:", placeholder="E.g., Reviewed for accuracy, all matches verified")
        
        st.markdown("**Final Checklist:**")
        check1 = st.checkbox("✅ I have reviewed all approved items and confirmed accuracy")
        check2 = st.checkbox("✅ All manual overrides have been validated")
        check3 = st.checkbox("✅ No conflicts with existing Aladdin rules")
        
        if signoff_name and signoff_role and signoff_team and check1 and check2 and check3:
            if st.button("🔏 Sign & Approve for Upload", use_container_width=True, type="primary"):
                st.session_state.signed_off = True
                st.session_state.signoff_user = f"{signoff_name} ({signoff_role})"
                st.session_state.signoff_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Generate signed CSV
                signed_export = export_data.copy()
                signed_export["signed_by"] = signoff_name
                signed_export["signed_at"] = st.session_state.signoff_timestamp
                signed_export["sign_off_reason"] = signoff_reason
                signed_export["team"] = signoff_team
                
                st.session_state.signed_export = signed_export
                
                st.rerun()
        else:
            st.warning("⚠️ Complete the checklist above to proceed with sign-off")
        
        if st.session_state.signed_off:
            st.divider()
            st.markdown("### ✅ Signed & Approved")
            st.success(f"Signed by {st.session_state.signoff_user} at {st.session_state.signoff_timestamp}")
            
            # Download signed export
            csv_buffer_signed = io.StringIO()
            st.session_state.signed_export.to_csv(csv_buffer_signed, index=False)
            csv_signed = csv_buffer_signed.getvalue().encode()
            
            st.download_button(
                label="📥 Download Signed CSV (Ready for Aladdin Upload)",
                data=csv_signed,
                file_name=f"aladdin_exclusions_SIGNED_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True,
                type="primary"
            )
            
            # Audit log
            st.markdown("### 📋 Audit Log")
            audit_log = {
                "Action": ["Data Loaded", "Items Reviewed", "Items Approved", "Data Signed Off"],
                "Timestamp": [
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    st.session_state.signoff_timestamp
                ],
                "User": ["System", "current_user", "current_user", st.session_state.signoff_user],
                "Details": [
                    f"{len(data)} items processed",
                    f"{len([d for d in data if d['status'] == 'approved'])} items approved, {len([d for d in data if d['status'] == 'rejected'])} rejected",
                    f"{len(approved_items)} final items ready",
                    "Sign-off approved"
                ]
            }
            audit_df = pd.DataFrame(audit_log)
            st.dataframe(audit_df, use_container_width=True, hide_index=True)

st.divider()
st.markdown("---")
st.markdown("**Enterprise Aladdin Exclusion Parser** | Built with Streamlit | v1.0")
