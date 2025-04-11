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

# === STREAMLIT CONFIG ===
st.set_page_config(page_title=" FC Lead Qualificator", layout="wide")

# === LANGUAGE SELECTION ===
st.sidebar.image("ecr_logo_resized.png", width=120)
language = st.sidebar.selectbox("Choose your language:", list(TEXTS.keys()))
TEXT = TEXTS[language]

# === TITLE & INTRO SECTION ===
st.markdown(f"""
    <div style="background-color: #0D18A1; padding: 1rem 1.5rem; border-radius: 0.5rem; margin-bottom: 1rem;">
        <h2 style="margin: 0; color: white;">FC Lead Qualificator</h2>
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

# === KEYWORDS ===
JOB_KEYWORDS = [
    "Chief Executive Officer", "CEO", "Chief Financial Officer", "CFO", "Chief Operating Officer", "COO",
    "Chief Investment Officer", "CIO", "Chief Risk Officer", "CRO", "Chief Compliance Officer", "CCO",
    "Chief Accounting Officer", "CAO", "Head of Treasury", "Treasury Director", "Treasury Manager",
    "Treasury Analyst", "Cash Manager", "Liquidity Manager", "Asset Liability Management Manager", "ALM Manager",
    "Head of Finance", "Finance Director", "Financial Controller", "FC", "Accounting Manager",
    "Financial Reporting Manager", "Financial Analyst", "FA", "Management Accountant", "Regulatory Reporting Analyst",
    "Financial Planning and Analysis Manager", "FP&A Manager", "Portfolio Manager", "PM", "Investment Director",
    "Fund Manager", "Buy-Side Analyst", "Sell-Side Analyst", "Investment Analyst", "Wealth Manager",
    "Private Banker", "Risk Manager", "Credit Risk Analyst", "Operational Risk Officer", "Market Risk Manager",
    "Compliance Officer", "Regulatory Affairs Manager", "Head of Strategy", "Strategy Director",
    "Corporate Development Manager", "Mergers and Acquisitions Analyst", "M&A Analyst", "M&A Manager",
    "Business Development Director", "BDD", "Relationship Manager", "RM", "Corporate Banker", "SME Banker",
    "Credit Analyst", "Loan Officer", "Branch Manager", "Head of Trading", "Trader", "FX Trader", "Equity Trader",
    "Fixed Income Trader", "Sales and Trading Analyst", "Market Analyst", "Internal Auditor", "Financial Crime Officer",
    "IT Risk Manager", "Data Analyst", "Financial Technology Manager", "Chief Actuary", "Actuary", "Underwriter",
    "Risk Pricing Analyst", "Claims Manager", "Claims Adjuster", "Operations Manager", "Policy Administration Officer",
    "Insurance Product Manager", "Broker Relations Manager", "Insurance Sales Manager", "Business Development Executive",
    "Reinsurance Analyst", "Reinsurance Manager", "Regulatory Compliance Officer", "Head of Finance Transformation",
    "Head of Digital Banking", "Fintech Manager", "ESG Finance Lead", "Financial Risk and Control Manager",
    "Data Governance Manager", "Procurement and Vendor Risk Manager", "Vice President of Finance", "VP Finance",
    "Director of Finance", "Director of Treasury", "Director of Risk", "Director of Compliance", "Head of Function",
    "VP of Function", "Director of Function", "Investment Manager", "Investment Assistant", "Head of Portfolio Management",
    "Head of Fund Management", "Fund Assistant", "Head of Multi-Asset Equity", "Head of Fixed Income", "Chief Strategist",
    "Strategist (Market/Financial)", "Chief Economist", "Head of Research", "Economist", "Chief Analyst",
    "Analyst (Fund or Other)", "Head of Asset Management", "Asset Manager", "Head of Wealth Management",
    "Wealth Adviser", "Chief Dealer", "Head of Money Markets", "Head of Capital Markets", "Chief Stockbroker",
    "Head of Private Banking", "Head of Client Advisory", "Head of Client Assets", "Client Portfolio Manager",
    "Head of HNWI", "Head of FX", "Head of Cash Management", "Head of Pensions", "Chief Investment Strategist",
    "Executive Director Investment Risk", "Chief Of Investment Execution", "Head Of M&A",
    "Liquidity Management & Financing", "Treasury", "Portfolio", "Asset", "Multi-asset", "Multi Asset"
]

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
    if st.checkbox("Show raw Hunter.io results (debug mode)"):
        st.markdown("#### Raw Contacts")
        st.json(leads)
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












