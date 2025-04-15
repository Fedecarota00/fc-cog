# === IMPORTS ===
import streamlit as st
import pandas as pd
import requests
import time
from io import BytesIO
import zipfile
import os
import openai
# from translations import TEXTS
from jobpositions import JOB_KEYWORDS

# === STREAMLIT CONFIG ===
st.set_page_config(page_title=" FC Lead Qualifier", layout="wide")

# === LANGUAGE SELECTION ===
st.sidebar.image("ecr_logo_resized.png", width=120)
st.sidebar.image("ecr_logo_resized1.png", width=120)
# language = st.sidebar.selectbox("Choose your language:", list(TEXTS.keys()))
language = "English"

# === SESSION STATE SETUP ===
if "df_salesflow" not in st.session_state:
    st.session_state.df_salesflow = pd.DataFrame()

# === TITLE & INTRO SECTION ===
st.markdown(f"""
    <div style="background-color: #0D18A1; padding: 1rem 1.5rem; border-radius: 0.5rem; margin-bottom: 1rem;">
        <h2 style="margin: 0; color: white;">FC Lead Qualifier</h2>
    </div>
""", unsafe_allow_html=True)

with st.expander("About this tool"):
    st.markdown("""
        This Lead Qualification Tool helps identify financial decision-makers within companies by:

        - Searching professional contacts using Cognism
        - Filtering based on relevant financial job titles
        - Generating personalized LinkedIn messages using AI
        - Allowing you to export contacts and messages in Excel and CSV format

        Developed by Federico Carota as part of a thesis project at HU University of Applied Sciences.
    """)

# === API CONFIG ===
COGNISM_API_KEY = st.secrets["COGNISM_API_KEY"]
openai.api_key = st.secrets["OPENAI_API_KEY"]
PUBLIC_DOMAINS = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com"]

# === FUNCTIONS ===
def is_public_email(email):
    return email.split('@')[-1].lower() in PUBLIC_DOMAINS

def job_matches(position):
    if not position:
        return False
    position = position.lower()
    return any(keyword.lower() in position for keyword in JOB_KEYWORDS)

def get_leads_from_cognism(domain):
    url = f"https://api.cognism.com/v1/contacts/search?domain={domain}&limit=10"
    headers = {
        "Authorization": f"Bearer {COGNISM_API_KEY}"
    }
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        try:
            error_text = response.json().get("message", response.text)
        except:
            error_text = response.text
        return [], f"Error fetching domain {domain}: {response.status_code} – {error_text}"

    data = response.json()
    contacts = []
    for item in data.get("contacts", []):
        company_info = item.get("company", {})
        contacts.append({
            "Email": item.get("email"),
            "Full Name": f"{item.get('firstName', '')} {item.get('lastName', '')}",
            "Position": item.get("jobTitle"),
            "LinkedIn": item.get("linkedinUrl"),
            "Company": company_info.get("name"),
            "Company Domain": domain,
            "Mobile": item.get("mobile"),
            "Direct Phone": item.get("phone"),
            "HQ Phone": company_info.get("phone")
        })
    return contacts, None

def filter_leads(leads):
    qualified = []
    for lead in leads:
        email = lead.get("Email")
        position = lead.get("Position")
        linkedin = lead.get("LinkedIn")
        company = lead.get("Company", "N/A")
        if not email or is_public_email(email):
            continue
        if job_matches(position):
            qualified.append({
                "Email": email,
                "Full Name": lead.get("Full Name"),
                "Position": position,
                "LinkedIn": linkedin,
                "Company": company,
                "Company Domain": lead.get("Company Domain"),
                "Mobile": lead.get("Mobile"),
                "Direct Phone": lead.get("Direct Phone"),
                "HQ Phone": lead.get("HQ Phone")
            })
    return qualified

def send_to_zapier(lead):
    zapier_url = st.secrets["ZAPIER_WEBHOOK_URL"]
    try:
        response = requests.post(zapier_url, json=lead)
        return response.status_code == 200
    except Exception as e:
        st.error(f"Error sending to Zapier: {e}")
        return False

# === SEND TO ZAPIER WITH DEBUG ===
if not st.session_state.df_salesflow.empty:
    if st.button("Send Qualified Leads to SugarCRM via Zapier"):
        st.write("✅ Button pressed! About to send leads to Zapier.")
        st.write("📤 Sending to Zapier... Leads found:", len(st.session_state.df_salesflow))

        zap_success = 0
        for _, row in st.session_state.df_salesflow.iterrows():
            zapier_payload = {
                "first_name": row.get("First Name"),
                "last_name": row.get("Last Name"),
                "email": row.get("Email"),
                "job_title": row.get("Job Title"),
                "company": row.get("Company"),
                "linkedin_url": row.get("LinkedIn URL"),
                "message": row.get("Personalized Message"),
                "domain": row.get("Company Domain"),
                "mobile": row.get("Mobile"),
                "direct_phone": row.get("Direct Phone"),
                "hq_phone": row.get("HQ Phone")
            }

            st.json(zapier_payload)

            if send_to_zapier(zapier_payload):
                zap_success += 1

        st.success(f"✅ {zap_success}/{len(st.session_state.df_salesflow)} leads sent to SugarCRM via Zapier.")
else:
    st.info("Run lead qualification first to see this button.")












