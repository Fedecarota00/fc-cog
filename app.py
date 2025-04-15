# === IMPORTS ===
import streamlit as st
import pandas as pd
import requests
import time
from io import BytesIO
import zipfile
import os
import openai
from translations import TEXTS
from jobpositions import JOB_KEYWORDS

# === STREAMLIT CONFIG ===
st.set_page_config(page_title=" FC Lead Qualifier", layout="wide")

# === LANGUAGE SELECTION ===
st.sidebar.image("ecr_logo_resized.png", width=120)
st.sidebar.image("ecr_logo_resized1.png", width=120)
language = st.sidebar.selectbox("Choose your language:", list(TEXTS.keys()))
TEXT = TEXTS[language]

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
        "Authorization": f"Bearer {st.secrets['COGNISM_API_KEY']}"
    }
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        return [], f"Error fetching from Cognism: {response.status_code} – {response.text}"

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
            qualified.append(lead)
    return qualified

def split_full_name(full_name):
    parts = full_name.strip().split()
    return (parts[0], " ".join(parts[1:])) if parts else ("", "")

def generate_ai_message(first_name, position, company, tone=None, custom_instruction=None):
    base_prompt = (
        f"You're writing a LinkedIn connection request to {first_name}, "
        f"who is a {position} at {company}."
    )

    tone_instructions = {
        "Friendly": "Write in a warm, conversational tone.",
        "Formal": "Use a professional and respectful tone.",
        "Data-driven": "Use language that emphasizes insights and value.",
        "Short & Punchy": "Be concise, bold, and impactful."
    }

    tone_text = tone_instructions.get(tone, "") if tone else ""
    custom_text = custom_instruction if custom_instruction else ""

    prompt = f"{base_prompt} {tone_text} {custom_text} Keep it under 250 characters."

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a LinkedIn outreach assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.9,
            max_tokens=100
        )
        return response['choices'][0]['message']['content'].strip()
    except:
        return f"Hi {first_name}, I’d love to connect regarding insights relevant to {position} at {company}."

def send_to_zapier(lead):
    zapier_url = st.secrets["ZAPIER_WEBHOOK_URL"]
    try:
        response = requests.post(zapier_url, json=lead)
        return response.status_code == 200
    except Exception as e:
        st.error(f"Error sending to Zapier: {e}")
        return False












