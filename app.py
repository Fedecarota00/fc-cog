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

REQUIRED_KEYS = ["step_1", "step_2", "step_3", "step_4", "run_button", "generate_message", "first_name", "job_title", "company", "message_tone", "custom_instruction", "ai_result", "qualified_count", "no_results", "download_xlsx", "download_csv", "download_zip", "download_sugarcrm", "upload_instruction", "uploaded_success", "enter_domain", "input_method", "manual_entry", "upload_file", "processing"]

# Fill in defaults if any key is missing
for key in REQUIRED_KEYS:
    TEXT.setdefault(key, f"[{key}]")

# === TITLE & INTRO SECTION ===
st.markdown(f"""
    <div style="background-color: #0D18A1; padding: 1rem 1.5rem; border-radius: 0.5rem; margin-bottom: 1rem;">
        <h2 style="margin: 0; color: white;">FC Lead Qualifier</h2>
    </div>
""", unsafe_allow_html=True)

with st.expander("About this tool"):
    st.markdown("""
        This Lead Qualification Tool helps identify financial decision-makers within companies by:

        - Searching professional contacts using Hunter.io
        - Filtering based on relevant financial job titles
        - Generating personalized LinkedIn messages using AI
        - Allowing you to export contacts and messages in Excel and CSV format

        Developed by Federico Carota as part of a thesis project at HU University of Applied Sciences.
    """)

# === API CONFIG ===
HUNTER_API_KEY = st.secrets["HUNTER_API_KEY"]
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

def get_leads_from_hunter(domain):
    url = f"https://api.hunter.io/v2/domain-search?domain={domain}&api_key={HUNTER_API_KEY}&limit=10"
    response = requests.get(url)
    if response.status_code != 200:
        try:
            error_text = response.json().get("errors", [{}])[0].get("details", "Unknown error")
        except:
            error_text = response.text
        return [], f"Error fetching domain {domain}: {response.status_code} – {error_text}"
    data = response.json()
    emails = data.get("data", {}).get("emails", [])
    company = data.get("data", {}).get("organization")
    for email in emails:
        email["company"] = company
    return emails, None

def filter_leads(leads):
    qualified = []
    for lead in leads:
        email = lead.get("value")
        position = lead.get("position")
        linkedin = lead.get("linkedin") or lead.get("linkedin_url")
        company = lead.get("company", "N/A")
        if not email or is_public_email(email):
            continue
        if job_matches(position):
            qualified.append({
                "Email": email,
                "Full Name": (lead.get("first_name") or "") + " " + (lead.get("last_name") or ""),
                "Position": position,
                "LinkedIn": linkedin,
                "Company": company,
                "Company Domain": lead.get("domain")
            })
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
        st.json(lead)  # Visualize the payload being sent
        response = requests.post(zapier_url, json=lead)
        return response.status_code == 200
    except Exception as e:
        st.error(f"Error sending to Zapier: {e}")
        return False














