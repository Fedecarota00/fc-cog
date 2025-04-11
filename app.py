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
    return any(set(keyword.lower().split()).issubset(set(position.split())) for keyword in JOB_KEYWORDS)

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

# === PAGE LAYOUT ===
st.markdown("### Step 1 – Upload or Enter Company Domains")
option = st.radio(TEXT['input_method'], (TEXT['manual_entry'], TEXT['upload_file']))

domains = []
if option == TEXT['manual_entry']:
    st.markdown(f"**{TEXT['enter_domain']}**")
    domain_input = st.text_input("e.g. ing.com")
    if domain_input:
        domains.append(domain_input.strip())
elif option == TEXT['upload_file']:
    uploaded_file = st.file_uploader(TEXT['upload_instruction'], type="xlsx")
    if uploaded_file:
        df_uploaded = pd.read_excel(uploaded_file)
        domains = df_uploaded.iloc[:, 1].dropna().unique().tolist()
        st.success(TEXT['uploaded_success'].format(n=len(domains)))

# === AI MESSAGE GENERATION ===
if "ai_template" not in st.session_state:
    st.session_state.ai_template = ""

st.markdown("### Step 2 – Preview a Sample Message")
col1, col2 = st.columns(2)
with col1:
    test_first_name = st.text_input(TEXT["first_name"], value="Alex")
    test_position = st.text_input(TEXT["job_title"], value="Chief Financial Officer")
    test_company = st.text_input(TEXT["company"], value="ING Bank")
with col2:
    tone = st.radio(TEXT["message_tone"], ["Friendly", "Formal", "Data-driven", "Short & Punchy"])
    custom_instruction = st.text_input(TEXT["custom_instruction"], placeholder="e.g. Mention we are macro research providers")

if st.button(TEXT["generate_message"]):
    ai_msg = generate_ai_message(test_first_name, test_position, test_company, tone, custom_instruction)
    st.session_state.ai_template = ai_msg
    st.success(TEXT["ai_result"])
    st.info(ai_msg)

# === EDIT MESSAGE TEMPLATE ===
st.markdown("### Step 3 – Customize the Message Template")
st.markdown("You can edit the message below. Use placeholders like {first_name}, {position}, {company} to personalize.")

first_name = test_first_name
position = test_position
company = test_company

preview_message = st.session_state.ai_template or generate_ai_message(first_name, position, company, tone, custom_instruction)
default_template = preview_message.replace(first_name, "{first_name}").replace(position, "{position}").replace(company, "{company}")
final_template = st.text_area("Custom message template", value=default_template)

# === RUN QUALIFICATION ===
st.markdown("### Step 4 – Run Lead Qualification")
if st.button(TEXT["run_button"]) and domains:
    all_qualified = []
    with st.spinner(TEXT['processing']):
        for idx, domain in enumerate(domains):
            st.write(f"[{idx+1}/{len(domains)}] Processing domain: {domain}")
            leads, error = get_leads_from_hunter(domain)
            if error:
                st.error(error)
                continue
            qualified = filter_leads(leads)
            st.success(TEXT["qualified_count"].format(domain=domain, count=len(qualified)))
            all_qualified.extend(qualified)
            time.sleep(1.5)

    if all_qualified:
        df_qualified = pd.DataFrame(all_qualified)
        records = []
        for lead in all_qualified:
            first_name, last_name = split_full_name(lead["Full Name"])
            company = lead["Company"]
            position = lead["Position"]
            message = final_template.format(
                first_name=first_name,
                position=position,
                company=company
            )
            records.append({
                "First Name": first_name,
                "Last Name": last_name,
                "LinkedIn URL": lead["LinkedIn"],
                "Company": company,
                "Job Title": position,
                "Personalized Message": message
            })

        df_salesflow = pd.DataFrame(records)

        buffer_xlsx = BytesIO()
        df_qualified.to_excel(buffer_xlsx, index=False)
        buffer_csv = BytesIO()
        df_salesflow.to_csv(buffer_csv, index=False, encoding="utf-8-sig")
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zipf:
            zipf.writestr("qualified_leads.xlsx", buffer_xlsx.getvalue())
            zipf.writestr("salesflow_leads.csv", buffer_csv.getvalue())

        st.markdown("### Step 5 – Export Your Results")
        st.dataframe(df_qualified, use_container_width=True)
        st.download_button(TEXT["download_xlsx"], data=buffer_xlsx.getvalue(), file_name="qualified_leads.xlsx")
        st.download_button(TEXT["download_csv"], data=buffer_csv.getvalue(), file_name="salesflow_leads.csv")
        st.download_button(TEXT["download_zip"], data=zip_buffer.getvalue(), file_name="lead_outputs.zip")
    else:
        st.warning(TEXT["no_results"])











