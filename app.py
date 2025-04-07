import streamlit as st
import pandas as pd
import requests
import time
from io import BytesIO
import zipfile
import os
import openai

# === CONFIGURATION ===
HUNTER_API_KEY = "f68566d43791af9b30911bc0fe8a65a89908d4fe"
PUBLIC_DOMAINS = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com"]
openai.api_key = st.secrets["OPENAI_API_KEY"]

JOB_KEYWORDS = ["Chief Executive Officer", "CEO", "Chief Financial Officer", "CFO", "Chief Operating Officer", "COO",
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
    domain = email.split('@')[-1]
    return domain.lower() in PUBLIC_DOMAINS

def job_matches(position):
    if not position:
        return False
    position = position.lower()
    for keyword in JOB_KEYWORDS:
        if keyword.lower() in position:
            return True
    return False

def get_leads_from_hunter(domain):
    all_emails = []
    offset = 0
    limit = 100

    while True:
        url = f"https://api.hunter.io/v2/domain-search?domain={domain}&api_key={HUNTER_API_KEY}&limit={limit}&offset={offset}&emails_type=personal"
        response = requests.get(url)
        if response.status_code != 200:
            return [], f"Error fetching domain {domain}: {response.status_code}"

        data = response.json()
        emails = data.get("data", {}).get("emails", [])
        company = data.get("data", {}).get("organization")

        for email in emails:
            email["company"] = company

        all_emails.extend(emails)

        if len(emails) < limit:
            break

        offset += limit
        time.sleep(1.2)

    return all_emails, None

def filter_leads(leads, score_threshold):
    qualified = []
    for lead in leads:
        email = lead.get("value")
        position = lead.get("position")
        score = lead.get("confidence", 0)
        linkedin = lead.get("linkedin") or lead.get("linkedin_url")
        company = lead.get("company", "N/A")
        if not email or is_public_email(email) or score < score_threshold:
            continue
        if job_matches(position):
            qualified.append({
                "Email": email,
                "Full Name": (lead.get("first_name") or "") + " " + (lead.get("last_name") or ""),
                "Position": position,
                "Confidence Score": score,
                "LinkedIn": linkedin,
                "Company": company,
                "Company Domain": lead.get("domain")
            })
    return qualified

def split_full_name(full_name):
    parts = full_name.strip().split()
    if len(parts) == 0:
        return "", ""
    elif len(parts) == 1:
        return parts[0], ""
    else:
        return parts[0], " ".join(parts[1:])

def generate_ai_message(first_name, position, company):
    prompt = (
        f"Write a short, professional LinkedIn connection request to {first_name}, "
        f"who is a {position} at {company}. The goal is to introduce macroeconomic insights "
        f"that could help their financial decision-making. Be friendly and under 250 characters."
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=100
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        return f"Hi {first_name}, I’d love to connect regarding insights relevant to {position} at {company}."

def generate_salesflow_data(qualified_leads, user_template, use_ai):
    records = []
    for lead in qualified_leads:
        first_name, last_name = split_full_name(lead["Full Name"])
        company = lead["Company"]
        position = lead["Position"]

        if use_ai:
            message = generate_ai_message(first_name, position, company)
        else:
            message = user_template.format(
                first_name=first_name,
                last_name=last_name,
                company=company,
                position=position
            )

        records.append({
            "First Name": first_name,
            "Last Name": last_name,
            "LinkedIn URL": lead["LinkedIn"],
            "Company": company,
            "Job Title": position,
            "Personalized Message": message
        })
    return pd.DataFrame(records)

# === STREAMLIT UI ===
st.set_page_config(page_title="Lead Qualifier", layout="centered")

logo_path = "ecr_logo_resized.png"
if os.path.exists(logo_path):
    st.image(logo_path, width=120)

st.markdown("""
<h2 style='text-align: center; color: #ffffff; background-color: #001F54; padding: 15px; border-radius: 10px;'>
    🔍 ECR Lead Qualification App
</h2>
""", unsafe_allow_html=True)

SCORE_THRESHOLD = st.slider("Minimum confidence score", min_value=0, max_value=100, value=50)

# --- Salesflow Message UI ---
st.markdown("### ✍️ Customize your Salesflow message")
default_template = "Hi {first_name}, I came across your profile as {position} at {company} – I'd love to connect!"
user_template = st.text_area("Message Template (you can use {first_name}, {position}, {company})", value=default_template)
use_ai = st.checkbox("✨ Suggest message with AI based on position and company")

option = st.radio("Choose input method:", ("Manual domain entry", "Upload Excel file"))
domains = []

if option == "Manual domain entry":
    domain_input = st.text_input("Enter a domain to search leads for (e.g. ing.com):")
    if domain_input:
        domains.append(domain_input.strip())
else:
    uploaded_file = st.file_uploader("Upload an .xlsx file with domains in column B:", type="xlsx")
    if uploaded_file:
        df_uploaded = pd.read_excel(uploaded_file)
        domains = df_uploaded.iloc[:, 1].dropna().unique().tolist()
        st.success(f"Loaded {len(domains)} domain(s) from file.")

st.markdown("""<br><hr style='border:1px solid #cccccc'>""", unsafe_allow_html=True)

if st.button("🚀 Run Lead Qualification") and domains:
    all_qualified = []
    with st.spinner("Working through the domains and filtering qualified leads..."):
        for idx, domain in enumerate(domains):
            st.write(f"[{idx+1}/{len(domains)}] Processing domain: `{domain}`")
            leads, error = get_leads_from_hunter(domain)
            if error:
                st.error(error)
                continue
            qualified = filter_leads(leads, SCORE_THRESHOLD)
            st.success(f"✅ Qualified leads from {domain}: {len(qualified)}")
            all_qualified.extend(qualified)
            time.sleep(1.5)

    if all_qualified:
        df_qualified = pd.DataFrame(all_qualified)
        df_salesflow = generate_salesflow_data(all_qualified, user_template, use_ai)

        buffer_xlsx = BytesIO()
        df_qualified.to_excel(buffer_xlsx, index=False)

        buffer_csv = BytesIO()
        df_salesflow.to_csv(buffer_csv, index=False, encoding="utf-8-sig", sep=',')

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zipf:
            zipf.writestr("qualified_leads.xlsx", buffer_xlsx.getvalue())
            zipf.writestr("salesflow_leads.csv", buffer_csv.getvalue())

        st.dataframe(df_qualified, use_container_width=True)

        st.download_button("⬇️ Download Qualified Leads (.xlsx)", data=buffer_xlsx.getvalue(), file_name="qualified_leads.xlsx")
        st.download_button("⬇️ Download Salesflow CSV", data=buffer_csv.getvalue(), file_name="salesflow_leads.csv")
        st.download_button("⬇️ Download All as ZIP", data=zip_buffer.getvalue(), file_name="lead_outputs.zip")
    else:
        st.warning("No qualified leads found. Try a different domain or file.")
