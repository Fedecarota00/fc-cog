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

JOB_KEYWORDS = [
    # ... trimmed for brevity
]

# === FUNCTIONS ===
def is_public_email(email):
    domain = email.split('@')[-1]
    return domain.lower() in PUBLIC_DOMAINS

def job_matches(position):
    if not position:
        return False
    position = position.lower()
    position_words = set(position.split())
    for keyword in JOB_KEYWORDS:
        keyword_words = set(keyword.lower().split())
        if keyword_words.issubset(position_words):
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
        f"You're creating a short, professional LinkedIn connection message for a person named {first_name}, "
        f"who is a {position} at {company}. The sender wants to offer macroeconomic research insights.\n"
        f"Keep it friendly, specific to the role, and under 250 characters. Avoid generic phrases."
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[{"role": "system", "content": "You are a LinkedIn outreach assistant."},
                      {"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=100
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        return f"Hi {first_name}, I’d love to connect regarding insights relevant to {position} at {company}."

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

st.markdown("Insert here the SalesFlow message you would like to send to each lead in the campaign:")
use_ai = st.checkbox("✨ Use AI to generate personalized messages", value=True)
default_template = "Hi {first_name}, I came across your profile as {position} at {company} – I'd love to connect!"
user_template = st.text_area("Message Template (you can use {first_name}, {position}, {company})", value=default_template)

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

        records = []
        first_example = None
        for lead in all_qualified:
            first_name, last_name = split_full_name(lead["Full Name"])
            company = lead["Company"]
            position = lead["Position"]

            message = generate_ai_message(first_name, position, company) if use_ai else user_template.format(
                first_name=first_name,
                last_name=last_name,
                company=company,
                position=position
            )

            if first_example is None:
                first_example = f"**{first_name}** ({position} at {company}):\n\n> {message}"

            records.append({
                "First Name": first_name,
                "Last Name": last_name,
                "LinkedIn URL": lead["LinkedIn"],
                "Company": company,
                "Job Title": position,
                "Personalized Message": message
            })

        df_salesflow = pd.DataFrame(records)

        if first_example:
            st.markdown("### 📄 Example AI-Generated Message")
            st.info(first_example)

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
















